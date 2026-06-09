"""Module for handling StageFlow configuration."""

import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict

import tomlkit
import typer


def load_local_config(repo_path: Path) -> Dict[str, Any]:
    """
    Load the local stageflow.toml configuration.

    Args:
        repo_path: Absolute path to the -dev repository root.

    Returns:
        The parsed configuration dictionary.

    Raises:
        SystemExit: If the file is missing, mandatory keys are absent, or a decode error occurs.
    """
    config_file = repo_path / "stageflow.toml"

    try:
        with config_file.open("rb") as f:
            config = tomllib.load(f)
    except FileNotFoundError:
        logging.error("stageflow.toml not found at %s", config_file)
        typer.secho("Error: stageflow.toml not found.", fg=typer.colors.RED)
        sys.exit(1)
    except tomllib.TOMLDecodeError as e:
        logging.error("Failed to parse stageflow.toml: %s", e)
        typer.secho(f"Error: Invalid TOML format in stageflow.toml: {e}", fg=typer.colors.RED)
        sys.exit(1)

    # Validation: mandatory keys (project.name, repository.production.path)
    if not config.get("project", {}).get("name"):
        logging.error("Missing mandatory key: project.name")
        typer.secho("Error: Missing mandatory key 'project.name' in stageflow.toml.", fg=typer.colors.RED)
        sys.exit(1)

    if not config.get("repository", {}).get("production", {}).get("path"):
        logging.error("Missing mandatory key: repository.production.path")
        typer.secho("Error: Missing mandatory key 'repository.production.path' in stageflow.toml.", fg=typer.colors.RED)
        sys.exit(1)

    logging.info("Successfully loaded local configuration from %s", config_file)
    return config


def get_global_registry_path() -> Path:
    """
    Get the path to the global project registry.

    Returns:
        Path object pointing to the global config.toml.
    """
    registry_path = Path.home() / ".config" / "stageflow" / "config.toml"
    os.makedirs(registry_path.parent, exist_ok=True)
    return registry_path


def load_global_registry() -> Dict[str, Any]:
    """
    Load the global project registry.

    Returns:
        The parsed registry dictionary, or empty structure if missing.
    """
    registry_path = get_global_registry_path()
    if not registry_path.exists():
        return {"projects": {}}

    try:
        with registry_path.open("rb") as f:
            return tomllib.load(f)
    except Exception as e:
        logging.error("Failed to parse global registry: %s", e)
        return {"projects": {}}


def register_project(dev_repo_path: Path, project_name: str) -> None:
    """
    Register a project in the global registry.

    Args:
        dev_repo_path: Absolute path to the -dev repository.
        project_name: Name of the project.
    """
    registry_path = get_global_registry_path()

    if registry_path.exists():
        try:
            content = registry_path.read_text(encoding="utf-8")
            doc = tomlkit.parse(content)
        except Exception:
            doc = tomlkit.document()
    else:
        doc = tomlkit.document()

    if "projects" not in doc:
        doc.add("projects", tomlkit.table())

    projects_table = doc["projects"]
    if isinstance(projects_table, tomlkit.items.Table):
        projects_table[project_name] = str(dev_repo_path)

    registry_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    logging.info("Registered project '%s' at %s", project_name, dev_repo_path)


def create_local_config(
    repo_path: Path,
    project_name: str,
    prod_path: str,
    test_command: str,
    stable_branch: str = "",
    is_blank: bool = False,
) -> None:
    """
    Create a new local stageflow.toml configuration and register the project.

    Args:
        repo_path: Absolute path to the repository root.
        project_name: Name of the project.
        prod_path: Absolute path to the production repository.
        test_command: Command to run pre-flight tests.
        stable_branch: Branch in the dev repository to sync from.
        is_blank: If True, creates a template configuration with empty/fallback values.
    """
    if is_blank:
        project_name = project_name or repo_path.name
        prod_path = prod_path or ""
        test_command = test_command or ""
        stable_branch = stable_branch or ""

    doc = tomlkit.document()

    # [project] table
    project_table = tomlkit.table()
    project_table.add("name", project_name)
    doc.add("project", project_table)

    # [repository.production] table
    repo_table = tomlkit.table()
    prod_table = tomlkit.table()
    prod_table.add("path", prod_path)
    repo_table.add("production", prod_table)
    doc.add("repository", repo_table)

    # [pre_flight.tests] table
    pre_flight_table = tomlkit.table()
    tests_table = tomlkit.table()
    tests_table.add("command", test_command)
    tests_table.add("abort_on_fail", True)
    pre_flight_table.add("tests", tests_table)
    doc.add("pre_flight", pre_flight_table)

    # [sync] table
    sync_table = tomlkit.table()
    sync_table.add("exclude", [".git/", ".github/", "tests/", "stageflow.toml"])
    doc.add("sync", sync_table)

    # [dev_repo] table
    dev_repo_table = tomlkit.table()
    dev_repo_table.add("stable_branch", stable_branch)
    doc.add("dev_repo", dev_repo_table)

    config_file = repo_path / "stageflow.toml"
    try:
        config_file.write_text(tomlkit.dumps(doc), encoding="utf-8")
        logging.info("Created local configuration at %s", config_file)
    except OSError as e:
        logging.error("Failed to write stageflow.toml: %s", e)
        typer.secho(f"Error: Could not write to {config_file}: {e}", fg=typer.colors.RED)
        sys.exit(1)

    register_project(repo_path, project_name)
