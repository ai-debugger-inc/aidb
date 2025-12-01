# Dev-CLI Service Patterns

Comprehensive guide to service architecture in AIDB dev-cli.

## BaseService Pattern

Services in AIDB dev-cli follow a consistent pattern for dependency injection and error handling.

### Recommended: Extend BaseService

Most services should extend the `BaseService` class located at `src/aidb_cli/managers/base/service.py`:

```python
from pathlib import Path
from aidb_cli.managers.base.service import BaseService

class MyService(BaseService):
    """Service extending BaseService for common functionality."""

    def __init__(self, repo_root: Path, command_executor=None, ctx=None):
        super().__init__(repo_root, command_executor, ctx)
        # Inherited: self.repo_root, self.command_executor (property),
        # self.resolved_env (property), logging methods

    def do_something(self, arg: str) -> str:
        """Do something useful."""
        from aidb.common.errors import AidbError

        self.log_info("Starting operation with %s", arg)
        result = self.command_executor.execute(["command", arg], cwd=self.repo_root)
        if result.returncode != 0:
            self.log_error("Command failed: %s", result.stderr)
            raise AidbError(f"Operation failed: {result.stderr}")
        return result.stdout.strip()
```

**BaseService provides**: `command_executor` (lazy-loaded property), `resolved_env` (from CLI context), logging helpers (`log_info`, `log_debug`, `log_warning`, `log_error`), path utilities (`validate_paths`, `ensure_directory`), `cleanup()` hook.

### Alternative: Standalone Service Structure

For simple services that don't need BaseService features:

```python
from pathlib import Path
from logging import Logger

from aidb_cli.services import CommandExecutor
from aidb_logging import get_cli_logger


class MyService:
    """Service for my operations."""

    def __init__(
        self,
        repo_root: Path,
        command_executor: CommandExecutor,
        logger: Logger | None = None
    ):
        """Initialize service with dependencies.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor
            Executor for subprocess commands
        logger : Logger | None
            Optional logger (defaults to module logger)
        """
        self.repo_root = repo_root
        self.executor = command_executor
        self.logger = logger or get_cli_logger(__name__)

    def do_something(self, arg: str) -> str:
        """Do something useful.

        Parameters
        ----------
        arg : str
            Input argument

        Returns
        -------
        str
            Operation result

        Raises
        ------
        AidbError
            If operation fails
        """
        from aidb.common.errors import AidbError

        # Use CommandExecutor for subprocess calls
        result = self.executor.execute(
            ["command", arg],
            cwd=self.repo_root,
            capture_output=True
        )

        if result.returncode != 0:
            self.logger.error(f"Command failed: {result.stderr}")
            raise AidbError(f"Operation failed: {result.stderr}")

        self.logger.info(f"Command succeeded: {result.stdout}")
        return result.stdout.strip()
```

## CommandExecutor Comprehensive Guide

The `CommandExecutor` is the **only** way to run subprocess commands in dev-cli. Never use `subprocess` directly.

### Basic Usage

```python
from aidb_cli.services import CommandExecutor

# Get from context
executor = ctx.obj.command_executor

# Execute command
result = executor.execute(
    ["docker", "build", "."],
    cwd=repo_root,
    capture_output=True
)

# Check result
if result.returncode != 0:
    from aidb.common.errors import AidbError
    raise AidbError(f"Docker build failed: {result.stderr}")
```

### Advanced Options

```python
# With environment variables
result = executor.execute(
    ["npm", "run", "build"],
    cwd=project_dir,
    env={"NODE_ENV": "production", "CI": "true"},
    capture_output=True
)

# With input piping
result = executor.execute(
    ["python", "-c", "import sys; print(sys.stdin.read())"],
    input="Hello from stdin",
    capture_output=True
)

# Stream output in real-time
result = executor.execute(
    ["pytest", "-v"],
    cwd=repo_root,
    capture_output=False  # Output goes to terminal
)
```

### Dry Run Support

CommandExecutor automatically respects the `--dry-run` flag:

```python
# In dry-run mode, this logs the command but doesn't execute
result = executor.execute(["rm", "-rf", "build/"])

# Returns mock result with returncode=0 in dry-run
```

### Error Handling with CommandExecutor

