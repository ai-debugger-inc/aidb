# Architectural Patterns & Resource Management

Core design patterns and resource lifecycle management for AIDB.

______________________________________________________________________

## Architectural Principles

### 1. Component Delegation (Not God Objects)

**Problem:** Monolithic classes become unmaintainable.

**Solution:** Delegate responsibilities to focused components with single responsibilities.

**Examples:**

- `Session` → `SessionState`, `SessionConnector`, `SessionDebugOperations`
- `DebugAdapter` → `ProcessManager`, `PortManager`, `LaunchOrchestrator`
- `DAPClient` → `Transport`, `RequestHandler`, `EventProcessor`

### 2. Language-Agnostic Design

Pluggable adapter architecture: abstract `DebugAdapter` base class, language adapters override abstract methods, common DAP client for all languages.

```python
# Same API for all languages
session = api.session_builder.python_module("script.py").build()
session = api.session_builder.javascript_file("app.js").build()
session = api.session_builder.java_class("Main").build()
```

### 3. Human-Cadence Debugging

Operations happen at human speed, not API speed:

- Breakpoints before execution (for fast programs)
- Inspection on paused programs only
- Stepping is sequential (one line at a time)

### 4. Single Request Path (DAP Client)

ALL requests through `DAPClient.send_request()`. Event handlers NEVER send requests. See [dap-client.md](dap-client.md).

### 5. Three-Tier Cleanup

Resources cleaned in reverse dependency order: DAP → Process → Port. See below.

______________________________________________________________________

## Resource Management

AIDB uses **defense-in-depth**: global registries + per-session managers + orphan cleanup.

### Global Process Registry

**File:** `src/aidb/resources/pids.py`

**Process Group Termination:** Debug adapters spawn child processes. Killing just the adapter PID leaves children orphaned. Process groups ensure ALL processes terminated together.

```python
# Two-phase termination
for pgid in self._process_groups.get(session_id, []):
    os.killpg(pgid, signal.SIGTERM)  # Graceful

for proc in processes:
    proc.terminate()  # SIGTERM
    await asyncio.wait_for(proc.wait(), timeout=5.0)
    # If timeout:
    proc.kill()  # SIGKILL
```

### Global Port Registry

**File:** `src/aidb/resources/ports.py`

**Cross-Process Coordination:** File-based locking (`fcntl.flock`) + socket reservation.

**Socket Reservation eliminates TOCTOU race:**

```python
# Without reservation (RACE):
if port_free():              # Process A checks
    # [Process B steals port here]
    bind(port)               # Process A fails!

# With reservation (SAFE):
sock = bind(port)            # Process A holds socket
# Process B cannot bind
adapter.bind(port)           # Process A releases, adapter binds
```

**Language-Specific Port Ranges:** Python (5678+), JavaScript (9229+), Java (5005+).

### Three-Tier Cleanup Strategy

**File:** `src/aidb/session/resource.py`

**Order is critical. Changing order causes port conflicts and orphaned processes.**

**Tier 1: DAP Disconnect**

- Send DAP `disconnect` request
- Allows adapter to gracefully shutdown
- Adapter terminates its own children

**Tier 2: Process Termination**

- SIGTERM to process groups
- SIGTERM → SIGKILL escalation for individuals
- Ensures resources freed

**Tier 3: Port Release**

- Close reserved sockets
- Update registries (in-process and cross-process)
- Ports available for reallocation

**Why This Order:**

- DAP first → Adapter cleans children gracefully
- Process second → Ensures port released at OS level
- Port third → Registry updated, port reusable

### Orphan Cleanup

**File:** `src/aidb/resources/orphan_cleanup.py`

Environment variable tagging for reliable detection:

```python
env["AIDB_OWNER"] = "aidb"
env["AIDB_SESSION_ID"] = session_id
env["AIDB_PROCESS_TYPE"] = "adapter"
```

**Orphan Criteria (ALL must be true):**

- `AIDB_OWNER == "aidb"`
- Session ID not in active sessions
- Age > 60s (race condition protection)
- Not pool resource

______________________________________________________________________

## Data Flow Summary

**Layer-by-Layer Transformations:**

1. **MCP → API** - JSON → Python args
1. **API → Session** - User params → Domain models
1. **Session → Adapter** - Models → Adapter config
1. **Adapter → DAP** - Config → Protocol requests
1. **DAP → Transport** - Typed → JSON bytes

**Key Flows:**

| Flow                | Layers | Notes                                                                |
| ------------------- | ------ | -------------------------------------------------------------------- |
| Session Start       | All 6  | Most complex: port allocation, process launch, DAP init, breakpoints |
| Stopped Event       | 5-1    | Adapter → Transport → Router → EventProcessor → State update         |
| Variable Inspection | 1-5    | Multiple DAP requests: threads, stack, scopes, variables             |
| Cleanup             | 3-tier | DAP disconnect → Process termination → Port release                  |

**Status Progression:** NOT_STARTED → INITIALIZING → CONNECTED → RUNNING → PAUSED ↔ RUNNING → TERMINATED

______________________________________________________________________

## Quick Reference

### Key Design Decisions

| Decision                | Why                                       |
| ----------------------- | ----------------------------------------- |
| Component Delegation    | Testability, maintainability, readability |
| Language-Agnostic API   | Same Python API for Python/JS/Java        |
| Human-Cadence Debugging | Matches real debugger usage               |
| Single Request Path     | Prevents race conditions, deadlocks       |
| Three-Tier Cleanup      | Defense-in-depth, prevents leaks          |
| Socket Reservation      | Eliminates TOCTOU races                   |
| Environment Tagging     | Reliable orphan detection                 |

### When to Apply

| Pattern              | Apply When                                   |
| -------------------- | -------------------------------------------- |
| Component Delegation | Class exceeds 300 lines                      |
| Language-Agnostic    | Adding new language support                  |
| Human-Cadence        | Documenting workflows, designing MCP tools   |
| Resource Lifecycle   | Creating new resource types, debugging leaks |
| Three-Tier Cleanup   | Modifying Session.stop(), cleanup logic      |

### Debugging Tips

- Enable trace logging: `AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1`
- Check session status: `session.status`
- Verify DAP connection: `session.dap.is_connected`
- Inspect breakpoints: `session.breakpoints`
- Check for orphans: `ps aux | grep debugpy`
- Check for port leaks: `lsof -i :PORT`
