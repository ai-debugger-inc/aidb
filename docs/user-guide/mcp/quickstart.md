---
myst:
  html_meta:
    description lang=en: Quick start guide for AI Debugger MCP - installation, setup, and your first debugging session.
---

# Quick Start Guide

Get up and running with AI Debugger in minutes. This guide walks you through installation, configuration, and your first debugging session.

```{include} /_snippets/system-requirements.md
```

## Installation

```{include} /_snippets/installation.md
```

## Client Configuration

AI Debugger works with multiple MCP-compatible clients. Choose your preferred client and follow the configuration steps below.

```{include} /_snippets/tool-name-prefixing.md
```

### Claude Code

```{include} /_snippets/mcp-client-claude-desktop.md
```

### VS Code (Cline Extension)

```{include} /_snippets/mcp-client-cline.md
```

### Codex

```{include} /_snippets/mcp-client-codex.md
```

### Cursor

```{include} /_snippets/mcp-client-cursor.md
```

### Windsurf

```{include} /_snippets/mcp-client-windsurf.md
```

## Your First Debugging Session

Now that AI Debugger is installed and configured, let's walk through a complete debugging session.

### Example: Debugging a Simple Python Program

We'll debug a simple Python program that calculates factorials. Create a file called `factorial.py`:

```python
def factorial(n):
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

def main():
    numbers = [3, 5, 7]
    for num in numbers:
        fact = factorial(num)
        print(f"Factorial of {num} is {fact}")

if __name__ == "__main__":
    main()
```

### Step 1: Initialize Debugging Context

**IMPORTANT:** You must call `init` before starting any debugging session. This is a required first step.

Ask your AI assistant:

> "Initialize debugging for Python. I want to debug `factorial.py`."

The AI assistant will call `init` (or `mcp__aidb-debug__init` depending on your client) with:

```python
language='python'
workspace_root='/path/to/your/project'
```

The response will include:

- Language-specific setup information
- Debug adapter status (whether it's installed)
- Example parameters for starting a session
- Framework-specific guidance (if applicable)

:::\{note}
If the Python debug adapter is not installed, the `init` response will include instructions for downloading it using the `adapter` tool.
:::

### Step 2: Start a Debug Session with Breakpoints

**Key Concept:** For programs that execute quickly, you must set breakpoints when starting the session. You cannot set them after the program has already finished running.

Ask your AI assistant:

> "Start a debug session for `factorial.py` and set a breakpoint at line 5 (inside the factorial function)."

The AI assistant will call `session_start` with initial breakpoints:

```python
target='factorial.py'
language='python'
workspace_root='/path/to/your/project'
breakpoints=[
    {'file': 'factorial.py', 'line': 5}
]
```

**Understanding the Parameters:**

- `target`: The **entrypoint** file that starts execution (`factorial.py`)
- `breakpoints`: Can be in **any files**, not just the target file
  - Example: `target='main.py'` with breakpoints in `utils/helper.py`, `models/user.py`, etc.

The session will start, run the program, and pause when it hits the breakpoint at line 5.

### Step 3: Inspect Program State

Once paused at the breakpoint, ask your AI assistant:

> "Show me the local variables."

The AI assistant will call `inspect`:

```python
target='locals'
```

You'll see the current state of variables:

```
Local Variables:
  n = 3
  result = 1
  i = 2
```

You can also inspect specific expressions:

> "What is the value of result * i?"

The AI assistant will call `inspect` or `variable`:

```python
target='expression'
expression='result * i'
```

### Step 4: Step Through Code

To step to the next line:

> "Step to the next line."

The AI assistant will call `step`:

```python
action='over'  # Step over (default)
```

To step into a function call:

> "Step into the factorial function."

```python
action='into'
```

To step out of the current function:

> "Step out of this function."

```python
action='out'
```

### Step 5: Continue Execution

To continue running until the next breakpoint or program end:

> "Continue execution."

The AI assistant will call `execute`:

```python
action='continue'
```

### Step 6: Stop the Session

When you're done debugging:

> "Stop the debugging session."

The AI assistant will call `session`:

```python
action='stop'
```

## Advanced: Setting Conditional Breakpoints

For more targeted debugging, you can set conditional breakpoints that only pause when a condition is true.

> "Start a debug session for `factorial.py` and break at line 5 only when n > 5."

The AI assistant will call `session_start`:

```python
target='factorial.py'
language='python'
breakpoints=[
    {
        'file': 'factorial.py',
        'line': 5,
        'condition': 'n > 5'
    }
]
```

Now the debugger will only pause when `n > 5`, skipping the first two iterations (n=3 and n=5).

## Troubleshooting Common Setup Issues

### "Adapter not found" Error

```{include} /_snippets/troubleshooting-adapter-not-found.md
```

### "Session won't start" Error

**Common causes and solutions:**

1. **Target file doesn't exist**

   - Verify the file path is correct
   - Use absolute paths or ensure `workspace_root` is set correctly

1. **Missing `init` call**

   - Always call `init` before `session_start`
   - The error message will explicitly state this

1. **Language runtime not installed**

   - Python: Ensure Python is installed (`python --version`)
   - JavaScript/TypeScript: Ensure Node.js is installed (`node --version`)
   - Java: Ensure JDK is installed (`java -version`)

1. **Permission issues**

   - Ensure the target file is executable (for compiled languages)
   - Check file permissions: `ls -l target_file.py`

### Breakpoints Not Working

**Common causes and solutions:**

1. **File paths are incorrect**

   - Use absolute paths or paths relative to `workspace_root`
   - Verify the file path matches exactly (case-sensitive)

1. **Breakpoints set after program finished**

   - Remember: Fast programs require breakpoints at session start
   - Use the `breakpoints` parameter in `session_start`

1. **Source code doesn't match running program**

   - Ensure you saved all file changes
   - For compiled languages, recompile before debugging

1. **Line number is not executable code**

   - Avoid setting breakpoints on comments, blank lines, or declarations
   - The debugger may automatically adjust to the nearest executable line

### Enable Debug Logging

For detailed troubleshooting information, enable debug logging:

```bash
export AIDB_LOG_LEVEL=DEBUG
```

For low-level DAP protocol tracing:

```bash
export AIDB_ADAPTER_TRACE=1
```

Then restart your MCP client and check the logs for detailed error messages.

## Next Steps

Now that you've completed your first debugging session, explore more advanced features:

- **[Core Concepts](core-concepts.md)** - Understand sessions, breakpoints, and execution flow
- **[Tool Reference](tools/session-management.md)** - Detailed documentation for all tools
- **[Language-Specific Guides](languages/python.md)** - Python, JavaScript, Java debugging tips
- **[Advanced Workflows](advanced-workflows.md)** - Multi-session debugging, conditional breakpoints, advanced breakpoint techniques

### Join the Community

Get help and share your debugging workflows:

- **Discord**: [https://discord.com/invite/UGS92b6KgR](https://discord.com/invite/UGS92b6KgR)
- **GitHub**: [https://github.com/ai-debugger-inc/aidb](https://github.com/ai-debugger-inc/aidb)
