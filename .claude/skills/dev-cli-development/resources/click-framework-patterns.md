# Click Framework Patterns

Comprehensive guide to Click framework usage in AIDB dev-cli.

## Decorator Stacking Rules

**CRITICAL**: Decorator order matters in Click. Wrong order causes cryptic errors.

### Correct Order

```python
@group.command()                    # 1. Click command decorator (FIRST)
@click.option("--opt", "-o")        # 2. Click options/arguments
@click.argument("arg")              # 3. Click arguments
@click.pass_context                 # 4. Pass context (BEFORE handle_exceptions)
@handle_exceptions                  # 5. Custom error handling (LAST)
def command(ctx: click.Context, opt: str, arg: str) -> None:
    """Command implementation."""
    pass
```

### Why This Order?

Click decorators work from **bottom to top** when decorating, but **top to bottom** when executing:

1. `@group.command()` - Registers function as Click command
1. `@click.option/argument` - Adds parameters to command
1. `@click.pass_context` - Injects context as first parameter
1. `@handle_exceptions` - Wraps entire function for error handling

### Common Mistakes

**Wrong - `@handle_exceptions` before `@click.pass_context`**:

```python
@group.command()
@click.option("--opt")
@handle_exceptions  # WRONG - too early
@click.pass_context
def command(ctx, opt):
    pass
# Error: handle_exceptions doesn't know about ctx parameter
```

**Wrong - `@click.pass_context` before options**:

```python
@group.command()
@click.pass_context  # WRONG - too early
@click.option("--opt")
def command(ctx, opt):
    pass
# Error: Click can't bind opt parameter correctly
```

## Custom Parameter Types

AIDB dev-cli uses custom parameter types for validation, autocompletion, and better UX.

### TestSuiteParamType

Validates test suite names dynamically based on available suites:

```python
from aidb_cli.core.param_types import TestSuiteParamType

@click.option(
    "--suite",
    "-s",
    type=TestSuiteParamType(),
    required=True,
    help="Test suite to run"
)
def test_command(ctx: click.Context, suite: str) -> None:
    """Run tests for a suite."""
    # suite is guaranteed to be valid
    pass
```

**Features**:

- Validates against available suites (reads from config/filesystem)
- Provides shell completion
- Shows helpful error if invalid suite

### LanguageParamType

Validates language selection:

```python
from aidb_cli.core.param_types import LanguageParamType

@click.option(
    "--language",
    "-l",
    type=LanguageParamType(),
    multiple=True,  # Allow multiple languages
    help="Languages to target"
)
def command(ctx: click.Context, language: tuple[str, ...]) -> None:
    """Command supporting multiple languages."""
    for lang in language:
        # Each lang is validated ("python", "javascript", "java")
        process_language(lang)
```

### DockerProfileParamType

Validates Docker Compose profiles:

```python
from aidb_cli.core.param_types import DockerProfileParamType

@click.option(
    "--profile",
    "-p",
    type=DockerProfileParamType(),
    default=None,
    help="Docker profile to use"
)
def docker_command(ctx: click.Context, profile: str | None) -> None:
    """Docker command with profile validation."""
    # profile is None or valid Docker profile name
    pass
```

### TestMarkerParamType & TestPatternParamType

For pytest-specific filtering:

```python
from aidb_cli.core.param_types import TestMarkerParamType, TestPatternParamType

@click.option(
    "--marker",
    "-m",
    type=TestMarkerParamType(),
    multiple=True,
    help="Pytest markers to filter by"
)
@click.option(
    "--pattern",
    "-p",
    type=TestPatternParamType(),
    help="Test name pattern (supports wildcards)"
)
def test_run(
    ctx: click.Context,
    marker: tuple[str, ...],
    pattern: str | None
) -> None:
    """Run tests with filtering."""
    pass
```

### Creating Custom Parameter Types

```python
import click
from typing import Any


class MyCustomParamType(click.ParamType):
    """Custom parameter type with validation."""

    name = "my_type"  # Used in error messages

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None
    ) -> str:
        """Convert and validate parameter value.

        Parameters
        ----------
        value : Any
            Raw value from command line
        param : click.Parameter | None
            Parameter being processed
        ctx : click.Context | None
            Command context

        Returns
        -------
        str
            Validated/converted value

        Raises
        ------
        click.BadParameter
            If validation fails
        """
        # Validation logic
        if not self._is_valid(value):
            self.fail(
                f"'{value}' is not a valid my_type. "
                f"Expected format: ...",
                param,
                ctx
            )

        return value

    def shell_complete(
        self,
        ctx: click.Context,
        param: click.Parameter,
        incomplete: str
    ) -> list[click.shell_completion.CompletionItem]:
        """Provide shell completion suggestions.

        Parameters
        ----------
        ctx : click.Context
            Command context
        param : click.Parameter
            Parameter being completed
        incomplete : str
            Partial value user has typed

        Returns
        -------
        list[CompletionItem]
            Completion suggestions
        """
        # Get valid options
        options = self._get_valid_options()

        # Filter by incomplete
        matches = [opt for opt in options if opt.startswith(incomplete)]

        return [
            click.shell_completion.CompletionItem(match)
            for match in matches
        ]
```

## Context Management

The Click context (`ctx.obj`) carries shared state across command execution.

**Standard attributes**: `repo_root` (Path), `command_executor` (CommandExecutor), `dry_run` (bool), `verbose` (int), `no_cleanup` (bool)

