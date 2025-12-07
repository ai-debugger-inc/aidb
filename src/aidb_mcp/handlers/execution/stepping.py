"""Stepping control handlers.

Handles the step tool for step into/over/out operations.
"""

from __future__ import annotations

from typing import Any

from aidb.dap.client.constants import StopReason as DAPStopReason
from aidb_logging import get_mcp_logger as get_logger

from ...core import StepAction, ToolName
from ...core.constants import ParamName, ResponseDataKey, SessionState
from ...core.context_utils import build_error_execution_state
from ...core.decorators import mcp_tool
from ...responses import StepResponse
from ...responses.errors import InternalError
from ...responses.helpers import handle_timeout_error, invalid_parameter, not_paused

logger = get_logger(__name__)


def _validate_step_action(action_str: str) -> StepAction | dict[str, Any]:
    """Validate step action string.

    Parameters
    ----------
    action_str : str
        The action string to validate

    Returns
    -------
    StepAction | dict
        Valid StepAction or error response dict
    """
    try:
        action = StepAction(action_str) if action_str else StepAction.OVER
        logger.debug(
            "Step action validated",
            extra={
                "action": action.name,
                "action_value": action.value,
            },
        )
        return action
    except ValueError:
        logger.warning(
            "Invalid step action",
            extra={
                "action": action_str,
                "valid_actions": [e.name for e in StepAction],
            },
        )
        return invalid_parameter(
            param_name=ParamName.ACTION,
            expected_type="'into', 'over', or 'out'",
            received_value=action_str,
            error_message=(
                f"Action must be 'into', 'over', or 'out', got '{action_str}'"
            ),
        )


def _check_debugger_paused(
    api: Any,
    action: StepAction,
    session_id: str,
) -> dict[str, Any] | None:
    """Check if debugger is paused (required for stepping).

    Parameters
    ----------
    api : Any
        Debug API instance
    action : StepAction
        The step action to perform
    session_id : str
        Session ID

    Returns
    -------
    dict | None
        Error response if not paused, None if ok
    """
    # Get active session (child if exists, otherwise parent)
    # to ensure we check the correct session's stopped state
    active_session = None
    if api and hasattr(api, "get_active_session"):
        active_session = api.get_active_session()

    if (
        active_session
        and hasattr(active_session, "dap")
        and not active_session.dap.is_stopped
    ):
        logger.debug(
            "Step operation blocked - not paused",
            extra={
                "action": action.name,
                "session_id": session_id,
                "state": SessionState.RUNNING.name,
            },
        )
        return not_paused(
            operation="step",
            suggestion="Set a breakpoint or wait for execution to pause",
            session=active_session,
        )
    return None


async def _execute_single_step(
    api: Any,
    action: StepAction,
    iteration: int,
    count: int,
) -> Any:
    """Execute a single step operation.

    Parameters
    ----------
    api : Any
        Debug API instance
    action : StepAction
        The step action
    iteration : int
        Current iteration (1-based)
    count : int
        Total count

    Returns
    -------
    Any
        Step result
    """
    action_map = {
        StepAction.INTO: (api.orchestration.step_into, "stepping into"),
        StepAction.OVER: (api.orchestration.step_over, "stepping over"),
        StepAction.OUT: (api.orchestration.step_out, "stepping out"),
    }

    method, desc = action_map.get(action, (None, None))
    if not method:
        msg = f"Unexpected step action: {action}"
        raise ValueError(msg)

    logger.debug(
        "Step %s/%s: %s",
        iteration,
        count,
        desc,
        extra={"action": action.name, "iteration": iteration},
    )
    return await method()


