---
skill_name: mcp-tools-development
description: Comprehensive guide for creating and modifying AIDB MCP tools with agent
  optimization
version: 1.0.0
author: AIDB Team
---

# MCP Tools Development Skill

This skill guides you through creating and modifying MCP tools for the AI Debugger (AIDB). MCP tools are the primary interface between AI agents and the debugging system - they must be fast, accurate, and clear.

## Core Philosophy: Agent Optimization

MCP tools are **user-facing products**. Every response is read by an AI agent with limited context. Your goal:

1. **Accuracy**: Responses must contain correct information (line numbers, values, state)
1. **Clarity**: Summaries must be clear and actionable, not verbose
1. **Speed**: Operations must be fast (agents iterate rapidly)
1. **No Junk**: No unnecessary fields, no bloated payloads, no redundant data

**Context windows are sacred** - every token matters.

## Quick Start

### When to Use This Skill

Invoke this skill when:

- Creating a new MCP tool (e.g., `aidb.watch` for watchpoints)
- Modifying existing tool behavior
- Fixing MCP response issues
- Optimizing tool performance
- Debugging tool handler errors

## Related Skills

When developing MCP tools, you may also need:

- **dap-protocol-guide** - MCP tools use DAP types for all debugging operations
- **testing-strategy** - MCP tools tested with DebugInterface for content accuracy
- **code-reuse-enforcement** - Must use existing constants/enums from core package

### MCP Architecture Overview

**For complete MCP server architecture**, see:

- `docs/developer-guide/overview.md` - System architecture showing MCP layer integration
- `src/aidb_mcp/` - MCP server implementation

```
User Request
    ↓
MCP Server (src/aidb_mcp/server/)
    ↓
Handler Registry (src/aidb_mcp/handlers/registry.py)
    ↓
Tool Handler (src/aidb_mcp/handlers/{category}/)
    ↓
DebugService (src/aidb/service/)
    ↓
Response Builder (src/aidb_mcp/responses/)
    ↓
MCP Response
```

**Key Components:**

- **Tool Definitions** (`src/aidb_mcp/tools/definitions.py`): Tool schemas and metadata
- **Handler Registry** (`src/aidb_mcp/handlers/registry.py`): Dispatcher to handlers
- **Tool Handlers** (`src/aidb_mcp/handlers/{category}/`): Business logic
- **Response Builders** (`src/aidb_mcp/responses/`): Standardized response construction
- **Decorators** (`src/aidb_mcp/core/decorators.py`): Common handler functionality

## Resource Files

For detailed guidance, see these resources:

- **[Tool Architecture](resources/tool-architecture.md)** - Tool structure, handlers, decorators
- **[Testing MCP Tools](resources/testing-mcp-tools.md)** - E2E and integration testing

## Code Reuse: Don't Reinvent

Before writing new code, check these shared modules:

### Constants and Enums

**File:** `src/aidb_mcp/core/constants.py`

```python
from aidb_mcp.core.constants import (
    ToolName,           # Tool names (INSPECT, STEP, EXECUTE, etc.) - class
    SessionAction,      # Session actions (START, STOP, STATUS, etc.) - Enum
    InspectTarget,      # Inspection targets (LOCALS, GLOBALS, STACK, etc.) - Enum
    StepAction,         # Step actions (INTO, OVER, OUT) - Enum
    ExecutionAction,    # Execution actions (RUN, CONTINUE) - Enum
    ErrorCode,          # Standardized error codes - Enum (in exceptions.py)
    ResponseStatus,     # Response statuses (OK, ERROR, WARNING) - class
    ParamName,          # Common parameter names - class
    ResponseFieldName,  # Response field names - class
    MCPResponseField,   # MCP protocol field names - class
)
```

**Note:** Some constants use classes instead of Enums for flexibility. Never use magic strings - always use constants.

### Exception Types

**File:** `src/aidb_mcp/core/exceptions.py`