```python
from aidb.common.errors import AidbError

try:
    result = executor.execute(
        ["docker-compose", "up", "-d"],
        cwd=repo_root,
        capture_output=True
    )

    if result.returncode != 0:
        # Log stderr for debugging
        self.logger.error(f"Docker compose failed:\n{result.stderr}")

        # Raise user-friendly error
        raise AidbError(
            "Failed to start Docker services. "
            "Check Docker is running and docker-compose.yaml is valid."
        )

except FileNotFoundError:
    raise AidbError(
        "docker-compose not found. Install Docker Desktop or docker-compose CLI."
    )
```

## Service Instantiation Patterns

### From Command Context

Most common pattern - instantiate service in command with context dependencies:

```python
@group.command()
@click.pass_context
@handle_exceptions
def command(ctx: click.Context) -> None:
    """Command that uses a service."""
    # Instantiate service with dependencies from context
    from aidb_cli.services.adapter.adapter_service import AdapterService

    service = AdapterService(
        repo_root=ctx.obj.repo_root,
        command_executor=ctx.obj.command_executor
    )

    # Call service method
    result = service.build_adapter("python")

    # Output result
    CliOutput.success(f"Built adapter: {result}")
```

### Service Composition

Services can compose other services:

```python
class TestCoordinatorService:
    """Orchestrates test execution."""

    def __init__(
        self,
        repo_root: Path,
        command_executor: CommandExecutor,
        ctx: click.Context
    ):
        self.repo_root = repo_root
        self.executor = command_executor
        self.logger = get_cli_logger(__name__)

        # Compose other services
        self.docker_service = DockerHealthService(command_executor)
        self.test_service = TestExecutionService(repo_root, command_executor)

    def run_tests(self, suite: str, parallel: int = 1) -> TestResult:
        """Run tests with Docker health check first."""
        from aidb.common.errors import AidbError

        # Use composed service
        if not self.docker_service.is_healthy():
            raise AidbError("Docker services not healthy")

        # Delegate to test service
        return self.test_service.execute_suite(suite, parallel=parallel)
```

### Singleton Services (Managers)

Complex stateful services use singleton pattern via `@dataclass` managers:

```python
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class BuildManager:
    """Singleton build manager."""

    _instance: ClassVar[Optional['BuildManager']] = None
    repo_root: Path
    executor: CommandExecutor

    @classmethod
    def get_instance(
        cls,
        repo_root: Path,
        executor: CommandExecutor
    ) -> 'BuildManager':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(repo_root, executor)
        return cls._instance
```

## Real Service Examples

### Example 1: DockerBuildService

**See real implementation**: `src/aidb_cli/services/docker/docker_build_service.py`

The `DockerBuildService` provides methods for building Docker images with intelligent rebuild detection based on checksum changes. Key pattern - services return exit codes and raise exceptions on failure.

**For checksum system details**, see [checksum-services.md](checksum-services.md) which covers DockerImageChecksumService integration, FrameworkDepsChecksumService, and the ChecksumServiceBase pattern.

```python
class DockerBuildService:
    """Service for building Docker images."""

    def __init__(self, repo_root: Path, command_executor: CommandExecutor):
        self.repo_root = repo_root
        self.executor = command_executor
        self.logger = get_cli_logger(__name__)

    def build_images(
        self,
        *,  # Keyword-only arguments
        profile: str | None = None,
        no_cache: bool = False,
        verbose: bool = False,
        auto_rebuild: bool = True,
        check_only: bool = False
    ) -> int:
        """Build Docker images with optional profile.

        Parameters
        ----------
        profile : str | None
            Docker compose profile to build
        no_cache : bool
            Build without using cache
        verbose : bool
            Verbose output
        auto_rebuild : bool
            Automatically rebuild if checksums changed
        check_only : bool
            Only check if rebuild needed, don't build

        Returns
        -------
        int
            Return code (0 for success, non-zero for failure)
        """
        # Actual implementation includes checksum verification for framework deps
        # See src/aidb_cli/services/docker/docker_build_service.py for full logic
        cmd = ["docker-compose", "build"]
        if profile:
            cmd.extend(["--profile", profile])
        if no_cache:
            cmd.append("--no-cache")

        result = self.executor.execute(cmd, cwd=self.repo_root)

        if result.returncode == 0:
            self.logger.info("Docker images built successfully")
            return 0
        else:
            self.logger.error(f"Build failed: {result.stderr}")
            return result.returncode
```

