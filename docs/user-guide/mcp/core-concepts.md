---
myst:
  html_meta:
    description lang=en: Core concepts of AI Debugger MCP - understanding the debugging workflow and tool categories.
---

# Core Concepts

This guide explains the fundamental concepts behind the AI Debugger MCP server, helping you understand how the tools work together to enable programmatic debugging through AI systems.

## Debugging Workflow Overview

The AI Debugger follows a structured workflow that mirrors how human developers debug code, but optimized for AI interaction:

### Standard Debugging Flow

```
1. Initialize Context (`init`)
   ↓
2. Create Debug Session (`session_start`)
   ↓
3. Execute Code (`execute`/`step`)
   ↓
4. Pause at Breakpoint or Step
   ↓
5. Inspect State (`inspect`/`variable`)
   ↓
6. Analyze & Decide
   ↓
7. Continue/Step/Modify (`execute`/`step`/`variable`)
   ↓
8. Repeat 3-7 until issue found
   ↓
9. Stop Session (`session` stop)
```

### Key Workflow Characteristics

**Human Cadence Operation**: The debugger operates at a human pace, not typical API speed. This means:

- Breakpoints must be set before starting execution (not "mid-flight")
- Inspection happens when the program is paused
- Stepping is one operation per line (not bulk operations)
- Each action is deliberate and observable

**Mandatory Initialization**: Every debugging session must start with the `init` tool to:

- Discover language-specific capabilities
- Load workspace configurations (`launch.json`)
- Get framework-aware examples
- Understand available debugging features

**Pause-Inspect Pattern**: Runtime introspection requires a paused program:

- Set breakpoints during session creation
- Wait for breakpoint hit or `step` to pause execution
- Inspect variables, stack, and state while paused
- Resume execution to continue

## Tool Categories

The 12 MCP tools are organized into 5 logical categories based on their purpose in the debugging workflow.

::::{grid} 1 1 2 3
:gutter: 3

:::{grid-item-card} 🚀 Context Discovery
:link: #context-discovery-entry-point
:link-type: ref

**Tool:** `init`

Mandatory first step - establishes debugging context and provides language-specific examples.
:::

:::{grid-item-card} 🔄 Session Management
:link: #session-management-lifecycle-control
:link-type: ref

**Tools:** `session_start`, `session`

Create, manage, and control debug session lifecycle with multi-session support.
:::

:::{grid-item-card} ⚡ Execution Control
:link: #execution-control-program-flow
:link-type: ref

**Tools:** `execute`, `step`, `run_until`

Control program flow with run, continue, step-over, step-into, and temporary breakpoints.
:::

:::{grid-item-card} 🔍 Inspection & Analysis
:link: #inspection-analysis-state-examination
:link-type: ref

**Tools:** `inspect`, `variable`, `breakpoint`

Examine program state, variables, and manage breakpoints during execution.
:::

:::{grid-item-card} ⚙️ Configuration & Context
:link: #configuration-context-environment
:link-type: ref

**Tools:** `config`, `context`, `adapter`

Manage configuration, get debugging context, and handle debug adapters.
:::

::::

### 1. Context Discovery (Entry Point)

**Tool**: `init`

**Purpose**: Mandatory first step that establishes debugging context.

**When to Use**:

- Always call this before any other debugging operation
- At the start of every debugging session
- When switching between languages or frameworks
- To check available capabilities

**What It Provides**:

- Language-specific initialization examples (Python, JavaScript, TypeScript, Java)
- Framework detection and patterns (`pytest`, `jest`, `django`, `spring`, etc.)
- Workspace-aware configuration discovery
- Debug adapter capabilities

**Example**:

::::{tab-set}

:::{tab-item} Python
```python
# Initialize for Python debugging
init(language="python", workspace_root="/path/to/project")

# With framework awareness
init(language="python", framework="pytest")
```
:::

:::{tab-item} JavaScript
```python
# Initialize for JavaScript debugging
init(language="javascript", workspace_root="/path/to/project")

# With framework awareness
init(language="javascript", framework="jest")
```
:::

:::{tab-item} Java
```python
# Initialize for Java debugging
init(language="java", workspace_root="/path/to/project")

# Use existing VS Code configuration
init(language="java", launch_config_name="Debug Tests")
```
:::

::::

### 2. Session Management (Lifecycle Control)

**Tools**: `session_start`, `session`

**Purpose**: Create, manage, and control debug session lifecycle.

