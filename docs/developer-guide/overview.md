# AI Debugger — Developer Overview

This repository provides a lightweight, language-agnostic Python API that lets
AI systems programmatically control and introspect live debugging sessions. By
mirroring familiar human debugging workflows (set/verify breakpoints, step,
inspect variables/stack, evaluate expressions), it enables building
self-correcting, reasoning-capable agents and intelligent developer tools. The
project is designed to be minimal in dependencies and portable across macOS,
Linux, and WSL.

## Architecture (at a glance)

The system centers around the Debug Adapter Protocol (DAP) and a session
orchestration layer that abstracts language/runtime specifics via pluggable
adapters.

### Detailed System Architecture

The following diagram illustrates the complete data flow from AI agents through the MCP layer, down to the debug adapter backends and target programs:

```mermaid
graph TB
    subgraph "Client Layer"
        Agent[AI Agent/Tool]
        PythonClient[Python Client]
    end

    subgraph "MCP Layer (aidb_mcp)"
        MCPServer[AidbMCPServer<br/>server/app.py]
        MCPTools[MCP Tools<br/>tools/definitions.py]
        MCPHandlers[Tool Handlers<br/>handlers/]

        MCPServer -->|list_tools| MCPTools
        MCPServer -->|call_tool| MCPHandlers
    end

    subgraph "AIDB API Layer (aidb.api)"
        DebugAPI[DebugAPI<br/>api/api.py]
        SessionManager[SessionManager<br/>api/session_manager.py]
        SessionBuilder[SessionBuilder<br/>api/session_builder.py]
        APIIntrospection[APIIntrospectionOperations]
        APIOrchestration[APIOrchestrationOperations]

        DebugAPI -->|manages| SessionManager
        DebugAPI -->|builds| SessionBuilder
        DebugAPI -->|delegates| APIIntrospection
        DebugAPI -->|delegates| APIOrchestration
    end

    subgraph "Session Layer (aidb.session)"
        Session[Session<br/>session/session_core.py]
        SessionState[SessionState<br/>session/state.py]
        SessionConnector[SessionConnector<br/>session/connector.py]
        SessionOps[SessionDebugOperations<br/>session/ops/]
        AdapterRegistry[AdapterRegistry<br/>session/adapter_registry.py]

        Session -->|manages| SessionState
        Session -->|connects via| SessionConnector
        Session -->|executes| SessionOps
        Session -->|selects from| AdapterRegistry
    end

    subgraph "Adapter Layer (aidb.adapters)"
        BaseAdapter[DebugAdapter<br/>adapters/base/adapter.py]
        PythonAdapter[PythonAdapter<br/>adapters/lang/python/python.py]
        JavaAdapter[JavaAdapter<br/>adapters/lang/java/java.py]
        JSAdapter[JavaScriptAdapter<br/>adapters/lang/javascript/javascript.py]

        AdapterRegistry -->|provides| BaseAdapter
        BaseAdapter -->|subclass| PythonAdapter
        BaseAdapter -->|subclass| JavaAdapter
        BaseAdapter -->|subclass| JSAdapter
    end

    subgraph "DAP Client Layer (aidb.dap.client)"
        DAPClient[DAPClient<br/>dap/client/client.py]
        Transport[DAPTransport<br/>dap/client/transport.py]
        RequestHandler[RequestHandler<br/>dap/client/request_handler.py]
        EventProcessor[EventProcessor<br/>dap/client/events.py]
        MessageRouter[MessageRouter<br/>dap/client/message_router.py]

        DAPClient -->|sends via| Transport
        DAPClient -->|processes requests| RequestHandler
        DAPClient -->|handles events| EventProcessor
        DAPClient -->|routes messages| MessageRouter
    end

    subgraph "Debug Adapter Backend Layer"
        Debugpy[debugpy<br/>Python Debug Adapter]
        JavaDebugServer[java-debug-server<br/>Java Debug Adapter]
        NodeDebugAdapter[vscode-js-debug<br/>JS/Node Debug Adapter]
    end

    subgraph "Target Program Layer"
        PythonDebuggee[Python Script/Module<br/>user_script.py]
        JavaDebuggee[Java Application<br/>MyApp.java]
        JSDebuggee[Node.js Application<br/>app.js]
    end

    %% Client to MCP Layer
    Agent -->|MCP Protocol| MCPServer
    PythonClient -->|Direct Import| DebugAPI

    %% MCP to API Layer
    MCPHandlers -->|calls| DebugAPI

    %% API to Session Layer
    SessionManager -->|creates/manages| Session
    SessionBuilder -->|builds| Session
    APIIntrospection -->|delegates to| SessionOps
    APIOrchestration -->|delegates to| SessionOps

    %% Session to Adapter Layer
    Session -->|uses| PythonAdapter
    Session -->|uses| JavaAdapter
    Session -->|uses| JSAdapter

    %% Adapter to DAP Client Layer
    PythonAdapter -->|owns| DAPClient
    JavaAdapter -->|owns| DAPClient
    JSAdapter -->|owns| DAPClient

    %% DAP Client to Debug Adapter Backend
    Transport -->|TCP Socket<br/>DAP Protocol| Debugpy
    Transport -->|TCP Socket<br/>DAP Protocol| JavaDebugServer
    Transport -->|TCP Socket<br/>DAP Protocol| NodeDebugAdapter

    %% Debug Adapter Backend to Debuggee
    Debugpy -->|Python Debugger API| PythonDebuggee
    JavaDebugServer -->|JDWP| JavaDebuggee
    NodeDebugAdapter -->|V8 Inspector Protocol| JSDebuggee

    %% Styling
    classDef mcpLayer fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef apiLayer fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef sessionLayer fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef adapterLayer fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef dapLayer fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef backendLayer fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef debuggeeLayer fill:#e0f2f1,stroke:#004d40,stroke-width:2px

    class MCPServer,MCPTools,MCPHandlers mcpLayer
    class DebugAPI,SessionManager,SessionBuilder,APIIntrospection,APIOrchestration apiLayer
    class Session,SessionState,SessionConnector,SessionOps,AdapterRegistry sessionLayer
    class BaseAdapter,PythonAdapter,JavaAdapter,JSAdapter adapterLayer
    class DAPClient,Transport,RequestHandler,EventProcessor,MessageRouter dapLayer
    class Debugpy,JavaDebugServer,NodeDebugAdapter backendLayer
    class PythonDebuggee,JavaDebuggee,JSDebuggee debuggeeLayer
```

