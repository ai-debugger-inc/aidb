---
myst:
  html_meta:
    description lang=en: Inspection tools in AI Debugger MCP - inspect, variable, and breakpoint management.
---

# Inspection Tools

The inspection tools allow you to examine and modify program state during debugging. These tools form the core of your debugging workflow, enabling you to peek inside your running application, evaluate expressions, manage variables, and control execution flow with breakpoints.

## inspect - Examine Program State

The `inspect` tool provides comprehensive visibility into your program's runtime state with multiple inspection modes.

### Overview

The inspect tool operates on a **paused** debugging session and allows you to examine:

- Local and global variables
- Call stack and thread information
- Arbitrary expressions

:::{important}
**Inspection requires a paused session!** You must hit a breakpoint or use step before inspecting state. If the program is running, inspection will fail with `SessionNotPausedError`.
:::

### Inspection Modes

**Available modes:** locals, globals, stack, threads, expression, all

#### locals - Local Variables

Examine variables in the current scope.

```python
# Inspect all local variables at current breakpoint
{
  "tool": "inspect",
  "arguments": {
    "target": "locals"
  }
}
```

**Response:**

```json
{
  "target": "locals",
  "result": {
    "x": 42,
    "username": "alice",
    "is_valid": true,
    "items": ["a", "b", "c"]
  },
  "frame": 0
}
```

#### globals - Global Variables

View all global variables accessible from the current scope.

```python
# Inspect global variables
{
  "tool": "inspect",
  "arguments": {
    "target": "globals"
  }
}
```

#### stack - Call Stack

Examine the complete call stack with all stack frames.

```python
# View call stack
{
  "tool": "inspect",
  "arguments": {
    "target": "stack"
  }
}
```

**Response:**

```json
{
  "target": "stack",
  "result": {
    "frames": [
      {
        "id": 0,
        "name": "calculate_tax",
        "file": "/app/billing.py",
        "line": 45,
        "column": 12
      },
      {
        "id": 1,
        "name": "process_order",
        "file": "/app/orders.py",
        "line": 102,
        "column": 8
      }
    ]
  }
}
```

#### threads - Thread Information

View all threads and their current state.

```python
# Inspect all threads
{
  "tool": "inspect",
  "arguments": {
    "target": "threads"
  }
}
```

#### expression - Evaluate Expressions

Evaluate arbitrary expressions in the current execution context.

```python
# Evaluate a complex expression
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "len(items) > 0 and items[0].price"
  }
}
```

**Response:**

```json
{
  "target": "expression",
  "result": 29.99,
  "expression": "len(items) > 0 and items[0].price"
}
```

#### all - Complete State

Get a comprehensive snapshot of all available information.

```python
# Get everything
{
  "tool": "inspect",
  "arguments": {
    "target": "all"
  }
}
```

### Frame Navigation

You can inspect variables at different stack frames using the `frame` parameter:

```python
# Inspect locals in the calling function (frame 1)
{
  "tool": "inspect",
  "arguments": {
    "target": "locals",
    "frame": 1
  }
}

# Inspect expression two frames up
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "order_total",
    "frame": 2
  }
}
```

Frame numbering:

- `0` - Current frame (default)
- `1` - Caller's frame
- `2` - Caller's caller, etc.

### Detailed Output

For more verbose output, use the `detailed` parameter:

```python
# Get detailed variable information
{
  "tool": "inspect",
  "arguments": {
    "target": "locals",
    "detailed": true
  }
}
```

Detailed mode includes:

- Variable types
- Object properties
- Nested structures expanded
- Memory addresses (where supported)

### Examples

**Example 1: Inspect loop variable**

```python
# At a breakpoint inside a loop
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "i"
  }
}
# Result: {"result": 3}
```

**Example 2: Check object state**

```python
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "user.__dict__"
  }
}
# Result: {"result": {"id": 123, "name": "Alice", "active": true}}
```

**Example 3: Evaluate condition**

```python
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "balance > 0 and not suspended"
  }
}
# Result: {"result": true}
```

______________________________________________________________________

## variable - Variable Operations

The `variable` tool provides enhanced variable operations with live patching capabilities.

### Overview

Variable operations require a **paused** debugging session. You can:

