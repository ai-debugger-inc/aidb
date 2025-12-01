---
myst:
  html_meta:
    description lang=en: Session management tools in AI Debugger MCP - init, session_start, and session.
---

# Session Management Tools

Session management is the foundation of AI-powered debugging workflows. The AI Debugger MCP provides three core tools for managing debug sessions: `init` for setup, `session_start` for launching debuggers, and `session` for lifecycle management.

## init - Initialize Debugging Context

The `init` tool is the **mandatory first step** for all debugging operations. It sets up language-specific context, discovers workspace configurations, and provides example debugging templates without creating an actual debug session.

### Overview

**When to use:**

- At the start of every debugging workflow (required)
- When switching between languages
- To discover available VS Code launch configurations
- To validate debug adapter availability

**Key capabilities:**

- Example configurations for common frameworks (pytest, django, jest, spring, etc.)
- VS Code launch.json discovery and integration
- Multi-root workspace support
- Language-specific debugging templates
- Adapter availability checking

### Key Parameters

| Parameter            | Type    | Description                                                                                                             |
| -------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------- |
| `language`           | string  | **Required**. Programming language: `python`, `javascript`, or `java` |
| `mode`               | string  | Debug mode: `launch` (default), `attach`, or `remote_attach`                                                            |
| `framework`          | string  | Optional framework name to get example configuration (pytest, django, jest, spring, etc.)                               |
| `workspace_root`     | string  | Root directory for discovering launch.json and project context                                                          |
| `workspace_roots`    | array   | Multiple workspace roots for multi-root/microservices projects                                                          |
| `launch_config_name` | string  | Name of specific VS Code launch configuration to reference                                                              |
| `verbose`            | boolean | Include educational content and key concepts (default: false)                                                           |

### Examples

#### Example 1: Basic Python Initialization

```json
{
  "language": "python"
}
```

**Response includes:**

- Generic Python debugging examples
- Standard breakpoint patterns
- Command-line debugging setup
- Adapter installation status

#### Example 2: Framework-Aware Initialization (pytest)

```json
{
  "language": "python",
  "framework": "pytest",
  "workspace_root": "/path/to/project"
}
```

**Response includes:**

- Example pytest launch configuration:
  ```json
  {
    "target": "pytest",
    "args": ["-xvs", "tests/test_example.py::TestClass::test_method"],
    "env": {"PYTEST_CURRENT_TEST": "true"},
    "breakpoints": [
      {"file": "/path/to/src/calculator.py", "line": 15},
      {"file": "/path/to/src/utils/validator.py", "line": 42}
    ]
  }
  ```
- Common breakpoint suggestions for testing
- Typical pytest environment variables
- Virtual environment detection

#### Example 3: VS Code Integration with Multi-Root Workspace

```json
{
  "language": "javascript",
  "workspace_roots": [
    "/path/to/frontend",
    "/path/to/backend"
  ],
  "launch_config_name": "Debug Express Server"
}
```

**Response includes:**

- Launch configuration from `.vscode/launch.json`
- Multi-root workspace path mappings
- Framework detection across workspaces
- Port availability checks

#### Example 4: Remote Debugging Setup

```json
{
  "language": "java",
  "mode": "remote_attach",
  "framework": "spring",
  "verbose": true
}
```

**Response includes:**

- Remote debugging connection details
- JVM arguments for debug mode: `-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005`
- Spring Boot debugging best practices
- Port forwarding examples
- Educational content about attach modes

### Best Practices

1. **Always call init first** - It's a hard requirement. Attempting to start a session without initialization will fail.

1. **Specify framework for targeted examples** - Get example configurations for your framework:

   ```json
   // Generic examples
   {"language": "python"}

   // Framework-specific examples
   {"language": "python", "framework": "django"}
   ```

1. **Use workspace_root for project discovery** - Enables automatic detection of:

   - Virtual environments (Python)
   - package.json and node_modules (JavaScript)
   - pom.xml and build.gradle (Java)
   - VS Code launch configurations