```python
from aidb_mcp.core.exceptions import (
    ErrorCode,          # Error codes enum
    ErrorCategory,      # Error categories (VALIDATION, SESSION, etc.)
    ErrorRecovery,      # Recovery strategies
    classify_error,     # Classify exception by type/message
    get_recovery_strategy,     # Get recovery options
    get_suggested_actions,     # Get user-friendly actions
)
```

**Use these for error handling** - don't create new exception types unless necessary.

### Performance Types

**File:** `src/aidb_mcp/core/performance_types.py`

```python
from aidb_mcp.core.performance_types import (
    SpanType,           # Performance span types
    PerformanceSpan,    # Span data class
    TimingFormat,       # Output formats
)
```

**Use for performance tracking** - consistent metrics across tools.

## Quick Patterns

### Creating a New Tool (Step-by-Step)

> **Note:** Examples below use placeholder names (`YOUR_TOOL`, `YourResponse`). See actual implementations in `src/aidb_mcp/handlers/execution/stepping.py` and `src/aidb_mcp/responses/execution.py`.

**1. Define the tool schema** (`src/aidb_mcp/tools/definitions.py`):

```python
Tool(
    name=ToolName.YOUR_TOOL,  # Use constant from core/constants.py
    description="Clear, concise description.\n\nActions:\n- 'action1': What it does",
    inputSchema={
        "type": "object",
        "properties": {
            ParamName.ACTION: {"type": "string", "enum": ["action1", "action2"]},
            ParamName.SESSION_ID: {"type": "string"},
        },
    },
)
```

**2. Create the handler** (`src/aidb_mcp/handlers/your_category/handler.py`):

```python
from aidb_logging import get_mcp_logger as get_logger
from aidb_mcp.core.decorators import with_execution_context
from aidb_mcp.responses.errors import ErrorResponse

@with_execution_context(track_variables=True)
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Handle your tool operation."""
    action = args.get(ParamName.ACTION)
    api = args.get("_api")

    try:
        result = await api.your_operation()
        return YourResponse(summary=f"Performed {action}", data={"result": result}).to_mcp_response()
    except Exception as e:
        return ErrorResponse(summary="Operation failed", error_code=ErrorCode.AIDB_ERROR.value, error_message=str(e)).to_mcp_response()
```

**3. Register the handler** (`src/aidb_mcp/handlers/your_category/__init__.py`):

```python
from .handler import handle_your_tool

HANDLERS = {ToolName.YOUR_TOOL: handle_your_tool}
```

**4. Add to registry** (`src/aidb_mcp/handlers/registry.py`):

```python
from .your_category import HANDLERS as YOUR_HANDLERS

TOOL_HANDLERS = {**SESSION_HANDLERS, **YOUR_HANDLERS}
```

**5. Create response class** (`src/aidb_mcp/responses/your_response.py`):

```python
from dataclasses import dataclass
from aidb_mcp.core.constants import MCPResponseField

@dataclass
class YourResponse:
    summary: str
    data: dict[str, Any]

    def to_mcp_response(self) -> dict[str, Any]:
        return {
            MCPResponseField.SUCCESS: True,
            MCPResponseField.SUMMARY: self.summary,
            MCPResponseField.DATA: self.data,
        }
```

### Modifying an Existing Tool

**1. Locate:** Tool definitions in `src/aidb_mcp/tools/definitions.py`, handlers in `src/aidb_mcp/handlers/{category}/`

**2. Update schema** (if adding parameters) in `definitions.py`

**3. Update handler** to extract new parameter and validate

**4. Update response** to include new fields if needed

## Common Decorators

### `@with_execution_context`

Captures debugging context and adds to response. Use when tool modifies execution state.

```python
@with_execution_context(include_after=True, track_variables=False)
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    pass  # Context automatically added
```

### `@with_thread_safety`

Ensures thread-safe access to shared resources. From `aidb_mcp.core.decorator_primitives`.

### `@timed`