**When to Use**:

- `session_start`: Create and start a new debug session
- `session` (status): Check current session state
- `session` (list): View all active sessions
- `session` (stop): Terminate a session
- `session` (restart): Restart with same configuration
- `session` (switch): Change active session

**What They Control**:

- Session creation with launch/attach modes
- Breakpoint initialization
- Process attachment (PID or remote host:port)
- Session state transitions
- Multi-session coordination

**Example**:

```python
# Start debugging a Python script with initial breakpoints
session_start(
    target="app.py",
    breakpoints=[
        {"file": "utils.py", "line": 42},
        {"file": "models.py", "line": 15, "condition": "x > 0"}
    ]
)

# Check session status
session(action="status")

# Attach to running process
session_start(pid=12345, language="python")
```

### 3. Execution Control (Program Flow)

**Tools**: `execute`, `step`, `run_until`

**Purpose**: Control program execution and flow.

**When to Use**:

- `execute` (run): Start execution from the beginning
- `execute` (continue): Resume execution from current position
- `step` (over): Execute current line without entering functions
- `step` (into): Enter function calls for deeper inspection
- `step` (out): Complete current function and return to caller
- `run_until`: Execute to a specific location with temporary breakpoint

**What They Control**:

- Program execution state
- Line-by-line stepping
- Function traversal
- Execution until conditions met

**Example**:

```python
# Start program execution
execute(action="run")

# Step over current line
step(action="over")

# Step into function call
step(action="into")

# Run to specific location
run_until(location="file.py:100")

# Continue to next breakpoint
execute(action="continue")
```

### 4. Inspection & Analysis (State Examination)

**Tools**: `inspect`, `variable`, `breakpoint`

**Purpose**: Examine program state, variables, and control breakpoints.

**When to Use**:

- `inspect` (locals): View local variables in current scope
- `inspect` (globals): View global variables
- `inspect` (stack): View call stack frames
- `inspect` (threads): View thread information
- `inspect` (expression): Evaluate arbitrary expressions
- `inspect` (all): Get comprehensive snapshot of all available information
- `variable` (get): Retrieve specific variable values
- `variable` (set): Modify variable values live
- `breakpoint` (set/remove/list): Manage breakpoints during execution

**What They Provide**:

- Runtime variable values and types
- Call stack with source locations
- Thread states and IDs
- Expression evaluation results
- Breakpoint verification and status

**Example**:

```python
# Inspect local variables while paused
inspect(target="locals")

# View call stack
inspect(target="stack")

# Evaluate expression
inspect(target="expression", expression="user.name")

# Get specific variable
variable(action="get", expression="config.debug")

# Modify variable during debugging
variable(action="set", name="retry_count", value="0")

# Set conditional breakpoint
breakpoint(
    action="set",
    location="auth.py:45",
    condition="user_id == 'admin'"
)
```

### 5. Configuration & Context (Environment)

**Tools**: `config`, `context`, `adapter`

**Purpose**: Manage configuration, provide debugging context, and handle debug adapters.

**When to Use**:

- `config` (show): Display current configuration
- `config` (env): View/set environment variables
- `config` (launch): Discover VS Code launch configurations
- `config` (capabilities): Check language debugging features
- `config` (adapters): Verify adapter installation
- `context`: Get intelligent next-step suggestions based on current state
- `adapter` (download): Install debug adapter for a language
- `adapter` (list): List installed adapters

**What They Provide**:

- Configuration discovery and validation
- Debugging context and session memory
- Next-step recommendations
- Adapter installation and status
- Environment variable management

**Example**:

```python
# Check Python debugging capabilities
config(action="capabilities", language="python")

# List available launch configurations
config(action="launch")

# Get context-aware suggestions
context(detail_level="detailed")

# Install missing adapter
adapter(action="download", language="javascript")

# Check adapter installation status
adapter(action="list")
```

## Session Lifecycle

Understanding session states helps you know when to use which tools.

### Session States

```
INITIALIZED
  ↓ session_start
RUNNING (executing code)
  ↓ breakpoint hit / step
PAUSED (stopped at breakpoint/step)
  ↓ execute continue / step
RUNNING
  ↓ program exit / session stop
TERMINATED
```

### State Transitions

**INITIALIZED → RUNNING**

- Trigger: `session_start` or `execute(action="run")`
- Available operations: None (session not yet started)
- Next steps: Start the session

**RUNNING → PAUSED**

