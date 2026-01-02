---
myst:
  html_meta:
    description lang=en: Configuration tools in AI Debugger MCP - config, adapter, and context management.
---

# Configuration Tools

The AI Debugger MCP provides three essential configuration tools that help you manage debugging capabilities, install debug adapters, and understand your current debugging context. These tools are critical for setting up your environment and maintaining awareness during debugging sessions.

## config - Configuration Management

The `config` tool provides comprehensive configuration and environment management, including capabilities discovery, environment variable inspection, and VS Code launch configuration management.

### Overview

The `config` tool is your central hub for:

- Discovering language-specific debugging capabilities
- Managing AIDB environment variables
- Finding VS Code launch configurations
- Checking debug adapter installation status

### Actions Explained

#### show (default)

Display current debugging configuration including active session, environment variables, and available launch configurations.

**When to use:** Get a quick overview of your current debugging setup.

:::{tip}
The `list` action is an alias for `show` and provides the same functionality.
:::

#### env

Show or set AIDB environment variables.

**When to use:** Check configuration settings or modify environment-specific behavior.

#### launch

Discover and list VS Code launch.json configurations in your workspace.

**When to use:** Find available launch configurations before starting a debug session.

#### capabilities

Show debugging capabilities for a specific programming language.

**When to use:** Understand what debugging features are supported for Python, JavaScript, or Java before starting a session.

#### adapters

Check debug adapter installation status for all supported languages.

**When to use:** Verify which debug adapters are installed and which are missing.

#### get

Retrieve a specific configuration value by key.

**When to use:** Check a particular environment variable or setting.

#### set

Set an AIDB environment variable (only AIDB\_\* variables allowed for safety).

**When to use:** Modify debugging configuration at runtime.

### Parameters

| Parameter     | Type   | Description                                           | Required                         |
| ------------- | ------ | ----------------------------------------------------- | -------------------------------- |
| `action`      | string | Configuration action (default: `show`)                | No                               |
| `language`    | string | Programming language (`python`, `javascript`, `java`) | No (required for `capabilities`) |
| `key`         | string | Configuration key (for `get`/`set` actions)           | No                               |
| `value`       | string | Configuration value (for `set` action)                | No                               |
| `config_name` | string | Launch configuration name (for `launch` action)       | No                               |

### Examples

#### Check Python Debugging Capabilities

```python
# Without an active session - shows adapter registry info
{
  "action": "capabilities",
  "language": "python"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Adapter capabilities for python (no active session)",
  "data": {
    "language": "python",
    "capabilities": {
      "breakpoints": ["line", "conditional", "logpoints"],
      "stepping": ["into", "over", "out"],
      "evaluation": ["set_variable", "hover"],
      "supported_hit_conditions": [">", ">=", "=", "<", "<=", "%"],
      "hit_condition_examples": [
        "> 5 (break after 5 hits)",
        "% 10 (break every 10th hit)"
      ]
    },
    "available": true,
    "message": "Start a debug session for full DAP capabilities"
  }
}
```

#### Discover VS Code Launch Configurations

```python
{
  "action": "launch"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Found 1 launch configurations",
  "data": {
    "configurations": [
      {
        "name": "Found launch.json",
        "path": ".vscode/launch.json"
      }
    ]
  }
}
```

#### Check Environment Variables

```python
{
  "action": "env"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Found 2 AIDB environment variables",
  "data": {
    "environment": {
      "AIDB_LOG_LEVEL": "DEBUG",
      "AIDB_ADAPTER_TRACE": "1"
    }
  }
}
```

#### Set Environment Variable

```python
{
  "action": "set",
  "key": "AIDB_LOG_LEVEL",
  "value": "INFO"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Set AIDB_LOG_LEVEL = INFO",
  "data": {
    "key": "AIDB_LOG_LEVEL",
    "value": "INFO",
    "set": true
  }
}
```

#### Check Adapter Installation Status

