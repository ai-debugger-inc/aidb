# DAP Breakpoint Operations

This document covers breakpoint operations in the Debug Adapter Protocol, including setting, verifying, and managing breakpoints across different languages.

## Overview

Breakpoints are the primary mechanism for pausing program execution at specific points. DAP supports multiple breakpoint types:

1. **Source Breakpoints** - Line-based breakpoints in source files (covered here)
1. **Function Breakpoints** - Break when entering a specific function
1. **Conditional Breakpoints** - Break only when condition is true
1. **Hit Condition Breakpoints** - Break after N hits
1. **Log Points** - Log a message without breaking
1. **Exception Breakpoints** - Break on thrown exceptions
1. **Data Breakpoints** - Break on memory/variable changes (limited support)
1. **Instruction Breakpoints** - Assembly-level breakpoints (advanced)

**For advanced breakpoint types**, see [Advanced Breakpoint Types](advanced-breakpoint-types.md).

**For breakpoint management and timing**, see [Breakpoint Management](breakpoint-management.md).

## Source Breakpoints

Source breakpoints are the most common type, set at specific lines in source files.

### Basic Source Breakpoint

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
                SourceBreakpoint(line=20),
            ]
        )
    )
)

# Check verification
for bp in response.body.breakpoints:
    if bp.verified:
        ctx.debug(f"Breakpoint set at line {bp.line}")
    else:
        ctx.warning(f"Breakpoint failed: {bp.message}")
```

### Conditional Breakpoint

Break only when a condition evaluates to true:

```python
from aidb.dap.protocol.types import SourceBreakpoint

breakpoint = SourceBreakpoint(
    line=15,
    condition="x > 5 and y < 10"  # Expression in target language syntax
)
```

**Language-specific condition syntax:**

```python
# Python
condition="len(items) > 0 and status == 'active'"

# JavaScript
condition="items.length > 0 && status === 'active'"

# Java
condition="items.size() > 0 && status.equals(\"active\")"
```

### Hit Condition Breakpoint

Break after the line has been hit N times:

```python
from aidb.dap.protocol.types import SourceBreakpoint

# Break on 5th hit
breakpoint = SourceBreakpoint(
    line=30,
    hitCondition="5"
)

# Break every 3rd hit
breakpoint = SourceBreakpoint(
    line=30,
    hitCondition="% 3"
)

# Break when hit count >= 10
breakpoint = SourceBreakpoint(
    line=30,
    hitCondition=">= 10"
)
```

### Log Points

Log a message without pausing execution:

```python
from aidb.dap.protocol.types import SourceBreakpoint

breakpoint = SourceBreakpoint(
    line=25,
    logMessage="Value of x is {x}, iteration {i}"  # Use {expr} for interpolation
)
```

**Language-specific log message syntax:**

```python
# Python
logMessage="User: {user.name}, Count: {len(items)}"

# JavaScript
logMessage="User: {user.name}, Count: {items.length}"

# Java
logMessage="User: {user.getName()}, Count: {items.size()}"
```

### Combined Conditions

You can combine condition types:

```python
from aidb.dap.protocol.types import SourceBreakpoint

# Conditional breakpoint with hit condition
breakpoint = SourceBreakpoint(
    line=40,
    condition="status == 'error'",
    hitCondition=">= 3"  # Break on 3rd error
)

# Conditional log point
breakpoint = SourceBreakpoint(
    line=50,
    condition="value > threshold",
    logMessage="Threshold exceeded: {value} > {threshold}"
)
```

## SetBreakpoints Request

The SetBreakpoints request **replaces** all breakpoints for a given source file.

### Complete Replacement Pattern

```python
from aidb.dap.protocol import SetBreakpointsRequest
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.dap.protocol.bodies import SetBreakpointsArguments

# Setting new breakpoints replaces any existing ones for this file
seq = await client.get_next_seq()
response = await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path="/path/to/file.py"),
            breakpoints=[
                SourceBreakpoint(line=10),
                SourceBreakpoint(line=20),
            ]
        )
    )
)

