# JavaScript Adapter Patterns (vscode-js-debug)

## Overview

The JavaScript adapter (`JavaScriptAdapter`) uses **vscode-js-debug** - Microsoft's DAP server that supports:

- Node.js debugging (scripts, modules, npm/yarn/pnpm scripts)
- TypeScript debugging (via ts-node)
- Source map support
- Child process debugging (automatic subprocess attachment)
- Chrome/Edge browser debugging

**File**: `src/aidb/adapters/lang/javascript/javascript.py`

## Critical Architectural Pattern: Child Sessions

**JavaScript uses parent-child sessions** - This is the most important concept:

1. **Parent session** launches vscode-js-debug DAP server
1. **Child session** is created via `startDebugging` reverse request when program starts
1. **Breakpoints** are transferred from parent to child
1. **Child session** does the actual debugging

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ├─────────────────────────────────────────┐
       │                                         │
┌──────▼──────────┐                    ┌────────▼────────┐
│ Parent Session  │─ startDebugging ──>│  Child Session  │
│  (launches DAP) │                    │ (actual debug)  │
└─────────────────┘                    └─────────────────┘
       │                                         │
       │                                         │
┌──────▼──────────────────────────────────────┐│
│         vscode-js-debug Server              ││
│  (single process, multiple connections)     ││
└──────────────────────────────────────────────┘
```

## Architecture

```
JavaScriptAdapter (extends DebugAdapter)
├── ProcessManager         - Launch vscode-js-debug subprocess
├── PortManager            - Acquire debug port
├── LaunchOrchestrator     - Coordinate launch sequence
└── Parent/Child Pattern   - Manage subprocess debugging
```

## Key Configuration Options

```python
@dataclass
class JavaScriptAdapterConfig(AdapterConfig):
    """JavaScript adapter configuration."""

    adapter_type: str = "pwa-node"     # pwa-node, pwa-chrome, pwa-msedge
    console: str = "internalConsole"   # Console to use
    output_capture: str = "console"    # Output capture mode
    enable_source_maps: bool = True    # Enable source map support
    use_ts_node: bool = True           # Use ts-node for TypeScript
    node_path: str | None = None       # Custom Node.js path
    js_debug_path: str | None = None   # Custom vscode-js-debug path
    show_async_stacks: bool = True     # Show async stack traces
```

## Breakpoint Transfer Pattern

**Critical**: Parent session must transfer breakpoints to child:

```python
def __init__(self, session, ctx=None, **kwargs):
    super().__init__(session, ctx, **kwargs)

    # JavaScript uses parent-child sessions
    # Only child sessions should have breakpoints
    if not session.is_child and session.breakpoints:
        # Store breakpoints for child session
        session._pending_child_breakpoints = session.breakpoints.copy()
        # Clear from parent
        session.breakpoints = []
        self.ctx.debug(
            f"Transferred {len(session._pending_child_breakpoints)} "
            f"breakpoints to _pending_child_breakpoints"
        )
```

## Child Session Initialization

```python
async def initialize_child_dap(
    self,
    child_session: "ISession",
    _start_request_type: StartRequestType,
    config: dict[str, Any],
) -> None:
    """Initialize JavaScript child session's DAP connection."""

    # Store __pendingTargetId for routing
    if "__pendingTargetId" in config:
        child_session._pending_target_id = config["__pendingTargetId"]

    # Create DAP client for child (connects to same adapter as parent)
    await child_session._setup_child_dap_client(
        self.adapter_host,
        self.session.adapter_port,
    )

    # Subscribe to breakpoint events
    await child_session._setup_breakpoint_event_subscription()

    # Execute child-specific initialization sequence
    child_sequence = [
        InitializationOp(InitializationOpType.INITIALIZE),
        InitializationOp(InitializationOpType.LAUNCH, wait_for_response=False),
        InitializationOp(
            InitializationOpType.WAIT_FOR_INITIALIZED,
            timeout=5.0,
            optional=True,
        ),
        InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=False),
        InitializationOp(InitializationOpType.CONFIGURATION_DONE),
        InitializationOp(
            InitializationOpType.WAIT_FOR_LAUNCH_RESPONSE,
            timeout=10.0,
        ),
    ]

    # InitializationOps is created internally by the session layer
    # See src/aidb/adapters/lang/javascript/javascript.py:initialize_child_dap()
    await init_ops._execute_initialization_sequence(child_sequence)
