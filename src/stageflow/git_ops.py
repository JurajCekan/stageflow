import filecmp
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
import pathspec
import typer

logger = logging.getLogger(__name__)


def ensure_clean_workspace(repo_path: Path) -> git.Repo:
    """
    Initializes a git.Repo and checks if the repository is clean.
    Aborts immediately if uncommitted changes exist.

    Args:
        repo_path (Path): Path to the Git repository.

    Returns:
        git.Repo: The initialized Git repository object.
    """
    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        logger.error(f"Invalid Git repository at {repo_path}")
        typer.secho(f"Error: Invalid Git repository at {repo_path}", fg=typer.colors.RED)
        sys.exit(1)

    if repo.is_dirty(untracked_files=True):
        logger.error(f"Repository at {repo_path} is dirty.")
        typer.secho(f"Error: Repository at {repo_path} contains uncommitted changes.", fg=typer.colors.RED)
        sys.exit(1)

    return repo


def get_non_excluded_paths(base_dir: Path, spec: pathspec.PathSpec[Any]) -> Dict[str, Path]:
    """
    Recursively finds all non-excluded files and directories in base_dir.
    Returns a dict mapping relative path string to the absolute Path object.
    For directories, the relative path string ends with a trailing slash '/'.

    Args:
        base_dir: The base directory to scan.
        spec: The pathspec instance to filter with.

    Returns:
        Dict[str, Path]: Mapping of relative path strings to Path objects.
    """
    paths = {}

    def walk(current_dir: Path) -> None:
        for path in current_dir.iterdir():
            rel_path = path.relative_to(base_dir)
            if path.is_dir():
                rel_path_str = str(rel_path) + "/"
                if spec.match_file(rel_path_str):
                    continue
                paths[rel_path_str] = path
                walk(path)
            else:
                rel_path_str = str(rel_path)
                if spec.match_file(rel_path_str):
                    continue
                paths[rel_path_str] = path

    if base_dir.exists():
        walk(base_dir)
    return paths


