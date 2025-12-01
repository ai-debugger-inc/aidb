# API & MCP Layers

The top two layers of AIDB: MCP server for AI agents and Python API for developers.

## MCP Layer (aidb_mcp/)

**Purpose:** Model Context Protocol server exposing 12 debugging tools to AI agents.

### Architecture

```
Client (AI Agent) → stdio → AidbMCPServer
  ├── _handle_list_tools() → Return tool definitions
  ├── _handle_call_tool() → Execute tool, return response
  └── _handle_list_resources() → Return debugging resources
      ↓
  TOOL_HANDLERS registry → DebugAPI
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
async def handle_step(args: dict) -> dict:
    # 1. Validate init completed
    # 2. Get session: session_id, debug_api, context = get_or_create_session(args)
    # 3. Validate params
    # 4. Call DebugAPI: await debug_api.orchestration.step_over()
    # 5. Update context
    # 6. Return Response().to_mcp_response()
```

### Response System

**Base Response** → auto-serializes dataclass fields + `to_mcp_response()`
**ErrorResponse** → `success=False`, `error_code`, `error_message`
**ResponseDeduplicator** → removes redundant fields (30-50% token savings)

### Session Management

```
MCP Session (1) → DebugAPI (1) → aidb.Session (1+)
              → MCPSessionContext (1)
```

**MCPSessionContext** tracks: current position, execution state, breakpoints, init status, stack/variable history.

______________________________________________________________________

## API Layer (aidb/api/)

**Purpose:** Python API providing `.introspection` and `.orchestration` properties.

### Core Components

**DebugAPI** (`api.py`) - Main entry point

- `create_session(target, language, ...)` → Session
- `.introspection` property → state inspection operations
- `.orchestration` property → control flow operations

**SessionManager** (`session_manager.py`) - Lifecycle management

- Thread-safe session count (max 10 concurrent)
- Creates sessions via SessionBuilder

**SessionBuilder** (`session_builder.py`) - Fluent construction

- `with_target()`, `with_attach()`, `with_language()`
- `with_launch_config()` for VS Code launch.json
- `with_breakpoints()`, `with_timeout()`

### Operations

**Introspection** (read-only):

- `locals()`, `globals()`, `evaluate()`
- `callstack()`, `threads()`, `frames()`, `scopes()`
- `read_memory()`, `write_memory()`

**Orchestration** (control):

- `continue_()`, `pause()`, `restart()`, `stop()`
- `step_into()`, `step_over()`, `step_out()`
- `breakpoint()`, `remove_breakpoint()`, `clear_breakpoints()`

### Usage

```python
api = DebugAPI()
session = await api.create_session(target="app.py", language="python")
await session.start()

locals_vars = await api.introspection.locals()
await api.orchestration.step_over()
await api.stop()
```

### Child Session Resolution

JavaScript uses parent-child sessions. `get_active_session()` returns child if exists:

```python
@property
def session(self) -> Session:
    if self._root_session.child_session_ids:
        child_id = self._root_session.child_session_ids[0]
        return self._root_session.registry.get_session(child_id)
    return self._root_session
```

______________________________________________________________________

## Key Files

**MCP:**

- `aidb_mcp/server/app.py` - AidbMCPServer
- `aidb_mcp/handlers/registry.py` - TOOL_HANDLERS
- `aidb_mcp/responses/base.py` - Response classes
- `aidb_mcp/session/manager.py` - Session management

**API:**

- `aidb/api/api.py` - DebugAPI
- `aidb/api/session_builder.py` - SessionBuilder
- `aidb/api/introspection/` - State operations
- `aidb/api/orchestration/` - Control operations
