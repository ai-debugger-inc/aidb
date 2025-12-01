# DAP Initialization Sequence

This document details the initialization sequence required to establish a DAP debugging session in AIDB. Understanding this sequence is critical for implementing adapters and debugging connection issues.

## Overview

The DAP initialization sequence is a strict, ordered series of requests and events that must occur before debugging can begin. Violating this sequence results in protocol errors.

## Standard Initialization Flow

```
1. Client establishes TCP connection to adapter
2. Client → Initialize Request
3. Adapter ← Initialize Response (with capabilities)
4. Adapter ← Initialized Event
5. Client → SetBreakpoints Requests (optional, can send multiple)
6. Client → SetExceptionBreakpoints Request (optional)
7. Client → ConfigurationDone Request
8. Adapter ← ConfigurationDone Response
9. Client → Launch or Attach Request
10. Adapter ← Launch/Attach Response
11. [Debug session is now active]
```

### Critical Rules

1. **No requests before Initialize response**: Client must wait for InitializeResponse before sending any other requests
1. **Wait for Initialized event**: After InitializeResponse, wait for InitializedEvent before sending configuration requests
1. **ConfigurationDone is the gate**: No Launch/Attach until after ConfigurationDone
1. **Order matters**: Initialize → (optional configs) → ConfigurationDone → Launch/Attach

## Initialize Request

The Initialize request is the first message sent by the client. It informs the adapter of client capabilities and identifies the client.

### Request Structure

```python
from aidb.dap.protocol import InitializeRequest
from aidb.dap.protocol.bodies import InitializeRequestArguments

seq = await client.get_next_seq()
request = InitializeRequest(
    seq=seq,
    arguments=InitializeRequestArguments(
        clientID="aidb",
        clientName="AI Debugger",
        adapterID="python",  # or "javascript", "java"
        locale="en-US",
        linesStartAt1=True,
        columnsStartAt1=True,
        pathFormat="path",
        supportsVariableType=True,
        supportsVariablePaging=False,
        supportsRunInTerminalRequest=False,
        supportsMemoryReferences=False,
        supportsProgressReporting=False,
        supportsInvalidatedEvent=False,
        supportsMemoryEvent=False,
        supportsArgsCanBeInterpretedByShell=False,
        supportsStartDebuggingRequest=True,  # For child sessions
    )
)

response = await client.send_request(request)
```

### Key Parameters

- `clientID`: Identifies the client (e.g., "aidb")
- `adapterID`: Identifies the target adapter ("python", "javascript", "java")
- `linesStartAt1`, `columnsStartAt1`: Line/column numbering convention (AIDB uses 1-based)
- `pathFormat`: How paths are represented ("path" for absolute paths)
- `supportsStartDebuggingRequest`: Required for JavaScript child session support

### Initialize Response

The response contains adapter capabilities that inform the client what features are supported:

```python
from aidb.dap.protocol.types import Capabilities

# Response body is Capabilities object
capabilities = response.body

# Check for specific capabilities
if capabilities.supportsConfigurationDoneRequest:
    # Adapter requires ConfigurationDone
    pass

if capabilities.supportsConditionalBreakpoints:
    # Can use conditional breakpoints
    pass

if capabilities.supportsSetVariable:
    # Can modify variable values
    pass
```

### Common Capabilities

```python
# Python (debugpy)
{
    "supportsConfigurationDoneRequest": True,
    "supportsConditionalBreakpoints": True,
    "supportsHitConditionalBreakpoints": True,
    "supportsSetVariable": True,
    "supportsSetExpression": True,
    "supportsEvaluateForHovers": True,
    "supportsLogPoints": True,
    "supportsExceptionOptions": True,
    "supportsExceptionInfoRequest": True,
    "supportTerminateDebuggee": True,
    "supportsDelayedStackTraceLoading": True,
    "supportsCompletionsRequest": True,
}

# JavaScript (vscode-js-debug)
{
    "supportsConfigurationDoneRequest": True,
    "supportsConditionalBreakpoints": True,
    "supportsRestartFrame": True,
    "supportsStepBack": False,
    "supportsSetVariable": True,
    "supportsCompletionsRequest": True,
    "supportsBreakpointLocationsRequest": True,
    "supportsClipboardContext": True,
}

# Java (java-debug-server)
{
    "supportsConfigurationDoneRequest": True,
    "supportsConditionalBreakpoints": True,
    "supportsHitConditionalBreakpoints": True,
    "supportsLogPoints": True,
    "supportsSetVariable": True,
    "supportsStepInTargetsRequest": True,
}
```

## Initialized Event

After the Initialize response, the adapter sends an Initialized event to signal it's ready for configuration requests.

