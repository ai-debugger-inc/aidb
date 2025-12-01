# DAP Variable and Expression Evaluation

This document details how to inspect and evaluate variables using DAP in AIDB. Variable inspection is fundamental to debugging - it shows program state, allows navigation through complex data structures, and enables expression evaluation.

## Overview

Variable inspection in DAP follows a hierarchical reference pattern:

```
Scopes Request → Variables Request → Nested Variables Request
    (frame)         (scope ref)         (variable ref)
```

Each level provides references needed for the next request. Expression evaluation operates in parallel, using frame context to resolve variables.

## Variables Request

### Request Structure

After obtaining a `variablesReference` from a scope or parent variable, retrieve its children:

```python
from aidb.dap.protocol import VariablesRequest
from aidb.dap.protocol.bodies import VariablesArguments

# Get variables reference from scope or parent variable
variables_reference = scope.variablesReference

request = VariablesRequest(
    seq=0,  # Sequence number managed by client
    arguments=VariablesArguments(
        variablesReference=variables_reference,
        filter=None,  # Optional: "named" or "indexed"
        start=None,   # Optional: for paging
        count=None    # Optional: for paging
    )
)

response = await client.send_request(request)
response.ensure_success()  # Raises if request failed
```

### Response Structure

```python
from aidb.dap.protocol.types import Variable

# Response contains list of variables
variables: list[Variable] = response.body.variables

for var in variables:
    print(f"{var.name} = {var.value}")
    print(f"  Type: {var.type}")
    print(f"  Has children: {var.variablesReference > 0}")
```

### Variable Fields

Key fields from `Variable` (see `src/aidb/dap/protocol/types.py:Variable`):

- `name`: Variable name
- `value`: String representation of the value
- `type`: Type name (language-specific: "int", "str", "Object", etc.)
- `variablesReference`: Reference for fetching children (0 if no children)
- `namedVariables`: Count of named children (objects, dicts)
- `indexedVariables`: Count of indexed children (arrays, lists)
- `evaluateName`: Expression to re-evaluate this variable
- `presentationHint`: Display hints for UI rendering

**Example:**

```python
Variable(
    name="user",
    value="User{id=123, name='Alice'}",
    type="User",
    variablesReference=42,
    namedVariables=2,
    indexedVariables=0,
    evaluateName="user"
)
```

## Variables Reference Tree

Variables form a tree structure navigated through references:

```
Scope (variablesReference=10)
  └─> Variables Request (ref=10)
      ├─> Variable "user" (variablesReference=20)
      │   └─> Variables Request (ref=20)
      │       ├─> Variable "id" (variablesReference=0)
      │       └─> Variable "name" (variablesReference=0)
      └─> Variable "items" (variablesReference=30)
          └─> Variables Request (ref=30)
              ├─> Variable "[0]" (variablesReference=0)
              └─> Variable "[1]" (variablesReference=0)
```

### Reference Lifecycle

**Important:** Variable references are only valid during the current stopped state. They become invalid after `continue`, `step`, or any execution resumes.

```python
# ✅ CORRECT: Use reference immediately
scopes_response = await client.send_request(ScopesRequest(...))
ref = scopes_response.body.scopes[0].variablesReference

vars_response = await client.send_request(
    VariablesRequest(arguments=VariablesArguments(variablesReference=ref))
)

# ❌ WRONG: Don't store references across execution changes
ref = scopes_response.body.scopes[0].variablesReference
await client.send_request(ContinueRequest(...))  # Reference now invalid!
vars_response = await client.send_request(
    VariablesRequest(arguments=VariablesArguments(variablesReference=ref))  # ERROR
)
```

## Named vs Indexed Variables

The `filter` parameter allows fetching only specific variable types:

### Filter Values

- `None` (default): Fetch all variables
- `"named"`: Fetch only named variables (object properties, dict keys)
- `"indexed"`: Fetch only indexed variables (array elements, list items)

### Usage Pattern

```python
# Fetch only named variables (efficient for large arrays)
request = VariablesRequest(
    seq=0,
    arguments=VariablesArguments(
        variablesReference=var_ref,
        filter="named"
    )
)

# Fetch indexed variables with paging
request = VariablesRequest(
    seq=0,
    arguments=VariablesArguments(
        variablesReference=var_ref,
        filter="indexed",
        start=0,
        count=100  # First 100 elements
    )
)
```

### Determining Variable Children

Check `namedVariables` and `indexedVariables` to determine structure:

