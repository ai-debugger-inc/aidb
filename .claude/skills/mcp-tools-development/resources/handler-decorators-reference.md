# Handler Decorators Reference

**Purpose:** Complete reference for all handler decorators used in AIDB MCP tools.

**See also:** [tool-architecture.md](tool-architecture.md) for overall architecture and tool creation guide.

______________________________________________________________________

## Overview

Decorators provide cross-cutting functionality for MCP tool handlers, including:

- Execution context capture (location, state, variable tracking)
- Thread safety for concurrent access
- Session validation and service injection
- Performance monitoring

**Location:** `src/aidb_mcp/core/decorators.py` and `src/aidb_mcp/core/decorator_primitives.py`

______________________________________________________________________

## @with_execution_context

Automatically captures debugging context and adds to response.

**Source:** `src/aidb_mcp/core/decorators.py`

### Signature

```python
@with_execution_context(
    include_before=False,      # Capture context before operation
    include_after=True,        # Capture context after operation
    track_variables=False,     # Track variable changes
    record_history=True,       # Record in execution history
    standardize_response=True, # Apply response standardization
)
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Handler logic
    pass
```

### What It Does

1. **Injects parameters** into args:

   - `_service`: DebugService instance (for operations)
   - `_context`: Session context (MCPSessionContext)
   - `_session_id`: Active session ID

1. **Captures execution context** (location, state) before/after operation

1. **Tracks variable changes** if `track_variables=True`

1. **Records operation** in execution history

1. **Standardizes response format** using response deduplicator

1. **Adds execution context** to response data

### Parameters

**include_before** (bool, default=False)

- Capture execution state BEFORE operation
- Use when you need to show "before" snapshot
- Adds `before_context` to response data

**include_after** (bool, default=True)

- Capture execution state AFTER operation
- Use for most operations to show current state
- Adds execution state fields to response data

**track_variables** (bool, default=False)

- Track variable changes between before/after
- Expensive operation - use only when needed
- Adds `changed_variables` to response data
- Requires both `include_before=True` and `include_after=True`

**record_history** (bool, default=True)

- Record operation in execution history
- Enables `aidb.context` tool to show recent operations
- Disable for read-only operations

**standardize_response** (bool, default=True)

- Apply response deduplication and formatting
- Remove redundant fields
- Should almost always be True

### When to Use

**✅ Use when:**

- Tools that modify execution state (step, continue, breakpoint)
- Tools that need current location/state context
- Tools where agents need to know "what changed"
- Any execution control or inspection operation

**❌ Don't use when:**

- Session management tools (start, stop)
- Adapter installation tools
- Tools that don't interact with debugging session

### Example: Basic Usage

```python
@with_execution_context()
async def handle_continue(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("_service")

    # Perform operation using DebugService
    thread_id = await service.execution.get_current_thread_id()
    request = ContinueRequest(seq=0, arguments=ContinueArguments(threadId=thread_id))
    await service.execution.continue_(request, wait_for_stop=True)

    # Response automatically includes current location and state
    return ContinueResponse(
        summary="Continued execution",
        data={"status": "running"},
    ).to_mcp_response()
```

### Example: Variable Tracking

```python
@with_execution_context(track_variables=True)
async def handle_step(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("_service")

    # Perform step using DebugService
    thread_id = await service.stepping.get_current_thread_id()
    await service.stepping.step_over(thread_id)

    # Response automatically includes:
    # - Current location
    # - Execution state
    # - Variable changes (because track_variables=True)
    return StepResponse(
        summary="Stepped to next line",
        data={},
    ).to_mcp_response()
```

### Example: Before and After Context

```python
@with_execution_context(include_before=True, include_after=True)
async def handle_run_until(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("_service")
    target_line = args.get(ParamName.LINE)

    # Run until target line using temporary breakpoint
    # (See run_until handler for full implementation)
    await service.breakpoints.set(...)
    await service.execution.continue_(...)

    # Response includes both before and after snapshots
    return RunUntilResponse(
        summary=f"Ran until line {target_line}",
        data={},
    ).to_mcp_response()
```

