"""State inspection handlers.

Handles the inspect tool for examining program state (locals, globals, stack, etc).
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import InspectTarget, ToolName
from ...core.constants import ParamName
from ...core.decorators import mcp_tool
from ...core.performance import timed
from ...responses import InspectResponse
from ...responses.errors import InternalError
from ...responses.helpers import missing_parameter
from .inspect_advanced import inspect_all
from .inspect_execution import inspect_stack, inspect_threads
from .inspect_variables import inspect_expression, inspect_globals, inspect_locals

logger = get_logger(__name__)


@timed
async def _parse_inspect_target(target: Any) -> InspectTarget | None:
    """Parse target string to InspectTarget enum."""
    if target and isinstance(target, str):
        try:
            return InspectTarget(target)
        except ValueError:
            return None
    return target


def _map_target_to_expression(target_enum: InspectTarget) -> str | None:
    """Map InspectTarget enum to its expression."""
    target_to_expression = {
        InspectTarget.LOCALS: "locals()",
        InspectTarget.GLOBALS: "globals()",
        InspectTarget.STACK: "__stack__",
        InspectTarget.THREADS: "__threads__",
        InspectTarget.EXPRESSION: None,  # Requires explicit expression
        InspectTarget.ALL: "__all__",  # Special target for all info
    }
    return target_to_expression.get(target_enum)


@mcp_tool(
    require_session=True,
    include_after=True,
    track_variables=True,
)
async def handle_inspect(args: dict[str, Any]) -> dict[str, Any]:
    """Inspect program state during debugging."""
    try:
        # Handle both 'target' (from schema) and 'expression' parameters
        target = args.get(ParamName.TARGET)
        expression = args.get(ParamName.EXPRESSION)

        logger.info(
            "Inspect handler invoked",
            extra={
                "target": target,
                "has_expression": bool(expression),
                "tool": ToolName.INSPECT,
            },
        )

        # Convert string target to enum if needed
        target_enum = await _parse_inspect_target(target)

        # Map target to expression if target is provided
        if target_enum and not expression:
            expression = _map_target_to_expression(target_enum)
            if expression:
                logger.debug(
                    "Target mapped to expression",
                    extra={
                        "target": target,
                        "mapped_expression": expression,
                        "target_enum": target_enum.name if target_enum else target,
                    },
                )

        frame_id = args.get(ParamName.FRAME, args.get(ParamName.FRAME_ID))
        session_id = args.get("_session_id")
        service = args.get("_service")  # Phase 2: DebugService for operations

        # The decorator guarantees service is present
        if not service:
            return InternalError(
                error_message="DebugService not available",
            ).to_mcp_response()

        if not expression:
            logger.debug(
                "Missing expression for inspection %s",
                extra={"target": target},
            )
            return missing_parameter(
                param_name=ParamName.EXPRESSION,
                param_description="Specify an expression or variable to inspect",
            )

        # Map expressions to handlers (Phase 2: pass service instead of api)
        expression_handlers = {
            "locals()": inspect_locals,
            "__locals__": inspect_locals,
            "globals()": inspect_globals,
            "__globals__": inspect_globals,
            "__stack__": inspect_stack,
            "__threads__": inspect_threads,
            "__all__": inspect_all,
        }

        # Execute appropriate handler or evaluate expression
        handler = expression_handlers.get(expression)
        if handler:
            data = await handler(service)
        else:
            data = await inspect_expression(service, expression, frame_id)

        # Return using new response class
        logger.info(
            "Inspection completed",
            extra={
                "target": target or expression,
                "frame_id": frame_id or 0,
                "has_result": bool(data),
                "session_id": session_id,
            },
        )
        return InspectResponse(
            target=target or InspectTarget.EXPRESSION.value,
            result=data,
            frame=frame_id or 0,
            expression=expression,
            session_id=session_id,
        ).to_mcp_response()

    except Exception as e:
        logger.exception(
            "Inspect failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "target": target,
                "expression": (
                    expression[:100]
                    if expression and len(expression) > 100
                    else expression
                ),
            },
        )
        return InternalError(
            operation="inspect",
            details=str(e),
            error_message=str(e),
        ).to_mcp_response()


# Export handler functions
HANDLERS = {
    ToolName.INSPECT: handle_inspect,
}
