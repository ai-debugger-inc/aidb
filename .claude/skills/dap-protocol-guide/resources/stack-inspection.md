# DAP Stack Inspection

This document details how to inspect program state using DAP stack trace and scope requests in AIDB. Stack inspection is fundamental to debugging - it shows where execution stopped, what functions are active, and what variables are accessible.

## Overview

Stack inspection in DAP involves a sequence of requests to navigate from a stopped thread to its variables:

```
Stopped Event → Threads → StackTrace → Scopes → Variables
```

Each step provides IDs needed for the next request (thread ID → frame ID → scope reference → variables reference).

## Stack Trace Request

After receiving a `stopped` event, retrieve the call stack using a `stackTrace` request.

### Request Structure

```python
from aidb.dap.protocol import StackTraceRequest
from aidb.dap.protocol.bodies import StackTraceArguments

# Get thread ID from stopped event
thread_id = stopped_event.body.threadId

# Request stack trace
request = StackTraceRequest(
    seq=0,  # Sequence number managed by client
    arguments=StackTraceArguments(
        threadId=thread_id,
        startFrame=0,     # Start from top of stack
        levels=20         # Number of frames to fetch (0 = all)
    )
)

response = await client.send_request(request)
response.ensure_success()  # Raises if request failed
```

### Response Structure

```python
from aidb.dap.protocol.types import StackFrame, Source

# Response contains list of stack frames
frames: list[StackFrame] = response.body.stackFrames
total_frames = response.body.totalFrames

# Top frame (current execution point)
current_frame = frames[0]
print(f"Stopped at: {current_frame.name}")
print(f"File: {current_frame.source.path}")
print(f"Line: {current_frame.line}")
```

### StackFrame Fields

Key fields from `StackFrame` (see `src/aidb/dap/protocol/types.py:StackFrame`):

- `id`: Unique frame identifier (used for scopes request)
- `name`: Function/method name
- `source`: Source file information
- `line`: Line number (1-based)
- `column`: Column number (1-based)
- `presentationHint`: Display hint ("normal", "label", "subtle")

**Example:**

```python
StackFrame(
    id=1,
    name="calculate_total",
    source=Source(path="/path/to/script.py"),
    line=42,
    column=5,
    presentationHint="normal"
)
```

## Frame ID Handling

Frame IDs are adapter-generated and temporary - they're only valid during the current stopped state.

### Important Rules

1. **Frame IDs are ephemeral**: They become invalid after `continue`, `step`, or any execution resumes
1. **Top frame is frame 0**: Frames are ordered from current (0) to oldest
1. **IDs are adapter-specific**: Don't assume sequential numbering

### Usage Pattern

```python
# ✅ CORRECT: Use frame ID immediately after stackTrace
stack_response = await client.send_request(StackTraceRequest(...))
frame_id = stack_response.body.stackFrames[0].id

# Request scopes for this frame
scopes_response = await client.send_request(
    ScopesRequest(arguments=ScopesArguments(frameId=frame_id))
)

# ❌ WRONG: Don't store frame IDs across execution state changes
frame_id = stack_response.body.stackFrames[0].id
await client.send_request(ContinueRequest(...))  # Frame ID now invalid!
scopes_response = await client.send_request(
    ScopesRequest(arguments=ScopesArguments(frameId=frame_id))  # ERROR
)
```

## Scopes Request

After obtaining a frame ID, request scopes to access variables within that frame.

### Request Structure

```python
from aidb.dap.protocol import ScopesRequest
from aidb.dap.protocol.bodies import ScopesArguments

request = ScopesRequest(
    seq=0,
    arguments=ScopesArguments(frameId=frame_id)
)

response = await client.send_request(request)
response.ensure_success()
```

### Response Structure

```python
from aidb.dap.protocol.types import Scope

# Response contains list of scopes
scopes: list[Scope] = response.body.scopes

# Common scopes (order and names are language-specific)
for scope in scopes:
    print(f"Scope: {scope.name}")
    print(f"Variables Reference: {scope.variablesReference}")
    print(f"Expensive: {scope.expensive}")
```

### Scope Types by Language

**Python (debugpy):**

- `"Locals"` - Local variables in current function
- `"Globals"` - Global module-level variables

**JavaScript (vscode-js-debug):**