async def _execute_step_sequence(
    api: Any,
    action: StepAction,
    count: int,
    session_id: str,
    context: Any = None,
) -> list[dict[str, Any]]:
    """Execute a sequence of step operations.

    Parameters
    ----------
    api : Any
        Debug API instance
    action : StepAction
        The step action to perform
    count : int
        Number of steps to execute
    session_id : str
        Session identifier
    context : Any, optional
        Session context to sync position from execution state

    Returns
    -------
    list[dict]
        List of step results
    """
    results = []
    last_exec_state = None
    logger.debug(
        "Executing step operations",
        extra={"action": action.name, "count": count, "session_id": session_id},
    )

    for i in range(count):
        result = await _execute_single_step(api, action, i + 1, count)

        step_info = {ResponseDataKey.STEP: i + 1}
        if hasattr(result, "execution_state"):
            exec_state = result.execution_state
            last_exec_state = exec_state  # Track last state for position sync
            step_info["stopped"] = exec_state.paused
            step_info["terminated"] = exec_state.terminated

            # If terminated, break early
            if exec_state.terminated:
                results.append(step_info)
                break

        results.append(step_info)

    # Sync MCP context position from last execution state
    if context and last_exec_state:
        from ...core.context_utils import sync_position_from_execution_state

        sync_position_from_execution_state(context, last_exec_state)

    return results


async def _build_step_response(
    action: StepAction,
    session_id: str,
    api: Any,
    context: Any,
) -> StepResponse:
    """Build step response with location and code context.

    Parameters
    ----------
    action : StepAction
        The step action performed
    session_id : str
        Session identifier
    api : Any
        Debug API instance
    context : Any
        Session context

    Returns
    -------
    StepResponse
        Formatted step response
    """
    from ...core.context_utils import build_response_context

    stop_reason = DAPStopReason.STEP.value
    is_paused = context and context.is_paused
    resp_ctx = await build_response_context(api, context, stop_reason, is_paused)

    return StepResponse(
        action=action.value,
        location=resp_ctx.location,
        stopped=True,
        session_id=session_id,
        code_context=resp_ctx.code_context,
        has_breakpoints=resp_ctx.has_breakpoints,
        detailed_status=resp_ctx.detailed_status,
    )


@mcp_tool(
    require_session=True,
    include_before=True,
    include_after=True,
)
async def handle_step(args: dict[str, Any]) -> dict[str, Any]:
    """Handle stepping operations (into, over, out)."""
    try:
        action_str = args.get(ParamName.ACTION, StepAction.OVER.value)
        count = args.get(ParamName.COUNT, 1)

        logger.info(
            "Step handler invoked",
            extra={
                "action": action_str,
                "count": count,
                "default_action": StepAction.OVER.name,
                "tool": ToolName.STEP,
            },
        )

        # Validate action
        action = _validate_step_action(action_str)
        if isinstance(action, dict):  # Error response
            return action

        # Get session components from decorator
        session_id = args.get("_session_id")
        api = args.get("_api")
        context = args.get("_context")

        # The decorator guarantees these are present
        if not api or not context:
            return InternalError(
                error_message="Debug API or context not available",
            ).to_mcp_response()

        if session_id is None:
            return InternalError(
                error_message="Session ID not available",
            ).to_mcp_response()

        # Check if debugger is paused
        error_response = _check_debugger_paused(api, action, session_id)
        if error_response:
            return error_response

        # Execute step sequence (context will be synced from execution state inside)
        _results = await _execute_step_sequence(api, action, count, session_id, context)

        # Build and return response with synced context
        response = await _build_step_response(action, session_id, api, context)
        return response.to_mcp_response()

    except Exception as e:
        logger.error("Step failed: %s", e, extra={"error_type": type(e).__name__})

        # Check if this is a timeout error and handle it globally
        timeout_response = handle_timeout_error(e, "step")
        if timeout_response:
            error_response = timeout_response
        else:
            # Regular error handling
            error_response = InternalError(
                operation="step",
                details=str(e),
                error_message=str(e),
            ).to_mcp_response()

        # Add execution state if we have context
        if "context" in locals() and context and "api" in locals() and api:
            execution_state = build_error_execution_state(api, context)
            if execution_state:
                error_response["data"]["execution_state"] = execution_state

        return error_response


# Export handler functions
HANDLERS = {
    ToolName.STEP: handle_step,
}