- Get: Evaluate and retrieve variable values
- Set: Modify variable values during execution
- Patch: Live code patching for rapid iteration

### Actions

#### get - Evaluate Expression

Retrieve the value of a variable or expression.

```python
# Get a simple variable
{
  "tool": "variable",
  "arguments": {
    "action": "get",
    "expression": "username"
  }
}
```

**Response:**

```json
{
  "action": "get",
  "expression": "username",
  "value": "alice_2024",
  "frame": 0
}
```

**Get object property:**

```python
{
  "tool": "variable",
  "arguments": {
    "action": "get",
    "expression": "order.items[0].price"
  }
}
```

**Get computed value:**

```python
{
  "tool": "variable",
  "arguments": {
    "action": "get",
    "expression": "sum([item.price for item in cart])"
  }
}
```

#### set - Modify Variable Value

Change a variable's value during debugging to test different scenarios.

```python
# Change a variable value
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "debug_mode",
    "value": "True"
  }
}
```

**Response:**

```json
{
  "action": "set",
  "name": "debug_mode",
  "new_value": "True",
  "frame": 0
}
```

**Set numeric value:**

```python
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "max_retries",
    "value": "10"
  }
}
```

**Set string value:**

```python
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "api_endpoint",
    "value": "https://staging.example.com/api"
  }
}
```

#### patch - Live Code Patching

Modify function code during debugging for rapid iteration without restarting the session.

```python
# Patch a function to fix a bug on the fly
{
  "tool": "variable",
  "arguments": {
    "action": "patch",
    "name": "calculate_tax",
    "code": "return amount * 0.08"
  }
}
```

**Response:**

```json
{
  "action": "patch",
  "name": "calculate_tax",
  "frame": 0,
  "message": "Function patched successfully"
}
```

**Patch with multi-line code:**

```python
{
  "tool": "variable",
  "arguments": {
    "action": "patch",
    "name": "validate_input",
    "code": "if value < 0:\n    return False\nreturn True"
  }
}
```

### Frame Context

Variable operations can target different stack frames:

```python
# Get variable from parent frame
{
  "tool": "variable",
  "arguments": {
    "action": "get",
    "expression": "total",
    "frame": 1
  }
}

# Set variable in specific frame
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "retry_count",
    "value": "0",
    "frame": 0
  }
}
```

### Examples

**Example 1: Debug flag manipulation**

```python
# Enable debug logging mid-execution
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "verbose",
    "value": "True"
  }
}
```

**Example 2: Test edge cases**

```python
# Force an error condition
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "remaining_balance",
    "value": "-100"
  }
}
```

**Example 3: Skip iterations**

```python
# Jump ahead in a loop
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "i",
    "value": "95"
  }
}
```

**Example 4: Inspect complex expressions**

```python
# Get nested property
{
  "tool": "variable",
  "arguments": {
    "action": "get",
    "expression": "config['database']['connection_pool']['max_size']"
  }
}
```

**Example 5: Patch function for testing**

```python
# Fix a calculation bug without restarting
{
  "tool": "variable",
  "arguments": {
    "action": "patch",
    "name": "calculate_discount",
    "code": "return price * 0.20 if quantity > 10 else price * 0.10"
  }
}
```

### Error Handling

**Session not paused:**

```json
{
  "error": "SessionNotPausedError",
  "message": "Variable operations require debugger to be paused",
  "suggestion": "Set a breakpoint or wait for execution to pause"
}
```

**Missing parameter:**

```json
{
  "error": "MissingParameterError",
  "message": "Missing required parameter: expression",
  "param": "expression"
}
```

______________________________________________________________________

## breakpoint - Manage Breakpoints

The `breakpoint` tool is your primary mechanism for controlling execution flow. It supports standard breakpoints, conditional breakpoints, hit conditions, logpoints, and column-level breakpoints for minified code.

### Overview

Breakpoints pause program execution when specific conditions are met. The AI Debugger supports:

- **Standard breakpoints** - Pause at a line
- **Conditional breakpoints** - Pause only when a condition is true
- **Hit condition breakpoints** - Pause after N hits or every Nth hit
- **Logpoints** - Log without pausing
- **Column breakpoints** - Precise placement in minified code

