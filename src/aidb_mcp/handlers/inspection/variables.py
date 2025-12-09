"""Variable operation handlers.

Handles the variable tool for getting, setting, and patching variables.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import ToolName, VariableAction
from ...core.constants import ParamName
from ...core.decorators import mcp_tool
from ...responses import VariableGetResponse, VariableSetResponse
from ...responses.errors import InternalError, UnsupportedOperationError
from ...responses.helpers import (
    internal_error,
    missing_parameter,
    not_paused,
)
from ...tools.actions import normalize_action

logger = get_logger(__name__)


def _check_paused_state(api, context) -> dict[str, Any] | None:
    """Check if debugger is paused.

    Returns error response if not paused, None otherwise.
    """
    # Check actual session state from the API
    if api and hasattr(api, "session"):
        session = api.session
        if hasattr(session, "state") and hasattr(session.state, "is_paused"):
            if not session.state.is_paused():
                return not_paused(
                    operation="variable operation",
                    suggestion=("Set a breakpoint or wait for execution to pause"),
                    session=session,
                )
        else:
            # Fallback to context check if state API not available
            if not context.at_breakpoint and not (context.error_info):
                return not_paused(
                    operation="variable operation",
                    suggestion=("Set a breakpoint or wait for execution to pause"),
                    session=session,
                )
    else:
        # No API available, use context check
        if not context.at_breakpoint and not (context.error_info):
            return not_paused(
                operation="variable operation",
                suggestion="Set a breakpoint or wait for execution to pause",
                # No session available in this case
            )
    return None


async def _handle_get_variable(
    api,
    session_id: str | None,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle GET variable action."""
    expression = args.get(ParamName.EXPRESSION)
    if not expression:
        logger.debug(
            "Missing expression for variable get",
            extra={"action": VariableAction.GET.name},
        )
        return missing_parameter(
            param_name=ParamName.EXPRESSION,
            param_description=("Provide 'expression' parameter with variable name"),
        )

    # Handle frame parameter - treat 0 (MCP default) as None for dynamic resolution
    frame_param = args.get(ParamName.FRAME, 0)
    if frame_param == 0:
        frame_param = None

    logger.debug(
        "Getting variable value",
        extra={
            "action": VariableAction.GET.name,
            "expression": expression,
            "frame_id": frame_param,
        },
    )
    eval_result = await api.introspection.evaluate(expression, frame_id=frame_param)

    # Extract only the needed fields from EvaluationResult
    # Avoid nesting the entire object which creates result.result structure
    return VariableGetResponse(
        expression=expression,
        value=eval_result.result,  # Just the actual value, not the whole object
        type_name=eval_result.type_name,
        frame=frame_param or 0,
        session_id=session_id,
    ).to_mcp_response()


async def _handle_set_variable(
    api,
    session_id: str | None,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle SET variable action."""
    name = args.get(ParamName.NAME)
    value = args.get(ParamName.VALUE)

    if not name:
        logger.debug(
            "Missing name for variable set",
            extra={"action": VariableAction.SET.name},
        )
        return missing_parameter(
            param_name=ParamName.NAME,
            param_description="Provide 'name' parameter with variable name",
        )

    if value is None:
        logger.debug(
            "Missing value for variable set",
            extra={"action": VariableAction.SET.name, "variable_name": name},
        )
        return missing_parameter(
            param_name=ParamName.VALUE,
            param_description="Provide 'value' parameter with new value",
        )

    logger.info(
        "Setting variable value",
        extra={
            "action": VariableAction.SET.name,
            "variable_name": name,
            "value_type": type(value).__name__,
            "frame_id": args.get(ParamName.FRAME),
        },
    )
    await api.introspection.set_variable(
        name=name,
        value=str(value),
        frame_id=args.get(ParamName.FRAME),
    )

    return VariableSetResponse(
        name=name,
        new_value=value,
        frame=args.get(ParamName.FRAME, 0),
        session_id=session_id,
    ).to_mcp_response()


async def _handle_patch_variable(
    _api,
    _session_id: str | None,
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Handle PATCH variable action."""
    logger.info(
        "Patch action requested but not supported",
        extra={"action": VariableAction.PATCH.name},
    )
    return UnsupportedOperationError(
        operation="Patch action",
        error_message="Live code patching is not yet supported",
    ).to_mcp_response()


@mcp_tool(
    require_session=True,
    include_after=True,
    track_variables=True,
)
async def handle_variable(args: dict[str, Any]) -> dict[str, Any]:
    """Handle variable - unified get/set variable operations."""
    from ..dispatch import dispatch_action

    raw_action = args.get(ParamName.ACTION, VariableAction.GET.value)
    logger.info(
        "Variable handler invoked",
        extra={
            "action": raw_action,
            "tool": ToolName.VARIABLE,
        },
    )

    # Get session components from decorator
    session_id = args.get("_session_id")
    api = args.get("_api")
    context = args.get("_context")

    # The decorator guarantees these are present
    if not api or not context:
        return InternalError(
            error_message="Debug API or context not available",
        ).to_mcp_response()

    action_handlers = {
        VariableAction.GET: _handle_get_variable,
        VariableAction.SET: _handle_set_variable,
        VariableAction.PATCH: _handle_patch_variable,
    }

    handler, error, handler_args = dispatch_action(
        args,
        VariableAction,
        action_handlers,
        default_action=VariableAction.GET,
        tool_name=ToolName.VARIABLE,
        handler_args=(api, session_id),
        normalize=True,
    )

    if error or handler is None:
        return error or internal_error(
            operation="variable",
            exception="No handler found",
        )

    # Check paused state for GET and SET actions
    action_str = normalize_action(raw_action, "variable")
    if action_str in [VariableAction.GET.value, VariableAction.SET.value]:
        pause_error = _check_paused_state(api, context)
        if pause_error:
            return pause_error

    try:
        return await handler(*handler_args)
    except Exception as e:
        logger.exception(
            "Variable operation failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "action": raw_action,
            },
        )
        return internal_error(operation="variable", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.VARIABLE: handle_variable,
}