1. **Check adapter status** - The response includes adapter availability:

   ```json
   {
     "adapter_status": {
       "available": false,
       "reason": "Python adapter not installed",
       "suggestions": [
         "Use download_adapter tool with language='python'"
       ]
     }
   }
   ```

1. **Leverage VS Code configurations** - If your project has launch.json:

   ```json
   {
     "language": "python",
     "workspace_root": "${workspace}",
     "launch_config_name": "Python: Debug Tests"
   }
   ```

## session_start - Start Debug Session

The `session_start` tool creates and starts a debug session in a single operation. It supports three launch modes and can set breakpoints before execution begins - a critical feature for AI debugging workflows.

### Overview

**When to use:**

- After calling `init` to start debugging
- To launch a new process with debugging enabled
- To attach to a running process by PID
- To connect to a remote debug server

**Key capabilities:**

- **Initial breakpoints** - Set breakpoints BEFORE execution starts (killer feature!)
- Three launch modes: launch, attach, remote_attach
- VS Code launch.json integration
- Event subscriptions (breakpoint hits, exceptions, termination)
- Advanced breakpoint types (conditional, hit count, logpoints)
- Multi-session support (debug multiple programs simultaneously)

### Key Parameters

#### Launch Mode Parameters

| Parameter | Type    | Required For  | Description                                      |
| --------- | ------- | ------------- | ------------------------------------------------ |
| `target`  | string  | launch        | Entrypoint file/executable that starts execution |
| `pid`     | integer | attach        | Process ID to attach to (local attach)           |
| `host`    | string  | remote_attach | Host to connect to for remote debugging          |
| `port`    | integer | remote_attach | Port to connect to for remote debugging          |

#### Common Parameters

| Parameter            | Type   | Description                                                                                             |
| -------------------- | ------ | ------------------------------------------------------------------------------------------------------- |
| `language`           | string | Programming language (python, javascript, java). Optional - inferred from init or auto-detected        |
| `breakpoints`        | array  | **Initial breakpoints** set before execution starts                                                     |
| `args`               | array  | Command-line arguments (launch mode)                                                                    |
| `env`                | object | Environment variables (launch mode)                                                                     |
| `cwd`                | string | Working directory (launch mode)                                                                         |
| `workspace_root`     | string | Workspace root directory                                                                                |
| `launch_config_name` | string | VS Code launch configuration name                                                                       |
| `session_id`         | string | Optional session ID (generated if not provided)                                                         |
| `subscribe_events`   | array  | Events to subscribe to: `exception` (breakpoint/terminated auto-subscribed)                             |

#### Breakpoint Specification

Each breakpoint in the `breakpoints` array supports:

| Field           | Type    | Required | Description                                             |
| --------------- | ------- | -------- | ------------------------------------------------------- |
| `file`          | string  | Yes      | Absolute path to file                                   |
| `line`          | integer | Yes      | Line number (1-indexed)                                 |
| `condition`     | string  | No       | Break only when condition is true (e.g., `x > 5`)       |
| `hit_condition` | string  | No       | Break after N hits (e.g., `>5` or `%10` for every 10th) |
| `log_message`   | string  | No       | Log message instead of pausing (logpoint)               |

### Examples

#### Example 1: Launch Python Script with Initial Breakpoints

This is the most common AI debugging pattern - start with breakpoints already set.