:::{tip}
**Breakpoint verification:** All breakpoints are automatically verified by the debug adapter. If a breakpoint is set on a non-executable line (like a comment or blank line), it may be adjusted to the nearest executable line. Always check the `verified` field in the response!
:::

### Actions

#### set - Set a Breakpoint

Create a new breakpoint at a specific location.

**Basic breakpoint:**

```python
# Set breakpoint at line 45 in billing.py
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/billing.py:45"
  }
}
```

**Response:**

```json
{
  "action": "set",
  "location": "/app/billing.py:45",
  "affected_count": 1,
  "verified": true
}
```

#### remove - Remove a Breakpoint

Remove an existing breakpoint.

```python
# Remove breakpoint
{
  "tool": "breakpoint",
  "arguments": {
    "action": "remove",
    "location": "/app/billing.py:45"
  }
}
```

**Response:**

```json
{
  "action": "remove",
  "location": "/app/billing.py:45",
  "affected_count": 1
}
```

#### list - List All Breakpoints

View all active breakpoints in the current session.

```python
# List all breakpoints
{
  "tool": "breakpoint",
  "arguments": {
    "action": "list"
  }
}
```

**Response:**

```json
{
  "breakpoints": [
    {
      "id": "/app/billing.py:45",
      "file": "/app/billing.py",
      "line": 45,
      "location": "/app/billing.py:45",
      "verified": true
    },
    {
      "id": "/app/orders.py:102",
      "file": "/app/orders.py",
      "line": 102,
      "location": "/app/orders.py:102",
      "condition": "order.total > 1000",
      "verified": true
    }
  ]
}
```

#### clear_all - Remove All Breakpoints

Clear all breakpoints from the session.

```python
# Clear all breakpoints
{
  "tool": "breakpoint",
  "arguments": {
    "action": "clear_all"
  }
}
```

**Response:**

```json
{
  "action": "clear_all",
  "affected_count": 5
}
```

### Conditional Breakpoints

Conditional breakpoints only pause when an expression evaluates to `true`.

:::{warning}
**Use language-specific syntax!** Conditions must be valid expressions in the target language:
- Python: `is None`, `and`, `or`, `not`
- JavaScript: `=== null`, `&&`, `||`, `!`
- Java: `== null`, `&&`, `||`, `!`

Invalid syntax will cause the breakpoint to fail silently or never trigger!
:::

**Basic condition:**

```python
# Break only when x is greater than 10
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:78",
    "condition": "x > 10"
  }
}
```

**Complex condition:**

```python
# Break on specific user
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/auth.py:234",
    "condition": "user.id == 12345 and user.role == 'admin'"
  }
}
```

**String comparison:**

```python
# Break on error status
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:156",
    "condition": "response.status == 'error'"
  }
}
```

**Collection check:**

```python
# Break when list is not empty
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/handler.py:67",
    "condition": "len(pending_jobs) > 0"
  }
}
```

**Null/None check:**

```python
# Break when value is null (JavaScript)
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/index.js:89",
    "condition": "result === null"
  }
}

# Break when value is None (Python)
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/service.py:123",
    "condition": "data is None"
  }
}
```

**Method call result:**

```python
# Break based on method return
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/validator.py:45",
    "condition": "validate_email(email) == False"
  }
}
```

### Hit Condition Breakpoints

Hit conditions control how many times a breakpoint must be hit before pausing.

#### Hit Condition Syntax

```{include} /_snippets/hit-conditions-table-full.md
```

#### Examples

**Skip first N iterations:**

```python
# Skip first 100 loop iterations, break on 101st
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:45",
    "hit_condition": ">100"
  }
}
```

**Sample every Nth execution:**

```python
# Break every 10th time through the loop
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/worker.py:89",
    "hit_condition": "%10"
  }
}
```

**Break once at specific iteration:**

```python
# Break only on the 50th hit
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/loop.py:23",
    "hit_condition": "50"
  }
}
```

**Debug early iterations:**

```python
# Break only on first 5 hits
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/init.py:67",
    "hit_condition": "<=5"
  }
}
```

**Combine with condition:**

