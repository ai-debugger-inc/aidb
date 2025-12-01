# Python Adapter Patterns (debugpy)

## Overview

The Python adapter (`PythonAdapter`) uses **debugpy** as the DAP server. Debugpy is Microsoft's official Python debug adapter that supports:

- Script and module debugging
- Virtual environments
- Frameworks (Django, Flask, pytest, etc.)
- Subprocess debugging
- Conditional breakpoints and logpoints

**File**: `src/aidb/adapters/lang/python/python.py`

## Architecture

```
PythonAdapter (extends DebugAdapter)
├── ProcessManager      - Launch debugpy subprocess
├── PortManager         - Acquire debug port
├── LaunchOrchestrator  - Coordinate launch sequence
└── PythonTraceManager  - Manage debugpy log files
```

## Key Configuration Options

```python
@dataclass
class PythonAdapterConfig(AdapterConfig):
    """Python adapter configuration."""

    # Core debugging flags
    justMyCode: bool = True          # Debug only user code (skip stdlib)
    subProcess: bool = False         # Enable subprocess debugging
    showReturnValue: bool = True     # Show function return values
    redirectOutput: bool = True      # Redirect stdout/stderr to debug console

    # Framework support
    django: bool = False             # Enable Django debugging
    flask: bool = False              # Enable Flask debugging
    jinja: bool = False              # Enable Jinja template debugging
    pyramid: bool = False            # Enable Pyramid debugging
    gevent: bool = False             # Enable gevent debugging
```

## Module vs Script Debugging

Python supports two launch modes via the `module` flag:

### Script Mode (module=False)

```python
adapter = PythonAdapter(
    session=session,
    module=False  # Default
)
# Launches: python -m debugpy --listen 5678 script.py
```

### Module Mode (module=True)

```python
adapter = PythonAdapter(
    session=session,
    module=True
)
# Launches: python -m debugpy --listen 5678 -m pytest tests/
```

**Common modules**: pytest, unittest, myapp.cli

## Launch Command Construction

```python
async def _build_launch_command(
    self,
    target: str,
    adapter_host: str,
    adapter_port: int,
    args: list[str] | None = None,
) -> list[str]:
    """Build the debugpy launch command."""
    python_executable = self.python_path or sys.executable
    listen_address = f"{adapter_host}:{adapter_port}"

    base = [
        python_executable,
        "-m", "debugpy",
        "--listen", listen_address,
        "--wait-for-client",
    ]

    argv: list[str] = list(args or [])

    if self.module:
        return base + ["-m", target, *argv]
    else:
        return base + [target, *argv]
```

## Environment Variables

Python adapter sets specific environment variables:

```python
def _add_adapter_specific_vars(self, env: dict) -> dict:
    """Add Python-specific environment variables."""
    # Set debugpy log directory
    env["DEBUGPY_LOG_DIR"] = self._debugpy_log_dir

    # Don't write bytecode during debugging
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    # Disable file validation checks for performance
    env["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"

    return env
```

## Target Validation Hook

Python adapter overrides target validation to support modules:

```python
def _validate_target_hook(self, context: HookContext) -> None:
    """Override target validation to handle Python modules."""
    target = context.data.get("target")
    if not target:
        return

    # If module mode, skip file validation
    if self.module:
        self.ctx.debug(f"Module mode: skipping file validation for '{target}'")
        return

    # For file mode, use base validation
    super()._validate_target_hook(context)
```

## Lifecycle Hooks Registration

```python
def _register_python_hooks(self) -> None:
    """Register Python-specific lifecycle hooks."""
    # Pre-launch: Setup trace configuration
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._setup_trace_before_launch,
        priority=90  # Very high priority
    )

    # Pre-launch: Validate Python target
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._validate_python_target,
        priority=80
    )

    # Post-launch: Wait for debugpy initialization
    self.register_hook(
        LifecycleHook.POST_LAUNCH,
        self._wait_for_debugpy,
        priority=20  # Low priority
    )

    # Post-stop: Consolidate debugpy logs
    self.register_hook(
        LifecycleHook.POST_STOP,
        self._consolidate_debugpy_logs,
        priority=10
    )
```

## Trace Log Management

Debugpy creates per-PID log files. The PythonTraceManager consolidates them:

```python
def _setup_trace_configuration(self) -> None:
    """Set up trace configuration for debugpy."""
    if self._debugpy_log_manager is not None:
        return

    if self._trace_manager:
        trace_path = self._trace_manager.get_trace_log_path(
            self.config.adapter_id
        )
        trace_dir = str(Path(trace_path).parent)
    else:
        trace_dir = self.ctx.get_storage_path("log/adapter_traces", "python")
        Path(trace_dir).mkdir(parents=True, exist_ok=True)

    self._debugpy_log_manager = PythonTraceManager(
        ctx=self.ctx,
        trace_dir=trace_dir,
    )

    # Cleanup old logs and rotate
    cleaned = self._debugpy_log_manager.cleanup_old_pid_logs()
    self._debugpy_log_manager.rotate_logs_on_start()

    self._debugpy_log_dir = trace_dir
```

## Launch Configuration for DAP

```python
def get_launch_configuration(self) -> dict[str, Any]:
    """Get the launch configuration for debugpy."""
    config: dict[str, Any] = {}

    # Core debugging flags
    config["justMyCode"] = self.config.justMyCode
    config["subProcess"] = self.config.subProcess
    config["showReturnValue"] = self.config.showReturnValue
    config["redirectOutput"] = self.config.redirectOutput

    # Framework flags
    if self.config.django:
        config["django"] = True
    if self.config.flask:
        config["flask"] = True
    # ... other frameworks

    # Adapter settings
    if self.module:
        config["module"] = True
    if self.python_path:
        config["python"] = self.python_path
    if self.env_file:
        config["envFile"] = self.env_file

    # Environment and working directory
    if self._target_env:
        config["env"] = self._target_env
    if self._target_cwd:
        config["cwd"] = self._target_cwd

    return config
```

## Environment File Support

Python adapter supports .env files for environment variables:

```python
def _load_env_file(self, env_file_path: str) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars: dict[str, str] = {}

    if not Path(env_file_path).is_file():
        self.ctx.warning(f"Environment file '{env_file_path}' not found")
        return env_vars

    with Path(env_file_path).open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]

                env_vars[key] = value

    return env_vars
```

## Custom Python Interpreter

Support for custom Python interpreters:

```python
adapter = PythonAdapter(
    session=session,
    python_path="/path/to/venv/bin/python"
)
```

The adapter validates the path and falls back to `sys.executable` if not found.

## Framework-Specific Debugging

### Django

```python
adapter = PythonAdapter(
    session=session,
    django=True,
    module=True  # Usually run as module
)
```

### Flask

```python
adapter = PythonAdapter(
    session=session,
    flask=True,
)
```

### pytest

```python
adapter = PythonAdapter(
    session=session,
    module=True,  # Run pytest as module
)
# Target: "pytest" or specific test file
```

## Common Patterns

### 1. Virtual Environment Detection

```python
# Adapter uses sys.executable by default, which respects active venv
python_executable = self.python_path or sys.executable
```

### 2. Subprocess Debugging

```python
config = PythonAdapterConfig(
    subProcess=True  # Enable subprocess debugging
)
```

## VS Code Launch.json Integration

Example launch.json for Python:

```json
{
  "type": "python",
  "request": "launch",
  "name": "Debug Python Script",
  "program": "${workspaceFolder}/app.py",
  "args": ["--verbose"],
  "cwd": "${workspaceFolder}",
  "env": {
    "DEBUG": "1"
  },
  "envFile": "${workspaceFolder}/.env",
  "justMyCode": false,
  "django": false,
  "flask": false
}
```

## Reusable Code Reference

### Base Classes

- `DebugAdapter` - `src/aidb/adapters/base/adapter.py`
- `AdapterConfig` - `src/aidb/adapters/base/config.py`

### Utilities

- `normalize_path()` - `aidb_common/path.py`
- `config` - `aidb_common/config/`

### Python-Specific

- `PythonTraceManager` - `src/aidb/adapters/lang/python/trace.py`
- `PythonSyntaxValidator` - `src/aidb/adapters/lang/python/syntax_validator.py`

## Common Pitfalls

1. **Forgetting module flag** - Use `module=True` for pytest, unittest, etc.
1. **Wrong Python path** - Verify virtual environment activation
1. **Missing wait-for-client** - Debugpy requires `--wait-for-client` flag
1. **Log consolidation** - Always register POST_STOP hook for log cleanup
1. **Environment variables** - Use .env file support for complex setups

## Testing Patterns (Conceptual Examples)

```python
# Test script debugging
session = await client.start_session(
    target="/path/to/script.py",
    language="python",
    breakpoints=[{"line": 10}]
)

# Test module debugging
session = await client.start_session(
    target="pytest",
    language="python",
    module=True,
    args=["tests/test_foo.py"],
    breakpoints=[{"line": 15}]
)
```

______________________________________________________________________

**See also**: [Adapter Development Main Skill](../SKILL.md) | [JavaScript Patterns](javascript-adapter-patterns.md) | [Java Patterns](java-adapter-patterns.md)