```json
{
  "language": "python",
  "target": "main.py",
  "breakpoints": [
    {
      "file": "/path/to/src/calculator.py",
      "line": 15,
      "comment": "Utility function we want to inspect"
    },
    {
      "file": "/path/to/src/validator.py",
      "line": 42,
      "condition": "user_id == 123",
      "comment": "Only break for specific user"
    },
    {
      "file": "/path/to/config/loader.py",
      "line": 10,
      "comment": "Configuration loading logic"
    }
  ],
  "cwd": "/path/to/project",
  "env": {
    "DEBUG": "1",
    "LOG_LEVEL": "DEBUG"
  }
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Debug session a1b2c3d4 started in launch mode",
  "data": {
    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "mode": "launch",
    "language": "python",
    "target": "main.py",
    "breakpoints_set": 3,
    "execution_state": {
      "status": "paused",
      "breakpoints_active": true,
      "stop_reason": "breakpoint"
    },
    "code_snapshot": {
      "formatted": "  14   \n  15 > def calculate(amount):\n  16       return amount * 1.1"
    },
    "location": "/path/to/src/calculator.py:15"
  },
  "next_steps": [
    "Use inspect(target='locals') to see local variables",
    "Use step(action='over') to step to next line",
    "Use variable(action='get', expression='x') to evaluate expressions"
  ]
}
```

:::{tip}
**Key insight:** The program started and immediately paused at the first breakpoint. You can now inspect state, step through code, or continue execution.
:::

#### Example 2: Pytest with Framework-Specific Breakpoints

```json
{
  "language": "python",
  "target": "pytest",
  "args": ["-xvs", "tests/test_calculator.py::test_add"],
  "breakpoints": [
    {
      "file": "/path/to/src/calculator.py",
      "line": 25,
      "comment": "The actual implementation being tested"
    },
    {
      "file": "/path/to/tests/test_calculator.py",
      "line": 15,
      "condition": "result != expected",
      "comment": "Break only when test assertion would fail"
    }
  ],
  "env": {
    "PYTEST_CURRENT_TEST": "true"
  }
}
```

**Why this works:**

- `target` is `pytest`, not the test file (pytest is the entry point)
- Breakpoints are in DIFFERENT files from the target
- The conditional breakpoint catches failures before assertions

#### Example 3: Local Attach to Running Process

Attach to a running process by PID without restarting it. Breakpoints are set immediately after attaching.

::::{tab-set}

:::{tab-item} Python
```json
{
  "language": "python",
  "pid": 12345,
  "breakpoints": [
    {
      "file": "/path/to/src/server.py",
      "line": 78,
      "comment": "Request handler in running Flask/Django server"
    }
  ]
}
```

**Use case:** Attach to a running Python web server (Flask, Django, FastAPI) without restarting it.
:::

:::{tab-item} JavaScript
```json
{
  "language": "javascript",
  "pid": 67890,
  "breakpoints": [
    {
      "file": "/path/to/routes/api.js",
      "line": 45,
      "comment": "Express route handler"
    }
  ]
}
```

**Use case:** Attach to a running Node.js server (Express, Nest.js) that was started with `--inspect`.
:::

:::{tab-item} Java
```json
{
  "language": "java",
  "pid": 23456,
  "breakpoints": [
    {
      "file": "/path/to/src/main/java/com/example/ApiController.java",
      "line": 67,
      "comment": "Spring Boot controller method"
    }
  ]
}
```

**Use case:** Attach to a running Java application (Spring Boot) that was started with JVM debug flags.
:::

::::

#### Example 4: Remote Attach to Containerized App

```json
{
  "language": "java",
  "host": "localhost",
  "port": 5005,
  "breakpoints": [
    {
      "file": "/app/src/main/java/com/example/UserService.java",
      "line": 45,
      "comment": "Business logic in container"
    },
    {
      "file": "/app/src/main/java/com/example/Repository.java",
      "line": 89,
      "hit_condition": ">10",
      "comment": "Break after 10th database call"
    }
  ],
  "workspace_root": "/local/project/path"
}
```

**Setup:** The containerized Java app was started with:

```bash
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005 -jar app.jar
```

#### Example 5: Advanced Breakpoints (Logpoints and Hit Conditions)

```json
{
  "language": "javascript",
  "target": "node",
  "args": ["server.js"],
  "breakpoints": [
    {
      "file": "/path/to/routes/api.js",
      "line": 34,
      "log_message": "Request received: method={req.method}, path={req.path}",
      "comment": "Logpoint - doesn't pause execution"
    },
    {
      "file": "/path/to/middleware/auth.js",
      "line": 56,
      "condition": "token === null || token === undefined",
      "comment": "Break only on authentication failures"
    },
    {
      "file": "/path/to/db/query.js",
      "line": 12,
      "hit_condition": "%100",
      "comment": "Break every 100th query for performance sampling"
    }
  ]
}
```