```python
{
  "action": "adapters"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Adapters: 2/3 installed",
  "data": {
    "adapters": {
      "python": {
        "installed": true,
        "version": "1.8.0",
        "path": "/Users/user/.aidb/adapters/debugpy",
        "status": "ready"
      },
      "javascript": {
        "installed": true,
        "version": "1.63.0",
        "path": "/Users/user/.aidb/adapters/js-debug",
        "status": "ready"
      },
      "java": {
        "installed": false,
        "status": "missing",
        "suggestions": [
          "Use adapter tool with action='download' and language='java'"
        ]
      }
    },
    "summary": {
      "total": 3,
      "installed": 2,
      "missing": 1,
      "install_directory": "/Users/user/.aidb/adapters"
    }
  },
  "quick_actions": [
    "Use adapter tool with action='download_all' to install all missing adapters",
    "Use adapter tool with action='list' for detailed status"
  ]
}
```

#### Show Current Configuration

```python
{
  "action": "show"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Current debugging configuration",
  "data": {
    "active_session": "session_abc123",
    "session_info": {
      "language": "python",
      "mode": "launch",
      "target": "app.py"
    },
    "environment": {
      "AIDB_LOG_LEVEL": "DEBUG"
    },
    "launch_configs": [
      {
        "name": "Found launch.json",
        "path": ".vscode/launch.json"
      }
    ]
  }
}
```

### Use Cases

**Verify Language Support Before Debugging**
Before starting a debug session, check what features are available for your target language:

```python
# Check what JavaScript supports
config(action="capabilities", language="javascript")
# Then start session knowing you can use conditional breakpoints, logpoints, etc.
```

**Environment Configuration Management**
Monitor and adjust debugging behavior through environment variables:

```python
# Check current settings
config(action="env")

# Enable detailed logging for troubleshooting
config(action="set", key="AIDB_LOG_LEVEL", value="DEBUG")
```

**Launch Configuration Discovery**
Find and use existing VS Code launch configurations:

```python
# Discover available configurations
config(action="launch")

# Use a specific configuration when starting a session
session_start(launch_config_name="Debug Python App", ...)
```

**Adapter Status Verification**
Ensure debug adapters are installed before debugging:

```python
# Check installation status
config(action="adapters")

# If adapters are missing, install them
adapter(action="download", language="java")
```

______________________________________________________________________

## adapter - Adapter Management

The `adapter` tool manages debug adapter installation, providing a consolidated interface for downloading, listing, and verifying debug adapters.

### Overview

Debug adapters are language-specific debugging backends that communicate via the Debug Adapter Protocol (DAP). The `adapter` tool handles:

- Downloading adapters from GitHub releases
- Installing adapters to `~/.aidb/adapters/`
- Listing installed adapters with version information
- Automatic version matching with your project

### Actions Explained

#### download

Download and install a specific language adapter.

**When to use:** Install a missing adapter when you encounter `AdapterNotFoundError` or want to debug a specific language.

#### download_all

Download and install all available adapters (Python, JavaScript, Java).

**When to use:** Set up a new environment or ensure all adapters are installed.

#### list (default)

List installed adapters and their status.

**When to use:** Verify which adapters are installed and check their versions.

### Parameters

| Parameter  | Type    | Description                                                        | Required             |
| ---------- | ------- | ------------------------------------------------------------------ | -------------------- |
| `action`   | string  | Adapter action (default: `list`)                                   | No                   |
| `language` | string  | Programming language (`python`, `javascript`, `java`)              | Yes (for `download`) |
| `version`  | string  | Specific version to download (defaults to latest matching project) | No                   |
| `force`    | boolean | Force re-download if already installed (default: `false`)          | No                   |

### Examples

#### Install Python Adapter

```python
{
  "action": "download",
  "language": "python"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "python adapter downloaded",
  "data": {
    "language": "python",
    "path": "/Users/user/.aidb/adapters/debugpy",
    "status": "downloaded",
    "message": "Successfully downloaded python adapter",
    "version": "1.8.0"
  }
}
```

#### Install All Adapters

```python
{
  "action": "download_all"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Downloaded adapters: 3 successful, 0 failed",
  "data": {
    "adapters": {
      "python": {
        "success": true,
        "status": "downloaded",
        "message": "Successfully downloaded python adapter",
        "path": "/Users/user/.aidb/adapters/debugpy",
        "version": "1.8.0"
      },
      "javascript": {
        "success": true,
        "status": "downloaded",
        "message": "Successfully downloaded javascript adapter",
        "path": "/Users/user/.aidb/adapters/js-debug",
        "version": "1.63.0"
      },
      "java": {
        "success": true,
        "status": "downloaded",
        "message": "Successfully downloaded java adapter",
        "path": "/Users/user/.aidb/adapters/java-debug",
        "version": "0.52.0"
      }
    },
    "summary": {
      "total": 3,
      "successful": 3,
      "failed": 0
    }
  }
}
```