```

## Launch Command Construction

```python
async def _build_launch_command(
    self,
    target: str,
    _adapter_host: str,
    adapter_port: int,
    args: list[str] | None = None,
) -> list[str]:
    """Build command to launch vscode-js-debug DAP server."""

    # Ensure we have the server path
    if not self._js_debug_server_path:
        self._js_debug_server_path = await self._resolve_js_debug_binary()

    # Command: node dapDebugServer.js <port>
    node_exe = self._node_path or self._get_node_executable()
    cmd = [node_exe, str(self._js_debug_server_path), str(adapter_port)]

    # Store target info for launch configuration
    self._target_file = target
    self._target_args = args or []

    return cmd
```

## Launch Configuration for DAP

The JavaScript adapter provides comprehensive vscode-js-debug configuration via `get_launch_configuration()`. See `src/aidb/adapters/lang/javascript/javascript.py` lines 250-320 for the full implementation.

Key configuration areas:

- **TypeScript support**: Automatic ts-node integration for `.ts/.tsx` files
- **Source maps**: Path overrides for webpack, turbopack, meteor bundlers
- **Runtime detection**: Configurable runtime executable (node/npm/yarn/pnpm)
- **Trace logging**: Integration with adapter trace system
- **Output capture modes**: stdout, console, or both
- **Auto-attach**: Child process debugging support

## TypeScript Support

Automatic TypeScript detection and ts-node integration:

```python
async def _check_ts_node_available(self) -> bool:
    """Check if ts-node is available."""
    if self._ts_node_available is not None:
        return self._ts_node_available

    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "ts-node", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5.0)
        self._ts_node_available = proc.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        self._ts_node_available = False

    return self._ts_node_available
```

## Environment Variables

```python
def _add_adapter_specific_vars(self, env: dict) -> dict:
    """Add JavaScript-specific environment variables."""
    # Set Node.js environment
    env["NODE_ENV"] = env.get("NODE_ENV", "development")

    # Enable source map support
    if self.config.enable_source_maps:
        env["NODE_OPTIONS"] = env.get("NODE_OPTIONS", "") + " --enable-source-maps"

    # Disable telemetry
    env["DA_TEST_DISABLE_TELEMETRY"] = "1"

    return env
```

## Lifecycle Hooks Registration

```python
def _register_javascript_hooks(self) -> None:
    """Register JavaScript-specific lifecycle hooks."""
    # Pre-launch hooks
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._validate_js_environment,
        priority=90
    )
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._detect_project_config,
        priority=80
    )
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._prepare_vscode_js_debug,
        priority=70
    )

    # Post-launch hooks
    self.register_hook(
        LifecycleHook.POST_LAUNCH,
        self._wait_for_js_debug_server,
        priority=20
    )

    # Post-stop hooks
    self.register_hook(
        LifecycleHook.POST_STOP,
        self._cleanup_js_debug_logs,
        priority=10
    )
```

## Project Configuration Detection

```python
def _get_package_json_info(self, target: str) -> dict | None:
    """Get package.json information if available."""
    target_path = normalize_path(target, strict=True, return_path=True)
    for parent in [target_path.parent] + list(target_path.parents):
        package_json = parent / "package.json"
        if package_json.exists():
            with package_json.open() as f:
                data = json.load(f)
                return {
                    "name": data.get("name", ""),
                    "version": data.get("version", ""),
                    "type": data.get("type", "commonjs"),
                    "scripts": data.get("scripts", {}),
                }
    return None
