# Session Layer Architecture

The session layer (`src/aidb/session/`) is the infrastructure hub of AIDB, managing debugging session lifecycle and coordinating language-specific adapters with DAP client connections.

**Related Skills:** `adapter-development` (adapter integration), `dap-protocol-guide` (DAP client interactions), `testing-strategy` (testing session lifecycle)

______________________________________________________________________

## Core Principle: Infrastructure Only

**Problem:** Monolithic session classes become unwieldy (1000+ lines) when mixing infrastructure with business logic.

**Solution:** `Session` is a thin infrastructure layer that delegates:

- **Infrastructure** (connection, state, resources) → Session components
- **Debugging operations** (step, continue, breakpoints) → Service layer (`src/aidb/service/`)

```python
class Session:
    def __init__(self, adapter, config):
        self._state = SessionState()
        self._connector = SessionConnector(self)
        self._resources = ResourceManager(config)
        # NOTE: No debug operations - those are in DebugService

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def dap(self) -> DAPClient:
        return self._connector.dap
```

______________________________________________________________________

## Components

### Session - Infrastructure Hub

**File:** `src/aidb/session/session_core.py`

Coordinates infrastructure components and provides unified interface. Does NOT implement debugging logic.

**Responsibilities:** Initialize components in correct order, expose properties for component access, provide lifecycle methods (`start()`, `cleanup()`), register with SessionRegistry.

### SessionState - Status Computation

**File:** `src/aidb/session/state.py`

Compute session status based on multiple state factors with precedence rules.

**Precedence Logic:**

1. If `self._error` is set → `SessionStatus.ERROR`
1. If not initialized → `SessionStatus.INITIALIZED`
1. If child session and stopped → `SessionStatus.STOPPED`
1. Evaluate DAP connection state
1. Evaluate adapter process state

**Key Pattern:** Status is COMPUTED, not stored. Every call to `get_status()` evaluates current conditions.

### SessionConnector - DAP Connection Lifecycle

**File:** `src/aidb/session/connector.py`

Manage DAP client connection lifecycle independently from session creation.

**Connection Flow:**

1. `session.connector.connect()` called
1. DAPClient created, transport started
1. DAP handshake: `initialize` request
1. Launch/attach request based on config
1. `configurationDone` request
1. `state.set_initialized()` called
1. Deferred event handlers registered

**Stub Events API:** Before DAP connection exists, `session.events.on()` stores handlers in queue. After connection, handlers registered with real DAPClient.

### InitializationMixin - DAP Sequence Handling

**File:** `src/aidb/session/ops/initialization.py`

Handles the complex DAP initialization sequence:

- `InitializationMixin` - DAP sequence: initialize → launch/attach → breakpoints → configurationDone

**Note:** Orchestration and introspection operations have moved to the Service layer (`src/aidb/service/`).

### SessionRegistry - Global Session Tracking

**File:** `src/aidb/session/registry.py`

Thread-safe global access to all active sessions using `threading.RLock` (reentrant for nested cleanup operations).

**Why Global Registry:** JavaScript/TypeScript creates child sessions for subprocesses that need to find their parent.

### ResourceManager - Three-Tier Cleanup

**File:** `src/aidb/session/resource.py`

Orchestrates three-tier cleanup strategy (DAP → processes → ports). See [patterns-and-resources.md](patterns-and-resources.md) for details.

### Parent-Child Sessions (JavaScript)

**Files:** `src/aidb/session/child_registry.py`, `src/aidb/adapters/lang/javascript/javascript.py`

JavaScript subprocess debugging creates child sessions that share parent's DAP client.

**Key Pattern:** Child sets `self._parent_session_id`, SessionConnector skips DAP client creation. Events routed by thread ID.

______________________________________________________________________

## Initialization Order (Critical)

Components initialize in specific order due to dependencies:

1. **SessionState** - No dependencies
1. **ResourceManager** - No dependencies
1. **SessionConnector** - Needs state for initialization status
1. **Adapter assignment** - Session holds adapter reference

______________________________________________________________________

## Design Decisions

### Infrastructure vs Operations

Session handles infrastructure (connection, state, resources). Debugging operations (step, continue, breakpoints, variables) live in the Service layer. This separation provides:

- Clear boundaries between infrastructure and business logic
- Stateless operations that are easier to test
- Clean MCP integration (handlers use DebugService)

### Thread-Safe Registries with RLock

Cleanup flow acquires lock to unregister session. During unregister, child cleanup may trigger, which also needs lock. RLock allows same thread to acquire again.

### Stub Events API for Deferred Connection

Adapters register event handlers during `start_session()`, but DAP connection doesn't exist yet. Stub API queues handlers until connection succeeds.

### Parent-Child DAP Client Sharing

DAP spec allows one connection per debug adapter instance. Node.js debugger handles all subprocesses on one connection, distinguishing by thread IDs.

______________________________________________________________________

## Quick Reference

### Where to Look

| Task                               | Location                                                            |
| ---------------------------------- | ------------------------------------------------------------------- |
| Adding a new session status        | `src/aidb/session/state.py` + `src/aidb/models/entities/session.py` |
| Debugging connection issues        | `src/aidb/session/connector.py`                                     |
| Adding a new debugging operation   | `src/aidb/service/{execution,breakpoints,variables,stack}/`         |
| Fixing resource leaks              | `src/aidb/session/resource.py`                                      |
| Working with parent-child sessions | `src/aidb/session/child_registry.py`                                |
| DAP initialization sequence        | `src/aidb/session/ops/initialization.py`                            |

### Common Mistakes

| Don't                                  | Why                                                           |
| -------------------------------------- | ------------------------------------------------------------- |
| Set status directly                    | Status is computed via `get_status()`, not stored             |
| Create multiple DAP clients            | One per debug adapter instance; child sessions share parent's |
| Access `session.dap` before connection | SessionConnector raises exception                             |
| Implement debug logic in Session       | Session is infrastructure; use DebugService for operations    |
| Skip adapter resource registration     | Cleanup can't release unregistered resources                  |

### Debugging Tips

- Enable logging: `AIDB_LOG_LEVEL=DEBUG`
- Check session state: `session.state.get_status()` and `session.state._error`
- Verify cleanup: Check for orphaned processes (`ps aux | grep debugpy`) and ports (`lsof -i :PORT`)