**Breakpoint types:**

1. **Logpoint** (line 34): Logs without pausing - perfect for observability
1. **Conditional** (line 56): Pauses only when condition is true
1. **Hit condition** (line 12): Statistical sampling for performance analysis

#### Example 6: Multi-Session Debugging

```json
// Start first session - backend
{
  "language": "python",
  "target": "uvicorn",
  "args": ["api:app", "--port", "8000"],
  "session_id": "backend-session",
  "breakpoints": [
    {"file": "/backend/api/endpoints.py", "line": 45}
  ]
}

// Start second session - worker
{
  "language": "python",
  "target": "celery",
  "args": ["-A", "tasks", "worker"],
  "session_id": "worker-session",
  "breakpoints": [
    {"file": "/backend/tasks/email.py", "line": 23}
  ]
}
```

**Use case:** Debug backend API and async worker simultaneously. Use `session(action='switch', session_id='...')` to switch between them.


### Best Practices

1. **Always set initial breakpoints** - Don't start without them:

   ```json
   // BAD: No breakpoints - program runs to completion
   {"language": "python", "target": "fast_script.py"}

   // GOOD: Breakpoint set before execution
   {
     "language": "python",
     "target": "fast_script.py",
     "breakpoints": [{"file": "/path/to/fast_script.py", "line": 5}]
   }
   ```

1. **Use absolute paths for breakpoint files** - Relative paths may not resolve:

   ```json
   // BAD
   {"file": "src/utils.py", "line": 10}

   // GOOD
   {"file": "/absolute/path/to/src/utils.py", "line": 10}
   ```

1. **Breakpoints can be in ANY file** - Not just the target:

   ```json
   {
     "target": "main.py",  // Entry point
     "breakpoints": [
       {"file": "/path/to/utils/helper.py", "line": 25},  // Utility
       {"file": "/path/to/models/user.py", "line": 78},   // Model
       {"file": "/path/to/db/query.py", "line": 156}      // Database
     ]
   }
   ```

1. **Use conditional breakpoints to reduce noise**:

   ```json
   {
     "file": "/path/to/loop.py",
     "line": 15,
     "condition": "i > 1000 and error_count > 0"
   }
   ```

1. **Leverage logpoints for observability**:

   ```json
   {
     "file": "/path/to/api.py",
     "line": 34,
     "log_message": "User {user_id} requested {endpoint} at {timestamp}"
   }
   ```

1. **Use hit conditions for sampling**:

   ```json
   // Break every 10th iteration
   {"file": "/path/to/loop.py", "line": 10, "hit_condition": "%10"}

   // Break after 5 hits
   {"file": "/path/to/init.py", "line": 5, "hit_condition": ">5"}
   ```

1. **Set workspace_root for path resolution**:

   ```json
   {
     "target": "main.py",
     "workspace_root": "/path/to/project",
     "breakpoints": [...]
   }
   ```

1. **Subscribe to exception events for error handling**:

   ```json
   {
     "target": "main.py",
     "subscribe_events": ["exception"],
     "breakpoints": [...]
   }
   ```

## session - Manage Sessions

The `session` tool provides comprehensive lifecycle management for debug sessions. It supports status checking, listing, stopping, restarting, and switching between multiple active sessions.

### Overview

**When to use:**

- Check if a session is running, paused, or terminated
- List all active debug sessions
- Stop a debug session and clean up resources
- Restart a session with the same configuration
- Switch between multiple concurrent sessions

**Key capabilities:**

- Multi-session orchestration
- Restart with breakpoint preservation
- Native vs. emulated restart (adapter-dependent)
- Session status introspection
- Resource cleanup

### Key Parameters