```python
if var.namedVariables and var.indexedVariables:
    # Mixed structure (unusual, some languages support this)
    pass
elif var.namedVariables:
    # Object/dict with properties
    filter_value = "named"
elif var.indexedVariables:
    # Array/list with indexed elements
    filter_value = "indexed"
else:
    # No children (primitive or empty)
    pass
```

## Variable Types by Language

### Python (debugpy)

```python
Variable(name="count", value="42", type="int")
Variable(name="message", value="'hello'", type="str")
Variable(name="items", value="[1, 2, 3]", type="list")
Variable(name="data", value="{'key': 'value'}", type="dict")
Variable(name="obj", value="<MyClass object at 0x...>", type="MyClass")
```

### JavaScript/TypeScript (vscode-js-debug)

```python
Variable(name="count", value="42", type="number")
Variable(name="message", value="'hello'", type="string")
Variable(name="items", value="Array(3)", type="Array")
Variable(name="data", value="{key: 'value'}", type="Object")
Variable(name="fn", value="ƒ myFunction()", type="function")
```

### Java (java-debug-server)

```python
Variable(name="count", value="42", type="int")
Variable(name="message", value='"hello"', type="String")
Variable(name="items", value="int[3]", type="int[]")
Variable(name="obj", value="User@1a2b3c", type="User")
```

## Evaluate Request

### Request Structure

Evaluate expressions in the context of a stopped frame:

```python
from aidb.dap.protocol import EvaluateRequest
from aidb.dap.protocol.bodies import EvaluateArguments

request = EvaluateRequest(
    seq=0,
    arguments=EvaluateArguments(
        expression="user.name.upper()",  # Expression to evaluate
        frameId=frame_id,                # Frame context
        context="repl"                   # Evaluation context
    )
)

response = await client.send_request(request)
response.ensure_success()
```

### Response Structure

```python
# Response contains evaluation result
result = response.body.result           # String representation
var_type = response.body.type           # Type name
var_ref = response.body.variablesReference  # For navigating result

# Check if result has children
if var_ref > 0:
    # Result is complex - can fetch children via Variables request
    child_vars = await client.send_request(
        VariablesRequest(arguments=VariablesArguments(variablesReference=var_ref))
    )
```

### Evaluation Contexts

The `context` parameter indicates the purpose of evaluation (see `src/aidb/api/constants.py`):

- `"repl"`: Interactive evaluation (default, may have side effects)
- `"watch"`: Watch expression (should avoid side effects)
- `"hover"`: Hover evaluation (must avoid side effects, quick)

**Note:** Some adapters respect context hints to avoid side effects in watch/hover contexts.

## Language-Specific Evaluation

### Python Evaluation

```python
# Simple expressions
await evaluate("x + y")                    # "15"
await evaluate("items[0]")                 # "first item"

# Method calls (may have side effects in REPL context)
await evaluate("message.upper()")          # "HELLO"
await evaluate("len(items)")               # "5"

# Complex expressions
await evaluate("sum([x * 2 for x in range(5)])")  # "20"
```

### JavaScript Evaluation

```python
# Simple expressions
await evaluate("x + y")                    # "15"
await evaluate("items[0]")                 # "first item"

# Property access
await evaluate("user.profile.name")        # "Alice"

# Method calls
await evaluate("message.toUpperCase()")    # "HELLO"
await evaluate("items.length")             # "5"

# Complex expressions
await evaluate("items.map(x => x * 2)")    # "[2, 4, 6]"
```

### Java Evaluation

```python
# Simple expressions
await evaluate("x + y")                    # "15"
await evaluate("items[0]")                 # "first item"

# Method calls
await evaluate("message.toUpperCase()")    # "HELLO"
await evaluate("user.getName()")           # "Alice"

# Field access
await evaluate("user.profile.name")        # "Alice"
```

## Common Patterns

### Pattern 1: Navigate Object Hierarchy

