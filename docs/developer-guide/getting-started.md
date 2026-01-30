# Getting Started

Quick setup for AIDB development.

## User Installation

To use AI Debugger as an end user:

```bash
pip install ai-debugger-inc
```

See the [User Guide](../user-guide/mcp-usage.md) for MCP configuration and usage.

---

## Developer Setup

For contributors and developers working on the AIDB codebase.

### Prerequisites

- Python 3.10+
- Docker installed and running

### First-Time Setup

```bash
# Install project
bash scripts/install/src/install.sh

# Verify installation
./dev-cli info

# Enable shell completion (optional)
./dev-cli completion install --yes

# Enable git pre-commit hooks (optional)
./venv/bin/pre-commit install
```

### VS Code Setup

Open the workspace file for project-specific settings:

```bash
code aidb.code-workspace
```

Alternatively, select 'File' -> 'Open Workspace from File...' and choose `aidb.code-workspace`.

This provides file excludes, search configuration, and venv selection. It is highly recommended for development QoL.

## Daily Development

```bash
# Run tests
./dev-cli test run -s shared -v

# Run specific suite
./dev-cli test run -s mcp

# Serve documentation
./dev-cli docs serve --build-first

# Build adapters
./dev-cli adapters build

# Run pre-commit checks
./dev-cli dev precommit
```

## Pre-commit Hooks

Configuration in `.pre-commit-config.yaml`:

| Hook | Purpose |
|------|---------|
| `ruff` | Linting with auto-fix |
| `ruff-format` | Code formatting |
| `mypy` | Type checking |
| `bandit` | Security checks |
| `shellcheck` | Shell script linting |
| `hadolint` | Dockerfile linting |
| `actionlint` | GitHub Actions validation |

Run manually:
```bash
pre-commit run --all-files
```

## Project Structure

```
src/
├── aidb/              # Core debugging API
│   ├── adapters/      # Language adapters (Python, JavaScript, Java)
│   ├── service/       # Stateless debugging operations (DebugService)
│   ├── dap/           # DAP protocol client
│   └── session/       # Session management
├── aidb_cli/          # Developer CLI
├── aidb_mcp/          # MCP server
├── aidb_common/       # Shared utilities
└── aidb_logging/      # Logging system
```

## Troubleshooting

### venv errors
```bash
bash scripts/install/src/install.sh  # Reinstall
# or
./dev-cli install reinstall
```

### Docker issues
```bash
./dev-cli docker status
./dev-cli docker build -p all
```

### Test failures
```bash
./dev-cli test run -s <suite> -x    # Stop on first failure
./dev-cli -vvv test run -s <suite>  # Maximum debug output
```