| Parameter          | Type    | Description                                                                          |
| ------------------ | ------- | ------------------------------------------------------------------------------------ |
| `action`           | string  | Action to perform: `status`, `list`, `stop`, `restart`, `switch`, `cleanup`, `subscribe` (default: `status`) |
| `session_id`       | string  | Target session ID for stop/restart/switch operations                                 |
| `keep_breakpoints` | boolean | Keep existing breakpoints on restart (default: true)                                 |

### Actions

#### status - Check Session Status

Query the current state of a debug session.

**Parameters:**

- `session_id` (optional): Session to check (uses default if omitted)

**Example:**

```json
{
  "action": "status"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Session paused at /path/to/src/calculator.py:15",
  "data": {
    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "status": "paused",
    "language": "python",
    "current_location": "/path/to/src/calculator.py:15",
    "breakpoint_count": 3,
    "execution_state": {
      "status": "paused",
      "breakpoints_active": true,
      "stop_reason": "breakpoint"
    }
  }
}
```

**Status values:**

- `running` - Program is executing
- `paused` - Stopped at breakpoint or step
- `terminated` - Session ended
- `idle` - Session not started

#### list - List All Sessions

Show all active debug sessions.

**Example:**

```json
{
  "action": "list"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "3 active sessions",
  "data": {
    "count": 3,
    "sessions": [
      {
        "session_id": "a1b2c3d4",
        "state": "paused",
        "language": "python",
        "active": true,
        "is_default": true
      },
      {
        "session_id": "e5f6g7h8",
        "state": "running",
        "language": "javascript",
        "active": true,
        "is_default": false
      },
      {
        "session_id": "i9j0k1l2",
        "state": "terminated",
        "language": "java",
        "active": false,
        "is_default": false
      }
    ]
  }
}
```

#### stop - Stop Session

Terminate a debug session and clean up resources.

**Parameters:**

- `session_id` (optional): Session to stop (uses default if omitted)

**Example:**

```json
{
  "action": "stop",
  "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Debug session stopped: User requested stop",
  "data": {
    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "terminated_reason": "User requested stop",
    "cleanup_performed": true
  },
  "next_steps": [
    "Start a new session with session_start",
    "Or switch to another active session"
  ]
}
```

**Cleanup performed:**

- DAP disconnect messages sent
- Debug adapter processes terminated
- Pooled resources released (e.g., JDT LS bridges)
- Port allocations freed

#### restart - Restart Session

Restart a session with the same configuration. Attempts native restart if the debug adapter supports it, otherwise performs an emulated restart (stop + start).

**Parameters:**

- `session_id` (optional): Session to restart (uses default if omitted)
- `keep_breakpoints` (default: true): Preserve existing breakpoints

**Example:**

```json
{
  "action": "restart",
  "keep_breakpoints": true
}
```

**Response (Native Restart):**

```json
{
  "success": true,
  "summary": "Session a1b2c3d4 restarted natively with 3 breakpoints",
  "data": {
    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "method": "native",
    "kept_breakpoints": true,
    "breakpoint_count": 3
  }
}
```

**Response (Emulated Restart):**

```json
{
  "success": true,
  "summary": "Session a1b2c3d4 restarted via stop+start with 3 breakpoints",
  "data": {
    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "method": "emulated",
    "kept_breakpoints": true,
    "breakpoint_count": 3
  }
}
```

**Native vs. Emulated:**

- **Native**: Debug adapter supports DAP `restart` request - faster, preserves more state
- **Emulated**: Falls back to stop + start with same parameters - works everywhere

#### switch - Switch Active Session

Switch the active context to a different session. Useful when debugging multiple programs simultaneously.

**Parameters:**

- `session_id` (required): Session to switch to

**Example:**

```json
{
  "action": "switch",
  "session_id": "backend-session"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Switched to session backend-session",
  "data": {
    "session_id": "backend-session",
    "previous_session": "frontend-session",
    "state": "paused",
    "language": "python"
  }
}
```

**Use case:** When debugging multiple services (e.g., frontend and backend), switch between them without stopping either.

