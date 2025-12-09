# AI Debugger (aidb) - Claude Code Context

## Project Overview

**AI Debugger (aidb)** is a lightweight, language-agnostic Python API that
enables AI systems to programmatically control and introspect live debugging
sessions through the Debug Adapter Protocol (DAP). It serves as an ideal Model
Context Protocol (MCP) tool for AI-assisted debugging workflows.

The debugger interface is intended to function at a ***human cadence***, not a
typical, super-fast API. For example:

- If you want to inspect runtime state in a program that executes quickly, you
  must set a breakpoint when you start the debug session. If you need to set a
  conditional breakpoint, you must do so before starting the debug session.
- If you want to perform introspection on the state, you must execute the
  operations on a paused program that fetch whatever is needed, e.g. local
  variables or a stack frame.
- If you want to advance a line, that is a single operation. To skip multiple
  lines, you must execute multiple operations, just like a human using a
  debugger.
- If you want to use your `launch.json` file, you can.

**User Profile:** Developers building debugging tools + AI agents using MCP for code debugging workflows.

## Project Components

**Core Debugger:** `aidb/` - Language-agnostic debugging API, adapters (Python/JavaScript/Java), session management
**MCP Integration:** `aidb_mcp/` - MCP server exposing 12 debugging tools to AI agents
**Developer Tools:** `aidb_cli/` - CLI for testing orchestration, Docker management, adapter builds
**Shared Libraries:** `aidb_common/` (config, validation, paths), `aidb_logging/` (structured logging)

## Architecture Overview

AI Debugger is built on a layered architecture that provides language-agnostic debugging capabilities:

1. **MCP Layer** (`aidb_mcp/`): Model Context Protocol server exposing 12 agent-optimized debugging tools
1. **API Layer** (`aidb/api/`): High-level Python API with `.introspection` and `.orchestration` operations
1. **Session Layer** (`aidb/session/`): Core session orchestration, state management, and lifecycle control
1. **Adapter Layer** (`aidb/adapters/`): Language-specific debug adapters (Python, JavaScript, Java)
1. **DAP Client Layer** (`aidb/dap/client/`): Debug Adapter Protocol client implementation
1. **Protocol Layer** (`aidb/dap/protocol/`): Fully-typed DAP specification (authoritative reference)

### Key Architectural Concepts

- **Human-Cadence Debugging**: Operations happen at human speed, not API speed. For fast-executing programs, breakpoints must be set when starting the session.
- **Language-Agnostic API**: The same Python API works for Python, JavaScript, and Java through pluggable adapters.
- **Component-Based Design**: Adapters delegate to focused components (`ProcessManager`, `PortManager`, `LaunchOrchestrator`) rather than monolithic classes.
- **Child Sessions**: JavaScript/TypeScript use parent-child session patterns to handle subprocess debugging.
- **Resource Management**: Centralized cleanup of ports, PIDs, and processes via `ResourceManager`.

### Critical References

- **Full DAP Protocol**: `src/aidb/dap/protocol.py` (fully typed, authoritative source)
- **Architecture Documentation**: `docs/developer-guide/overview.md`
- **Adapter Implementations**: `src/aidb/adapters/lang/{python,javascript,java}/`

## Skills System

This project uses Claude Code skills for domain-specific guidance. Skills activate automatically when relevant topics or files are detected.

**Key Skills:** testing-strategy, adapter-development, dap-protocol-guide, mcp-tools-development, dev-cli-development, code-reuse-enforcement, ci-cd-workflows
**Meta-Skill:** skill-developer (always active, maintains the skills system)
**Configuration:** `.claude/skills/skill-rules.json`

### Automatic Skill Loading

Skills are automatically loaded based on context detection:

- The UserPromptSubmit hook analyzes your prompt using AI-powered intent analysis
- When relevant skills are detected, they are automatically injected into the conversation context
- You'll see a "📚 AUTO-LOADED SKILLS" banner showing which skills were loaded
- Skills are loaded once per conversation and reused in subsequent turns

**Why Skills Matter:**

- The codebase is complex with critical patterns, constraints, and architectural decisions
- Skills contain domain-specific knowledge essential for correct implementation
- Auto-loading ensures you always have the right context without manual intervention

**Examples:**

- Working on adapter code → `adapter-development` skill auto-loads
- Writing/modifying tests → `testing-strategy` skill auto-loads
- Multiple relevant topics → Multiple skills auto-load together

## Communication Guidelines

### Avoid Sycophantic Language

- Avoid phrases like "You're absolutely right!", "Excellent point!", or similar flattery
- Do not validate statements as "right" when no factual claim was made
- Do not use general praise or validation as conversational filler

## Testing

**All tests MUST be run via `./dev-cli test run`:**

```bash
./dev-cli test run -s {suite} [-k 'pattern'] [-l {lang}]
```

- Multiple `-k` and `-l` flags are supported
- **NEVER use `--local`** - suites already know their natural execution environment (local or Docker); forcing local can cause unexpected behavior

For testing strategy, test organization, and execution guidance, use the `testing-strategy` skill (auto-activates on testing topics).

## General Prompt Instructions

1. If we add/change any code, lint it. It should pass pre-commit checks
   (excluding bandit and vulture).
1. If we add/change code, check to see if there are any related tests. If there
   are, modify them as necessary to account for the changed code.
1. If we add/change code, check to see if there are any related docs. If there
   are, modify them as necessary to account for the changed code.
1. Always be sure to check for existing functionality/implementations that we may be able to use prior to
   writing new code.
1. Always check for existing constant/enum patterns that we should adhere to. If
   we find ourselves adding lots of magic strings/numbers, perhaps we need to add
   constants and/or enums.
1. Refactor to eliminate duplication.

## Code Reuse

Before implementing new functionality, use the `code-reuse-enforcement` skill to check for existing utilities and patterns (auto-activates when adding new code).

## Important Notes

- Avoid unnecessary comments; code should be self-documenting where possible
- Always use the repo's venv when running project-related Python commands
- This is a greenfield project: prefer clean implementations over backward
  compatibility layers or deprecation patterns
- Place imports at the top of the file (unless avoiding a circular import)
- Do not use emojis in log messages
- Adhere to the style guidelines defined in the pre-commit configuration
- For DAP protocol questions, refer to our fully-typed DAP implementation: `src/aidb/dap/protocol.py`