- `"Local"` - Local variables
- `"Closure"` - Closure variables
- `"Global"` - Global scope
- `"Catch"` - Exception variables in catch block

**Java (java-debug):**

- `"Local"` - Local variables
- `"Static"` - Static class variables

### Scope Fields

Key fields from `Scope` (see `src/aidb/dap/protocol/types.py:Scope`):

- `name`: Display name ("Locals", "Globals", etc.)
- `variablesReference`: ID for variables request (0 = no variables)
- `expensive`: Whether fetching variables is expensive
- `presentationHint`: Display category ("arguments", "locals", "registers")

### Usage Pattern

```python
# Get locals scope
locals_scope = next(s for s in scopes if s.name == "Locals")

# Check if scope has variables
if locals_scope.variablesReference > 0:
    # Request variables for this scope
    vars_response = await client.send_request(
        VariablesRequest(
            arguments=VariablesArguments(
                variablesReference=locals_scope.variablesReference
            )
        )
    )
```

## Variables Request

The `variables` request is covered in detail in [variable-evaluation.md](variable-evaluation.md). This section covers stack-specific variable patterns.

### Basic Request

```python
from aidb.dap.protocol import VariablesRequest
from aidb.dap.protocol.bodies import VariablesArguments

request = VariablesRequest(
    seq=0,
    arguments=VariablesArguments(
        variablesReference=scope.variablesReference,
        filter="indexed",  # Optional: "indexed", "named"
        start=0,           # Optional: paging support
        count=100          # Optional: paging support
    )
)

response = await client.send_request(request)
response.ensure_success()
variables = response.body.variables
```

## Source References

Stack frames include source information that may be a file path or a reference.

### Source Types

```python
from aidb.dap.protocol.types import Source

# File-based source
source = Source(
    name="script.py",
    path="/absolute/path/to/script.py",
    sourceReference=0  # 0 = file path available
)

# Reference-based source (e.g., dynamically generated code)
source = Source(
    name="<eval>",
    sourceReference=1234  # Non-zero = use source request
)
```

### Checking Source Availability

```python
frame = stack_response.body.stackFrames[0]

if frame.source.sourceReference == 0:
    # Source available as file path
    file_path = frame.source.path
    print(f"Source file: {file_path}")
else:
    # Source must be fetched via source request
    source_ref = frame.source.sourceReference
    # Use SourceRequest to fetch content
```

### Presentation Hints

Frames may include presentation hints for UI rendering:

- `"normal"` - Regular user code
- `"label"` - Not a real frame (e.g., async boundary)
- `"subtle"` - Library/framework code (less important)

## Language-Specific Differences

### Python (debugpy)

**Scope Names:**

- `"Locals"` - Function-local variables
- `"Globals"` - Module-level globals

**Stack Frame Names:**

- Function name or `"<module>"` for module-level code

**Special Cases:**

- List comprehensions show as `"<listcomp>"`
- Lambda functions show as `"<lambda>"`

**Example:**

```python
# Python stack trace
[
    StackFrame(id=1, name="inner_function", line=10),
    StackFrame(id=2, name="outer_function", line=5),
    StackFrame(id=3, name="<module>", line=1)
]
```

### JavaScript/TypeScript (vscode-js-debug)

**Scope Names:**

- `"Local"` - Function-local variables
- `"Closure"` - Variables from enclosing functions
- `"Global"` - Window/global object
- `"Catch"` - Exception variable in catch block
- `"Block"` - Block-scoped variables (let/const)

**Stack Frame Names:**

- Function name or `"(anonymous function)"` for arrow functions

**Special Cases:**

- Async functions show async boundaries
- Promise chains may show multiple internal frames

**Example:**

```javascript
// JavaScript stack trace
[
    StackFrame(id=1, name="fetchData", line=25),
    StackFrame(id=2, name="Promise.then", line=18, presentationHint="subtle"),
    StackFrame(id=3, name="(anonymous)", line=12)
]
```

### Java (java-debug)

**Scope Names:**

- `"Local"` - Method-local variables
- `"Static"` - Static class fields

**Stack Frame Names:**

- Fully-qualified method name (e.g., `com.example.MyClass.myMethod`)

**Special Cases:**

- Lambda expressions show generated method names
- Synthetic frames from compiler-generated code

**Example:**