# To add a breakpoint, include all existing + new
seq = await client.get_next_seq()
response = await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path="/path/to/file.py"),
            breakpoints=[
                SourceBreakpoint(line=10),  # existing
                SourceBreakpoint(line=20),  # existing
                SourceBreakpoint(line=30),  # new
            ]
        )
    )
)
```

### Clearing Breakpoints

Send empty breakpoints array to clear all breakpoints for a file:

```python
seq = await client.get_next_seq()
response = await client.send_request(
    SetBreakpointsRequest(
        seq=seq,
        arguments=SetBreakpointsArguments(
            source=Source(path="/path/to/file.py"),
            breakpoints=[]  # Clear all
        )
    )
)
```

## Breakpoint Verification

The SetBreakpoints response indicates whether each breakpoint was successfully set.

### Verification Response

```python
from aidb.dap.protocol.types import Breakpoint

response = await client.send_request(set_breakpoints_request)

for requested, actual in zip(
    request.arguments.breakpoints,
    response.body.breakpoints
):
    if actual.verified:
        ctx.debug(
            f"Breakpoint at line {requested.line} verified at line {actual.line}"
        )
    else:
        ctx.warning(
            f"Breakpoint at line {requested.line} not verified: {actual.message}"
        )
```

### Verification Fields

```python
@dataclass
class Breakpoint:
    verified: bool               # Whether breakpoint is verified
    line: int | None             # Actual line (may differ from requested)
    column: int | None           # Actual column
    endLine: int | None          # End of breakpoint range
    endColumn: int | None        # End column
    source: Source | None        # Source location
    message: str | None          # Error/warning message
    id: int | None              # Unique breakpoint ID
```

### Common Verification Failures

1. **Invalid source location**

   ```python
   # message: "Source file not found"
   # verified: False
   ```

1. **No executable code at line**

   ```python
   # message: "No executable code at line 5"
   # verified: False
   # May adjust to nearest executable line
   ```

1. **Adapter doesn't support feature**

   ```python
   # Conditional breakpoint on adapter without support
   # message: "Conditional breakpoints not supported"
   # verified: False
   ```

### Handling Adjusted Breakpoints

Adapters may adjust breakpoint locations:

```python
requested_line = 10
response = await client.send_request(set_breakpoints_request)

actual_bp = response.body.breakpoints[0]
if actual_bp.verified and actual_bp.line != requested_line:
    ctx.info(
        f"Breakpoint moved from line {requested_line} to {actual_bp.line} "
        f"(no executable code at original line)"
    )
```

## Breakpoint Events

Adapters send BreakpointEvent when breakpoint state changes.

### Handling Breakpoint Events

```python
from aidb.dap.client.constants import EventType

async def handle_breakpoint_event(event):
    breakpoint = event.body.breakpoint
    reason = event.body.reason  # "changed", "new", "removed"

    if reason == "changed":
        if breakpoint.verified:
            ctx.debug(f"Breakpoint verified: line {breakpoint.line}")
        else:
            ctx.warning(f"Breakpoint unverified: {breakpoint.message}")
    elif reason == "new":
        ctx.debug(f"New breakpoint: {breakpoint.id}")
    elif reason == "removed":
        ctx.debug(f"Breakpoint removed: {breakpoint.id}")

# Subscribe to breakpoint events
subscription_id = await client.events.subscribe_to_event(
    EventType.BREAKPOINT.value,
    handle_breakpoint_event
)
```

## Summary

Key takeaways for breakpoint operations:

1. **SetBreakpoints replaces all breakpoints** for a file - include existing when adding
1. **Check verification** - `verified` field and `message` for failures
1. **Use protocol types** - SourceBreakpoint, FunctionBreakpoint, etc.
1. **Language differences matter** - Condition syntax, verification timing
1. **Set before ConfigurationDone** - For initial breakpoints
1. **Handle breakpoint events** - Track state changes
1. **Absolute paths** - Most reliable across adapters
1. **Test conditionals** - Expression syntax varies by language

## Additional Resources

For detailed information on specific topics:

1. **[Advanced Breakpoint Types](advanced-breakpoint-types.md)**

   - Function breakpoints
   - Exception breakpoints (language-specific filters)
   - Data breakpoints
   - Instruction breakpoints

1. **[Breakpoint Management](breakpoint-management.md)**

   - Managing breakpoints across files
   - **CRITICAL: Breakpoint timing and race conditions**
   - Language-specific quirks
   - Common patterns and best practices

For real-world examples, see:

- `src/aidb/session/session_breakpoints.py` - Breakpoint management implementation
- Framework tests for working examples:
  - `src/tests/frameworks/python/pytest/e2e/test_pytest_debugging.py`
  - `src/tests/frameworks/javascript/jest/e2e/test_jest_debugging.py`
  - `src/tests/frameworks/java/junit/e2e/test_junit_debugging.py`