```python
# Break every 5th time when error occurs
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/handler.py:234",
    "condition": "status == 'error'",
    "hit_condition": "%5"
  }
}
```

#### Language Support

**Python:**

- Supports: All modes (`EXACT`, `MODULO`, `GREATER_THAN`, `GREATER_EQUAL`, `LESS_THAN`, `LESS_EQUAL`, `EQUALS`)
- Examples: `"5"`, `"%10"`, `">20"`, `">=20"`, `"<20"`, `"<=20"`, `"==20"`

**JavaScript:**

- Supports: All modes (`EXACT`, `MODULO`, `GREATER_THAN`, `GREATER_EQUAL`, `LESS_THAN`, `LESS_EQUAL`, `EQUALS`)
- Examples: `"5"`, `"%10"`, `">20"`, `">=20"`, `"<20"`, `"<=20"`, `"==20"`

**Java:**

- Supports: `EXACT` only (plain integers)
- Examples: `"5"`, `"10"`, `"100"`

If you use an unsupported mode, you'll receive an error:

```json
{
  "error": "UnsupportedOperationError",
  "message": "The python adapter doesn't support LESS_THAN hit conditions. Supported: EXACT, MODULO, GREATER_THAN"
}
```

### Logpoints

Logpoints write messages to the debug console without pausing execution. They're perfect for observing program flow without interrupting it.

:::{tip}
**When to use logpoints:**
- Production debugging where pausing would impact users
- High-frequency code paths (tight loops, hot paths)
- Collecting data over time without manual intervention
- Understanding control flow without stopping execution

Use regular breakpoints when you need to inspect state in detail!
:::

**Basic logpoint:**

```python
# Log a message every time line executes
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:45",
    "log_message": "Processing started"
  }
}
```

**Log with variables:**

```python
# Log variable values (use curly braces for expressions)
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/handler.py:89",
    "log_message": "Processing item {i} of {total}: {item.name}"
  }
}
```

**Log expressions:**

```python
# Evaluate expressions in log message
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/calc.py:67",
    "log_message": "Calculation result: {x + y}, ratio: {x/y if y != 0 else 'undefined'}"
  }
}
```

**Conditional logging:**

```python
# Log only when condition is true
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:123",
    "condition": "response.status >= 400",
    "log_message": "Error response: {response.status} - {response.body}"
  }
}
```

**Logpoint with hit condition:**

```python
# Log every 100th execution
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/loop.py:45",
    "hit_condition": "%100",
    "log_message": "Progress checkpoint: iteration {i}"
  }
}
```

### Column-Level Breakpoints

For minified or single-line code, you can set breakpoints at specific columns.

**Using column parameter:**

```python
# Break at column 245 in minified JavaScript
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/dist/bundle.min.js:1",
    "column": 245
  }
}
```

**Using location syntax:**

```python
# Alternative: include column in location string
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/dist/bundle.min.js:1:245"
  }
}
```

**Conditional column breakpoint:**

```python
# Conditional breakpoint in minified code
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/dist/app.min.js:1:1024",
    "condition": "user.authenticated === false"
  }
}
```

### Advanced Techniques

#### Debugging Loops

**Skip to specific iteration:**

```python
# Set breakpoint to pause on 1000th iteration
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:78",
    "hit_condition": "1000"
  }
}
```

**Sample large dataset processing:**

```python
# Check every 100th record
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/etl.py:234",
    "hit_condition": "%100",
    "log_message": "Processed {records_count} records, current: {record.id}"
  }
}
```

#### Debugging Race Conditions

**Break on specific thread state:**

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/worker.py:156",
    "condition": "len(active_workers) > 5"
  }
}
```

#### Performance Investigation

**Log execution timing:**

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:89",
    "log_message": "Request started: {time.time()}"
  }
}

{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:145",
    "log_message": "Request completed: {time.time()}"
  }
}
```

#### User-Specific Debugging

**Break for specific user:**

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/auth.py:67",
    "condition": "request.user_id == 'debug_user_123'"
  }
}
```

#### Error Condition Detection

**Break on error state:**

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/handler.py:234",
    "condition": "error_count > 0 or status == 'failed'"
  }
}
```

### Breakpoint Verification