**Key Architecture Components:**

1. **MCP Layer** (`aidb_mcp/`): Exposes AIDB capabilities via Model Context Protocol

   - `AidbMCPServer`: Main MCP server handling tool calls
   - Tool definitions and handlers bridge MCP to AIDB API

1. **AIDB API Layer** (`aidb/api/`): High-level Python API for debugging operations

   - `DebugAPI`: Main entry point with introspection/orchestration operations
   - `SessionManager`: Manages session lifecycle and registry
   - `SessionBuilder`: Constructs sessions with proper configuration

1. **Session Layer** (`aidb/session/`): Core session orchestration and state management

   - `Session`: Central orchestrator coordinating adapters and DAP clients
   - `SessionConnector`: Manages DAP connection lifecycle
   - `SessionDebugOperations`: Executes debug operations (breakpoints, stepping, evaluation)

1. **Adapter Layer** (`aidb/adapters/`): Language-specific debug adapter implementations

   - `PythonAdapter`: Launches/attaches debugpy, manages Python-specific configuration
   - `JavaAdapter`: Launches/attaches java-debug-server with JDWP
   - `JavaScriptAdapter`: Launches/attaches Node.js debug adapter

1. **DAP Client Layer** (`aidb/dap/client/`): Debug Adapter Protocol client implementation

   - `DAPClient`: Single request path for all DAP operations
   - `DAPTransport`: TCP socket communication with debug adapters
   - `EventProcessor`: Handles DAP events (stopped, breakpoint, output, etc.)
   - `RequestHandler`: Manages request/response lifecycle with futures

1. **Debug Adapter Backend Layer**: Language-specific debug servers (external)

   - `debugpy`: Microsoft's Python debug adapter implementing DAP
   - `java-debug-server`: Java debug adapter using JDWP
   - `node-debug2`: Node.js/JavaScript debug adapter using V8 Inspector Protocol

1. **Target Program Layer**: The actual programs being debugged

   - User's Python scripts, Java applications, or Node.js programs

**Data Flow Example (Setting a Breakpoint):**

1. AI Agent → MCP Server: `call_tool("debug_set_breakpoint")`
1. MCP Handler → DebugAPI: `api.orchestration.set_breakpoint()`
1. DebugAPI → Session: `session.set_breakpoint()`
1. Session → Adapter: `adapter.verify_breakpoint_location()`
1. Adapter → DAPClient: `dap_client.send_request(SetBreakpointsRequest)`
1. DAPClient → Transport: Serialize and send over TCP socket
1. Transport → debugpy: DAP protocol message
1. debugpy → Python Debuggee: Set actual breakpoint in interpreter
1. Response flows back up the stack with breakpoint verification

High-level flow:

- An agent/tool or Python client uses the AIDB API to create/manage sessions.
- A session selects a language adapter that knows how to launch/attach to the
  target program and speak DAP to its debug adapter (e.g., `debugpy` for
  Python).
- The DAP client manages requests/events and exposes a typed, ergonomic
  interface for stepping, breakpoints, inspection, and execution.
- Optional integration layers expose AIDB capabilities to non-Python clients
  (via MCP).
- A shared logging layer provides consistent, structured observability across
  all components.

Key packages (code roots under `src/`):

- `src/aidb/` — Core library: DAP protocol implementations, session
  orchestration, language adapters, high-level Python API.
- `src/aidb_mcp/` — MCP server and tools exposing AIDB capabilities over Model
  Context Protocol; CLI entrypoint `aidb-mcp`.
- `src/aidb_logging/` — Structured logging utilities and configuration used
  across components.

## Key Source Locations

| Package | Purpose |
|---------|---------|
| `src/aidb/` | Core library: DAP protocol, session orchestration, language adapters |
| `src/aidb/api/` | High-level Python API |
| `src/aidb/session/` | Session management and state |
| `src/aidb/adapters/` | Language-specific adapters (Python, JavaScript, Java) |
| `src/aidb/dap/` | DAP protocol client implementation |
| `src/aidb_mcp/` | MCP server exposing debugging tools |
| `src/aidb_cli/` | Developer CLI |
| `src/aidb_common/` | Shared utilities |
| `src/aidb_logging/` | Structured logging |
