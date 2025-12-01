---
myst:
  html_meta:
    description lang=en: Execution control tools in AI Debugger MCP - execute, step, and run_until.
---

# Execution Control Tools

The execution control tools manage program flow during debugging. These tools allow you to start, stop, and navigate through your code at various levels of granularity.

## Overview

Three core tools control execution:

- **execute**: Run or continue program execution with automatic breakpoint detection
- **step**: Navigate code line-by-line with precision control
- **run_until**: Jump to specific locations using temporary breakpoints

All execution control tools provide execution state information including:

- Execution status (stopped_at_breakpoint, running, terminated, etc.)
- Stop reason (breakpoint, exception, step, completion)
- Code context (formatted code snippet)
- Next-step recommendations

## execute - Run Program

The `execute` tool starts or continues program execution. It intelligently handles breakpoints and provides detailed execution state information.

### Actions

**run**

- Restarts program execution from the beginning
- Preserves existing breakpoints
- Useful for re-running with different breakpoint configurations
- Not all debug adapters support restart (error returned if unsupported)

**continue** (default)

- Continues execution from current position
- Runs until next breakpoint, exception, or program completion
- Most common execution action

### Parameters

| Parameter     | Type    | Required | Default    | Description                                                         |
| ------------- | ------- | -------- | ---------- | ------------------------------------------------------------------- |
| action        | string  | No       | "continue" | Action to perform: "run" or "continue"                              |
| wait_for_stop | boolean | No       | auto       | Wait for breakpoint/stop event. Auto-enabled when breakpoints exist |
| session_id    | string  | No       | current    | Session to execute                                                  |

### Execution State Response

Every execution operation returns detailed state information:

```json
{
  "execution_state": {
    "status": "stopped_at_breakpoint",
    "breakpoints_active": true,
    "stop_reason": "breakpoint"
  },
  "code_snapshot": {
    "formatted": "  41   def calculate_tax(amount):\n  42 >     result = calculate_tax(amount)\n  43       return result"
  },
  "location": "src/app.py:42"
}
```

### Examples

#### Starting Program Execution

```python
# Start program from beginning
execute(action="run")

# Response:
# {
#   "summary": "Execution run started",
#   "data": {
#     "execution_state": {
#       "status": "running",
#       "breakpoints_active": false,
#       "stop_reason": null
#     }
#   }
# }
```

#### Continuing from Breakpoint

```python
# Continue execution (runs until next breakpoint or completion)
execute(action="continue")

# Response when hitting breakpoint:
# {
#   "summary": "Stopped at breakpoint: src/utils.py:15\n\n
#              15 >  def validate_input(data):\n
#              16        if not data:",
#   "data": {
#     "location": "src/utils.py:15",
#     "execution_state": {
#       "status": "stopped_at_breakpoint",
#       "breakpoints_active": true,
#       "stop_reason": "breakpoint"
#     },
#     "code_snapshot": {
#       "formatted": "  14   \n  15 >  def validate_input(data):\n  16        if not data:"
#     }
#   },
#   "next_steps": [
#     {
#       "tool": "inspect",
#       "description": "Examine local variables",
#       "when": "to understand current state"
#     },
#     {
#       "tool": "step",
#       "description": "Step through function execution",
#       "when": "to trace execution flow"
#     }
#   ]
# }
```

#### Running to Completion

```python
# Continue without breakpoints
execute(action="continue")

# Response when program completes:
# {
#   "summary": "Program execution completed",
#   "data": {
#     "execution_state": {
#       "status": "terminated",
#       "breakpoints_active": false,
#       "stop_reason": null
#     }
#   },
#   "next_steps": [
#     {
#       "tool": "session",
#       "description": "Start new debugging session",
#       "when": "to debug again"
#     }
#   ]
# }
```

### When to Use

**Use execute when:**

- Starting initial program execution
- Continuing after examining state at a breakpoint
- Running to the next breakpoint or completion
- Restarting program with same breakpoint configuration

**Don't use execute when:**

- You need line-by-line control (use `step` instead)
- You want to jump to a specific line (use `run_until` instead)
- Program is not yet started (use `session_start` first)

### Automatic Features

**Breakpoint Detection**: The `wait_for_stop` parameter automatically enables when breakpoints are set, ensuring execution pauses at breakpoints without manual configuration.