```python
from aidb.dap.client.constants import EventType

# Wait for the event
await client.wait_for_event("initialized")

# Or subscribe to the event
async def handle_initialized(event):
    ctx.debug("Adapter initialized, ready for configuration")

subscription_id = await client.events.subscribe_to_event(
    "initialized",
    handle_initialized
)
```

**Important**: Do NOT send SetBreakpoints or other configuration requests before this event arrives.

## Configuration Phase

Between Initialized event and ConfigurationDone, the client can send configuration requests:

### Setting Breakpoints

```python
from aidb.dap.protocol import SetBreakpointsRequest
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.dap.protocol.bodies import SetBreakpointsArguments

seq = await client.get_next_seq()
response = await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path="/absolute/path/to/file.py"),
            breakpoints=[
                SourceBreakpoint(line=10),
                SourceBreakpoint(line=20, condition="x > 5"),
            ]
        )
    )
)

# Check breakpoint verification
for bp in response.body.breakpoints:
    if bp.verified:
        ctx.debug(f"Breakpoint verified at line {bp.line}")
    else:
        ctx.warning(f"Breakpoint NOT verified: {bp.message}")
```

### Setting Exception Breakpoints

```python
from aidb.dap.protocol import SetExceptionBreakpointsRequest
from aidb.dap.protocol.bodies import SetExceptionBreakpointsArguments

seq = await client.get_next_seq()
await client.send_request(
    SetExceptionBreakpointsRequest(
        seq=seq,
        arguments=SetExceptionBreakpointsArguments(
            filters=["raised", "uncaught"]  # Adapter-specific
        )
    )
)
```

## Configuration Done

After all configuration requests, send ConfigurationDone to signal readiness:

```python
from aidb.dap.protocol import ConfigurationDoneRequest
from aidb.dap.protocol.bodies import ConfigurationDoneArguments

seq = await client.get_next_seq()
response = await client.send_request(
    ConfigurationDoneRequest(
        seq=seq,
        arguments=ConfigurationDoneArguments()
    )
)

# Response is just acknowledgement (no body)
if response.success:
    ctx.debug("Configuration complete")
```

**Critical**: Do NOT send Launch or Attach requests before ConfigurationDone completes.

## Launch vs Attach

After ConfigurationDone, choose either Launch or Attach. Note that launch/attach arguments are implementation-specific dictionaries obtained from adapters.

### Launch Request

```python
from aidb.dap.protocol import LaunchRequest

# Get language-specific launch configuration from adapter
launch_config = adapter.get_launch_configuration()

seq = await client.get_next_seq()
response = await client.send_request(
    LaunchRequest(seq=seq, arguments=launch_config)
)
```

### Attach Request

```python
from aidb.dap.protocol import AttachRequest

# Attach configs are also adapter-specific dictionaries
attach_config = {
    "type": "python",  # or "node", "java"
    "connect": {"host": "localhost", "port": 5678}
}

seq = await client.get_next_seq()
response = await client.send_request(
    AttachRequest(seq=seq, arguments=attach_config)
)
```

## Language-Specific Launch Parameters

Launch configurations are adapter-specific dictionaries. Each adapter provides a `get_launch_configuration()` method that returns the appropriate configuration.

**Python (debugpy)** - Common fields: `program`, `module`, `args`, `cwd`, `env`, `console`, `justMyCode`, `django`, `flask`, `jinja`, `subProcess`, `showReturnValue`, `redirectOutput`

**JavaScript (vscode-js-debug)** - Common fields: `program`, `runtimeExecutable`, `runtimeArgs`, `args`, `cwd`, `env`, `console`, `sourceMaps`, `outFiles`, `outputCapture`, `showAsyncStacks`

**Java (java-debug-server)** - Common fields: `mainClass`, `projectName`, `cwd`, `env`, `args`, `vmArgs`, `classPaths`, `modulePaths`, `console`

See adapter implementations in `src/aidb/adapters/lang/*/` for complete configuration options.

## Complete Initialization Example