def sync_files(src_dir: Path, dest_dir: Path, exclude_patterns: List[str], dry_run: bool) -> Dict[str, List[str]]:
    """Synchronizes files from src_dir to dest_dir, ignoring exclude_patterns.

    Computes added, modified, and deleted files and directories, and applies them.

    Args:
        src_dir (Path): Source directory.
        dest_dir (Path): Destination directory.
        exclude_patterns (List[str]): List of gitignore-style patterns to exclude.
        dry_run (bool): If True, only log actions without executing them.

    Returns:
        Dict[str, List[str]]: A dictionary of changes grouped by category.
    """
    spec = pathspec.PathSpec.from_lines("gitignore", exclude_patterns)

    src_paths = get_non_excluded_paths(src_dir, spec)
    dest_paths = get_non_excluded_paths(dest_dir, spec)

    new_dirs: List[str] = []
    changed_files: List[str] = []
    deleted_files: List[str] = []
    deleted_dirs: List[str] = []

    # 1. Identify additions and modifications
    for rel_path, src_path in src_paths.items():
        if rel_path.endswith("/"):
            if rel_path not in dest_paths:
                new_dirs.append(rel_path)
        else:
            if rel_path not in dest_paths:
                changed_files.append(rel_path)
            else:
                # Compare file contents
                dest_path = dest_paths[rel_path]
                if not filecmp.cmp(src_path, dest_path, shallow=False):
                    changed_files.append(rel_path)

    # 2. Identify deletions
    for rel_path in dest_paths.keys():
        if rel_path not in src_paths:
            if rel_path.endswith("/"):
                deleted_dirs.append(rel_path)
            else:
                deleted_files.append(rel_path)

    changes = {
        "new_dirs": new_dirs,
        "changed_files": changed_files,
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
    }

    if dry_run:
        if new_dirs or changed_files or deleted_files or deleted_dirs:
            typer.secho("\n📋 Sync Plan (Dry Run):", fg=typer.colors.CYAN, bold=True)
            if new_dirs:
                typer.secho("Directories to create:", fg=typer.colors.GREEN, bold=True)
                for d in sorted(new_dirs):
                    typer.echo(f"  + {d}")
            if changed_files:
                typer.secho("Files to copy/update:", fg=typer.colors.GREEN, bold=True)
                for f in sorted(changed_files):
                    typer.echo(f"  -> {f}")
            if deleted_files:
                typer.secho("Files to delete:", fg=typer.colors.RED, bold=True)
                for f in sorted(deleted_files):
                    typer.echo(f"  - {f}")
            if deleted_dirs:
                typer.secho("Directories to delete:", fg=typer.colors.RED, bold=True)
                for d in sorted(deleted_dirs, key=len, reverse=True):
                    typer.echo(f"  - {d}")
        else:
            typer.echo("Dry-run: No changes detected to release.")
        return changes

    # Non dry-run execution
    # First delete files
    for f in sorted(deleted_files):
        dest_file = dest_dir / f
        if dest_file.exists():
            try:
                os.remove(dest_file)
                logger.info("Deleted file: %s", dest_file)
            except OSError as e:
                logger.error("Failed to delete file %s: %s", dest_file, e)
                typer.secho(f"Error: Failed to delete file {f}: {e}", fg=typer.colors.RED)
                sys.exit(1)

    # Delete directories (sort by length descending to process children before parents)
    for d in sorted(deleted_dirs, key=len, reverse=True):
        dest_path = dest_dir / d
        if dest_path.exists() and dest_path.is_dir():
            try:
                os.rmdir(dest_path)
                logger.info("Deleted directory: %s", dest_path)
            except OSError as e:
                # Expected when directory is not empty (e.g. contains excluded files)
                logger.debug("Skipping deletion of non-empty directory %s: %s", dest_path, e)

    # Create directories
    for d in sorted(new_dirs):
        dest_path = dest_dir / d
        try:
            os.makedirs(dest_path, exist_ok=True)
            logger.info("Created directory: %s", dest_path)
        except OSError as e:
            logger.error("Failed to create directory %s: %s", dest_path, e)
            typer.secho(f"Error: Failed to create directory {d}: {e}", fg=typer.colors.RED)
            sys.exit(1)

    # Copy / update files
    for f in sorted(changed_files):
        src_file = src_dir / f
        dest_file = dest_dir / f
        try:
            os.makedirs(dest_file.parent, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            logger.info("Copied file: %s -> %s", src_file, dest_file)
        except OSError as e:
            logger.error("Failed to copy file %s to %s: %s", src_file, dest_file, e)
            typer.secho(f"Error: Failed to copy file {f}: {e}", fg=typer.colors.RED)
            sys.exit(1)

    return changes


def write_sync_plan(
    output_path: Path,
    target_env: str,
    stable_branch: str,
    changes: Dict[str, List[str]],
    dry_run: bool,
) -> None:
    """Writes the synchronization plan in Markdown format to the specified path.

    Args:
        output_path (Path): Path where the plan will be written.
        target_env (str): Target environment (branch) name.
        stable_branch (str): Stable development branch name.
        changes (Dict[str, List[str]]): Dictionary mapping change types to lists of paths.
        dry_run (bool): Flag indicating if this is a dry-run release simulation.
    """
    lines = [
        "# 📋 StageFlow Sync Plan",
        "",
        f"- **Target Environment:** `{target_env}`",
        f"- **Stable Branch:** `{stable_branch}`",
        f"- **Generated At:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- **Mode:** `{'Dry-Run' if dry_run else 'Execution'}`",
        "",
        "## 📊 Summary",
        f"- **Directories to create:** {len(changes['new_dirs'])}",
        f"- **Files to copy/update:** {len(changes['changed_files'])}",
        f"- **Files to delete:** {len(changes['deleted_files'])}",
        f"- **Directories to delete:** {len(changes['deleted_dirs'])}",
        "",
    ]

    if changes["new_dirs"]:
        lines.extend(["### 📁 Directories to Create", ""])
        for d in sorted(changes["new_dirs"]):
            lines.append(f"- `+ {d}`")
        lines.append("")

    if changes["changed_files"]:
        lines.extend(["### 📄 Files to Copy/Update", ""])
        for f in sorted(changes["changed_files"]):
            lines.append(f"- `-> {f}`")
        lines.append("")

    if changes["deleted_files"]:
        lines.extend(["### ❌ Files to Delete", ""])
        for f in sorted(changes["deleted_files"]):
            lines.append(f"- `- {f}`")
        lines.append("")

    if changes["deleted_dirs"]:
        lines.extend(["### 🗑️ Directories to Delete", ""])
        for d in sorted(changes["deleted_dirs"], key=len, reverse=True):
            lines.append(f"- `- {d}`")
        lines.append("")

    try:
        resolved_path = output_path.resolve()
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Sync plan successfully exported to %s", resolved_path)
    except OSError as e:
        logger.error("Failed to write sync plan to %s: %s", output_path, e)
        typer.secho(f"Error: Failed to write sync plan to {output_path}: {e}", fg=typer.colors.RED)
        sys.exit(1)


def perform_release(
    dev_repo_path: Path,
    prod_repo_path: Path,
    target_env: str,
    config: Dict[str, Any],
    dry_run: bool,
    commit: bool = False,
    commit_message: Optional[str] = None,
    push: bool = False,
    output_plan: Optional[Path] = None,
) -> None:
    """Orchestrates the release process between dev and prod repositories.

    Args:
        dev_repo_path (Path): Path to the development repository.
        prod_repo_path (Path): Path to the production repository.
        target_env (str): The target environment (branch) to release to.
        config (Dict): Configuration dictionary.
        dry_run (bool): If True, do not commit or push changes.
        commit (bool): If True, commit changes with auto-generated message.
        commit_message (str, optional): Custom commit message to use.
        push (bool): If True, push committed changes to remote.
        output_plan (Path, optional): Path where the markdown sync plan should be written.
    """
    logger.info("Starting pre-flight Git checks...")
    dev_repo = ensure_clean_workspace(dev_repo_path)

    stable_branch = config.get("dev_repo", {}).get("stable_branch", "main")
    exclude_patterns = config.get("sync", {}).get("exclude", [])

    try:
        logger.info("Preparing dev repo: fetching and checking out %s", stable_branch)
        dev_repo.remotes.origin.fetch()
        dev_repo.git.checkout(stable_branch)
        dev_repo.remotes.origin.pull()
        short_hash = dev_repo.head.commit.hexsha[:7]
    except git.exc.GitCommandError as e:
        logger.error("Git command failed during dev repo preparation: %s", e)
        typer.secho(f"Git error: {e}", fg=typer.colors.RED)
        sys.exit(1)

    # Run pre-flight formatting checks and tests on the stable branch
    from stageflow import pre_flight

    pre_flight.run_all_checks(dev_repo_path, config)

    prod_repo = ensure_clean_workspace(prod_repo_path)
    try:
        logger.info("Preparing prod repo: fetching and checking out %s", target_env)
        prod_repo.remotes.origin.fetch()
        prod_repo.git.checkout(target_env)
        prod_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        logger.error("Git command failed during prod repo preparation: %s", e)
        typer.secho(f"Git error: {e}", fg=typer.colors.RED)
        sys.exit(1)

    logger.info("Starting synchronization...")
    changes = sync_files(dev_repo_path, prod_repo_path, exclude_patterns, dry_run)

    if dry_run or output_plan is not None:
        resolved_plan_path = output_plan or Path("sync-plan.md").resolve()
        write_sync_plan(resolved_plan_path, target_env, stable_branch, changes, dry_run)

    if dry_run:
        typer.secho("Dry-run: Skipping git add, commit, and push.", fg=typer.colors.YELLOW)
        return

    should_commit = commit or (commit_message is not None)

    if should_commit:
        try:
            prod_repo.git.add(all=True)
            if not prod_repo.is_dirty(untracked_files=True):
                logger.info("No changes to release.")
                typer.echo("No changes to release")
                return

            if commit_message:
                resolved_msg = commit_message
            else:
                current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                resolved_msg = f"release({target_env}): sync from dev@{short_hash} [{current_timestamp}]"

            logger.info("Committing changes with message: %s", resolved_msg)
            prod_repo.index.commit(resolved_msg)
            typer.secho("Committed changes in production repository.", fg=typer.colors.GREEN)

            if push:
                logger.info("Pushing changes to remote...")
                prod_repo.remotes.origin.push()
                typer.secho("Pushed changes to remote repository.", fg=typer.colors.GREEN)

        except git.exc.GitCommandError as e:
            logger.error("Git command failed during commit/push: %s", e)
            typer.secho(f"Git error: {e}", fg=typer.colors.RED)
            sys.exit(1)
