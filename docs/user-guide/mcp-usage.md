---
myst:
  html_meta:
    description lang=en: AI Debugger MCP Documentation - Enable your AI assistant to debug Python, JavaScript, TypeScript, and Java with framework-aware capabilities.
---

# MCP Usage Guide

AI Debugger is a Model Context Protocol (MCP) server that enables AI assistants to programmatically control live debugging sessions across Python, JavaScript, TypeScript, and Java. Your AI assistant can set breakpoints, step through code, inspect variables, and analyze runtime behavior just as you would with a traditional debugger.

Built on the Debug Adapter Protocol (DAP), AI Debugger provides a unified interface for debugging multiple languages through a single MCP server.

## Key Features

### Initial Breakpoints

For programs that execute quickly, breakpoints must be set before execution begins. AI Debugger supports setting breakpoints during session creation, ensuring your program pauses exactly where you need it to.

```python
# Start session with breakpoints already configured
session_start(
    target="app.py",
    breakpoints=[
        {"file": "utils.py", "line": 42},
        {"file": "models.py", "line": 15, "condition": "x > 0"}
    ]
)
```

This "pause-first" approach is critical for debugging fast-running scripts, tests, and startup sequences.

[Learn more about session management →](mcp/tools/session-management.md)

### Remote Debugging

Debug applications running in Docker containers, remote servers, or production-like environments. AI Debugger supports both local and remote attach modes.

**Remote attach modes:**

- **PID attach**: Connect to a running process by process ID (Python, Java)
- **Remote attach**: Connect to a debug server at host:port (all languages)
- **Docker debugging**: Attach to containerized applications

:::{note}
**Attach Mode**: Connect to an already-running process. The target application must be started with debugging enabled before you can attach.
:::

```python
# Attach to remote debug server (Python example)
session_start(
    mode="remote_attach",
    host="localhost",
    port=5678,
    language="python"
)
```