**Stop Reason Classification**: Automatically detects and reports why execution stopped:

- `breakpoint`: Hit a configured breakpoint
- `exception`: Encountered an exception
- `step`: Stopped after step operation
- `entry`: Paused at program entry point

**Code Context**: Automatically captures and formats code around the stop location when execution pauses.

## step - Step Through Code

The `step` tool provides line-by-line execution control with three levels of granularity.

### Actions

**over** (default)

- Executes current line without entering function calls
- Steps over function/method invocations
- Stays at current call stack level
- Fastest way to move through code sequentially

**into**

- Steps into function/method calls
- Descends into call stack
- Useful for debugging function internals
- Shows execution flow through function boundaries

**out**

- Completes current function and returns to caller
- Ascends call stack
- Useful for exiting deep call stacks quickly
- Stops at the line after the function call

:::{tip}
**Choosing the right step mode:**
- **over**: When you want to see what happens next but don't care about function internals (most common)
- **into**: When the bug might be inside the function call you're about to execute
- **out**: When you've seen enough of the current function and want to return to the caller

Avoid stepping through framework code - set breakpoints in your code instead!
:::

### Parameters

| Parameter  | Type    | Required | Default | Description                           |
| ---------- | ------- | -------- | ------- | ------------------------------------- |
| action     | string  | No       | "over"  | Step action: "over", "into", or "out" |
| count      | integer | No       | 1       | Number of steps to execute            |
| session_id | string  | No       | current | Session to step in                    |

### Multi-Step Support

Execute multiple steps in a single operation using the `count` parameter:

```python
# Step over 5 lines
step(action="over", count=5)
```

The debugger executes all steps and returns state after the final step. If execution terminates before completing all steps, it returns the state at termination.

### Examples

#### Stepping Over Function Calls

```python
# Current location: app.py:42
# 42 >  result = calculate_tax(amount)
# 43    print(result)

step(action="over")

# Response:
# {
#   "summary": "Stepped over to app.py:43\n\n
#              43 >  print(result)",
#   "data": {
#     "location": "app.py:43",
#     "execution_state": {
#       "status": "stopped_after_step",
#       "breakpoints_active": true,
#       "stop_reason": "step"
#     },
#     "code_snapshot": {
#       "formatted": "  42       result = calculate_tax(amount)\n  43 >     print(result)\n  44       return 0"
#     }
#   }
# }
```

#### Stepping Into Functions

```python
# Current location: app.py:42
# 42 >  result = calculate_tax(amount)

step(action="into")

# Response (now inside calculate_tax):
# {
#   "summary": "Stepped into to utils.py:10\n\n
#              10 > def calculate_tax(amount):",
#   "data": {
#     "location": "utils.py:10",
#     "execution_state": {
#       "status": "stopped_after_step",
#       "breakpoints_active": true,
#       "stop_reason": "step"
#     }
#   }
# }
```

#### Stepping Out of Functions

```python
# Current location: utils.py:15 (inside calculate_tax)
# 15 >      return amount * tax_rate

step(action="out")

# Response (back in caller):
# {
#   "summary": "Stepped out to app.py:42",
#   "data": {
#     "location": "app.py:42",
#     "execution_state": {
#       "status": "stopped_after_step",
#       "breakpoints_active": true,
#       "stop_reason": "step"
#     }
#   }
# }
```

#### Multi-Step Navigation

```python
# Step through a loop iteration
step(action="over", count=3)

# Response shows location after 3 steps:
# {
#   "summary": "Stepped over to app.py:48",
#   "data": {
#     "location": "app.py:48"
#   }
# }
```

### When to Use

**Use step when:**

- Examining execution flow line-by-line
- Debugging logic errors in algorithms
- Understanding how code executes through branches
- Verifying variable state changes between lines
- Navigating call stacks (into/out)

**Step Over when:**

- Function behavior is known and working correctly
- You want to stay at the current level of abstraction
- Moving through sequential code quickly

**Step Into when:**

- Investigating function implementation details
- Debugging function internals
- Following execution into library code
- Understanding call chains

**Step Out when:**

- Current function behavior is understood
- You've gone too deep in the call stack
- Want to return to higher-level context quickly
- Completing execution of uninteresting functions

### Requirements

The debugger must be paused before stepping. If execution is running, step operations return an error suggesting to set a breakpoint first.

### Performance Considerations

