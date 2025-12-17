# MCP & Service Layers

The top two layers of AIDB: MCP server for AI agents and Service layer for debugging operations.

## MCP Layer (aidb_mcp/)

**Purpose:** Model Context Protocol server exposing 12 debugging tools to AI agents.

### Architecture

```
Client (AI Agent) → stdio → AidbMCPServer
  ├── _handle_list_tools() → Return tool definitions
  ├── _handle_call_tool() → Execute tool, return response
  └── _handle_list_resources() → Return debugging resources
      ↓
  TOOL_HANDLERS registry → DebugService
```

### The 12 Tools

| Tool                 | Purpose                              | Handler Location                          |
| -------------------- | ------------------------------------ | ----------------------------------------- |
| `aidb.init`          | Initialize debugging context         | `handlers/session/initialization.py`      |
| `aidb.session_start` | Create and start debug session       | `handlers/session/lifecycle.py`           |
| `aidb.execute`       | Run/continue actions                 | `handlers/execution/control.py`           |
| `aidb.step`          | Step over/into/out                   | `handlers/execution/stepping.py`          |
| `aidb.inspect`       | Inspect locals/globals/stack/threads | `handlers/inspection/state_inspection.py` |
| `aidb.breakpoint`    | Set/remove/list/clear breakpoints    | `handlers/inspection/breakpoints.py`      |
| `aidb.variable`      | Get/set/patch variables              | `handlers/inspection/variables.py`        |
| `aidb.session`       | Status/list/stop/restart/switch      | `handlers/session/management.py`          |
| `aidb.config`        | Config, env vars, launch.json        | `handlers/session/configuration.py`       |
| `aidb.context`       | Rich debugging context               | `handlers/context/handler.py`             |
| `aidb.run_until`     | Temporary breakpoints                | `handlers/execution/run_until.py`         |
| `aidb.adapter`       | Download/install adapters            | `handlers/adapter_download.py`            |

### Handler Pattern

```python
@mcp_tool()
async def handle_step(args: dict) -> dict:
    # 1. Validate init completed (via decorator)
    # 2. Get injected parameters from decorator:
    service = args["_service"]      # DebugService instance
    context = args["_context"]      # MCPSessionContext
    session_id = args["_session_id"]
    # 3. Validate params
    # 4. Call DebugService: await service.stepping.step_over(thread_id)
    # 5. Update context
    # 6. Return Response().to_mcp_response()
```

### @mcp_tool Decorator Stack

The `@mcp_tool()` decorator provides a standardized wrapper for all handlers:

```
@timed                    # 1. Performance tracking
@audit_operation          # 2. Audit logging (persistent trail)
@with_thread_safety       # 3. Thread safety + session injection
@with_parameter_validation # 4. Parameter validation (optional)
@with_execution_context   # 5. Context capture + history recording
```

### Response System

**Base Response** → auto-serializes dataclass fields + `to_mcp_response()`
**ErrorResponse** → `success=False`, `error_code`, `error_message`
**ResponseDeduplicator** → removes redundant fields (30-50% token savings)

### Session Management

```
MCP Session (1) → DebugService (1) → aidb.Session (1+)
              → MCPSessionContext (1)
```

**MCPSessionContext** tracks: current position, execution state, breakpoints, init status, stack/variable history.

______________________________________________________________________

## Service Layer (aidb/service/)

**Purpose:** Stateless service layer providing debugging operations on a Session.

### Core Components

**DebugService** (`debug_service.py`) - Main entry point

```python
class DebugService:
    """Stateless debugging operations on a Session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.execution = ExecutionControl(session)
        self.stepping = SteppingService(session)
        self.breakpoints = BreakpointManager(session)
        self.variables = VariableInspector(session)
        self.stack = StackNavigator(session)
```

**SessionBuilder** (`session/builder.py`) - Fluent construction

- `with_target()`, `with_attach()`, `with_language()`
- `with_launch_config()` for VS Code launch.json
- `with_breakpoints()`, `with_timeout()`

**SessionManager** (`session/manager.py`) - Lifecycle management

- Thread-safe session count (max 10 concurrent)
- Creates sessions via SessionBuilder

### Operations by Namespace

**Execution Control** (`service.execution`):

- `continue_()`, `pause()`, `restart()`, `terminate()`
- `get_current_thread_id()`, `get_output()`

**Stepping** (`service.stepping`):

- `step_into()`, `step_over()`, `step_out()`, `step_back()`
- `get_current_thread_id()`

**Breakpoints** (`service.breakpoints`):

- `set()`, `remove()`, `list()`, `clear_all()`
- `watch()`, `unwatch()` (watchpoints)

**Variables** (`service.variables`):

- `evaluate()`, `set_variable()`, `set_expression()`
- `locals_()`, `globals_()`, `scopes()`

**Stack** (`service.stack`):

- `callstack()`, `threads()`, `exception()`
- `get_current_thread_id()`, `get_current_frame_id()`

### Child Session Resolution

JavaScript uses parent-child sessions. Service resolves to active session automatically:

```python
@property
def session(self) -> Session:
    return resolve_active_session(self._session, self.ctx)
```

______________________________________________________________________

## Key Files

**MCP:**

- `aidb_mcp/server/app.py` - AidbMCPServer
- `aidb_mcp/handlers/registry.py` - TOOL_HANDLERS
- `aidb_mcp/core/decorators.py` - @mcp_tool decorator
- `aidb_mcp/responses/base.py` - Response classes
- `aidb_mcp/session/manager.py` - Session management

**Service:**

- `aidb/service/debug_service.py` - DebugService
- `aidb/service/execution/control.py` - ExecutionControl
- `aidb/service/execution/stepping.py` - SteppingService
- `aidb/service/breakpoints/manager.py` - BreakpointManager
- `aidb/service/variables/inspector.py` - VariableInspector
- `aidb/service/stack/navigator.py` - StackNavigator

**Session:**

- `aidb/session/builder.py` - SessionBuilder
- `aidb/session/manager.py` - SessionManager