```

## NPM/Yarn/PNPM Script Support

```python
adapter = JavaScriptAdapter(
    session=session,
    runtime_executable="npm",
    runtime_args=["run", "debug"]
)
```

Configuration adjusts for package managers:

```python
# For npm/yarn/pnpm scripts
if self.runtime_executable in ["npm", "yarn", "pnpm"]:
    # Find package.json directory
    package_json_dir = self._find_package_json_dir(target_path)
    if package_json_dir:
        config["cwd"] = str(package_json_dir)
    # Clear program when using npm scripts
    config.pop("program", None)
```

## Child Session Wait Pattern

```python
@property
def requires_child_session_wait(self) -> bool:
    """JavaScript requires waiting for child session creation."""
    return True
```

This flag tells the session manager to wait for child session creation before proceeding.

## Trace Configuration

```python
def get_trace_config(self) -> dict[str, Any] | None:
    """Get trace configuration for vscode-js-debug."""
    if not config.is_adapter_trace_enabled():
        return None

    log_file_path = None
    if self._trace_manager:
        trace_path = self._trace_manager.get_trace_log_path(
            self.config.adapter_id
        )
        log_file_path = str(trace_path)

    return {"stdio": True, "logFile": log_file_path}
```

## Common Patterns

### 1. Basic Node.js Script

```python
session = await client.start_session(
    target="/path/to/app.js",
    language="javascript",
    breakpoints=[{"line": 10}]
)
```

### 2. TypeScript Script

```python
session = await client.start_session(
    target="/path/to/app.ts",
    language="javascript",
    breakpoints=[{"line": 10}]
)
# Automatically uses ts-node if available
```

### 3. NPM Script

```python
session = await client.start_session(
    target="/path/to/package.json",
    language="javascript",
    runtime_executable="npm",
    runtime_args=["run", "dev"],
    breakpoints=[{"line": 10}]
)
```

## VS Code Launch.json Integration

Example launch.json for JavaScript:

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug Node App",
  "program": "${workspaceFolder}/app.js",
  "args": ["--verbose"],
  "cwd": "${workspaceFolder}",
  "env": {
    "NODE_ENV": "development"
  },
  "sourceMaps": true,
  "outFiles": ["${workspaceFolder}/dist/**/*.js"],
  "skipFiles": ["<node_internals>/**/*.js"],
  "console": "internalConsole"
}
```

## Reusable Code Reference

### Base Classes

- `DebugAdapter` - `src/aidb/adapters/base/adapter.py`
- `AdapterConfig` - `src/aidb/adapters/base/config.py`

### Utilities

- `normalize_path()` - `aidb_common/path.py`
- `config` - `aidb_common/config/`

### JavaScript-Specific

- `JavaScriptAdapterConfig` - `src/aidb/adapters/lang/javascript/config.py`

## Common Pitfalls

1. **Parent session breakpoints** - Always transfer breakpoints to child session
1. **Child session wait** - Must wait for `startDebugging` reverse request
1. **\_\_pendingTargetId missing** - Child launch requires this for routing
1. **Source maps** - Enable for TypeScript and transpiled code
1. **ts-node detection** - Check availability before enabling TypeScript
1. **Console output** - Use `outputCapture: "std"` to capture output
1. **Post-launch delay** - vscode-js-debug needs ~2s to initialize

## Testing Patterns (Conceptual Examples)

```python
# Test JavaScript file
session = await client.start_session(
    target="/path/to/app.js",
    language="javascript",
    breakpoints=[{"line": 10}]
)

# Test TypeScript file
session = await client.start_session(
    target="/path/to/app.ts",
    language="javascript",
    breakpoints=[{"line": 10}]
)

# Verify child session creation
assert session.is_child == False  # Parent session
child = await wait_for_child_session(session)
assert child.is_child == True
assert len(child.breakpoints) > 0  # Breakpoints transferred
```

## Critical Reminder

**JavaScript adapter is the most complex** due to the parent-child session pattern. Always:

1. Transfer breakpoints from parent to child
1. Initialize child DAP connection separately
1. Wait for child session before proceeding
1. Set \_\_pendingTargetId in child launch config

______________________________________________________________________

**See also**: [Adapter Development Main Skill](../SKILL.md) | [Python Patterns](python-adapter-patterns.md) | [Java Patterns](java-adapter-patterns.md)
