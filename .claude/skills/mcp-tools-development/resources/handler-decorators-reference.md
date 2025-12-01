# Handler Decorators Reference

**Purpose:** Complete reference for all handler decorators used in AIDB MCP tools.

**See also:** [tool-architecture.md](tool-architecture.md) for overall architecture and tool creation guide.

______________________________________________________________________

## Overview

Decorators provide cross-cutting functionality for MCP tool handlers, including:

- Execution context capture (location, state, variable tracking)
- Thread safety for concurrent access
- Session validation and API injection
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

   - `_api`: Debug API instance
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
    api = args.get("_api")

    # Perform operation
    await api.orchestration.continue_execution()

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
    api = args.get("_api")

    # Perform step
    await api.orchestration.step_over()

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
    api = args.get("_api")
    target_line = args.get(ParamName.LINE)

    # Run until target line
    await api.orchestration.run_until_line(target_line)

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
    api = args.get("_api")
    context = args.get("_context")

    # Safe concurrent access to context
    result = await api.introspection.evaluate(expression)

    return InspectResponse(
        summary="Evaluated expression",
        data={"result": result},
    ).to_mcp_response()
```

______________________________________________________________________

## @require_initialized_session

Validates session exists and is active, injects API and context.

**Source:** `src/aidb_mcp/core/decorator_primitives.py`

### Signature

```python
@require_initialized_session
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    # Session is guaranteed to exist and be active
    api = args.get("_api")  # Injected
    context = args.get("_context")  # Injected
    session_id = args.get("_session_id")  # Injected
    pass
```

### What It Does

1. Checks if session exists
1. Validates session is active (not stopped/terminated)
1. Injects `_api`, `_context`, `_session_id` into args
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
    api = args.get("_api")  # Guaranteed to exist
    context = args.get("_context")  # Guaranteed to exist
    session_id = args.get("_session_id")  # Guaranteed to exist

    action = args.get(ParamName.ACTION)

    if action == "set":
        await api.orchestration.set_breakpoint(...)

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

## @timed

Tracks operation performance and token estimates.

**Source:** `src/aidb_mcp/core/performance.py`

### Signature

```python
@timed
async def your_operation(api, *args, **kwargs) -> Any:
    result = await api.introspection.locals()
    return result
```

### What It Does

1. Records operation start time
1. Executes operation
1. Records end time and duration
1. Logs performance metrics
1. Tracks token estimates if response is dict
1. Adds performance data to structured logs

### When to Use

**✅ Use when:**

- All operations that call Debug API
- Operations where performance matters
- Operations you want to monitor/optimize
- Any operation that might be slow

**❌ Don't use when:**

- Operation is trivial (\<1ms)
- Already wrapped by higher-level timer
- Performance tracking not needed

### Example

```python
@timed
async def inspect_locals(api) -> dict[str, Any]:
    """Get local variables with performance tracking."""
    result = await api.introspection.locals()
    return result

