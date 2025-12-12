---
myst:
  html_meta:
    description lang=en: Complete guide to contributing to AI Debugger - setup, workflow, code style, and more.
---

# Contributing Guide

Thank you for your interest in contributing to AI Debugger! This guide covers
everything you need to know to contribute effectively.

## Quick Start

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/aidb.git
cd aidb

# 2. Set up development environment
bash scripts/install/src/install.sh

# 3. Verify installation
./dev-cli info

# 4. Create a branch
git checkout -b feature/your-feature-name
```

## Development Environment

### Prerequisites

- **Python 3.10+** - Core runtime
- **Docker** - Required for running the full test suite
- **Node.js 18+** - Only if working on JavaScript adapter
- **JDK 17+** - Only if working on Java adapter

### Initial Setup

```bash
# Install dependencies and set up venv
bash scripts/install/src/install.sh

# Optional: Enable shell completion
./dev-cli completion install --yes

# Install pre-commit hooks
./venv/bin/pre-commit install
```

### VS Code Setup

For the best development experience, open the workspace file:

```bash
code aidb.code-workspace
```

This provides file excludes, search configuration, and automatic venv selection.

## Development Workflow

### Running Tests

All tests must be run through the dev-cli:

```bash
# Run shared tests (fast, good for iteration)
./dev-cli test run -s shared

# Run specific test pattern
./dev-cli test run -s shared -k "test_session"

# Run language-specific tests
./dev-cli test run -s python
./dev-cli test run -s javascript
./dev-cli test run -s java

# Run with coverage
./dev-cli test run -s shared --coverage
```

```{important}
Never use `--local` flag unless you know what you're doing. Test suites already
know their natural execution environment.
```

### Code Quality

Before submitting a PR, ensure your code passes all checks:

```bash
# Run all pre-commit hooks
./dev-cli dev precommit

# Or run individually
./venv/bin/ruff check src/
./venv/bin/ruff format src/
./venv/bin/mypy src/
```

### Building Documentation

```bash
# Build and serve docs locally
./dev-cli docs serve --build-first

# Just build
./dev-cli docs build
```

## Code Style

### Python

- **Formatting**: Ruff (configured in `pyproject.toml`)
- **Linting**: Ruff
- **Type Checking**: mypy with strict settings
- **Docstrings**: NumPy format

```python
def process_breakpoint(
    file_path: str,
    line: int,
    condition: str | None = None,
) -> BreakpointResult:
    """
    Process a breakpoint request.

    Parameters
    ----------
    file_path
        Absolute path to the source file.
    line
        Line number for the breakpoint (1-indexed).
    condition
        Optional conditional expression.

    Returns
    -------
    BreakpointResult
        Result containing breakpoint ID and verification status.

    Raises
    ------
    InvalidBreakpointError
        If the breakpoint location is invalid.
    """
```

### General Guidelines

- **Imports**: All imports at the top of the file (unless avoiding circular deps)
- **Comments**: Code should be self-documenting; avoid unnecessary comments
- **Types**: Everything should be properly typed
- **Constants**: Use enums/constants instead of magic strings/numbers
- **DRY**: Check for existing implementations before writing new code

## Pull Request Process

### Before Submitting

1. **Tests pass**: `./dev-cli test run -s shared`
2. **Linting passes**: `./dev-cli dev precommit`
3. **Documentation updated**: If you changed behavior, update relevant docs
4. **Commit messages**: Clear, descriptive messages

### PR Guidelines

- **One concern per PR**: Keep PRs focused on a single change
- **Description**: Explain what and why, not just how
- **Link issues**: Reference related issues with `Fixes #123` or `Related to #456`
- **Screenshots**: Include for UI/output changes

### Review Process

1. Submit your PR against the `main` branch
2. Automated checks will run (CI, linting, tests)
3. A maintainer will review your code
4. Address any feedback
5. Once approved, a maintainer will merge

## Types of Contributions

### Bug Fixes

1. Check if an issue already exists
2. Create an issue if not, describing the bug
3. Fork, fix, and submit a PR referencing the issue

### New Features

1. **Discuss first**: Open an issue or discussion to propose the feature
2. Wait for feedback from maintainers
3. Implement once there's agreement on the approach

### Documentation

- Fix typos, improve clarity, add examples
- Documentation lives in `docs/`
- Uses MyST Markdown (Sphinx-compatible)

### Language Adapters

Adding support for a new language is a significant contribution. Please:

1. Open an issue to discuss the adapter
2. Review existing adapters in `src/aidb/adapters/lang/`
3. See the [Adapter Development Guide](../developer-guide/adapters.md)

## Project Structure

```
src/
├── aidb/              # Core debugging API
│   ├── adapters/      # Language adapters (Python, JavaScript, Java)
│   ├── api/           # High-level Python API
│   ├── dap/           # DAP protocol client
│   └── session/       # Session management
├── aidb_cli/          # Developer CLI
├── aidb_mcp/          # MCP server
├── aidb_common/       # Shared utilities
├── aidb_logging/      # Logging system
└── tests/             # Test suite
```

## Getting Help

- **Discord**: [Join our server](https://discord.com/invite/UGS92b6KgR) for
  real-time help
- **GitHub Discussions**: For longer-form questions
- **Issues**: For bugs and feature requests

## Recognition

Contributors are recognized in our release notes and on our documentation site.
Thank you for helping make AI Debugger better!

## Code of Conduct

Please note that this project is released with a [Code of
Conduct](https://github.com/ai-debugger-inc/aidb/blob/main/CODE_OF_CONDUCT.md).
By participating in this project you agree to abide by its terms.
