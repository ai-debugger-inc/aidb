# Tool Architecture

This document explains the architecture of MCP tools in AIDB, including tool handlers, decorators, and request/response flow.

## Overview

MCP tools follow a layered architecture:

```
Tool Definition (schema + metadata)
    ↓
Handler Registry (routing)
    ↓
Tool Handler (business logic)
    ↓
DebugService (core operations)
    ↓
Response Builder (standardized format)
```

## Directory Structure

```
src/aidb_mcp/
├── tools/
│   ├── definitions.py        # Tool schemas and metadata
│   ├── registry.py           # Tool handler mapping
│   ├── actions.py            # Action enums and validation
│   └── validation.py         # Parameter validation helpers
├── handlers/
│   ├── registry.py           # Central handler dispatcher
│   ├── session/              # Session management handlers
│   ├── execution/            # Execution control handlers
│   ├── inspection/           # Inspection handlers
│   ├── context/              # Context handlers
│   └── adapter_download/     # Adapter management handlers
├── responses/
│   ├── builders.py           # Response component builders
│   ├── errors.py             # Error response classes
│   ├── execution_responses.py # Execution response classes
│   ├── inspection_responses.py # Inspection response classes
│   └── session_responses.py   # Session response classes
├── core/
│   ├── constants.py          # Enums and constants
│   ├── exceptions.py         # Error classification
│   ├── decorators.py         # Handler decorators
│   ├── performance.py        # Performance tracking
│   ├── serialization.py      # JSON serialization
│   ├── response_limiter.py   # Size limiting
│   └── types.py              # Type definitions
└── server/
    └── server.py             # MCP server implementation
```

## Tool Definition

Tool definitions are in `src/aidb_mcp/tools/definitions.py`. They define the schema and metadata for each tool.

### Tool Schema Components

```python
from mcp.types import Tool
from aidb_mcp.core.constants import ToolName, ParamName

Tool(
    name=ToolName.YOUR_TOOL,  # Use constant, not string
    description=(
        "Primary description for the agent.\n\n"
        "Actions:\n"
        "- 'action1': What it does\n"
        "- 'action2': What it does\n"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            ParamName.ACTION: {
                "type": "string",
                "enum": ["action1", "action2"],
                "description": "Action to perform",
                "default": "action1",
            },
            ParamName.SESSION_ID: {
                "type": "string",
                "description": "Optional session ID",
            },
        },
        "required": [],  # Optional parameters have defaults
    },
)
```

### Schema Best Practices

**DO:**

- Use constants from `core/constants.py` for names
- Provide clear, concise descriptions
- Include examples for complex parameters
- Set sensible defaults
- Document enum values

**DON'T:**

- Use magic strings for parameter names
- Write verbose descriptions (agents need clarity, not essays)
- Require optional parameters
- Add unnecessary parameters "just in case"

## Handler Architecture

Handlers contain the business logic for tool operations. They are organized by category.

### Handler Categories

1. **Session Handlers** (`handlers/session/`)

   - Session lifecycle (start, stop, restart)
   - Session status and listing
   - Session switching

1. **Execution Handlers** (`handlers/execution/`)

   - Program execution (run, continue)
   - Stepping (into, over, out)
   - Breakpoint management
   - Run until operations

1. **Inspection Handlers** (`handlers/inspection/`)

   - Variable inspection (locals, globals)
   - Expression evaluation
   - Stack frame inspection
   - Thread inspection

1. **Context Handlers** (`handlers/context/`)

   - Debugging context gathering
   - Next-step suggestions
   - Execution history

1. **Adapter Handlers** (`handlers/adapter_download.py`)

   - Adapter installation
   - Adapter listing
   - Version management

### Handler Structure