**Usage**:

```python
@click.pass_context
def command(ctx: click.Context) -> None:
    # Always available
    repo_root = ctx.obj.repo_root
    executor = ctx.obj.command_executor

    # Optional - use getattr with defaults
    verbose = getattr(ctx.obj, "verbose", 0)
```

**Context object**: See `src/aidb_cli/cli.py` for CliContext structure

**Subcommands inherit context** from parent groups automatically

## Error Handling Patterns

### Using @handle_exceptions

The `@handle_exceptions` decorator provides unified error handling:

```python
from aidb_cli.core.decorators import handle_exceptions
from aidb.common.errors import AidbError

@group.command()
@click.pass_context
@handle_exceptions
def command(ctx: click.Context) -> None:
    """Command with automatic error handling."""

    # Just raise errors naturally - decorator handles:
    # - KeyboardInterrupt (cleanup Docker resources)
    # - AidbError (formatted error output)
    # - FileNotFoundError (specific exit code)
    # - PermissionError (specific exit code)
    # - Generic exceptions (traceback in verbose mode)

    if not valid:
        raise AidbError("Validation failed")

    if not Path("required.txt").exists():
        raise FileNotFoundError("required.txt not found")
```

### What @handle_exceptions Does

1. **Catches KeyboardInterrupt** (Ctrl+C)

   - Logs graceful shutdown
   - Cleans up Docker resources if `--no-cleanup` not set
   - Exits with code 130

1. **Catches AidbError** (domain exceptions)

   - Shows user-friendly error message
   - Logs full traceback to debug log
   - Exits with error-specific code

1. **Catches FileNotFoundError, PermissionError**

   - Maps to specific exit codes
   - Shows helpful error messages

1. **Catches all other exceptions**

   - Shows full traceback if `--verbose`
   - Shows brief error otherwise
   - Exits with code 1

### Custom Exception Types

```python
from aidb.common.errors import AidbError

class DockerNotRunningError(AidbError):
    """Docker daemon is not running."""

    def __init__(self):
        super().__init__(
            "Docker is not running. Start Docker Desktop and try again."
        )


class TestSuiteNotFoundError(AidbError):
    """Test suite not found."""

    def __init__(self, suite: str):
        super().__init__(
            f"Test suite '{suite}' not found. "
            f"Available suites: {', '.join(get_available_suites())}"
        )


# In command:
@handle_exceptions
def command(ctx: click.Context):
    if not docker_is_running():
        raise DockerNotRunningError()

    if suite not in get_available_suites():
        raise TestSuiteNotFoundError(suite)
```

### Exit Codes

```python
from aidb_cli.core.constants import ExitCode

@click.pass_context
def command(ctx: click.Context):
    """Command with explicit exit codes."""

    if config_error:
        CliOutput.error("Configuration invalid")
        ctx.exit(ExitCode.CONFIG_ERROR)  # 3

    if not found:
        CliOutput.error("Resource not found")
        ctx.exit(ExitCode.NOT_FOUND)  # 2

    if general_error:
        CliOutput.error("Operation failed")
        ctx.exit(ExitCode.GENERAL_ERROR)  # 1

    # Success
    CliOutput.success("Operation completed")
    ctx.exit(ExitCode.SUCCESS)  # 0
```

## Command Groups and Subcommands

**Pattern**: Use `@click.group()` to create command groups, `@group.command()` to add subcommands

```python
@click.group(name="docker")
def docker_group(ctx: click.Context) -> None:
    """Docker management commands."""
    pass

@docker_group.command(name="build")
@click.pass_context
@handle_exceptions
def build_command(ctx: click.Context) -> None:
    """Invoked as: ./dev-cli docker build"""
    pass
```

**Nested groups**: Use `@group.group()` for multi-level nesting. See `src/aidb_cli/commands/docker.py` and `src/aidb_cli/commands/test.py` for real examples

## Advanced Click Patterns

For advanced patterns like callbacks, mutually exclusive options, dynamic defaults, see [Click documentation](https://click.palletsprojects.com/).

**Common AIDB-specific patterns**: Custom parameter types (above), `@handle_exceptions` decorator, context management

## Best Practices Summary

### 1. Always Use Type Hints

```python
# Good
def command(ctx: click.Context, option: str) -> None:

# Bad
def command(ctx, option):
```

### 2. Use Custom Param Types for Complex Validation

```python
# Good
@click.option("--suite", type=TestSuiteParamType())

# Bad
@click.option("--suite", type=str, callback=validate_suite_manually)
```

### 3. Keep Commands Thin

```python
# Good
@handle_exceptions
def command(ctx: click.Context):
    service = MyService(ctx.obj.repo_root, ctx.obj.command_executor)
    result = service.do_work()
    CliOutput.success(f"Done: {result}")

# Bad
@handle_exceptions
def command(ctx: click.Context):
    # 100 lines of business logic inline
```

### 4. Use @handle_exceptions

```python
# Good
@handle_exceptions
def command(ctx):
    raise AidbError("Something went wrong")

# Bad
def command(ctx):
    try:
        # Manual error handling
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

### 5. Access Context with getattr for Optional Attributes

```python
# Good
verbose = getattr(ctx.obj, "verbose", 0)

# Bad
verbose = ctx.obj.verbose  # May not exist
```

This ensures Click commands are consistent, maintainable, and provide excellent UX.
