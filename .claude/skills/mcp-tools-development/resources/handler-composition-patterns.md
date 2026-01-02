# Handler Composition Patterns

**Purpose:** Best practices for composing handler decorators and performance optimization.

**See also:** [handler-decorators-reference.md](handler-decorators-reference.md) for individual decorator documentation.

______________________________________________________________________

## @timed

Tracks operation performance and token estimates.

**Source:** `src/aidb_mcp/core/performance.py`

### Signature

```python
@timed
async def your_operation(service, *args, **kwargs) -> Any:
    result = await service.variables.locals()
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

**Use when:**

- All operations that call Debug API
- Operations where performance matters
- Operations you want to monitor/optimize
- Any operation that might be slow

**Don't use when:**

- Operation is trivial (\<1ms)
- Already wrapped by higher-level timer
- Performance tracking not needed

### Example

```python
@timed
async def inspect_locals(service) -> dict[str, Any]:
    """Get local variables with performance tracking."""
    result = await service.variables.locals()
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

**Execution flow (outer to inner):**

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

**Wrong order:**

```python
@require_initialized_session  # Wrong: session check before thread safety
@with_thread_safety
async def bad_handler(args): pass
```

**Unnecessary context tracking:**

```python
@with_execution_context(track_variables=True)  # Expensive, not needed
async def list_sessions(args): pass
```

**Missing thread safety:**

```python
@require_initialized_session  # Missing thread safety
async def risky_handler(args): pass
```

**Correct patterns:**

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