```python
from aidb.dap.protocol import VariablesRequest, ScopesRequest
from aidb.dap.protocol.bodies import VariablesArguments, ScopesArguments

# 1. Get scopes for current frame
scopes_response = await client.send_request(
    ScopesRequest(seq=0, arguments=ScopesArguments(frameId=frame_id))
)
scopes_response.ensure_success()

# 2. Get locals scope
locals_scope = next(s for s in scopes_response.body.scopes if s.name == "Locals")

# 3. Get variables in locals
vars_response = await client.send_request(
    VariablesRequest(
        seq=0,
        arguments=VariablesArguments(variablesReference=locals_scope.variablesReference)
    )
)
vars_response.ensure_success()

# 4. Find specific variable and navigate children
user_var = next(v for v in vars_response.body.variables if v.name == "user")

if user_var.variablesReference > 0:
    # 5. Get user's properties
    user_props_response = await client.send_request(
        VariablesRequest(
            seq=0,
            arguments=VariablesArguments(variablesReference=user_var.variablesReference)
        )
    )
    user_props_response.ensure_success()
```

### Pattern 2: Efficient Large Array Inspection

```python
# Fetch pages from large array using start/count parameters
array_var = next(v for v in variables if v.name == "large_array")

if array_var.indexedVariables:
    # Fetch page: start=0, count=100 for first 100 elements
    page = await client.send_request(
        VariablesRequest(
            seq=0,
            arguments=VariablesArguments(
                variablesReference=array_var.variablesReference,
                filter="indexed",
                start=0,
                count=100
            )
        )
    )
```

### Pattern 3: Expression-Based Navigation

```python
from aidb.dap.protocol import EvaluateRequest
from aidb.dap.protocol.bodies import EvaluateArguments

# Evaluate complex expression to navigate deeply nested structures
result = await client.send_request(
    EvaluateRequest(
        seq=0,
        arguments=EvaluateArguments(
            expression="users[0].profile.settings.theme",
            frameId=frame_id,
            context="repl"
        )
    )
)

# Navigate children if result is an object
if result.body.variablesReference > 0:
    children = await client.send_request(
        VariablesRequest(seq=0, arguments=VariablesArguments(
            variablesReference=result.body.variablesReference))
    )
```

### Pattern 4: AIDB Session-Level Pattern

```python
# AIDB provides higher-level operations in session.debug
from aidb.session import Session

session = Session(...)

# Get locals (handles scope lookup internally)
locals_response = await session.debug.locals(frame_id=None)  # None = current frame
for name, var in locals_response.variables.items():
    print(f"{name}: {var.value} ({var.type_name})")

# Evaluate expression
result = await session.debug.evaluate(
    expression="x + y",
    frame_id=None,  # None = current frame
    context="repl"
)
print(f"Result: {result.result} (type: {result.type_name})")

# Navigate nested structure
if result.has_children:
    children = await session.debug.get_variables(
        variables_reference=result.variablesReference
    )
```

## Troubleshooting

### Issue: Variables reference returns empty list

**Cause:** Reference expired after execution resumed

**Solution:** Fetch variables immediately after stopped event

```python
# ❌ WRONG
stopped_event = await client.wait_for_event("stopped")
scopes_response = await client.send_request(ScopesRequest(...))
await client.send_request(ContinueRequest(...))
vars_response = await client.send_request(VariablesRequest(...))  # Empty!

# ✅ CORRECT
stopped_event = await client.wait_for_event("stopped")
scopes_response = await client.send_request(ScopesRequest(...))
vars_response = await client.send_request(VariablesRequest(...))  # Works!
await client.send_request(ContinueRequest(...))
```

### Issue: Evaluate fails with "not available"

**Cause:** Variable not in scope for the specified frame

**Solution:** Verify frame context. Try different frames in the stack trace to find where the variable is in scope.

### Issue: Named/indexed filter returns wrong variables

**Cause:** Adapter-specific behavior with complex types

**Solution:** Fetch without filter first, then inspect `namedVariables`/`indexedVariables` counts to determine if filtering is needed.

## Summary

**Key Takeaways:**

1. Variables are accessed through hierarchical references: Scope → Variables → Nested Variables
1. References are ephemeral - only valid during current stopped state
1. Use `filter` parameter for efficient large array/object inspection
1. Evaluation contexts (`repl`, `watch`, `hover`) hint at side-effect tolerance
1. `namedVariables`/`indexedVariables` indicate structure before fetching
1. AIDB's `session.debug` provides higher-level abstractions over raw DAP

**See also:**

- [Stack Inspection](./stack-inspection.md) - Getting scopes and frames
- [Initialization Sequence](./initialization-sequence.md) - Session setup
- [Breakpoint Operations](./breakpoint-operations.md) - Stopping execution
- `src/aidb/dap/protocol/types.py:Variable` - Full Variable type definition
- `src/aidb/session/ops/introspection/variables.py` - AIDB variable operations