```python
from typing import Any
from aidb_logging import get_mcp_logger as get_logger
from aidb_mcp.core.decorators import with_execution_context
from aidb_mcp.core.constants import ParamName, ResponseStatus
from aidb_mcp.core.exceptions import ErrorCode
from aidb_mcp.responses.errors import ErrorResponse
from aidb_mcp.responses.your_response import YourResponse

logger = get_logger(__name__)


@with_execution_context(track_variables=True)
async def handle_your_tool(args: dict[str, Any]) -> dict[str, Any]:
    """Handle your tool operation.

    Parameters
    ----------
    args : dict
        Tool arguments including:
        - action: Action to perform
        - session_id: Optional session ID
        - _service: DebugService instance (injected by decorator)
        - _context: Session context (injected by decorator)
        - _session_id: Active session ID (injected by decorator)

    Returns
    -------
    dict
        MCP response with success/error status
    """
    # Extract parameters
    action = args.get(ParamName.ACTION, "default_action")
    service = args.get("_service")
    context = args.get("_context")
    session_id = args.get("_session_id")

    logger.info(
        "Handling tool operation",
        extra={"action": action, "session_id": session_id}
    )

    try:
        # Validation
        if not action:
            return ErrorResponse(
                summary="Missing action parameter",
                error_code=ErrorCode.AIDB_VALIDATION_MISSING_PARAM.value,
                error_message="action is required",
            ).to_mcp_response()

        # Business logic using DebugService
        result = await service.your_component.your_operation(action)

        # Build response
        return YourResponse(
            summary=f"Successfully performed {action}",
            data={"result": result},
            next_steps=["Next action the agent could take"],
        ).to_mcp_response()

    except Exception as e:
        logger.warning(
            "Tool operation failed",
            extra={"error": str(e), "action": action}
        )
        return ErrorResponse(
            summary=f"Failed to perform {action}",
            error_code=ErrorCode.AIDB_EXECUTION_FAILED.value,
            error_message=str(e),
        ).to_mcp_response()
```

### Handler Registration

Handlers are registered in category modules:

```python
# handlers/your_category/__init__.py
from .handler import handle_tool1, handle_tool2
from aidb_mcp.core.constants import ToolName

HANDLERS = {
    ToolName.TOOL1: handle_tool1,
    ToolName.TOOL2: handle_tool2,
}
```

Then added to central registry:

```python
# handlers/registry.py
from .your_category import HANDLERS as YOUR_HANDLERS

TOOL_HANDLERS = {
    **SESSION_HANDLERS,
    **EXECUTION_HANDLERS,
    **YOUR_HANDLERS,  # Add here
}
```

## Decorators

Decorators provide cross-cutting functionality for handlers. AIDB provides four main decorators:

1. **@with_execution_context** - Captures debugging context (location, state, variables)
1. **@with_thread_safety** - Ensures thread-safe access to shared resources
1. **@require_initialized_session** - Validates session exists and injects service
1. **@timed** - Tracks operation performance

### Quick Reference

**Common patterns:**

```python
# Execution control tools (step, continue, run)
@with_thread_safety
@require_initialized_session
@with_execution_context(track_variables=True)
async def handle_step(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("_service")
    thread_id = await service.stepping.get_current_thread_id()
    await service.stepping.step_over(thread_id)
    return StepResponse(...).to_mcp_response()

# Inspection tools (evaluate, locals, stack)
@with_thread_safety
@require_initialized_session
@with_execution_context()
async def handle_inspect(args: dict[str, Any]) -> dict[str, Any]:
    service = args.get("_service")
    result = await service.variables.evaluate(expr)
    return InspectResponse(...).to_mcp_response()

# Session management (no active session required)
@with_thread_safety
async def handle_start_session(args: dict[str, Any]) -> dict[str, Any]:
    # Start new session
    return SessionResponse(...).to_mcp_response()
```

**Decorator order matters:**

- Outermost: `@with_thread_safety` (acquire lock first)
- Middle: `@require_initialized_session` (validate session, inject service)
- Innermost: `@with_execution_context` (capture context around handler)

**For complete reference:** See [handler-decorators-reference.md](handler-decorators-reference.md) for detailed documentation, parameters, examples, and best practices

## Request Flow

1. **MCP Server** receives tool call request
1. **Handler Registry** looks up handler by tool name
1. **Decorator Chain** executes (outer to inner)
1. **Handler** extracts parameters and validates
1. **DebugService** performs core debugging operation
1. **Response Builder** constructs standardized response
1. **Decorator Chain** adds context/metadata (inner to outer)
1. **MCP Server** returns response to client

### Request Arguments

Handlers receive a dictionary with:

**User-provided parameters:**

- From tool inputSchema
- Example: `action`, `target`, `location`, `expression`

**Injected parameters (by decorators):**

- `_service`: DebugService instance (for operations)
- `_context`: Session context (MCPSessionContext)
- `_session_id`: Active session ID

### Extracting Parameters

```python
# User parameters
action = args.get(ParamName.ACTION, "default")
target = args.get(ParamName.TARGET)
expression = args.get(ParamName.EXPRESSION)

# Injected parameters (from decorators)
service = args.get("_service")
context = args.get("_context")
session_id = args.get("_session_id")
```