Tracks operation performance. From `aidb_mcp.core.performance`.

## Response Construction

### Response Builders

Use `ExecutionStateBuilder` and `CodeSnapshotBuilder` from `aidb_mcp.responses.builders` to avoid duplication.

### Response Deduplication

Use `ResponseDeduplicator.deduplicate()` from `aidb_mcp.responses.deduplicator` to remove duplicate fields.

### Response Size Limiting

Use `ResponseLimiter` from `aidb_mcp.core.response_limiter`:

- `limit_stack_frames(frames, max_frames=10)`
- `limit_variables(variables, max_vars=50)`
- `limit_code_context(lines, current_line, context_lines=5)`

### Compact Mode (Agent-Optimized Responses)

By default (`AIDB_MCP_VERBOSE=0`), responses are optimized for AI agents:

- **init**: Returns minimal `{language, framework, ready}` instead of full examples/tips
- **session_start**: Excludes `next_steps` guidance (agents learn from schema descriptions)
- **inspect (locals/globals)**: Variables use compact format `{"varName": {"v": "value", "t": "type", "varRef": N}}`

Set `AIDB_MCP_VERBOSE=1` for human-friendly responses with full details and guidance.

**Implementation pattern:**

```python
from aidb_common.config.runtime import ConfigManager

if ConfigManager().is_mcp_verbose():
    # Return full format
else:
    # Return compact format
```

## Validation

### Parameter Validation

Use `ErrorResponse` for missing/invalid parameters. Use `validate_action(action, EnumClass)` from `aidb_mcp.tools.actions` for action validation.

### Session Validation

Use `@require_initialized_session` decorator from `aidb_mcp.core.decorator_primitives` to auto-validate session and inject `_api`, `_context`, `_session_id`.

## Error Handling

Use `classify_error()` and `get_suggested_actions()` from `aidb_mcp.core.exceptions` to provide user-friendly error messages with recovery suggestions. Always include `suggested_actions` in error responses.

## Testing Your Tool

Use `DebugInterface` from `tests._helpers.debug_interface` for E2E tests. Validate three dimensions:

1. **Structure**: Response matches MCP protocol
1. **Content accuracy**: Data reflects actual debug state
1. **Efficiency**: No bloat (essential fields only)

See **[Testing MCP Tools](resources/testing-mcp-tools.md)** for comprehensive testing guidance.

## Best Practices

### DO

- Use constants from `core/constants.py` instead of magic strings
- Use existing exception types from `core/exceptions.py`
- Use response builders to avoid duplication
- Limit response size with `ResponseLimiter`
- Provide clear, actionable error messages
- Track performance with `@timed` decorator
- Write E2E tests that validate content accuracy
- Set breakpoints at session start to avoid race conditions:
  ```python
  # ✅ CORRECT
  await api.start_session(program=file, breakpoints=[{"line": 10}])
  ```

### DON'T

- Return verbose summaries (agents need concise guidance)
- Include unnecessary fields in responses
- Use magic strings for field names or error codes
- Create new exception types without checking existing ones
- Skip input validation
- Ignore performance implications
- Test only structure (validate content accuracy too)

## Common Pitfalls

1. **Bloated Responses**: Include only essential fields the agent needs for next action
1. **Verbose Summaries**: Keep concise and actionable (e.g., "Retrieved 5 local variables at line 42")
1. **Poor Error Messages**: Provide user-friendly guidance with suggested actions, not technical errors

## Summary

**Internal Documentation**: For MCP server implementation details, see `src/aidb_mcp/` and `docs/developer-guide/overview.md` for system architecture.

MCP tools are the user-facing product of AIDB. Every tool must be:

1. **Accurate** - Correct line numbers, values, state
1. **Clear** - Concise summaries, actionable next steps
1. **Fast** - Optimized operations, limited responses
1. **Clean** - No junk fields, no redundant data

Use the resources linked above for deep dives into specific topics. Always prioritize agent experience - context windows are precious.