#### List Installed Adapters

```python
{
  "action": "list"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Found 2 installed adapters",
  "data": {
    "adapters": {
      "python": {
        "version": "1.8.0",
        "path": "/Users/user/.aidb/adapters/debugpy",
        "installed": true
      },
      "javascript": {
        "version": "1.63.0",
        "path": "/Users/user/.aidb/adapters/js-debug",
        "installed": true
      }
    },
    "summary": {
      "total_installed": 2,
      "install_directory": "/Users/user/.aidb/adapters"
    }
  }
}
```

#### Force Re-download Adapter

```python
{
  "action": "download",
  "language": "python",
  "force": true
}
```

**Response:**

```json
{
  "success": true,
  "summary": "python adapter downloaded",
  "data": {
    "language": "python",
    "path": "/Users/user/.aidb/adapters/debugpy",
    "status": "downloaded",
    "message": "Successfully re-downloaded python adapter",
    "version": "1.8.0"
  }
}
```

#### Install Specific Version

```python
{
  "action": "download",
  "language": "javascript",
  "version": "1.62.0"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "javascript adapter downloaded",
  "data": {
    "language": "javascript",
    "path": "/Users/user/.aidb/adapters/js-debug",
    "status": "downloaded",
    "message": "Successfully downloaded javascript adapter version 1.62.0",
    "version": "1.62.0"
  }
}
```

### Use Cases

**Initial Environment Setup**
Set up a new development environment with all debug adapters:

```python
# Install all adapters at once
adapter(action="download_all")

# Verify installation
adapter(action="list")
```

**Handle Missing Adapter Errors**
When you encounter `AdapterNotFoundError`:

```python
# Error indicates missing Java adapter
# Install it
adapter(action="download", language="java")

# Retry your debug session
session_start(target="Main.java", language="java")
```

**Update Corrupted Adapters**
If an adapter is not working correctly:

```python
# Force re-download to fix corruption
adapter(action="download", language="python", force=True)
```

**Version Management**
Install a specific adapter version for compatibility:

```python
# Install specific version for project requirements
adapter(action="download", language="javascript", version="1.60.0")
```

**Installation Verification**
Check adapter status before starting a debug session:

```python
# List installed adapters
adapter(action="list")

# If Python not installed, download it
adapter(action="download", language="python")
```

### Offline Adapter Installation

For air-gapped environments or when automatic download fails, you can manually install adapters:

**Method 1: Manual Download and Extract**