```java
// Java stack trace
[
    StackFrame(id=1, name="com.example.Service.processData", line=42),
    StackFrame(id=2, name="com.example.Controller.handleRequest", line=18),
    StackFrame(id=3, name="com.example.Main.main", line=5)
]
```

## Common Patterns

### Pattern 1: Get Current Line Variables

```python
async def get_current_variables(client, thread_id):
    """Get variables at current execution point."""
    # Get stack trace
    stack_response = await client.send_request(
        StackTraceRequest(
            arguments=StackTraceArguments(threadId=thread_id, levels=1)
        )
    )

    # Get top frame
    frame_id = stack_response.body.stackFrames[0].id

    # Get scopes
    scopes_response = await client.send_request(
        ScopesRequest(arguments=ScopesArguments(frameId=frame_id))
    )

    # Get locals
    locals_scope = next(s for s in scopes_response.body.scopes if s.name in ["Locals", "Local"])
    vars_response = await client.send_request(
        VariablesRequest(
            arguments=VariablesArguments(
                variablesReference=locals_scope.variablesReference
            )
        )
    )

    return vars_response.body.variables
```

### Pattern 2: Walk Up Stack

```python
async def inspect_call_stack(client, thread_id):
    """Inspect variables at each level of call stack."""
    stack_response = await client.send_request(
        StackTraceRequest(arguments=StackTraceArguments(threadId=thread_id))
    )

    results = []
    for frame in stack_response.body.stackFrames:
        scopes_response = await client.send_request(
            ScopesRequest(arguments=ScopesArguments(frameId=frame.id))
        )

        frame_vars = {}
        for scope in scopes_response.body.scopes:
            if scope.variablesReference > 0:
                vars_response = await client.send_request(
                    VariablesRequest(
                        arguments=VariablesArguments(
                            variablesReference=scope.variablesReference
                        )
                    )
                )
                frame_vars[scope.name] = vars_response.body.variables

        results.append({
            "frame": frame.name,
            "line": frame.line,
            "variables": frame_vars
        })

    return results
```

### Pattern 3: Find Frame by Name

```python
async def find_frame_by_name(client, thread_id, function_name):
    """Find specific frame in call stack."""
    stack_response = await client.send_request(
        StackTraceRequest(arguments=StackTraceArguments(threadId=thread_id))
    )

    for frame in stack_response.body.stackFrames:
        if function_name in frame.name:
            return frame

    return None
```

## Troubleshooting

### Issue: "Invalid frame ID"

**Cause:** Frame ID used after execution state changed

**Solution:** Always fetch fresh stack trace after program stops

```python
# ✅ CORRECT
await client.wait_for_event("stopped")
stack_response = await client.send_request(StackTraceRequest(...))
frame_id = stack_response.body.stackFrames[0].id
# Use frame_id immediately

# ❌ WRONG
frame_id = old_stack_response.body.stackFrames[0].id
await client.send_request(ContinueRequest(...))
# frame_id is now invalid
```

### Issue: Empty scopes list

**Cause:** Language adapter doesn't support scopes at this location (e.g., global scope in some languages)

**Solution:** Check frame name and source - some frames (like library code) may not have accessible scopes

### Issue: VariablesReference is 0

**Cause:** Scope has no variables, or they're not accessible

**Solution:** Check `scope.expensive` and `scope.namedVariables` - some scopes are empty

### Issue: Stack trace shows internal frames

**Cause:** Debugger showing library/framework internal calls

**Solution:** Filter by `presentationHint` - use only "normal" frames, skip "subtle" or "label"

```python
user_frames = [f for f in frames if f.presentationHint != "subtle"]
```

## Summary

Stack inspection in DAP follows a clear request chain:

1. **Thread ID** (from stopped event) → `StackTraceRequest` → **Frame IDs**
1. **Frame ID** → `ScopesRequest` → **Variables References**
1. **Variables Reference** → `VariablesRequest` → **Variables**

Key principles:

- Frame IDs are temporary (valid only while stopped)
- Scope names vary by language
- Variables references form a tree (nested objects have their own references)
- Always use fresh frame IDs after execution resumes

**See also:**

- [variable-evaluation.md](variable-evaluation.md) - Variable inspection and evaluation
- [initialization-sequence.md](initialization-sequence.md) - Session setup
- [breakpoint-operations.md](breakpoint-operations.md) - Breakpoint management
