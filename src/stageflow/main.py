import logging
import sys
from pathlib import Path
from typing import Optional

import typer

from stageflow import config, git_ops

# Initialize Typer application
app = typer.Typer(help="StageFlow: Selective Git synchronization tool.")

# Configure the global logging format and level
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


@app.command("init")
def init(blank: bool = typer.Option(False, "--blank", help="Generate a blank template.")) -> None:
    """
    Initialize a new StageFlow configuration in the current directory.
    """
    cwd = Path.cwd().resolve()
    try:
        if blank:
            config.create_local_config(
                cwd, project_name="", prod_path="", test_command="", stable_branch="", is_blank=True
            )
            typer.secho("Successfully initialized blank configuration.", fg=typer.colors.GREEN)
        else:
            project_name = typer.prompt("Project Name")
            prod_path = typer.prompt("Production Repository Path")
            test_command = typer.prompt("Test Command")
            stable_branch = typer.prompt("Stable Branch", default="")
            config.create_local_config(
                cwd,
                project_name=project_name,
                prod_path=prod_path,
                test_command=test_command,
                stable_branch=stable_branch,
                is_blank=False,
            )
            typer.secho("Successfully initialized configuration.", fg=typer.colors.GREEN)
    except (ValueError, OSError, RuntimeError, FileNotFoundError) as e:
        typer.secho(f"Error initializing configuration: {e}", fg=typer.colors.RED)
        sys.exit(1)


@app.command("release")
def release(
    env: str = typer.Argument(..., help="Target environment branch (e.g., alpha, beta)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate the release process without modifying files or Git history."
    ),
    commit: bool = typer.Option(
        False, "--commit", help="Commit changes in production repository with auto-generated message."
    ),
    commit_message: Optional[str] = typer.Option(
        None, "--commit-message", help="Commit changes in production repository with a custom message."
    ),
    push: bool = typer.Option(
        False,
        "--push",
        help="Push committed changes to the remote. Can only be used with --commit or --commit-message.",
    ),
) -> None:
    """
    Perform a selective Git synchronization to the target environment.
    """
    if commit and commit_message is not None:
        typer.secho("Error: --commit and --commit-message cannot be used together.", fg=typer.colors.RED)
        sys.exit(1)

    if commit_message is not None and not commit_message.strip():
        typer.secho("Error: --commit-message cannot be empty.", fg=typer.colors.RED)
        sys.exit(1)

    if push and not commit and commit_message is None:
        typer.secho("Error: --push can only be used if --commit or --commit-message is specified.", fg=typer.colors.RED)
        sys.exit(1)

    repo_path = Path.cwd().resolve()
    try:
        # Load local configuration
        cfg = config.load_local_config(repo_path)

        # Execution
        if dry_run:
            typer.secho("⚠️ DRY RUN MODE ACTIVATED", fg=typer.colors.YELLOW, bold=True)

        prod_repo_path = Path(cfg["repository"]["production"]["path"]).expanduser().resolve()
        git_ops.perform_release(
            repo_path,
            prod_repo_path,
            env,
            cfg,
            dry_run=dry_run,
            commit=commit,
            commit_message=commit_message,
            push=push,
        )

        # Completion
        typer.secho("Successfully performed release.", fg=typer.colors.GREEN)

    except (ValueError, OSError, RuntimeError, FileNotFoundError) as e:
        typer.secho(f"Error during release: {e}", fg=typer.colors.RED)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