- Trigger: Breakpoint hit, step completion, exception
- Available operations: `inspect`, `variable`, `step`, `execute`
- Next steps: Examine state, then continue or step

**PAUSED → RUNNING**

- Trigger: `execute(action="continue")`, `step`, `run_until`
- Available operations: Limited (program executing)
- Next steps: Wait for next pause

**RUNNING/PAUSED → TERMINATED**

- Trigger: Program exit, `session(action="stop")`, fatal error
- Available operations: `session(action="status")` only
- Next steps: Start new session if needed

### When Each Operation Works

| Operation       | INITIALIZED | RUNNING | PAUSED | TERMINATED |
| --------------- | ----------- | ------- | ------ | ---------- |
| `session_start` | ✓           | ✗       | ✗      | ✓          |
| `execute`       | ✗           | ✓       | ✓      | ✗          |
| `step`          | ✗           | ✗       | ✓      | ✗          |
| `inspect`       | ✗           | Limited | ✓      | ✗          |
| `variable`      | ✗           | Limited | ✓      | ✗          |
| `breakpoint`    | ✗           | ✓       | ✓      | ✗          |
| `session` stop  | ✓           | ✓       | ✓      | ✗          |

## Breakpoint Types

The debugger supports five types of breakpoints, each suited for different debugging scenarios.

### 1. Line Breakpoints

**Description**: Pause execution when a specific line is reached.

**Use Case**: Basic debugging, stopping at known code locations.

**Example**:

```python
breakpoint(action="set", location="app.py:42")
```

**Behavior**: Execution pauses every time line 42 in `app.py` is executed.

### 2. Conditional Breakpoints

**Description**: Pause only when a condition evaluates to true.

**Use Case**: Debugging specific scenarios (e.g., when a variable has a certain value).

**Example**:

```python
breakpoint(
    action="set",
    location="process.py:100",
    condition="count > 1000"
)
```

**Behavior**: Pauses at line 100 only when `count` is greater than 1000.

**Condition Syntax**: Language-specific expressions (Python: `x > 5 and y != None`, JavaScript: `x > 5 && y !== null`)

### 3. Hit Count Breakpoints

**Description**: Pause after a breakpoint has been hit a certain number of times.

**Use Case**: Debugging loops, finding issues that occur after N iterations.

**Example**:

```python
# Break on exactly 5th hit
breakpoint(action="set", location="loop.py:20", hit_condition="5")

# Break after more than 10 hits
breakpoint(action="set", location="loop.py:20", hit_condition=">10")

# Break every 10th hit
breakpoint(action="set", location="loop.py:20", hit_condition="%10")
```

```{include} /_snippets/hit-conditions-table.md
```

```{include} /_snippets/hit-conditions-language-note.md
```

### 4. Logpoints

**Description**: Log a message without pausing execution.

**Use Case**: Non-intrusive debugging, collecting data without stopping the program.

**Example**:

```python
breakpoint(
    action="set",
    location="api.py:55",
    log_message="Request received: {request_id}, User: {user.name}"
)
```

**Behavior**: When line 55 is executed, the message is logged with variable values interpolated. Execution continues without pausing.

**Message Format**: Curly braces `{}` contain expressions to evaluate and interpolate.

### 5. Column Breakpoints

**Description**: Pause at a specific column on a line (for minified code).

**Use Case**: Debugging minified JavaScript/TypeScript where multiple statements exist on one line.

**Example**:

```python
breakpoint(
    action="set",
    location="bundle.min.js:1",
    column=4582
)
```

**Behavior**: Pauses at column 4582 of line 1, useful when multiple function calls are on the same line.

### Breakpoint Management

**List All Breakpoints**:

```python
breakpoint(action="list")
```

**Remove Specific Breakpoint**:

```python
breakpoint(action="remove", location="app.py:42")
```

**Remove All Breakpoints**:

```python
breakpoint(action="clear_all")
```

**Verification**: After setting a breakpoint, the debugger verifies it can be placed at that location. If the line contains no executable code, it may adjust to the nearest valid line.

## MCP Tool Naming Convention

Understanding tool naming helps avoid confusion when using different MCP clients.

### Server-Side Names (Canonical)

The AI Debugger MCP server defines tools with simple, descriptive names:

- `init`
- `session_start`
- `session`
- `execute`
- `step`
- `inspect`
- `breakpoint`
- `variable`
- `config`
- `context`
- `run_until`
- `adapter`

