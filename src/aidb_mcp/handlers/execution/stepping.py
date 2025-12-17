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
from ...responses.helpers import (
    handle_timeout_error,
    invalid_parameter,
    is_session_paused,
    not_paused,
)
from ...session import get_session

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
    service: Any,
    action: StepAction,
    session_id: str,
) -> dict[str, Any] | None:
    """Check if debugger is paused (required for stepping).

    Parameters
    ----------
    service : Any
        DebugService instance (Phase 2)
    action : StepAction
        The step action to perform
    session_id : str
        Session ID

    Returns
    -------
    dict | None
        Error response if not paused, None if ok
    """
    # Get active session from service (handles child session resolution)
    active_session = service.session if service else None

    # Use shared utility for defensive session state checking
    if not is_session_paused(active_session):
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
    service: Any,
    action: StepAction,
    iteration: int,
    count: int,
) -> Any:
    """Execute a single step operation.

    Parameters
    ----------
    service : Any
        DebugService instance (Phase 2)
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
    # Get current thread_id for stepping operations
    thread_id = await service.stepping.get_current_thread_id()

    # Map step actions to service methods (Phase 2)
    action_desc_map = {
        StepAction.INTO: "stepping into",
        StepAction.OVER: "stepping over",
        StepAction.OUT: "stepping out",
    }

    desc = action_desc_map.get(action)
    if not desc:
        msg = f"Unexpected step action: {action}"
        raise ValueError(msg)

    logger.debug(
        "Step %s/%s: %s",
        iteration,
        count,
        desc,
        extra={"action": action.name, "iteration": iteration, "thread_id": thread_id},
    )

    # Execute the step using service (Phase 2)
    if action == StepAction.INTO:
        return await service.stepping.step_into(thread_id)
    if action == StepAction.OVER:
        return await service.stepping.step_over(thread_id)
    if action == StepAction.OUT:
        return await service.stepping.step_out(thread_id)

    msg = f"Unexpected step action: {action}"
    raise ValueError(msg)


async def _execute_step_sequence(
    service: Any,
    action: StepAction,
    count: int,
    session_id: str,
    context: Any = None,
) -> list[dict[str, Any]]:
    """Execute a sequence of step operations.

    Parameters
    ----------
    service : Any
        DebugService instance (Phase 2)
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
        result = await _execute_single_step(service, action, i + 1, count)

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
    session: Any,
    context: Any,
) -> StepResponse:
    """Build step response with location and code context.

    Parameters
    ----------
    action : StepAction
        The step action performed
    session_id : str
        Session identifier
    session : Any
        Session instance for status/property access
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
    resp_ctx = await build_response_context(session, context, stop_reason, is_paused)

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
        service = args.get("_service")
        context = args.get("_context")

        # The decorator guarantees these are present
        if not service or not context:
            return InternalError(
                error_message="DebugService or context not available",
            ).to_mcp_response()

        if session_id is None:
            return InternalError(
                error_message="Session ID not available",
            ).to_mcp_response()

        # Check if debugger is paused (Phase 2: using service)
        error_response = _check_debugger_paused(service, action, session_id)
        if error_response:
            return error_response

        # Execute step sequence using service (Phase 2)
        _results = await _execute_step_sequence(
            service,
            action,
            count,
            session_id,
            context,
        )

        # Get session for response building
        session = get_session(session_id)

        # Build and return response with synced context
        response = await _build_step_response(action, session_id, session, context)
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
        has_context = "context" in locals() and context
        has_session = "session_id" in locals() and session_id
        if has_context and has_session:
            session = get_session(session_id)
            execution_state = (
                build_error_execution_state(session, context) if session else None
            )
            if execution_state:
                error_response["data"]["execution_state"] = execution_state

        return error_response


# Export handler functions
HANDLERS = {
    ToolName.STEP: handle_step,
}
