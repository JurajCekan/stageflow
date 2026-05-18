# StageFlow

🚀 A smart CLI tool for selective, fail-fast code synchronization between development and production Git repositories with built-in pre-flight testing.

## 1. Introduction

StageFlow is a robust, "fail-fast" Command Line Interface (CLI) tool meticulously designed to enforce rigorous pre-flight validation before executing Git-based release or staging workflows. It acts as an uncompromising gatekeeper between your development branch and your production repository, guaranteeing that code is fully tested and validated before synchronization. Because deploying directly to production without running tests is a thrill ride nobody actually wants to be on.

## 2. Installation

StageFlow leverages modern Python tooling. We recommend using `uv` for lightning-fast environment setup and dependency management.

### Install `uv`
If you haven't installed `uv` yet, you can do so via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Global Installation (For Users)
The recommended way to install StageFlow globally on your system is using `uv tool`:

```bash
# Install directly from the repository root
uv tool install .
```
This ensures the `stageflow` CLI command is instantly available from anywhere in your terminal.

### Local Development Setup (For Contributors)
If you are developing or testing StageFlow locally, initialize your environment and install the dependencies:

```bash
# Initialize a new project with uv
uv init

# Add core dependencies
uv add typer gitpython pathspec tomlkit

# Add development dependencies
uv add --dev pytest black ruff mypy
```
*(Yes, it brings enough dependencies to make you feel safe, but not enough to slow down your CI.)*

## 3. Configuration (`stageflow.toml`)

The behavior of StageFlow is entirely driven by the `stageflow.toml` configuration file located at the root of your development repository. This file defines project metadata, repository paths, and the rules of engagement for your sync processes.

### Expected TOML Structure

```toml
[project]
name = "your_project_name"

[dev_repo]
stable_branch = "master" # Defaults to "main" if not specified

[repository.production]
path = "../your_project_production"

[pre_flight.tests]
command = "uv run pytest"
abort_on_fail = true

[sync]
exclude = [
    ".git/", 
    ".github/", 
    "tests/", 
    "stageflow.toml"
]
```

### Configuration Keys Defined

*   **`project.name`**: The identifier for your project.
*   **`dev_repo.stable_branch`**: The branch in your development repository to sync from (defaults to `main`). Set this to `master` if your repository uses it instead of the default.
*   **`repository.production.path`**: The relative or absolute path to the target production Git repository.
*   **`pre_flight.tests.command`**: The exact shell command executed to run your test suite during the pre-flight phase.
*   **`pre_flight.tests.abort_on_fail`**: The cornerstone of the "fail-fast" rule. When `true`, StageFlow immediately halts the release process if the test command fails.
*   **`sync.exclude`**: A default list of paths to exclude during the file synchronization phase. This strictly follows standard `.gitignore` syntax (powered by the `pathspec` library). This means you can use powerful wildcards (e.g., `*.log`, `**/*.tmp`) or complex negation patterns exactly as you would in Git.

## 4. Usage (CLI Commands)

StageFlow provides intuitive commands for managing your release pipelines.

### Generating Configuration

StageFlow provides two ways to scaffold your `stageflow.toml` configuration file in the current directory:

**Interactive Initialization (Default):**
Walks you through a series of prompts to set up your project name, production path, and test command.

```bash
stageflow init
```

**Blank Template Initialization:**
Generates a clean, empty template silently without prompting for any input. Ideal for fast setups or when you want to write the configuration manually.

```bash
stageflow init --blank
```

### Executing a Release

The primary command to initiate a synchronization and deployment sequence is:

```bash
stageflow release <env> [OPTIONS]
```

*   **`<env>` (Required):** The target environment branch you are releasing to (e.g., `alpha`, `beta`, `main`).
*   **`--dry-run` (Optional):** Simulates the entire release process—including file synchronization and Git operations—without actually modifying any files or committing history. Highly recommended for establishing trust before making irreversible changes.

## 5. Pre-Flight Policy

The StageFlow pre-flight phase is a strict, non-negotiable step. Every execution *must* run the configured test suite. StageFlow monitors the command's exit status and will immediately and strictly abort the entire process if it encounters a failure (i.e., when the test command returns `returncode != 0`). 

By failing fast, StageFlow guarantees that broken code, failing tests, or unhandled exceptions never make it into your target repository. It's not personal; bad code simply doesn't get past the bouncer. This maintains data integrity and ensures your staging and production environments remain stable.

## 6. User Experience (UX)

To ensure clarity during complex operations, StageFlow employs semantic, color-coded terminal output. This visual hierarchy clearly separates StageFlow's native execution logging from the output of underlying tools (like `pytest` or `git`).

*   🟢 **Green:** Success messages and successful phase transitions.
*   🔴 **Red:** Critical errors and pre-flight failures (the fail-fast trigger).
*   🟡 **Yellow:** Warnings and informative output during `--dry-run` executions.
