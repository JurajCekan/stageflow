# StageFlow

🚀 A smart CLI tool for selective, fail-fast code synchronization between development and production Git repositories with built-in pre-flight testing and code quality checks.

## 1. Introduction

StageFlow is a robust, "fail-fast" Command Line Interface (CLI) tool meticulously designed to enforce rigorous pre-flight validation before executing Git-based release or staging workflows. It acts as an uncompromising gatekeeper between your development branch and your production repository, guaranteeing that code is fully formatted, typed, tested, and validated before synchronization. Because deploying directly to production without running tests and lint check is a thrill ride nobody actually wants to be on.

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
uv add --dev pytest black ruff mypy pytest-cov
```

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
Walks you through a series of prompts to set up your project name, production path, test command, and stable branch (which can be left empty).

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
*   **`--commit` (Optional):** A boolean flag that commits all synchronization changes in the production repository with an automatically generated message: `release(<env>): sync from dev@<short_hash> [<timestamp>]`.
*   **`--commit-message <message>` (Optional):** Commits all changes in the production repository with the specified custom message.
*   **`--push` (Optional):** A boolean flag that pushes the committed changes to the production repository's remote origin.

### Validation Rules for Git Operations
- **Mutual Exclusivity:** `--commit` and `--commit-message` cannot be used together. If both are specified, the program will abort.
- **Message Validation:** `--commit-message` cannot be empty or contain only whitespace. If it does, the program will abort.
- **Push Validation:** `--push` requires either `--commit` or `--commit-message` to be specified. Running `--push` without selecting a commit option will abort.

## 5. Pre-Flight Policy

The StageFlow pre-flight phase is a strict, non-negotiable step. Every execution *must* validate the environment and code quality. Before synchronizing files, StageFlow automatically:

1.  **Ensures Clean Workspace:** Aborts immediately if the development repository contains uncommitted or untracked changes.
2.  **Switches to Stable Branch:** Switches the development repository to your configured `dev_repo.stable_branch` (defaults to `main`), fetches, and pulls the latest updates.
3.  **Runs Formatting & Lint Checks:**
    - **Python Projects:** If `pyproject.toml`, `requirements.txt`, or `setup.py` are detected, it executes `ruff check .` and `mypy .` (wrapped in `uv run` if a `uv.lock` is present).
    - **Laravel Projects:** If `composer.json` and `vendor/bin/pint` are detected, it executes `./vendor/bin/pint --test` to verify code style formatting.
    - If formatting or linting fails, it aborts immediately.
4.  **Runs Test Suite:** Executes the test suite command configured under `pre_flight.tests.command` (e.g. `pytest` or `phpunit`). If tests fail, it aborts immediately.

By failing fast, StageFlow guarantees that broken code, unformatted files, failing tests, or unhandled exceptions never make it into your target repository. It's not personal; bad code simply doesn't get past the bouncer.

## 6. Advanced Selective Synchronization

StageFlow performs a complete, bi-directional path comparison between the development and production repositories:
- **Exclusion Matching:** Respects `sync.exclude` rules, pruning directory scans early to optimize sync speed.
- **Additions and Modifications:** Compares files and syncs new or modified files (content checks using `filecmp.cmp`).
- **Deletions Synchronization:** Identifies files and directories that were deleted in the development branch and deletes them in production.
- **Safety Protection:** When deleting directories in production, if they contain local-only excluded files, StageFlow automatically preserves the directory and its excluded files intact.

## 7. User Experience (UX)

To ensure clarity during complex operations, StageFlow employs semantic, color-coded terminal output. This visual hierarchy clearly separates StageFlow's native execution logging from the output of underlying tools (like `pytest`, `ruff`, `mypy`, `pint`, or `git`).

*   🟢 **Green:** Success messages and successful phase transitions.
*   🔴 **Red:** Critical errors and pre-flight failures (the fail-fast trigger).
*   🟡 **Yellow:** Warnings and informative output during `--dry-run` executions.
*   🔵 **Cyan/Blue:** Headers, command boundaries, and info messages.