Each step operation involves:

1. DAP protocol round-trip to debug adapter
1. State synchronization with IDE
1. Code context retrieval

For large step counts, consider using `run_until` with a target line instead, as it uses temporary breakpoints which can be more efficient.

## run_until - Temporary Breakpoints

The `run_until` tool runs execution to a specific location using an automatically managed temporary breakpoint.

### How It Works

1. Sets a temporary breakpoint at target location
1. Continues execution
1. Automatically removes the temporary breakpoint when hit
1. Returns execution state

This provides a quick way to jump to specific code locations without permanently modifying breakpoint configuration.

:::{tip}
**When to use run_until vs step:**
- Use `run_until` to skip over 10+ lines of code you know works correctly
- Use `step` with `count` for 2-5 lines when you might need to inspect intermediate state
- Use `run_until` with a condition to jump to a specific state without manual stepping

**Warning:** If the target line isn't in the execution path, the program will complete without reaching it!
:::

### Parameters

| Parameter             | Type   | Required | Default | Description                                        |
| --------------------- | ------ | -------- | ------- | -------------------------------------------------- |
| location              | string | Yes      | -       | Target location: "file:line" or line number        |
| alternative_locations | array  | No       | -       | Additional locations to stop at (any hit triggers) |
| condition             | string | No       | -       | Optional condition for temporary breakpoint        |
| session_id            | string | No       | current | Session to run in                                  |

### Location Formats

**File and Line**:

```python
run_until(location="src/app.py:42")
```

**Line Only** (requires paused execution):

```python
run_until(location="42")  # Uses current file
```

The line-only format automatically determines the current file from the call stack.

### Examples

#### Jumping to Specific Line

```python
# Current location: app.py:10
# Want to jump to app.py:50

run_until(location="app.py:50")

# Response:
# {
#   "summary": "Paused at app.py:50",
#   "data": {
#     "reached_target": true,
#     "current_location": "app.py:50",
#     "execution_state": {
#       "status": "paused",
#       "breakpoints_active": true,
#       "stop_reason": "breakpoint"
#     },
#     "code_snapshot": {
#       "formatted": "  49   \n  50 >     process_results(data)\n  51       return"
#     }
#   }
# }
```

#### Conditional Temporary Breakpoint

```python
# Run until line 25, but only when x > 100
run_until(location="app.py:25", condition="x > 100")

# Response:
# {
#   "summary": "Paused at app.py:25",
#   "data": {
#     "reached_target": true,
#     "current_location": "app.py:25"
#   }
# }
```

#### Skipping to Loop Exit

```python
# Current location: inside a loop at line 20
# Loop exits at line 30

run_until(location="30")  # Line-only format

# Response:
# {
#   "summary": "Paused at app.py:30",
#   "data": {
#     "reached_target": true
#   }
# }
```

#### Multiple Target Locations

```python
# Run until hitting any of these locations
run_until(
    location="app.py:50",
    alternative_locations=["app.py:75", "utils/helper.py:20"]
)

# Response:
# {
#   "summary": "Paused at utils/helper.py:20",
#   "data": {
#     "reached_target": true,
#     "current_location": "utils/helper.py:20"
#   }
# }
```

The `alternative_locations` parameter is useful when control flow could take multiple paths and you want to stop at whichever is reached first.

#### Target Not Reached

```python
# Target location is after program completion
run_until(location="app.py:999")

# Response:
# {
#   "summary": "Program completed without reaching target location",
#   "data": {
#     "reached_target": false,
#     "stop_reason": "completed",
#     "execution_state": {
#       "status": "terminated",
#       "breakpoints_active": false,
#       "stop_reason": "completed"
#     }
#   }
# }
```

### When to Use

**Use run_until when:**

- Jumping past known working code
- Skipping loop iterations to reach specific iteration
- Moving to exception handler code
- Navigating to function exit point
- Testing specific code path with condition

**Don't use run_until when:**

- You need permanent breakpoint (use `breakpoint` tool instead)
- Target is in different execution path (might not reach it)
- You want to inspect state along the way (use `step` instead)

### Differences from Regular Breakpoints

| Feature       | run_until                | breakpoint                |
| ------------- | ------------------------ | ------------------------- |
| Persistence   | Temporary (auto-removed) | Permanent (until cleared) |
| Use Case      | Quick one-time jump      | Repeated debugging        |
| Management    | Automatic cleanup        | Manual management         |
| Multiple Hits | Stops on first hit       | Stops every time          |