[Learn more about remote debugging →](mcp/advanced-workflows.md#remote-debugging)

### Advanced Breakpoints

Go beyond simple line breakpoints with conditional logic, hit counts, and non-intrusive logpoints.

```{include} /_snippets/breakpoint-types-overview.md
```

[Learn more about advanced breakpoints →](mcp/core-concepts.md#breakpoint-types)

### Multi-Session Debugging

Debug multiple processes simultaneously with independent sessions. Perfect for microservices, client-server architectures, and concurrent workers.

```python
# Start multiple sessions
backend_id = session_start(target='server.py')["session_id"]
worker_id = session_start(target='worker.py')["session_id"]

# Interact with specific sessions using session_id
execute(action='continue', session_id=backend_id)
inspect(target='locals', session_id=worker_id)
```

[Learn more about multi-session debugging →](mcp/advanced-workflows.md#multi-session-debugging)

### VS Code Integration

Leverage your existing VS Code launch configurations directly from MCP. No need to duplicate configuration.

```python
# Use existing launch.json configuration
init(
    language="python",
    launch_config_name="Debug Tests"
)
```

AI Debugger discovers and applies your launch.json settings automatically, including environment variables, arguments, and working directories.

[Learn more about configuration →](mcp/tools/configuration.md)

### Comprehensive Tool Suite

12 MCP tools organized into 5 intuitive categories provide complete debugging control:

1. **Context Discovery**: Configuration discovery, workspace analysis, debugging examples
1. **Session Management**: Create, control, and manage debug sessions
1. **Execution Control**: Run, step, continue, and navigate through code
1. **Inspection & Analysis**: Examine variables, stack traces, and runtime state
1. **Configuration & Context**: Manage settings, adapters, and get intelligent suggestions

[View all MCP tools →](#mcp-tools-reference)

## Getting Started

New to AI Debugger? Start here:

1. **[Quick Start Guide](mcp/quickstart.md)** - Install, configure, and run your first debugging session in 5 minutes
1. **[Core Concepts](mcp/core-concepts.md)** - Understand sessions, breakpoints, and debugging workflow
1. **[Language Guide](mcp/languages/python.md)** - Language-specific examples for Python, JavaScript, and Java

## Documentation Navigation

### Core Guides

**[Core Concepts](mcp/core-concepts.md)**
Understand the fundamental concepts behind AI Debugger MCP:

- Debugging workflow and human-cadence operation
- Session lifecycle and state transitions
- Breakpoint types and management
- Tool categories and organization
- MCP naming conventions

**[Quick Start Guide](mcp/quickstart.md)**
Get up and running quickly:

- Installation and setup
- MCP client configuration (Claude Code, Cline, Cursor, etc.)
- Your first debugging session walkthrough
- Troubleshooting common setup issues

**[Advanced Workflows](mcp/advanced-workflows.md)**
Master advanced debugging techniques:

- Framework-specific debugging (pytest, jest, spring, django)
- Remote debugging (Docker, remote servers)
- Multi-session debugging for microservices
- Advanced breakpoint strategies

(mcp-tools-reference)=

### MCP Tools Reference

#### Session Management

**[Session Management Tools](mcp/tools/session-management.md)**

- `init` - Initialize debugging context (required first step)
- `session_start` - Create and start debug sessions
- `session` - Manage session lifecycle (status, list, stop, restart)

#### Execution Control

**[Execution Control Tools](mcp/tools/execution-control.md)**

- `execute` - Run or continue program execution
- `step` - Step through code (over, into, out)
- `run_until` - Run to specific location with temporary breakpoints

#### Inspection & Analysis

**[Inspection Tools](mcp/tools/inspection.md)**

- `inspect` - Examine program state (locals, globals, stack, threads, expressions, all)
- `variable` - Get, set, and patch variables
- `breakpoint` - Set, remove, list, and manage breakpoints

#### Configuration & Environment

**[Configuration Tools](mcp/tools/configuration.md)**

- `config` - View configuration, capabilities, and launch.json settings
- `context` - Get debugging context and intelligent next-step suggestions
- `adapter` - Download and manage debug adapters

### Language-Specific Guides

**[Python Guide](mcp/languages/python.md)**
Python-specific debugging workflows:

- pytest test debugging
- django application debugging
- flask/fastapi debugging
- Virtual environment handling

**[JavaScript & TypeScript Guide](mcp/languages/javascript.md)**
JavaScript/TypeScript debugging workflows:

- jest test debugging
- Node.js application debugging
- Express server debugging
- TypeScript projects

**[Java Guide](mcp/languages/java.md)**
Java debugging workflows:

- JUnit test debugging
- Spring application debugging
- Maven/Gradle project debugging
- Multi-module project handling

## Supported MCP Clients

AI Debugger works with any MCP-compatible client:

- **[Claude Code](https://claude.com/download)** - Official Claude desktop and CLI (built-in MCP support)
- **[VS Code + Cline](https://github.com/cline/cline)** - Cline extension with MCP integration
- **[Cursor](https://cursor.com/)** - AI-powered code editor
- **[Windsurf](https://windsurf.com/)** - AI coding assistant
- **Codex** - MCP-compatible coding assistant

Client configuration examples are provided in the [Quick Start Guide](mcp/quickstart.md#client-configuration).

## System Requirements

```{include} /_snippets/system-requirements.md
```

## Installation

Install via pip:

```bash
pip install ai-debugger-inc
```

Or from source:

```bash
git clone https://github.com/ai-debugger-inc/aidb.git
cd aidb
pip install -e .
```

All features and languages (Python, JavaScript, Java) are available for free under the Apache 2.0 license. No license key required.

Full installation instructions in the [Quick Start Guide](mcp/quickstart.md).

## Common Use Cases

### Debug Failing Tests

```python
# Initialize debugging context
init(language="python")

# Start with breakpoint in test
session_start(
    target="tests/test_api.py",
    breakpoints=[{"file": "tests/test_api.py", "line": 45}]
)

# Inspect test state when paused
inspect(target="locals")
```

### Debug Production Issues

```python
# Attach to running production process
session_start(
    mode="remote_attach",
    host="prod-server.example.com",
    port=5678,
    language="python"
)

# Set conditional breakpoint for specific user
breakpoint(
    action="set",
    location="api/routes.py:156",
    condition="user_id == '12345'"
)
```

### Debug Microservices

```python
# Debug multiple services simultaneously
api_id = session_start(target='api/server.py')["session_id"]
worker_id = session_start(target='worker/processor.py')["session_id"]

# Interact with specific sessions using session_id
inspect(target='stack', session_id=api_id)
inspect(target='locals', session_id=worker_id)
```

## Community & Support

### Join the Community

- **Discord**: [https://discord.com/invite/UGS92b6KgR](https://discord.com/invite/UGS92b6KgR) - Get help, share workflows, discuss features
- **GitHub**: [https://github.com/ai-debugger-inc/aidb](https://github.com/ai-debugger-inc/aidb) - Report bugs, request features, contribute

### Get Help

- **Documentation**: You're here! Browse the guides above
- **Discord**: [Join the community](https://discord.com/invite/UGS92b6KgR)
- **GitHub**: [Report bugs or contribute](https://github.com/ai-debugger-inc/aidb)

## Troubleshooting

Quick troubleshooting tips:

**"Adapter not found" error:**

Ask your AI assistant to download the adapter:

> "Download the Python debug adapter."

The AI assistant will call the `adapter` tool automatically.

**Enable debug logging:**

```bash
export AIDB_LOG_LEVEL=DEBUG
export AIDB_ADAPTER_TRACE=1
```

**Session won't start:**

- Verify target file path is correct
- Ensure language runtime is installed (python, node, java)
- Check that `init` was called before `session_start`

Full troubleshooting guide in the [Quick Start Guide](mcp/quickstart.md#troubleshooting-common-setup-issues).

## What's Next?

Ready to start debugging with AI?

1. **[Install and configure](mcp/quickstart.md)** AI Debugger in your MCP client
1. **[Learn core concepts](mcp/core-concepts.md)** to understand the debugging workflow
1. **[Explore language guides](mcp/languages/python.md)** for framework-specific examples
1. **[Master advanced workflows](mcp/advanced-workflows.md)** for complex debugging scenarios

Happy debugging!