### Example 2: AdapterBuildService

**See real implementation**: `src/aidb_cli/services/adapter/adapter_build_service.py`

The `AdapterBuildService` extends `BaseService` and provides methods for building language adapters locally. Key methods:

- `build_locally(languages, verbose, resolved_env)` - Builds adapters for specified languages
- Uses CommandExecutor to run language-specific build commands
- Handles environment resolution and validation

## Testing Services

Services are easily testable through dependency injection:

**Unit tests**: Mock `CommandExecutor` to test service logic without executing commands
**Integration tests**: Use real `CommandExecutor(dry_run=True)` for faster tests

**Pattern**:

```python
from unittest.mock import Mock, MagicMock

def test_service():
    executor = Mock()
    executor.execute.return_value = MagicMock(returncode=0, stdout="output")
    service = MyService(repo_root, executor)
    result = service.do_something()
    assert result == "output"
```

**See actual test examples**:

- `src/tests/aidb_cli/` - CLI service unit and integration tests

## Best Practices

### 1. Always Accept Dependencies in __init__

**Good**:

```python
def __init__(self, repo_root: Path, command_executor: CommandExecutor):
    self.repo_root = repo_root
    self.executor = command_executor
```

**Bad**:

```python
def __init__(self):
    self.repo_root = Path.cwd()  # Hardcoded, not testable
    self.executor = CommandExecutor()  # Can't mock
```

### 2. Use CommandExecutor, Not subprocess

**Good**:

```python
result = self.executor.execute(["docker", "ps"])
```

**Bad**:

```python
result = subprocess.run(["docker", "ps"])  # Bypasses dry-run, logging
```

### 3. Log Operations, Don't Print

**Good**:

```python
self.logger.info("Building Docker images...")
self.logger.debug(f"Command: {cmd}")
```

**Bad**:

```python
print("Building Docker images...")  # Not structured logging
```

### 4. Raise Exceptions, Don't Return Error Codes

**Good**:

```python
from aidb.common.errors import AidbError

if result.returncode != 0:
    raise AidbError(f"Build failed: {result.stderr}")
```

**Bad**:

```python
if result.returncode != 0:
    return False  # Caller has to check return value
```

### 5. Type Hint Everything

**Good**:

```python
def build_images(self, profile: str | None = None) -> int:
```

**Bad**:

```python
def build_images(self, profile=None):
```

## Common Pitfalls

### 1. Creating Services Without Dependency Injection

**Wrong**:

```python
class MyService:
    def __init__(self):
        self.executor = CommandExecutor()  # Creates its own
```

**Right**:

```python
class MyService:
    def __init__(self, command_executor: CommandExecutor):
        self.executor = command_executor  # Accepts from caller
```

### 2. Using Global State

**Wrong**:

```python
REPO_ROOT = Path("/hardcoded/path")

class MyService:
    def do_something(self):
        # Uses global
        result = subprocess.run(["cmd"], cwd=REPO_ROOT)
```

**Right**:

```python
class MyService:
    def __init__(self, repo_root: Path, executor: CommandExecutor):
        self.repo_root = repo_root
        self.executor = executor

    def do_something(self):
        result = self.executor.execute(["cmd"], cwd=self.repo_root)
```

### 3. Mixing User Output with Logging

**Wrong**:

```python
def build(self):
    print("Building...")  # User-facing
    logger.info("Build started")  # Debugging
```

**Right**:

```python
def build(self):
    self.logger.info("Building...")  # Only logging in service
    # Let command layer handle user output with CliOutput
```

## Service Layer Architecture Summary

**Commands** → Thin Click wrappers

- Handle CLI arguments
- Instantiate services
- Use `CliOutput` for user messages
- Delegate to services

**Services** → Business logic

- Accept dependencies in `__init__`
- Use `CommandExecutor` for subprocesses
- Use `logger` for debugging
- Raise exceptions for errors
- Return typed results

**Managers** → Complex orchestration

- Singleton pattern
- Coordinate multiple services
- Maintain state across operations
- Handle complex workflows

This separation keeps code testable, maintainable, and consistent across all dev-cli commands.
