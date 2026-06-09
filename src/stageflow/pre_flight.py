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


def run_formatting_checks(repo_path: Path) -> None:
    """
    Run formatting and linting checks on the dev repository.
    Aborts immediately (sys.exit(1)) if any checks fail.

    Args:
        repo_path: Absolute path to the -dev repository.

    Raises:
        SystemExit: If formatting or linting checks fail.
    """
    is_python = (
        (repo_path / "pyproject.toml").exists()
        or (repo_path / "requirements.txt").exists()
        or (repo_path / "setup.py").exists()
    )
    is_laravel = (repo_path / "composer.json").exists() and (repo_path / "vendor/bin/pint").exists()

    if not is_python and not is_laravel:
        logging.info("No Python or Laravel project detected. Skipping formatting checks.")
        return

    typer.secho("\n✨ Running formatting and quality checks...", fg=typer.colors.BLUE, bold=True)

    if is_python:
        has_uv_lock = (repo_path / "uv.lock").exists()

        # Check ruff
        ruff_cmd = "uv run ruff check ." if has_uv_lock else "ruff check ."
        logging.info("Running Python formatting check: %s", ruff_cmd)
        typer.secho(f"Running: {ruff_cmd}", fg=typer.colors.CYAN)
        result = subprocess.run(ruff_cmd, shell=True, cwd=repo_path)
        if result.returncode != 0:
            typer.secho("❌ Ruff validation failed. Aborting.", fg=typer.colors.RED, bold=True)
            sys.exit(1)

        # Check mypy
        mypy_cmd = "uv run mypy ." if has_uv_lock else "mypy ."
        logging.info("Running Python type check: %s", mypy_cmd)
        typer.secho(f"Running: {mypy_cmd}", fg=typer.colors.CYAN)
        result = subprocess.run(mypy_cmd, shell=True, cwd=repo_path)
        if result.returncode != 0:
            typer.secho("❌ Mypy static type checking failed. Aborting.", fg=typer.colors.RED, bold=True)
            sys.exit(1)

    if is_laravel:
        pint_cmd = "./vendor/bin/pint --test"
        logging.info("Running Laravel Pint check: %s", pint_cmd)
        typer.secho(f"Running: {pint_cmd}", fg=typer.colors.CYAN)
        result = subprocess.run(pint_cmd, shell=True, cwd=repo_path)
        if result.returncode != 0:
            typer.secho("❌ Laravel Pint formatting check failed. Aborting.", fg=typer.colors.RED, bold=True)
            sys.exit(1)

    typer.secho("✅ Formatting checks passed successfully.", fg=typer.colors.GREEN, bold=True)


def run_all_checks(repo_path: Path, config: Dict[str, Any]) -> None:
    """
    Main entry point to run all pre-flight checks.

    Args:
        repo_path: Absolute path to the -dev repository.
        config: Full configuration dictionary.
    """
    run_formatting_checks(repo_path)
    test_config = config.get("pre_flight", {}).get("tests", {})
    run_tests(repo_path, test_config)