# Logs will include:
# - operation_name: "inspect_locals"
# - duration_ms: 42.3
# - estimated_tokens: 1500 (if result is dict)
```

### Logged Metrics

The decorator logs the following to structured logs:

- `operation_name`: Function name
- `duration_ms`: Execution time in milliseconds
- `estimated_tokens`: Rough token count (if result is dict)
- `success`: Boolean indicating if operation succeeded
- `error`: Error message (if operation failed)

______________________________________________________________________

## Decorator Composition

Decorators can be composed for complex functionality. Order matters!

### Composition Pattern

```python
@with_thread_safety              # 1. Outermost: Thread safety
@require_initialized_session     # 2. Middle: Session validation
@with_execution_context(...)     # 3. Innermost: Context capture
async def handle_complex_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Complex handler with full decorator stack."""
    # This handler:
    # 1. Has thread-safe access to context
    # 2. Requires active session (API injected)
    # 3. Tracks execution context and variable changes
    pass
```

### Order Explanation

**Execution flow (outer → inner):**

1. `@with_thread_safety` - Acquire lock
1. `@require_initialized_session` - Validate session, inject API
1. `@with_execution_context` - Capture context, call handler
1. Handler executes
1. `@with_execution_context` - Add context to response
1. `@require_initialized_session` - (no action on return)
1. `@with_thread_safety` - Release lock

**Why this order:**

- Thread safety must be outermost (acquire lock before any access)
- Session validation must happen before context capture
- Execution context should be innermost (closest to handler logic)

### Common Patterns

**Pattern 1: Execution Control Tool**

```python
@with_thread_safety
@require_initialized_session
@with_execution_context(track_variables=True)
async def handle_step(args: dict[str, Any]) -> dict[str, Any]:
    """Step with variable tracking."""
    pass
```

**Pattern 2: Read-Only Inspection**

```python
@with_thread_safety
@require_initialized_session
async def handle_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """Inspect without context capture."""
    pass
```

**Pattern 3: Session Management (No Session Required)**

```python
@with_thread_safety
async def handle_start_session(args: dict[str, Any]) -> dict[str, Any]:
    """Start session - no active session required."""
    pass
```

### Advanced Composition

**Conditional context capture:**

```python
@with_thread_safety
@require_initialized_session
async def handle_conditional(args: dict[str, Any]) -> dict[str, Any]:
    """Handler with conditional context capture."""
    action = args.get(ParamName.ACTION)

    # Manually capture context only if needed
    if action in ["step", "continue"]:
        # Capture context
        from aidb_mcp.core.decorators import capture_execution_context
        context_data = await capture_execution_context(api, track_variables=True)
        # Add to response...

    return response
```

______________________________________________________________________

## Best Practices

### Decorator Selection Checklist

**For execution control tools (step, continue, run):**

```python
@with_thread_safety
@require_initialized_session
@with_execution_context(track_variables=True)
```

**For inspection tools (evaluate, locals, stack):**

```python
@with_thread_safety
@require_initialized_session
@with_execution_context()  # or no decorator if no state change
```

**For breakpoint management:**

```python
@with_thread_safety
@require_initialized_session
@with_execution_context(include_after=True)
```

**For session management:**

```python
@with_thread_safety  # No session requirement
```

### Common Mistakes

**❌ Wrong order:**

```python
@require_initialized_session  # Wrong: session check before thread safety
@with_thread_safety
async def bad_handler(args): pass
```

**❌ Unnecessary context tracking:**

```python
@with_execution_context(track_variables=True)  # Expensive, not needed
async def list_sessions(args): pass
```

**❌ Missing thread safety:**

```python
@require_initialized_session  # Missing thread safety
async def risky_handler(args): pass
```

**✅ Correct patterns:**

```python
@with_thread_safety
@require_initialized_session
@with_execution_context(track_variables=False)  # Only when needed
async def good_handler(args): pass
```

### Performance Considerations

**Variable tracking is expensive:**

- Only use `track_variables=True` when agent needs to see changes
- Typical tools that need it: step, continue, run_until
- Tools that don't: breakpoint set/remove, evaluate, locals

**Context capture overhead:**

- `include_after=True`: ~10-50ms (reads current state)
- `track_variables=True`: +100-500ms (compares all variables)
- Consider disabling for high-frequency operations

**Thread safety overhead:**

- Lock acquisition: ~1-5ms (negligible for most operations)
- Always prefer safety over minor performance gain

______________________________________________________________________

## Related Files

**Decorator Implementation:**

- `src/aidb_mcp/core/decorators.py` - Main decorators
- `src/aidb_mcp/core/decorator_primitives.py` - Low-level decorators
- `src/aidb_mcp/core/performance.py` - Performance tracking

**Usage Examples:**

- `src/aidb_mcp/handlers/execution/` - Execution control handlers
- `src/aidb_mcp/handlers/inspection/` - Inspection handlers
- `src/aidb_mcp/handlers/session/` - Session management handlers

**Architecture:**

- See [tool-architecture.md](tool-architecture.md) for overall tool architecture
