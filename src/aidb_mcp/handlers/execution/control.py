"""Execution control handlers.

Handles the execute tool for running and continuing program execution.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core import ExecutionAction, ToolName
from ...core.constants import ErrorMessage, ParamName, SessionState
from ...core.decorators import mcp_tool
from ...core.exceptions import ErrorCode
from ...responses import ExecuteResponse
from ...responses.errors import ErrorResponse, InternalError
from ...responses.helpers import handle_timeout_error, invalid_parameter

logger = get_logger(__name__)


def _validate_action(action_str: str | None) -> ExecutionAction | dict[str, Any]:
    """Validate and normalize action parameter.

    Parameters
    ----------
    action_str : str | None
        Action string to validate

    Returns
    -------
    ExecutionAction | dict[str, Any]
        Valid ExecutionAction or error response
    """
    try:
        action = ExecutionAction(action_str) if action_str else ExecutionAction.CONTINUE
        logger.debug(
            "Execution action validated",
            extra={"action": action.name, "action_value": action.value},
        )
        return action
    except ValueError:
        logger.warning(
            "Invalid execution action",
            extra={
                "action": action_str,
                "valid_actions": [e.name for e in ExecutionAction],
            },
        )
        return invalid_parameter(
            param_name=ParamName.ACTION,
            expected_type="'run' or 'continue'",
            received_value=action_str,
            error_message=f"Action must be 'run' or 'continue', got '{action_str}'",
        )


def _determine_wait_for_stop(
    args: dict[str, Any],
    context: Any,
    session_id: str,
) -> bool:
    """Determine if wait_for_stop should be enabled.

    Parameters
    ----------
    args : dict[str, Any]
        Handler arguments
    context : Any
        Session context
    session_id : str
        Session ID

    Returns
    -------
    bool
        Whether to wait for stop
    """
    wait_for_stop = args.get(ParamName.WAIT_FOR_STOP)

    if wait_for_stop is None:
        wait_for_stop = False
        if context and hasattr(context, "breakpoints_set") and context.breakpoints_set:
            wait_for_stop = True
            logger.debug(
                "Auto-enabling wait_for_stop due to active breakpoints",
                extra={
                    "breakpoint_count": len(context.breakpoints_set),
                    "session_id": session_id,
                },
            )
    else:
        logger.debug(
            "Using explicit wait_for_stop parameter",
            extra={
                "wait_for_stop": wait_for_stop,
                "session_id": session_id,
            },
        )

    return wait_for_stop


async def _execute_action(
    action: ExecutionAction,
    api: Any,
    wait_for_stop: bool,
    session_id: str,
) -> Any:
    """Execute the specified action.

    Parameters
    ----------
    action : ExecutionAction
        Action to execute
    api : Any
        Debug API
    wait_for_stop : bool
        Whether to wait for stop
    session_id : str
        Session ID

    Returns
    -------
    Any
        Execution result

    Raises
    ------
    Exception
        If execution fails
    """
    if action == ExecutionAction.RUN:
        # Restart execution from beginning
        logger.debug(
            "Restarting execution from beginning",
            extra={"action": ExecutionAction.RUN.name, "session_id": session_id},
        )
        try:
            await api.orchestration.restart()
            return await api.orchestration.continue_(wait_for_stop=wait_for_stop)
        except Exception as restart_error:
            error_msg = str(restart_error).lower()
            if "not supported" in error_msg or "unsupported" in error_msg:
                logger.warning(
                    "Restart not supported by adapter",
                    extra={
                        "session_id": session_id,
                        "error": str(restart_error),
                    },
                )
                raise ValueError(ErrorMessage.RESTART_NOT_SUPPORTED) from restart_error
            raise  # Re-raise if it's not a "not supported" error
    else:
        # Continue from current position
        logger.debug(
            "Continuing execution from current position",
            extra={
                "action": ExecutionAction.CONTINUE.name,
                "session_id": session_id,
                "wait_for_stop": wait_for_stop,
            },
        )
        return await api.orchestration.continue_(wait_for_stop=wait_for_stop)


def _extract_execution_state(result: Any, context: Any) -> dict[str, Any]:
    """Extract execution state from result.

    Parameters
    ----------
    result : Any
        Execution result
    context : Any
        Session context

    Returns
    -------
    dict[str, Any]
        Execution state data
    """
    stopped = False
    terminated = False
    stop_reason = None
    location = None

    if result and hasattr(result, "execution_state"):
        exec_state = result.execution_state
        stopped = exec_state.paused
        terminated = exec_state.terminated

        logger.debug(
            "Execution state from result",
            extra={
                "stopped": stopped,
                "stopped_type": type(stopped).__name__,
                "terminated": terminated,
                "exec_state_paused": exec_state.paused,
                "exec_state_terminated": exec_state.terminated,
            },
        )

        # Sync MCP context position from core execution state
        if context:
            from ...core.context_utils import sync_position_from_execution_state

            sync_position_from_execution_state(context, exec_state)

        # Convert stop_reason enum to string if present
        if stopped and exec_state.stop_reason:
            # Convert enum name to lowercase string
            # (e.g., StopReason.BREAKPOINT -> "breakpoint")
            stop_reason = exec_state.stop_reason.name.lower()

    if stopped and context:
        location = (
            f"{context.current_file}:{context.current_line}"
            if context.current_file
            else None
        )
        logger.debug(
            "Location from context",
            extra={
                "has_context": context is not None,
                "current_file": context.current_file if context else None,
                "current_line": context.current_line if context else None,
                "location": location,
            },
        )

    return {
        "stopped": stopped,
        "terminated": terminated,
        "stop_reason": stop_reason,
        "location": location,
    }


def _build_error_execution_state(api: Any, context: Any) -> dict[str, Any]:
    """Build execution state for error response.

    Parameters
    ----------
    api : Any
        Debug API instance
    context : Any
        Session context

    Returns
    -------
    dict
        Execution state dictionary
    """
    try:
        from ...core.context_utils import determine_detailed_status

        detailed_status = determine_detailed_status(api, context, None)
        return {
            "status": detailed_status.value,
            "session_state": (
                SessionState.PAUSED.value
                if context.is_paused
                else SessionState.RUNNING.value
                if context.is_running
                else SessionState.STOPPED.value
            ),
            "current_location": (
                f"{context.current_file}:{context.current_line}"
                if context.current_file
                else None
            ),
            "breakpoints_active": bool(context.breakpoints_set),
            "error_context": True,
        }
    except Exception as state_error:
        logger.debug("Could not build execution state: %s", state_error)
        return {}


async def _build_execution_response(
    action: ExecutionAction,
    session_id: str,
    api: Any,
    context: Any,
    state: dict[str, Any],
) -> ExecuteResponse:
    """Build execution response with code context.

    Parameters
    ----------
    action : ExecutionAction
        The action performed
    session_id : str
        Session identifier
    api : Any
        Debug API instance
    context : Any
        Session context
    state : dict
        Execution state

    Returns
    -------
    ExecuteResponse
        Formatted execution response
    """
    from ...core.context_utils import (
        determine_detailed_status,
        get_code_snapshot_if_paused,
    )

    detailed_status = determine_detailed_status(api, context, state["stop_reason"])
    has_breakpoints = bool(context.breakpoints_set) if context else False

    # Get code snapshot if paused
    code_context = None
    if state["stopped"] and context:
        code_context = await get_code_snapshot_if_paused(api, context)

    logger.info(
        "Execution completed",
        extra={
            "action": action.name,
            "stopped": state["stopped"],
            "terminated": state["terminated"],
            "location": state["location"],
            "stop_reason": state["stop_reason"],
            "detailed_status": detailed_status.value,
            "has_breakpoints": has_breakpoints,
            "session_id": session_id,
            "has_code_context": code_context is not None,
            "state": (
                SessionState.PAUSED.name
                if state["stopped"]
                else SessionState.RUNNING.name
            ),
        },
    )

    response = ExecuteResponse(
        action=action.value,
        stopped=state["stopped"],
        terminated=state["terminated"],
        location=state["location"],
        stop_reason=state["stop_reason"],
        session_id=session_id,
        code_context=code_context,
        has_breakpoints=has_breakpoints,
        detailed_status=detailed_status.value,
    )

    logger.debug(
        "ExecuteResponse created",
        extra={
            "stopped": response.stopped,
            "stopped_type": type(response.stopped).__name__,
            "terminated": response.terminated,
            "location": response.location,
            "stop_reason": response.stop_reason,
        },
    )

    return response


@mcp_tool(require_session=True, include_after=True)
async def handle_execution(args: dict[str, Any]) -> dict[str, Any]:
    """Handle execute - unified run/continue operations."""
    try:
        action_str = args.get(ParamName.ACTION, ExecutionAction.CONTINUE.value)

        logger.info(
            "Execution handler invoked",
            extra={
                "action": action_str,
                "default_action": ExecutionAction.CONTINUE.name,
                "tool": ToolName.EXECUTE,
            },
        )

        # Validate and normalize action
        action_result = _validate_action(action_str)
        if isinstance(action_result, dict):
            # It's an error response
            return action_result
        action = action_result

        # Get session components from decorator
        session_id = args.get("_session_id")
        api = args.get("_api")
        context = args.get("_context")

        # The decorator guarantees api and session_id are present
        if not api:
            return InternalError(
                error_message="Debug API not available",
            ).to_mcp_response()

        if session_id is None:
            return InternalError(
                error_message="Session ID not available",
            ).to_mcp_response()

        # Determine wait_for_stop
        wait_for_stop = _determine_wait_for_stop(args, context, session_id)

        # Execute the action
        try:
            result = await _execute_action(action, api, wait_for_stop, session_id)
        except ValueError as e:
            if str(e) == ErrorMessage.RESTART_NOT_SUPPORTED:
                return ErrorResponse(
                    error_code=ErrorCode.AIDB_CAPABILITY_NOT_SUPPORTED.value,
                    error_message=(
                        "Restart operation not supported by this debug adapter"
                    ),
                    summary="Restart not supported",
                ).to_mcp_response()
            raise

        # Extract execution state
        state = _extract_execution_state(result, context)

        # Build and return response
        response = await _build_execution_response(
            action,
            session_id,
            api,
            context,
            state,
        )
        return response.to_mcp_response()

    except Exception as e:
        logger.exception(
            "Execution failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": "execute",
                "action": action_str if "action_str" in locals() else "unknown",
            },
        )

        # Check if this is a timeout error and handle it globally
        timeout_response = handle_timeout_error(e, "execute")
        if timeout_response:
            error_response = timeout_response
        else:
            # Regular error handling
            error_response = InternalError(
                operation="execute",
                details=str(e),
                error_message=str(e),
            ).to_mcp_response()

        # Try to add execution state if we have context
        if "context" in locals() and context and "api" in locals() and api:
            execution_state = _build_error_execution_state(api, context)
            if execution_state:
                error_response["data"]["execution_state"] = execution_state

        return error_response


# Export handler functions
HANDLERS = {
    ToolName.EXECUTE: handle_execution,
}