#### cleanup - Clean Up Orphaned Sessions

Clean up stale or orphaned debug sessions that may have failed to terminate properly.

**Example:**

```json
{
  "action": "cleanup"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Cleaned up 2 orphaned sessions",
  "data": {
    "cleaned_count": 2,
    "remaining_active": 1
  }
}
```

**Use case:** Recover from failed debug sessions or clean up resources when sessions weren't properly stopped.

#### subscribe - Subscribe to Debug Events

Subscribe to specific debug events for real-time notifications.

**Example:**

```json
{
  "action": "subscribe",
  "session_id": "main-session"
}
```

**Note:** The `breakpoint` and `terminated` events are automatically subscribed. Use `subscribe_events` in `session_start` to subscribe to additional events like `exception`.

### Examples

#### Example 1: Session Status Check

```json
{
  "action": "status"
}
```

**Use case:** Check if the program is paused, running, or terminated before deciding next action.

#### Example 2: List All Sessions

```json
{
  "action": "list"
}
```

**Use case:** See all active debug sessions when managing multiple programs (e.g., microservices, frontend + backend).

#### Example 3: Stop Specific Session

```json
{
  "action": "stop",
  "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab"
}
```

**Use case:** Clean up a specific session while leaving others running.




### Best Practices

1. **Check status before operations** - Avoid errors by verifying session state:

   ```json
   // Check first
   {"action": "status"}

   // Then operate based on state
   {"action": "restart"}
   ```

1. **Use session_id for explicit control** - Be specific in multi-session scenarios:

   ```json
   // Implicit (uses default)
   {"action": "stop"}

   // Explicit (better for multi-session)
   {"action": "stop", "session_id": "backend"}
   ```

1. **List sessions periodically** - Track active sessions to avoid leaks:

   ```json
   {"action": "list"}
   ```

1. **Always stop sessions when done** - Clean up resources:

   ```json
   {"action": "stop"}
   ```

1. **Preserve breakpoints on restart** - Usually you want them:

   ```json
   {"action": "restart", "keep_breakpoints": true}
   ```

1. **Handle terminated sessions gracefully** - Check status first:

   ```json
   {"action": "status"}
   // If terminated, start new session instead of restarting
   ```

## Common Patterns

### Common Workflow Patterns

**Basic Single Session:**
1. Initialize → Start with breakpoints → Debug → Stop

**Multi-Session:**
1. Initialize → Start multiple sessions → Switch between them → Stop all

**Restart-Based:**
1. Start → Debug → Restart (keep or clear breakpoints) → Debug again

See [Advanced Workflows](../advanced-workflows.md) for detailed multi-session and remote debugging examples.

## Troubleshooting

### Init Issues

**Problem:** "Adapter not available"

```json
{
  "adapter_status": {
    "available": false,
    "reason": "Python adapter not installed"
  }
}
```

**Solution:** Install the adapter:

```json
{
  "action": "download",
  "language": "python"
}
```

### Session Start Issues

**Problem:** "Init required" error

**Solution:** Always call `init` first:

```json
// 1. Init first
{"language": "python"}

// 2. Then start
{"language": "python", "target": "main.py"}
```

**Problem:** Program exits before hitting breakpoints

**Solution:** Set breakpoints in `session_start`:

```json
{
  "target": "fast_script.py",
  "breakpoints": [
    {"file": "/path/to/fast_script.py", "line": 1}
  ]
}
```

**Problem:** Breakpoints not hit

**Solution:** Check file paths are absolute:

```json
// BAD
{"file": "src/utils.py", "line": 10}

// GOOD
{"file": "/absolute/path/to/src/utils.py", "line": 10}
```

### Session Management Issues

**Problem:** Session already terminated

**Solution:** Check status first:

```json
{"action": "status"}
// If terminated, start new session instead
```

**Problem:** Too many sessions

**Solution:** List and clean up:

```json
{"action": "list"}
// Stop unused sessions
{"action": "stop", "session_id": "old-session-id"}
```
