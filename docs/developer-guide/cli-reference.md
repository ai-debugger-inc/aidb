# CLI Reference

The AIDB developer CLI (`./dev-cli`) provides commands for testing, Docker management, adapter builds, and documentation.

## Quick Start

```bash
# Initial setup
./dev-cli install setup --completion

# Run tests
./dev-cli test run -s shared -v

# Serve docs
./dev-cli docs serve --build-first

# Build adapters
./dev-cli adapters build
```

## Command Groups

### install

```bash
./dev-cli install setup [--completion]     # Install dependencies
./dev-cli install reinstall [--completion] # Clean reinstall
```

### test

```bash
./dev-cli test run -s <suite> [options]    # Run tests
./dev-cli test list [--markers] [--patterns] # List available tests
./dev-cli test cleanup                     # Clean test artifacts
```

**Options:**
- `-s, --suite` — Test suite (shared, mcp, cli, frameworks, etc.)
- `-l, --language` — Language filter (python, javascript, java)
- `-t, --target` — Specific test path (repeatable)
- `-p, --pattern` — pytest `-k` pattern
- `--local` — Run locally instead of Docker
- `-x, --failfast` — Stop on first failure
- `--lf, --last-failed` — Rerun failed tests only
- `-c, --coverage` — Enable coverage reporting
- `-v` — Verbose output

**Examples:**
```bash
./dev-cli test run -s shared -v                    # Shared tests, verbose
./dev-cli test run -s mcp --local -x               # MCP tests, local, stop on fail
./dev-cli test run -s cli -p "test_docs*"          # Pattern matching
./dev-cli test run -t src/tests/aidb/test_api.py  # Specific file
```

### adapters

```bash
./dev-cli adapters build [-l LANG] [--install]     # Build adapters
./dev-cli adapters download [-l LANG] [--install]  # Download pre-built
./dev-cli adapters list                            # List adapters
./dev-cli adapters status                          # Show installed status
./dev-cli adapters clean                           # Clean cache
```

### docker

```bash
./dev-cli docker build [-p PROFILE]                # Build images
./dev-cli docker cleanup [--all] [--dry-run]       # Clean resources
./dev-cli docker status                            # Show Docker status
```

### docs

```bash
./dev-cli docs build                               # Build documentation
./dev-cli docs serve [--port N] [--build-first]    # Serve locally
./dev-cli docs stop                                # Stop server
./dev-cli docs status                              # Show status
./dev-cli docs open                                # Open in browser
```

### dev

```bash
./dev-cli dev precommit [--staged-only]            # Run pre-commit
./dev-cli dev clean                                # Clean artifacts
./dev-cli dev gen-test-programs [-l LANG]          # Generate test programs
```

### config

```bash
./dev-cli config show [-f yaml|json]               # Show config
./dev-cli config set <key> <value>                 # Set value
./dev-cli config paths                             # Show config paths
```

### mcp

```bash
./dev-cli mcp register                             # Register with Claude
./dev-cli mcp unregister                           # Unregister
./dev-cli mcp status                               # Show status
./dev-cli mcp restart                              # Restart server
```

### completion

```bash
./dev-cli completion install [--yes]               # Install shell completion
./dev-cli completion show                          # Show completion script
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `AIDB_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `AIDB_DOCS_PORT` | Docs server port (default: 8000) |
| `AIDB_ADAPTER_TRACE` | Enable adapter tracing |

## Troubleshooting

### Pre-commit failures

```bash
./dev-cli -v dev precommit          # Verbose output
cat .local/pre-commit.log           # View log
```

### Docker issues

```bash
./dev-cli docker status             # Check Docker
./dev-cli docker build -p all       # Rebuild images
```

### Test failures

```bash
./dev-cli test run -s <suite> -x    # Stop on first failure
./dev-cli test run -s <suite> --lf  # Rerun failed only
./dev-cli -vvv test run -s <suite>  # Maximum debug output
```

### Shell completion not working

```bash
./dev-cli completion install --yes
source ~/.zshrc                     # Reload shell config
```

## Verbosity Levels

| Flag | Effect |
|------|--------|
| (none) | Normal output |
| `-v` | Verbose, streaming output |
| `-vvv` | Maximum debug, all component logs |

Log files:
- CLI: `~/.aidb/log/cli.log`
- Tests: `~/.aidb/log/test-container-output.log`
