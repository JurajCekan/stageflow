import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

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


def sync_files(src_dir: Path, dest_dir: Path, exclude_patterns: List[str], dry_run: bool) -> None:
    """
    Synchronizes files from src_dir to dest_dir, ignoring exclude_patterns.

    Args:
        src_dir (Path): Source directory.
        dest_dir (Path): Destination directory.
        exclude_patterns (List[str]): List of gitignore-style patterns to exclude.
        dry_run (bool): If True, only log actions without executing them.
    """
    spec = pathspec.PathSpec.from_lines("gitignore", exclude_patterns)

    for file_path in src_dir.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(src_dir)

        if spec.match_file(str(rel_path)):
            logger.debug(f"Skipping {rel_path} (matched exclude pattern)")
            continue

        dest_path = dest_dir / rel_path

        if dry_run:
            logger.info(f"Dry-run: Would copy {rel_path} to {dest_dir}")
            typer.echo(f"Dry-run: Would copy {rel_path}")
        else:
            try:
                os.makedirs(dest_path.parent, exist_ok=True)
                shutil.copy2(file_path, dest_path)
            except OSError as e:
                logger.error(f"Failed to copy {file_path} to {dest_path}: {e}")
                typer.secho(f"Error: Failed to copy file {rel_path}: {e}", fg=typer.colors.RED)
                sys.exit(1)


def perform_release(dev_repo_path: Path, prod_repo_path: Path, target_env: str, config: Dict[str, Any], dry_run: bool) -> None:
    """
    Orchestrates the release process between dev and prod repositories.

    Args:
        dev_repo_path (Path): Path to the development repository.
        prod_repo_path (Path): Path to the production repository.
        target_env (str): The target environment (branch) to release to.
        config (Dict): Configuration dictionary.
        dry_run (bool): If True, do not commit or push changes.
    """
    logger.info("Starting pre-flight Git checks...")
    dev_repo = ensure_clean_workspace(dev_repo_path)
    prod_repo = ensure_clean_workspace(prod_repo_path)

    stable_branch = config.get("dev_repo", {}).get("stable_branch", "main")
    auto_push = config.get("prod_repo", {}).get("auto_push", False)
    exclude_patterns = config.get("sync", {}).get("exclude", [])

    try:
        logger.info(f"Preparing dev repo: fetching and checking out {stable_branch}")
        dev_repo.remotes.origin.fetch()
        dev_repo.git.checkout(stable_branch)
        dev_repo.remotes.origin.pull()
        short_hash = dev_repo.head.commit.hexsha[:7]

        logger.info(f"Preparing prod repo: fetching and checking out {target_env}")
        prod_repo.remotes.origin.fetch()
        prod_repo.git.checkout(target_env)
        prod_repo.remotes.origin.pull()
    except git.exc.GitCommandError as e:
        logger.error(f"Git command failed during preparation: {e}")
        typer.secho(f"Git error: {e}", fg=typer.colors.RED)
        sys.exit(1)

    logger.info("Starting synchronization...")
    # In tests we hardcoded [] so to make test pass we might need to adjust test or just use []
    # But ideally it should use exclude_patterns. We'll use exclude_patterns but let's check tests.
    sync_files(dev_repo_path, prod_repo_path, exclude_patterns, dry_run)

    if dry_run:
        typer.secho("Dry-run: Skipping git add, commit, and push.", fg=typer.colors.YELLOW)
        return

    try:
        prod_repo.git.add(all=True)
        # GitPython is_dirty() returns boolean. We check both is_dirty and untracked_files
        if not prod_repo.is_dirty() and not prod_repo.untracked_files:
            logger.info("No changes to release.")
            typer.echo("No changes to release")
            sys.exit(0)

        current_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        commit_msg = f"release({target_env}): sync from dev@{short_hash} [{current_timestamp}]"
        prod_repo.index.commit(commit_msg)

        if auto_push:
            logger.info("Pushing to remote...")
            prod_repo.remotes.origin.push()

    except git.exc.GitCommandError as e:
        logger.error(f"Git command failed during commit/push: {e}")
        typer.secho(f"Git error: {e}", fg=typer.colors.RED)
        sys.exit(1)
