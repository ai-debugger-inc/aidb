# Breakpoint Management and Timing

Complete guide to managing breakpoints across files, critical timing considerations, and language-specific quirks.

## Managing Breakpoints Across Files

AIDB session manages breakpoints per file:

```python
# Track breakpoints per file
breakpoint_map: dict[str, list[SourceBreakpoint]] = {}

async def add_breakpoint(file_path: str, line: int, condition: str | None = None):
    """Add a breakpoint to a file."""
    if file_path not in breakpoint_map:
        breakpoint_map[file_path] = []

    # Add new breakpoint
    bp = SourceBreakpoint(line=line, condition=condition)
    breakpoint_map[file_path].append(bp)

    # Send updated list to adapter
    seq = await client.get_next_seq()
    response = await client.send_request(
        SetBreakpointsRequest(
            seq=seq,
            arguments=SetBreakpointsArguments(
                source=Source(path=file_path),
                breakpoints=breakpoint_map[file_path]
            )
        )
    )

    return response.body.breakpoints[-1]  # Return newly added breakpoint

async def remove_breakpoint(file_path: str, line: int):
    """Remove a breakpoint from a file."""
    if file_path not in breakpoint_map:
        return

    # Remove breakpoint
    breakpoint_map[file_path] = [
        bp for bp in breakpoint_map[file_path]
        if bp.line != line
    ]

    # Send updated list to adapter
    seq = await client.get_next_seq()
    await client.send_request(
        SetBreakpointsRequest(
            seq=seq,
            arguments=SetBreakpointsArguments(
                source=Source(path=file_path),
                breakpoints=breakpoint_map[file_path]
            )
        )
    )

async def clear_all_breakpoints():
    """Clear all breakpoints in all files."""
    for file_path in list(breakpoint_map.keys()):
        seq = await client.get_next_seq()
        await client.send_request(
            SetBreakpointsRequest(
                seq=seq,
                arguments=SetBreakpointsArguments(
                    source=Source(path=file_path),
                    breakpoints=[]
                )
            )
        )
    breakpoint_map.clear()
```

## Breakpoint Timing

### CRITICAL: Race Conditions with Fast-Executing Programs

**Breakpoints MUST be set when starting a debug session, not after, to avoid race conditions.**

For programs that execute quickly (scripts, tests), code may run to completion before a post-launch breakpoint request arrives. This mirrors human debugging workflow: set breakpoints BEFORE clicking "Debug".

```python
# ✅ CORRECT: Set breakpoints at session start
await debug_interface.start_session(
    program=program,
    breakpoints=[{"file": str(program), "line": 10}]
)

# ❌ WRONG: Race condition - code may have already run
await debug_interface.start_session(program=program)
await debug_interface.set_breakpoint(file=str(program), line=10)  # Too late!
```

**Exception:** Long-running processes (servers, REPLs) where you attach - safe to set breakpoints after.

**Reliable pattern:** Once stopped at initial breakpoint, additional breakpoints can be set safely.

Reference: `src/tests/aidb_shared/e2e/test_complex_workflows.py:39-43`

### During Initialization

Breakpoints should be set **before** ConfigurationDone:

```python
# ✅ Correct: Set breakpoints during configuration
await client.send_request(initialize_request)
await client.wait_for_event("initialized")

# Set breakpoints here
await client.send_request(set_breakpoints_request)

await client.send_request(configuration_done_request)
await client.send_request(launch_request)
```

### After Launch (When Paused)

Breakpoints can be added/modified while stopped:

```python
# Program is paused at breakpoint
await client.wait_for_event(EventType.STOPPED.value)

# Add new breakpoint while paused - safe now
seq = await client.get_next_seq()
await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path="/path/to/file.py"),
            breakpoints=[SourceBreakpoint(line=50)]
        )
    )
)

# Continue execution
await client.send_request(continue_request)
```

## Language-Specific Quirks

### Python (debugpy)

- Source paths must be absolute
- Supports conditional breakpoints with Python expressions
- Log points support Python f-string-like syntax
- Breakpoint verification is immediate
- Supports `justMyCode` to skip library code

### JavaScript (vscode-js-debug)