### Automatic Cleanup

The temporary breakpoint is removed whether or not the target is reached:

- Hit: Removed immediately after stopping
- Not Hit: Removed when execution completes or stops elsewhere
- Error: Best-effort removal (logged if fails)

This ensures temporary breakpoints don't interfere with subsequent debugging operations.

## Common Workflows

### Debugging Loop Iterations

```python
# 1. Set breakpoint at loop start
breakpoint(action="set", location="app.py:20")

# 2. Run to breakpoint
execute(action="continue")

# 3. Examine first iteration
inspect(target="locals")

# 4. Jump to 10th iteration
run_until(location="app.py:20", condition="i == 10")

# 5. Step through critical section
step(action="over", count=3)
```

### Navigating Call Stacks

```python
# 1. Hit breakpoint in deep function
# Current location: utils/helpers.py:45

# 2. Step into nested function
step(action="into")

# 3. Examine state
inspect(target="locals")

# 4. Return to original caller
step(action="out")
step(action="out")  # Exit two levels
```

### Exception Investigation

```python
# 1. Program stops at exception
# execute() returned: "Exception occurred at app.py:42"

# 2. Examine variables at exception point
inspect(target="locals")

# 3. Check call stack
inspect(target="stack")

# 4. Restart and stop before exception
execute(action="run")
run_until(location="app.py:41")  # Line before exception

# 5. Step through to see what causes exception
step(action="over")
```

### Performance Analysis

```python
# 1. Run to start of slow function
run_until(location="app.py:100")

# 2. Step into to see which subfunctions are slow
step(action="into")

# 3. Step over quickly through known fast code
step(action="over", count=5)

# 4. Step into suspected slow function
step(action="into")
```

## Error Handling

### Not Paused Error

Stepping requires paused execution:

```python
# Program is running
step(action="over")

# Error response:
# {
#   "error": "Cannot step: debugger is not paused",
#   "suggestion": "Set a breakpoint or wait for execution to pause",
#   "data": {
#     "execution_state": {
#       "status": "running",
#       "breakpoints_active": true,
#       "stop_reason": null
#     }
#   }
# }
```

**Solution**: Set a breakpoint and run to it, or wait for existing breakpoint.

### Restart Not Supported

Some debug adapters don't support restart:

```python
execute(action="run")

# Error response:
# {
#   "error": "Restart operation not supported by this debug adapter",
#   "summary": "Restart not supported"
# }
```

**Solution**: Stop the session and start a new one.

### Invalid Location

Location must be reachable:

```python
run_until(location="app.py:9999")

# Response:
# {
#   "summary": "Program completed without reaching target location",
#   "data": {
#     "reached_target": false
#   }
# }
```

**Solution**: Verify line number exists and is in execution path.

## Best Practices

### Execution Control

1. **Use breakpoints for repeated debugging**: Set permanent breakpoints at locations you'll debug multiple times.

1. **Use run_until for one-time jumps**: Quick navigation to specific lines without breakpoint management.

1. **Combine tools effectively**: Use `execute` to run between major checkpoints, `step` for detailed inspection, and `run_until` for quick jumps.

1. **Leverage automatic wait**: Let `execute` auto-detect breakpoints rather than manually setting `wait_for_stop`.

### Stepping Strategy

1. **Start broad, narrow down**: Use `execute` to reach problem area, then `step` for details.

1. **Step over by default**: Only step into when you need to debug function internals.

1. **Use multi-step for repetitive code**: `step(count=N)` is faster than N separate step calls.

1. **Step out when too deep**: If you've stepped into unnecessary functions, step out immediately.

### Performance

1. **Minimize step operations**: Each step is a round-trip to debug adapter. Use `run_until` to skip large sections.

1. **Use conditional run_until**: Add conditions to temporary breakpoints to skip to specific program states.

1. **Batch operations**: When possible, use single operations (like `step(count=5)`) instead of multiple calls.

## Related Tools

- **session_start**: Initialize debugging session before execution
- **breakpoint**: Set permanent breakpoints for repeated use
- **inspect**: Examine program state when paused
- **variable**: Evaluate expressions and modify state
- **context**: Get intelligent suggestions for next steps
