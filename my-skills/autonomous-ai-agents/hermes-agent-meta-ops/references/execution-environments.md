# Hermes Python Execution Environments

When operating the agent, you must deliberately choose between `terminal` and `execute_code` based on the Python dependencies and environment required for the task.

## `execute_code` (Hermes Internal Venv)

- **Environment**: Runs inside the agent's own virtual environment (`~/.hermes/hermes-agent/venv/bin/python`).
- **Access**: Has access to all Hermes internal dependencies (e.g., `requests`, `urllib`). Does **NOT** inherit the user's global `pyenv` or `uv` environments.
- **When to use**: Data cleaning, complex logical branching, parsing JSON/XML to reduce context load, and multi-step orchestration using `from hermes_tools import ...`.

## `terminal` (System/User Shell)

- **Environment**: Spawns a standard bash shell. Uses the host's default Python (`/usr/bin/python3`) OR the user's active shell Python (via `~/.bashrc` PATH injection).
- **Access**: Can access macOS native frameworks (like `Quartz` via `/usr/bin/python3`) and the user's project-specific dependencies.
- **Pitfall**: Because `terminal` defaults to bash, it may not load `~/.zshrc` exports. If a specific `uv` or `pyenv` environment is required, you must explicitly invoke it (e.g., `uv run python script.py`).
- **When to use**: System administration, executing user scripts, running Git commands, and lightweight OS-level probes (`pmset`, `ioreg`).