### Response Data Additions

The decorator adds the following fields to response data:

**With include_after=True (default):**

- `execution_state`: Current execution status
- `location`: Current file:line
- `code_snapshot`: Formatted code context
- `stop_reason`: Why execution stopped (if applicable)

**With include_before=True:**

- `before_context`: Execution state before operation

**With track_variables=True:**

- `changed_variables`: Dict of variables that changed
- Format: `{"var_name": {"old": "value1", "new": "value2"}}`

______________________________________________________________________

## @with_thread_safety

Ensures thread-safe access to shared resources.

**Source:** `src/aidb_mcp/core/decorator_primitives.py`

### Signature

```python
@with_thread_safety
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Thread-safe access to context
    pass
```

### What It Does

1. Acquires lock before accessing session context
1. Ensures serialized access to shared state
1. Releases lock after operation (even on exception)

### When to Use

**✅ Use when:**

- Tools that read/write session context
- Tools that access shared state
- Any tool that could have concurrent calls
- Most tools should have this for safety

**❌ Don't use when:**

- Tool is guaranteed to be single-threaded
- Performance is critical and concurrency is impossible

### Example

```python
@with_thread_safety
@require_initialized_session
async def handle_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """Thread-safe inspection handler."""
    service = args.get("_service")
    context = args.get("_context")

    # Safe concurrent access to context
    result = await service.variables.evaluate(expression)

    return InspectResponse(
        summary="Evaluated expression",
        data={"result": result},
    ).to_mcp_response()
```

______________________________________________________________________

## @require_initialized_session

Validates session exists and is active, injects service and context.

**Source:** `src/aidb_mcp/core/decorator_primitives.py`

### Signature

```python
@require_initialized_session
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Session is guaranteed to exist and be active
    service = args.get("_service")  # Injected
    context = args.get("_context")  # Injected
    session_id = args.get("_session_id")  # Injected
    pass
```

### What It Does

1. Checks if session exists
1. Validates session is active (not stopped/terminated)
1. Injects `_service`, `_context`, `_session_id` into args
1. Returns error response if session not found/inactive

### When to Use

**✅ Use when:**

- Any tool that requires an active debugging session
- Tools that interact with Debug API
- Most execution and inspection tools

**❌ Don't use when:**

- Session management tools (start session, list sessions)
- Adapter installation tools
- Tools that work without active session

### Example

```python
@with_thread_safety
@require_initialized_session
async def handle_breakpoint(args: dict[str, Any]) -> dict[str, Any]:
    """Breakpoint handler requiring active session."""
    service = args.get("_service")  # Guaranteed to exist
    context = args.get("_context")  # Guaranteed to exist
    session_id = args.get("_session_id")  # Guaranteed to exist

    action = args.get(ParamName.ACTION)

    if action == "set":
        request = SetBreakpointsRequest(...)
        await service.breakpoints.set(request)

    return BreakpointResponse(
        summary="Breakpoint set",
        data={},
    ).to_mcp_response()
```

### Error Response

If session is not found or inactive, decorator returns:

```python
{
    "success": False,
    "summary": "No active session found",
    "error_code": "AIDB_SESSION_NOT_FOUND",
    "error_message": "Please start a session first using aidb.session with action='start'",
}
```

______________________________________________________________________

## Additional Resources

For decorator composition patterns, best practices, and performance considerations:

- **[handler-composition-patterns.md](handler-composition-patterns.md)** - @timed decorator, composition order, best practices

**Decorator Implementation:**

- `src/aidb_mcp/core/decorators.py` - Main decorators
- `src/aidb_mcp/core/decorator_primitives.py` - Low-level decorators
- `src/aidb_mcp/core/performance.py` - Performance tracking

**Architecture:**

- See [tool-architecture.md](tool-architecture.md) for overall tool architecture