```python
from aidb.dap.protocol import (
    InitializeRequest,
    SetBreakpointsRequest,
    ConfigurationDoneRequest,
    LaunchRequest,
)
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.dap.protocol.bodies import (
    InitializeRequestArguments,
    SetBreakpointsArguments,
    ConfigurationDoneArguments,
)

async def initialize_debug_session(client, adapter, program_path, breakpoint_lines):
    # 1. Initialize
    seq = await client.get_next_seq()
    init_response = await client.send_request(
        InitializeRequest(
            seq=seq,
            arguments=InitializeRequestArguments(
                clientID="aidb",
                adapterID="python",
                linesStartAt1=True,
                columnsStartAt1=True,
            )
        )
    )
    ctx.debug(f"Adapter capabilities: {init_response.body}")

    # 2. Wait for initialized event
    await client.wait_for_event("initialized")
    ctx.debug("Adapter initialized")

    # 3. Set breakpoints
    seq = await client.get_next_seq()
    bp_response = await client.send_request(
        SetBreakpointsRequest(
            seq=seq,
            arguments=SetBreakpointsArguments(
                source=Source(path=program_path),
                breakpoints=[
                    SourceBreakpoint(line=line)
                    for line in breakpoint_lines
                ]
            )
        )
    )
    ctx.debug(f"Set {len(bp_response.body.breakpoints)} breakpoints")

    # 4. Configuration done
    seq = await client.get_next_seq()
    await client.send_request(
        ConfigurationDoneRequest(
            seq=seq,
            arguments=ConfigurationDoneArguments()
        )
    )
    ctx.debug("Configuration complete")

    # 5. Launch with adapter-provided configuration
    launch_config = adapter.get_launch_configuration()
    seq = await client.get_next_seq()
    launch_response = await client.send_request(
        LaunchRequest(seq=seq, arguments=launch_config)
    )
    ctx.debug("Program launched")

    return launch_response
```

## Handling Initialization Errors

### Common Issues

1. **Timeout waiting for Initialized event**

   - Adapter may have crashed during startup
   - Check adapter process is running
   - Review adapter logs

1. **ConfigurationDone fails**

   - May have sent Launch/Attach too early
   - Ensure ConfigurationDone completes before Launch/Attach

1. **Breakpoints not verified**

   - Source path may be incorrect
   - File may not exist or not be loadable
   - Check `bp.message` in response for details

1. **Launch/Attach fails**

   - Missing required parameters for language
   - Check launch configuration is correct
   - Review error message in response

### Error Handling Pattern

```python
async def safe_initialize(client, launch_config):
    try:
        # Initialize
        seq = await client.get_next_seq()
        init_response = await client.send_request(
            InitializeRequest(seq=seq, arguments=init_args),
            timeout=5.0
        )
        if not init_response.success:
            raise DebugAdapterError(f"Initialize failed: {init_response.message}")

        # Wait for initialized event with timeout
        initialized_event = await asyncio.wait_for(
            client.wait_for_event("initialized"),
            timeout=5.0
        )

        # Configuration
        seq = await client.get_next_seq()
        config_response = await client.send_request(
            ConfigurationDoneRequest(seq=seq, arguments=ConfigurationDoneArguments()),
            timeout=5.0
        )
        if not config_response.success:
            raise DebugAdapterError(f"ConfigurationDone failed: {config_response.message}")

        # Launch
        seq = await client.get_next_seq()
        launch_response = await client.send_request(
            LaunchRequest(seq=seq, arguments=launch_args),
            timeout=10.0
        )
        if not launch_response.success:
            raise DebugAdapterError(f"Launch failed: {launch_response.message}")

        return launch_response

    except asyncio.TimeoutError as e:
        ctx.error("Initialization timed out")
        raise DebugConnectionError("Failed to initialize debug adapter") from e
    except Exception as e:
        ctx.error(f"Initialization failed: {e}")
        raise
```

## Adapter-Specific Initialization Quirks

### Python (debugpy)

- Responds quickly to Initialize
- Initialized event arrives immediately
- Breakpoint verification happens during SetBreakpoints
- Launch may delay if program imports take time

### JavaScript (vscode-js-debug)

- May take longer to initialize (loading source maps)
- Initialized event may be delayed
- Child sessions require `supportsStartDebuggingRequest` capability
- Source maps affect breakpoint verification timing

### Java (java-debug-server)

- Initialization can be slow (JVM startup, JDT LS connection)
- May require classpath resolution before breakpoint verification
- Launch delay depends on JVM startup time
- Attach requires target JVM running with debug agent

## Session State Tracking

AIDB tracks session state using boolean flags in the `SessionState` dataclass (`src/aidb/dap/client/state.py`):

```python
# Session state transitions
client.state.connected = True          # After connect()
client.state.initialized = True        # After Initialize response
client.state.ready_for_configuration = True  # After Initialized event
client.state.configuration_done = True # After ConfigurationDone
client.state.session_established = True # After Launch/Attach

# Check state before operations
if not client.state.connected:
    raise DebugConnectionError("Not connected")

if not client.state.configuration_done:
    ctx.warning("Configuration not complete")
```

## Summary

Key points for initialization:

1. **Strict ordering**: Initialize → Initialized event → (configs) → ConfigurationDone → Launch/Attach
1. **Use protocol types**: Always import from `aidb.dap.protocol`
1. **Check capabilities**: Adapter capabilities determine available features
1. **Handle errors**: Timeout and error handling is critical
1. **Language differences**: Launch parameters vary by language
1. **State tracking**: Track session state to prevent protocol violations

Refer to adapter implementations in `src/aidb/adapters/lang/*/` for real-world examples.