These are the "true" names defined in the MCP server.

### Client-Side Prefixes (Namespacing)

MCP clients add prefixes to prevent naming conflicts between different MCP servers:

**Claude Code**:

```
mcp__ai-debugger__init
mcp__ai-debugger__session_start
mcp__ai-debugger__execute
...
```

**Pattern**: `mcp__<server-name>__<tool-name>`

**Other Clients** (Cline, Cursor, Windsurf, etc.) may use different prefixing schemes:

```
ai-debugger:init
ai_debugger__init
...
```

### Why This Matters

1. **Documentation Uses Server Names**: All documentation refers to tools by their canonical server names (e.g., `init`, `session_start`)

1. **Client Adds Prefix**: When you use a tool, your client adds its prefix automatically

1. **Examples Are Portable**: Examples showing `session_start(...)` work across all clients, even though the actual invocation might be `mcp__ai-debugger__session_start(...)`

1. **No Need to Memorize Prefixes**: Focus on learning the canonical tool names. Your client handles the prefix.

### How to Find Your Client's Prefix

Most MCP clients display available tools in their interface:

**Claude Code**:

- Tools appear with `mcp__ai-debugger__` prefix
- Auto-completion shows full names

**VS Code (Cline)**:

- Check the MCP server configuration in settings
- Tools list shows the naming scheme

**General**:

- Your client's documentation explains its naming convention
- The server name in your config determines the prefix

### Consistency Across Documentation

Throughout all AI Debugger documentation:

- Tool names are written without prefixes
- Examples use canonical names
- Code samples are client-agnostic
- Your client transparently applies its prefix

**Example**:

```python
# Documentation shows:
init(language="python")

# Claude Code invokes:
mcp__ai-debugger__init(language="python")

# Another client might invoke:
ai-debugger:init(language="python")

# But you write the same code in both cases
```

```{include} /_snippets/known-limitations.md
```

## Environment Variables

The AI Debugger can be configured using environment variables for advanced tuning and debugging.

### Logging & Debugging

| Variable | Default | Description |
|----------|---------|-------------|
| `AIDB_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AIDB_ADAPTER_TRACE` | `false` | Enable DAP protocol wire traces (saved to `~/.aidb/log/adapter_traces/`) |

### MCP Response Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AIDB_MCP_VERBOSE` | `false` | Enable human-friendly verbose responses |
| `AIDB_MCP_OPERATION_TIMEOUT` | `120000` | Operation timeout in milliseconds |
| `AIDB_MCP_MAX_STACK_FRAMES` | `10` | Maximum stack frames in response |
| `AIDB_MCP_MAX_VARIABLES` | `20` | Maximum variables in response |
| `AIDB_MCP_VARIABLE_INSPECTION_DEPTH` | `3` | Depth for nested variable inspection |

### Audit Logging

Enable comprehensive audit logging for compliance and debugging:

| Variable | Default | Description |
|----------|---------|-------------|
| `AIDB_AUDIT_LOG` | `false` | Enable audit logging |
| `AIDB_AUDIT_LOG_PATH` | `~/.aidb/log/audit.log` | Custom audit log path |
| `AIDB_AUDIT_LOG_MB` | `100` | Maximum audit log size in MB |
| `AIDB_AUDIT_LOG_DAP` | `false` | Include DAP protocol in audit logs |

### Java-Specific Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JAVA_HOME` | (system) | Java installation path |
| `JDT_LS_HOME` | (bundled) | Eclipse JDT Language Server path |
| `AIDB_JAVA_AUTO_COMPILE` | `false` | Auto-compile Java files before debugging |

### Example Usage

```bash
# Enable debug logging
export AIDB_LOG_LEVEL=DEBUG

# Enable adapter tracing for troubleshooting
export AIDB_ADAPTER_TRACE=1

# Enable audit logging
export AIDB_AUDIT_LOG=1
export AIDB_AUDIT_LOG_PATH=/var/log/aidb-audit.log

# Increase operation timeout for slow operations
export AIDB_MCP_OPERATION_TIMEOUT=300000
```

## Next Steps

Now that you understand the core concepts:

1. Follow the [Quick Start Guide](quickstart.md) to set up your first debugging session
1. Explore [Advanced Workflows](advanced-workflows.md) for common debugging patterns, remote debugging, and more
1. Reference the [Tool Documentation](tools/session-management.md) for detailed parameter documentation