## Response Flow

### Response Classes

Response classes are in `src/aidb_mcp/responses/`. They provide standardized response construction.

**Base structure:**

```python
from dataclasses import dataclass
from typing import Any
from aidb_mcp.core.constants import MCPResponseField


@dataclass
class YourResponse:
    """Response for your tool."""

    summary: str
    data: dict[str, Any]
    next_steps: list[str] | None = None

    def to_mcp_response(self) -> dict[str, Any]:
        """Convert to MCP response format."""
        response = {
            MCPResponseField.SUCCESS: True,
            MCPResponseField.SUMMARY: self.summary,
            MCPResponseField.DATA: self.data,
        }

        if self.next_steps:
            response[MCPResponseField.NEXT_STEPS] = self.next_steps

        return response
```

### Response Builders

Use builders to avoid duplication:

```python
from aidb_mcp.responses.builders import (
    ExecutionStateBuilder,
    CodeSnapshotBuilder,
)
from aidb_mcp.core.constants import DetailedExecutionStatus

# Build execution state
execution_state = ExecutionStateBuilder.build(
    detailed_status=DetailedExecutionStatus.STOPPED_AT_BREAKPOINT,
    has_breakpoints=True,
    stop_reason="breakpoint",
)
# Result: {"status": "stopped_at_breakpoint", "breakpoints_active": true, ...}

# Build code snapshot
code_snapshot = CodeSnapshotBuilder.build(
    code_context=context_result,
)
# Result: {"formatted": "...code..."} or None
```

### Response Optimization

**Deduplication:**

```python
from aidb_mcp.responses.deduplicator import ResponseDeduplicator

response = {
    "execution_state": execution_state,
    "code_snapshot": code_snapshot,
    "location": "file.py:42",  # Duplicate of execution_state.location
}

# Remove duplicate fields
deduplicated = ResponseDeduplicator.deduplicate(response)
```

**Size Limiting:**

```python
from aidb_mcp.core.response_limiter import ResponseLimiter

# Limit stack frames
frames, truncated = ResponseLimiter.limit_stack_frames(
    frames=all_frames,
    max_frames=10,
)

if truncated:
    response["truncated"] = True
    response["total_frames"] = len(all_frames)
    response["showing_frames"] = len(frames)
```

## Adding a New Tool (Condensed Example)

> **Note:** This is a conceptual example showing the complete flow. Actual implementation may vary.

**Pattern:** Define constants → Tool schema → Handler → Response class → Register → Test

**Key Steps:**

1. **Add Constants** (`src/aidb_mcp/core/constants.py`):

   ```python
   class ToolName:
       WATCH = "watch"  # Add to existing tools

   class WatchAction(Enum):
       SET = "set"
       REMOVE = "remove"
       LIST = "list"
   ```

1. **Define Tool Schema** (`src/aidb_mcp/tools/definitions.py`):

   - Add Tool definition with name, description, inputSchema
   - Use existing constants for parameter names

1. **Create Handler** (`src/aidb_mcp/handlers/execution/watch.py`):

   ```python
   @with_execution_context()
   async def handle_watch(args: dict[str, Any]) -> dict[str, Any]:
       """Handle watchpoint operations."""
       action = args.get(ParamName.ACTION, WatchAction.LIST.value)
       # Validate params, call API, return response
       return WatchResponse(summary="...", data={...}).to_mcp_response()
   ```

1. **Register Handler** (`src/aidb_mcp/handlers/execution/__init__.py`):

   ```python
   HANDLERS = {
       ToolName.WATCH: handle_watch,  # Add to registry
   }
   ```

1. **Create Response Class** (`src/aidb_mcp/responses/watch_response.py`):

   - Use dataclass pattern with `to_mcp_response()` method
   - Include summary, data, optional next_steps

1. **Write Tests** - See `resources/testing-mcp-tools.md`

**For Full Details:** Study existing tools like `aidb.breakpoint` or `aidb.inspect` in `src/aidb_mcp/`

## Summary

- **Tool definitions** provide schema and metadata
- **Handlers** contain business logic
- **Decorators** add cross-cutting functionality
- **Response builders** ensure consistency
- **Response classes** standardize format
- **Registry** dispatches to correct handler

Always prioritize agent experience: accuracy, clarity, speed, no junk.