All breakpoints are verified by the debug adapter:

**Verified breakpoint:**

```json
{
  "verified": true,
  "message": "Breakpoint set successfully"
}
```

**Unverified breakpoint:**

```json
{
  "verified": false,
  "message": "Breakpoint could not be verified - line may not be executable"
}
```

Common reasons for unverified breakpoints:

- Line contains only comments
- Line is a blank line
- Line is in an unreachable code block
- File path is incorrect

### Error Handling

**Invalid location format:**

```json
{
  "error": "InvalidParameterError",
  "message": "Breakpoint location must include line number (e.g., 'file.py:10')",
  "param": "location"
}
```

**Invalid hit condition:**

```json
{
  "error": "InvalidParameterError",
  "message": "Invalid hit condition format: abc",
  "param": "hit_condition"
}
```

**Unsupported hit condition mode:**

```json
{
  "error": "UnsupportedOperationError",
  "message": "The python adapter doesn't support LESS_EQUAL hit conditions. Supported: EXACT, MODULO, GREATER_THAN"
}
```

### Complete Examples

#### Example 1: Debug Pricing Logic

```python
# Set breakpoint to check pricing calculation
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/pricing.py:89",
    "condition": "total > 10000"
  }
}

# When hit, inspect the variables
{
  "tool": "inspect",
  "arguments": {
    "target": "locals"
  }
}

# Modify discount for testing
{
  "tool": "variable",
  "arguments": {
    "action": "set",
    "name": "discount_rate",
    "value": "0.15"
  }
}

# Continue execution
{
  "tool": "execute",
  "arguments": {
    "action": "continue"
  }
}
```

#### Example 2: Monitor Loop Performance

```python
# Log every 50th iteration
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:45",
    "hit_condition": "%50",
    "log_message": "Iteration {i}: processed {count} items, elapsed: {elapsed_time}s"
  }
}

# Break on potential issue
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/processor.py:67",
    "condition": "processing_time > 5.0"
  }
}
```

#### Example 3: Debug Authentication

```python
# Break on failed login for specific user
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/auth.py:123",
    "condition": "username == 'alice' and login_result == False"
  }
}

# When paused, check auth state
{
  "tool": "inspect",
  "arguments": {
    "target": "expression",
    "expression": "auth_state.__dict__"
  }
}
```

#### Example 4: Production Debugging

```python
# Logpoint to track API calls without pausing
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:234",
    "log_message": "API call: {request.method} {request.path} - User: {request.user_id}"
  }
}

# Conditional break only for errors
{
  "tool": "breakpoint",
  "arguments": {
    "action": "set",
    "location": "/app/api.py:345",
    "condition": "response.status >= 500",
    "log_message": "Server error: {response.status} - {error_message}"
  }
}
```

### Best Practices

**1. Start with initial breakpoints**

Set breakpoints when starting your session to ensure deterministic behavior:

```python
{
  "tool": "session_start",
  "arguments": {
    "target": "main.py",
    "breakpoints": [
      {"file": "app.py", "line": 45},
      {"file": "handler.py", "line": 89, "condition": "error_count > 0"}
    ]
  }
}
```

**2. Use conditions to reduce noise**

Instead of breaking every time, use conditions:

```python
# Bad: breaks every iteration
{"location": "loop.py:45"}

# Good: breaks on interesting iterations
{"location": "loop.py:45", "condition": "i % 100 == 0 or error_occurred"}
```

**3. Use logpoints for observation**

Prefer logpoints over breakpoints when you just need visibility:

```python
# Observe without interrupting
{
  "location": "worker.py:67",
  "log_message": "Worker {worker_id} processing job {job.id}"
}
```

**4. Combine hit conditions with conditions**

For precise control:

```python
{
  "location": "handler.py:89",
  "condition": "status == 'error'",
  "hit_condition": ">5"  # Only after error has occurred 5+ times
}
```

**5. List breakpoints regularly**

Keep track of active breakpoints:

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "list"
  }
}
```

**6. Clean up when done**

Remove unnecessary breakpoints to avoid confusion:

```python
{
  "tool": "breakpoint",
  "arguments": {
    "action": "remove",
    "location": "/app/temp.py:45"
  }
}
```
