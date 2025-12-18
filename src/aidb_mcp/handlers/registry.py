"""Handler registry for consolidated MCP tools."""

from __future__ import annotations

import asyncio
from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ..core.constants import EXECUTION_TOOLS
from ..core.exceptions import ErrorCode
from ..core.performance import TraceSpan
from ..core.performance_types import SpanType
from ..core.types import ErrorContext

# Central registry for cross-package access
from ..registry import load_tool_mapping
from ..responses.errors import ErrorResponse
from ..responses.helpers import invalid_action, invalid_parameter
from ..session.manager_state import get_session_id_from_args

# Import all handlers
from .adapter_download import HANDLERS as ADAPTER_DOWNLOAD_HANDLERS
from .context import HANDLERS as CONTEXT_HANDLERS
from .execution import HANDLERS as EXECUTION_HANDLERS
from .inspection import HANDLERS as INSPECTION_HANDLERS
from .session import HANDLERS as SESSION_HANDLERS

logger = get_logger(__name__)

# Build the complete registry
TOOL_HANDLERS = {
    **SESSION_HANDLERS,
    **EXECUTION_HANDLERS,
    **INSPECTION_HANDLERS,
    **CONTEXT_HANDLERS,
    **ADAPTER_DOWNLOAD_HANDLERS,
}

# Populate central registry once on import for other packages (e.g., tools)
load_tool_mapping(TOOL_HANDLERS)


async def _cleanup_cancelled_tool(name: str, args: dict[str, Any]) -> None:
    """Cleanup resources for cancelled tool operations.

    Parameters
    ----------
    name : str
        Tool name that was cancelled
    args : dict
        Arguments passed to the tool
    """
    try:
        # Get session ID if available (uses canonical resolution pattern)
        session_id = get_session_id_from_args(args)

        if session_id and name in EXECUTION_TOOLS:
            # For debug operations, ensure session state is consistent
            from ..session import get_or_create_session

            logger.debug(
                "Cleaning up cancelled debug operation",
                extra={"tool_name": name, "session_id": session_id},
            )

            try:
                _, context = get_or_create_session(session_id)
                if context and hasattr(context, "is_running"):
                    context.is_running = False
                    # Don't terminate the session, just ensure it's in a clean state
            except Exception as cleanup_err:
                logger.warning(
                    "Error during session cleanup",
                    extra={
                        "tool_name": name,
                        "session_id": session_id,
                        "error": str(cleanup_err),
                    },
                )

        logger.debug(
            "Completed cleanup for cancelled tool",
            extra={"tool_name": name},
        )

    except Exception as e:
        logger.warning(
            "Failed to cleanup cancelled tool",
            extra={"tool_name": name, "error": str(e)},
        )


async def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Handle a tool invocation with smart defaults and tracing.

    Parameters
    ----------
    name : str
        Tool name
    args : dict
        Tool arguments

    Returns
    -------
    dict
        Tool response
    """
    with TraceSpan(SpanType.HANDLER_DISPATCH, f"dispatch.{name}") as span:
        # Defensive input validation
        if not name or not isinstance(name, str):
            logger.error("Invalid tool name: %s", name)
            return invalid_parameter(
                param_name="name",
                expected_type="non-empty string",
                received_value=str(type(name)),
            )

        if args is None:
            args = {}
        elif not isinstance(args, dict):
            logger.warning("Tool args not a dict for %s: %s", name, type(args))
            args = {}

        # Get handler
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            available_tools = list(TOOL_HANDLERS.keys())
            logger.warning(
                "Unknown tool requested",
                extra={"tool_name": name, "available_tools": available_tools},
            )
            return invalid_action(
                action=name,
                valid_actions=available_tools,
                tool_name="registry",
            )

        # Add handler name to span metadata
        if span:
            span.metadata["handler_name"] = handler.__name__

        # Execute handler with its own tracing and cancellation handling
        session_id = get_session_id_from_args(args)
        logger.info(
            "Executing tool: %s",
            name,
            extra={
                "tool_name": name,
                "handler": handler.__name__,
                "session_id": session_id,
            },
        )

        try:
            return await handler(args)
        except asyncio.CancelledError:
            logger.info(
                "Tool execution cancelled",
                extra={"tool_name": name, "handler": handler.__name__},
            )
            # Perform cleanup for the specific tool if needed
            await _cleanup_cancelled_tool(name, args)

            # Return a proper cancellation response instead of re-raising
            return ErrorResponse(
                summary=f"Tool '{name}' execution was cancelled",
                error_code=ErrorCode.AIDB_OPERATION_CANCELLED.value,
                error_message=f"Execution of '{name}' was cancelled by the client",
                context=ErrorContext(tool_name=name, cancelled=True),
            ).to_mcp_response()
        except Exception as e:
            logger.exception(
                "Tool execution failed",
                extra={"tool_name": name, "handler": handler.__name__, "error": str(e)},
            )
            # Re-raise unexpected exceptions
            raise
