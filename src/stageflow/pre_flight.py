"""Module for pre-flight environment checks before Git operations."""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import typer


def run_tests(repo_path: Path, test_config: Dict[str, Any]) -> None:
    """
    Execute defined pre-flight tests.

    Args:
        repo_path: Absolute path to the -dev repository.
        test_config: Data dictionary from the [pre_flight.tests] section.

    Raises:
        SystemExit: If tests fail and abort_on_fail is True.
    """
    command = test_config.get("command")
    if not command:
        logging.info("No pre-flight test command defined. Skipping tests.")
        return

    abort_on_fail = test_config.get("abort_on_fail", True)

    typer.secho(f"\n🚀 Running tests: {command}", fg=typer.colors.BLUE, bold=True)
    logging.info(f"Executing pre-flight tests in {repo_path}: {command}")

    # Crucial: do not use capture_output=True so that output flows to the terminal
    result = subprocess.run(command, shell=True, cwd=repo_path)

    logging.info(f"Test command finished with exit code {result.returncode}")

    if result.returncode != 0:
        typer.secho("\n❌ Tests failed.", fg=typer.colors.RED, bold=True)
        if abort_on_fail:
            logging.error("Tests failed and abort_on_fail is True. Aborting.")
            typer.secho("Aborting process.", fg=typer.colors.RED)
            sys.exit(1)
        else:
            logging.warning("Tests failed but abort_on_fail is False. Continuing.")
    else:
        typer.secho("\n✅ Tests passed successfully.", fg=typer.colors.GREEN, bold=True)


def run_all_checks(repo_path: Path, config: Dict[str, Any]) -> None:
    """
    Main entry point to run all pre-flight checks.

    Args:
        repo_path: Absolute path to the -dev repository.
        config: Full configuration dictionary.
    """
    test_config = config.get("pre_flight", {}).get("tests", {})
    run_tests(repo_path, test_config)