1. Download the adapter from [GitHub Releases](https://github.com/ai-debugger-inc/aidb/releases)
2. Extract to `~/.aidb/adapters/{language}/`

```bash
# Example: Install Python adapter offline
mkdir -p ~/.aidb/adapters/python
tar -xzf debugpy-1.8.0-{platform}.tar.gz -C ~/.aidb/adapters/python/

# Example: Install JavaScript adapter offline
mkdir -p ~/.aidb/adapters/javascript
tar -xzf js-debug-1.104.0-{platform}.tar.gz -C ~/.aidb/adapters/javascript/

# Example: Install Java adapter offline (universal - works on all platforms)
mkdir -p ~/.aidb/adapters/java
tar -xzf java-debug-0.53.1-universal.tar.gz -C ~/.aidb/adapters/java/
```

**Method 2: Custom Adapter Path**

Set environment variables to point to your adapter installation:

```bash
# Point to custom Python adapter location
export AIDB_PYTHON_ADAPTER_PATH=/path/to/custom/debugpy

# Point to custom JavaScript adapter location
export AIDB_JAVASCRIPT_ADAPTER_PATH=/path/to/custom/js-debug

# Point to custom Java adapter location
export AIDB_JAVA_ADAPTER_PATH=/path/to/custom/java-debug
```

**Verify Offline Installation**

After manual installation, verify the adapter is detected:

```python
# Check if manually installed adapter is recognized
adapter(action="list")

# Should show your offline-installed adapters
```

:::{tip}
**Platform-specific downloads:**
- Python & JavaScript adapters require platform-specific builds (linux, darwin, windows; x64, arm64)
- Java adapter is universal and works on all platforms
- Check your platform: `uname -m` (architecture) and `uname -s` (OS)
:::

______________________________________________________________________

## context - Debugging Context

The `context` tool provides rich debugging state awareness with intelligent next-step suggestions, helping you understand your current debugging situation and what actions to take next.

### Overview

The `context` tool is designed for AI agents and developers who need to:

- Understand current debugging state and session memory
- Get intelligent next-step recommendations
- View recent operations and their outcomes
- Access cross-tool workflow suggestions
- Track debugging history and patterns

This tool is particularly useful for AI-assisted debugging workflows where the agent needs contextual awareness to make informed decisions.

### Detail Levels

#### brief

Minimal context information for quick status checks.

**When to use:** Fast status verification without detailed information.

#### detailed (default)

Comprehensive context with all relevant debugging information.

**When to use:** Most debugging scenarios requiring full situational awareness.

#### full

Complete context including verbose execution history and detailed state information.

**When to use:** Complex debugging scenarios or troubleshooting workflow issues.

### Parameters

| Parameter             | Type    | Description                                                                | Required |
| --------------------- | ------- | -------------------------------------------------------------------------- | -------- |
| `detail_level`        | string  | Level of context detail: `brief`, `detailed`, `full` (default: `detailed`) | No       |
| `include_suggestions` | boolean | Include next-step suggestions (default: `true`)                            | No       |
| `session_id`          | string  | Optional session ID (uses active session if not provided)                  | No       |

### Examples

#### Get Current Debugging Context (Paused)

```python
{
  "detail_level": "detailed",
  "include_suggestions": true
}
```

**Response (when paused at breakpoint):**

```json
{
  "success": true,
  "summary": "Debugging context for session session_abc123",
  "data": {
    "session_id": "session_abc123",
    "status": "active",
    "session": {
      "target": "app.py",
      "language": "python",
      "pid": 12345,
      "port": 5678
    },
    "execution_state": "paused",
    "current_location": {
      "file": "/path/to/app.py",
      "line": 42,
      "function": "process_data"
    },
    "locals": {
      "x": 10,
      "y": 20,
      "result": null
    },
    "stack_depth": 3,
    "breakpoints": {
      "active": [
        {
          "file": "/path/to/app.py",
          "line": 42,
          "verified": true
        }
      ],
      "total": 1
    },
    "execution_history": {
      "recent_steps": [
        "Started session",
        "Hit breakpoint at app.py:42"
      ],
      "step_count": 2
    }
  },
  "suggestions": [
    "Inspect local variables to understand state",
    "Step through code to trace execution",
    "Continue to next breakpoint"
  ],
  "detail_level": "detailed"
}
```

#### Get Brief Context (Running)

```python
{
  "detail_level": "brief",
  "include_suggestions": false
}
```

**Response (when running):**

```json
{
  "success": true,
  "summary": "Debugging context for session session_abc123",
  "data": {
    "session_id": "session_abc123",
    "status": "active",
    "execution_state": "running"
  },
  "detail_level": "brief"
}
```

#### Get Full Context with Suggestions

```python
{
  "detail_level": "full",
  "include_suggestions": true
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Debugging context for session session_abc123",
  "data": {
    "session_id": "session_abc123",
    "status": "active",
    "session": {
      "target": "app.py",
      "language": "python",
      "pid": 12345,
      "port": 5678
    },
    "execution_state": "paused",
    "current_location": {
      "file": "/path/to/app.py",
      "line": 42,
      "function": "process_data",
      "frame_id": 0
    },
    "locals": {
      "x": 10,
      "y": 20,
      "result": null,
      "config": {
        "debug": true,
        "timeout": 30
      }
    },
    "stack": [
      {
        "level": 0,
        "function": "process_data",
        "file": "/path/to/app.py",
        "line": 42
      },
      {
        "level": 1,
        "function": "main",
        "file": "/path/to/app.py",
        "line": 100
      },
      {
        "level": 2,
        "function": "<module>",
        "file": "/path/to/app.py",
        "line": 105
      }
    ],
    "stack_depth": 3,
    "breakpoints": {
      "active": [
        {
          "file": "/path/to/app.py",
          "line": 42,
          "verified": true,
          "hit_count": 1
        }
      ],
      "total": 1
    },
    "execution_history": {
      "recent_steps": [
        {
          "action": "session_start",
          "timestamp": "2025-10-23T10:30:00Z",
          "file": "/path/to/app.py",
          "line": 1
        },
        {
          "action": "breakpoint_hit",
          "timestamp": "2025-10-23T10:30:01Z",
          "file": "/path/to/app.py",
          "line": 42
        }
      ],
      "step_count": 2,
      "total_operations": 5
    }
  },
  "suggestions": [
    "Inspect local variables to understand state",
    "Step through code to trace execution",
    "Continue to next breakpoint"
  ],
  "detail_level": "full"
}
```

#### Get Context for Specific Session

```python
{
  "session_id": "session_xyz789",
  "detail_level": "detailed"
}
```

**Response:**

```json
{
  "success": true,
  "summary": "Debugging context for session session_xyz789",
  "data": {
    "session_id": "session_xyz789",
    "status": "active",
    "execution_state": "terminated"
  },
  "suggestions": [
    "Set a breakpoint to pause execution",
    "Inspect current state when paused"
  ],
  "detail_level": "detailed"
}
```

### Use Cases

**AI Agent Decision Making**
AI agents use context to determine next steps:

```python
# Get current context
context_data = context(detail_level="detailed", include_suggestions=True)

# Check execution state
if context_data["data"]["execution_state"] == "paused":
    # Paused - inspect variables
    inspect(target="locals")
else:
    # Running - set breakpoint
    breakpoint(action="set", location="app.py:50")
```

**Debugging Session Recovery**
After connection issues or session interruption:

```python
# Get full context to understand where we are
context(detail_level="full")

# Context shows we were at line 42 in process_data
# Resume debugging from there
```

**Workflow Guidance**
Get intelligent suggestions for next actions:

```python
# Get context with suggestions enabled
context(include_suggestions=True)

# Response includes suggestions that guide the workflow:
# - "Inspect local variables to understand state"
# - "Step through code to trace execution"
# - "Continue to next breakpoint"
```

**Session State Verification**
Verify session state before performing operations:

```python
# Check if session is in expected state
context(detail_level="brief")

# Based on execution_state in response:
# - If "paused": can inspect variables or step
# - If "running": need to wait for breakpoint
```

**Multi-Session Management**
Monitor multiple debugging sessions:

```python
# Get context for each session
context(session_id="session_abc123")
context(session_id="session_xyz789")

# Compare states from responses and choose which to work with
```

**Execution History Tracking**
Review what operations have been performed:

```python
# Get full context with complete history
context(detail_level="full")

# Response includes execution_history showing:
# - session_start, breakpoint_hit, step_over, etc.
```

**Performance Analysis**
Monitor debugging session for performance issues:

```python
# Get detailed context
context(detail_level="detailed")

# Response includes stack_depth - can identify recursion issues
# AI can detect if stack_depth > 100 and warn about deep recursion

# Response also includes breakpoint hit counts for identifying hotspots
```

______________________________________________________________________

## Summary

The configuration tools provide essential capabilities for managing your debugging environment:

- **config**: Discover capabilities, manage environment variables, and verify adapter installation
- **adapter**: Download, install, and manage debug adapters for different languages
- **context**: Get intelligent debugging state awareness with next-step suggestions

These tools work together to ensure you have a properly configured debugging environment and maintain situational awareness throughout your debugging sessions.

### Common Workflows

**New Environment Setup**

```python
# 1. Install all adapters
adapter(action="download_all")

# 2. Verify installation
config(action="adapters")

# 3. Check Python capabilities
config(action="capabilities", language="python")

# 4. Start debugging with confidence
session_start(target="app.py", language="python")
```

**Troubleshooting Setup Issues**

```python
# 1. Check environment
config(action="env")

# 2. Verify adapters
config(action="adapters")

# 3. Install missing adapter if needed
adapter(action="download", language="java")

# 4. Verify capabilities
config(action="capabilities", language="java")
```

**AI-Assisted Debugging**

```python
# 1. Get current context
context_data = context(detail_level="detailed", include_suggestions=True)

# 2. Follow suggestions
# If paused: inspect variables
# If running: set breakpoint

# 3. Check context again after each action
context(detail_level="brief")
```