- Source paths can be relative to workspace
- Source maps affect breakpoint verification
- May adjust breakpoints due to transpilation
- Async breakpoints require special handling
- Child sessions inherit parent breakpoints

### Java (java-debug-server)

- Requires class to be loaded for verification
- Breakpoints in unloaded classes remain unverified
- May need classpath for source resolution
- Function breakpoints use fully qualified method names
- Hot code reload can invalidate breakpoints

## Common Patterns

### Breakpoint Hit Workflow

```python
# Set breakpoint
seq = await client.get_next_seq()
bp_response = await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path=file_path),
            breakpoints=[SourceBreakpoint(line=10)]
        )
    )
)

# Launch program
await client.send_request(launch_request)

# Wait for breakpoint hit
stopped_event = await client.wait_for_event(EventType.STOPPED.value)

if stopped_event.body.reason == StopReason.BREAKPOINT.value:
    ctx.debug("Hit breakpoint!")
    # Inspect state, then continue
    await client.send_request(continue_request)
```

### Conditional Debugging

```python
# Set conditional breakpoint
breakpoint = SourceBreakpoint(
    line=25,
    condition="error_count > threshold"
)

# When hit, condition was true
stopped_event = await client.wait_for_event(EventType.STOPPED.value)

# Evaluate to see actual values
seq = await client.get_next_seq()
eval_response = await client.send_request(
    EvaluateRequest(
        seq=seq,
        arguments=EvaluateArguments(
            expression="error_count",
            frameId=frame_id
        )
    )
)
ctx.debug(f"error_count = {eval_response.body.result}")
```

## Best Practices

### 1. Always Track Breakpoint State

Maintain a map of all breakpoints per file to correctly handle additions and removals.

```python
# Track state
breakpoint_map: dict[str, list[SourceBreakpoint]] = {}

# When adding, include existing breakpoints
breakpoint_map[file].append(new_breakpoint)
await set_breakpoints(file, breakpoint_map[file])
```

### 2. Verify Breakpoint Success

Always check verification status and messages:

```python
response = await client.send_request(set_breakpoints_request)

for bp in response.body.breakpoints:
    if not bp.verified:
        ctx.warning(f"Breakpoint not verified: {bp.message}")
```

### 3. Use Absolute Paths

Most adapters work more reliably with absolute file paths:

```python
# ✅ Preferred
file_path = Path("/absolute/path/to/file.py")

# ⚠️ May cause issues
file_path = Path("relative/path/to/file.py")
```

### 4. Handle Breakpoint Events

Listen for breakpoint state changes:

```python
async for event in client.event_stream():
    if event.event == "breakpoint":
        bp = event.body.breakpoint
        ctx.debug(f"Breakpoint {bp.id} reason: {event.body.reason}")
```

### 5. Clear Breakpoints on Session End

Ensure cleanup when session ends:

```python
async def cleanup_session():
    # Clear all breakpoints
    for file_path in breakpoint_map.keys():
        await client.send_request(
            SetBreakpointsRequest(
                arguments=SetBreakpointsArguments(
                    source=Source(path=file_path),
                    breakpoints=[]
                )
            )
        )
    breakpoint_map.clear()
```

## Troubleshooting

### Breakpoints Not Hit

1. **Check verification**: Unverified breakpoints won't be hit
1. **Check timing**: For fast programs, set breakpoints at start
1. **Check file paths**: Use absolute paths
1. **Check source maps**: JavaScript/TypeScript transpilation issues

### Breakpoints Not Verified

1. **Python**: Check file exists and path is absolute
1. **JavaScript**: Check source maps and transpilation
1. **Java**: Check class is loaded and classpath is correct
1. **All**: Check line is executable (not comment/blank line)

### Breakpoints Disappear

1. **Check adapter events**: Listen for breakpoint events
1. **Check hot reload**: Code changes can invalidate breakpoints
1. **Check session state**: Breakpoints cleared on session end

## Reference

For working examples, see:

- `src/aidb/session/session_breakpoints.py` - Breakpoint management implementation
- Framework tests:
  - `src/tests/frameworks/python/pytest/e2e/test_pytest_debugging.py`
  - `src/tests/frameworks/javascript/jest/e2e/test_jest_debugging.py`
  - `src/tests/frameworks/java/junit/e2e/test_junit_debugging.py`
