"""
Main module for the StageFlow CLI.
Serves as the main entry point and terminal user interface (UI).
"""

import logging
import sys
from pathlib import Path

import typer

from stageflow import config, git_ops, pre_flight

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
            config.create_local_config(cwd, project_name="", prod_path="", test_command="", is_blank=True)
            typer.secho("Successfully initialized blank configuration.", fg=typer.colors.GREEN)
        else:
            project_name = typer.prompt("Project Name")
            prod_path = typer.prompt("Production Repository Path")
            test_command = typer.prompt("Test Command")
            config.create_local_config(
                cwd,
                project_name=project_name,
                prod_path=prod_path,
                test_command=test_command,
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
) -> None:
    """
    Perform a selective Git synchronization to the target environment.
    """
    repo_path = Path.cwd().resolve()
    try:
        # Load local configuration
        cfg = config.load_local_config(repo_path)

        # Run pre-flight checks
        pre_flight.run_all_checks(repo_path, cfg)

        # Execution
        if dry_run:
            typer.secho("⚠️ DRY RUN MODE ACTIVATED", fg=typer.colors.YELLOW, bold=True)

        prod_repo_path = Path(cfg["repository"]["production"]["path"]).expanduser().resolve()
        git_ops.perform_release(repo_path, prod_repo_path, env, cfg, dry_run=dry_run)

        # Completion
        typer.secho("Successfully performed release.", fg=typer.colors.GREEN)

    except (ValueError, OSError, RuntimeError, FileNotFoundError) as e:
        typer.secho(f"Error during release: {e}", fg=typer.colors.RED)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
