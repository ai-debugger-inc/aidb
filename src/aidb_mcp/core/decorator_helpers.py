"""Helper functions for decorator implementations.

This module contains pure helper functions used by decorators, with no decorator logic
themselves. These functions handle tasks like session management, variable conversion,
result formatting, and execution tracking.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ..responses.errors import (
    ConnectionLostError,
    SessionNotStartedError,
)
from ..session import (
    get_last_active_session,
    get_or_create_session,
)
from ..session.health import attempt_recovery, check_connection_health
from .constants import ParamName
from .context_utils import (
    compute_context_diff,
    format_location_summary,
)

logger = get_logger(__name__)


def _convert_variables_to_dict(variables_data: Any) -> dict[str, Any]:
    """Convert various variable formats to a dictionary.

    Parameters
    ----------
    variables_data : Any
        Variables in various formats (list of objects, dict, etc.)

    Returns
    -------
    Dict[str, Any]
        Variables as a dictionary mapping names to values
    """
    var_dict = {}

    if hasattr(variables_data, "__iter__") and not isinstance(
        variables_data,
        str | bytes,
    ):
        for var in variables_data:
            if hasattr(var, "name") and hasattr(var, "value"):
                var_dict[var.name] = var.value
            elif isinstance(var, dict) and "name" in var:
                var_dict[var["name"]] = var.get("value", var.get("data"))
    elif isinstance(variables_data, dict):
        var_dict = variables_data

    return var_dict


def _get_session_or_error(
    require_session: bool,
    session_id: str | None,
    func_name: str,
) -> tuple[str | None, dict | None]:
    """Get session ID or return error if required.

    Returns (session_id, error_response).
    """
    if session_id is None and require_session:
        session_id = get_last_active_session()
        if session_id is None:
            tool_name = func_name.replace("handle_", "")
            logger.warning(
                "Tool '%s' called without active session",
                tool_name,
                extra={"tool": tool_name},
            )
            error = SessionNotStartedError(
                session_id=None,
                error_message=(
                    f"No active debug session. You must call 'init' and "
                    f"then 'session_start' before using '{tool_name}'."
                ),
            ).to_mcp_response()
            return None, error
    return session_id, None


def _setup_session_context(
    require_session: bool,
    session_id: str | None,
) -> tuple[str | None, Any]:
    """Set up session context.

    Returns (sid, context).
    """
    if not require_session and session_id is None:
        session_id = get_last_active_session()

    if session_id is not None:
        return get_or_create_session(session_id)
    return None, None


async def _check_connection_health(
    require_session: bool,
    sid: str | None,
) -> dict[str, Any] | None:
    """Check connection health and attempt recovery if needed.

    Returns error or None.
    """
    if (
        require_session
        and sid
        and not check_connection_health(sid)
        and not await attempt_recovery(sid)
    ):
        return ConnectionLostError(
            session_id=sid,
            error_message="Connection lost and recovery failed",
        ).to_mcp_response()
    return None


def _check_termination_status(
    require_session: bool,
    service: Any,
    sid: str | None,
    args: dict[str, Any],
    allow_on_terminated: list[str] | None,
) -> dict[str, Any] | None:
    """Check if session is terminated and handle allowed actions.

    For terminated sessions, blocks operations UNLESS the action is in
    allow_on_terminated list (for read-only operations like 'list').

    Parameters
    ----------
    require_session : bool
        Whether the handler requires an active session
    service : Any
        DebugService instance (or None if not yet created)
    sid : str
        Session ID
    args : dict
        Handler arguments
    allow_on_terminated : list[str], optional
        Actions allowed on terminated sessions

    Returns
    -------
    dict or None
        Error response or None to proceed
    """
    if not require_session or not service or not hasattr(service, "session"):
        return None

    session = service.session
    # Only check termination if session has its OWN DAP client
    # Don't check inherited parent DAP (JavaScript child sessions)
    if not (hasattr(session, "connector") and session.connector):
        return None

    dap = getattr(session.connector, "_dap", None)
    if not dap:
        return None

    # Follow same pattern as SessionState.get_status():
    # Check if stopped/paused BEFORE checking terminated
    dap_is_stopped = getattr(dap, "is_stopped", False)
    dap_is_terminated = getattr(dap, "is_terminated", False)

    # Only block if session is terminated AND not just paused
    if not (dap_is_terminated and not dap_is_stopped):
        return None

    # Check if this action is allowed on terminated sessions
    current_action = args.get("action") or args.get("_action")
    if allow_on_terminated and current_action in allow_on_terminated:
        logger.debug(
            "Allowing action '%s' on terminated session",
            current_action,
        )
        return None

    # Block the operation
    from ..responses.errors import SessionTerminatedError

    return SessionTerminatedError(
        session_id=sid,
        error_message="Session has terminated and cannot execute commands",
    ).to_mcp_response()


def _add_session_id_to_result(
    result: dict[str, Any] | tuple,
    sid: str | None,
) -> dict[str, Any] | tuple:
    """Add session_id to result if not present."""
    if isinstance(result, dict) and "session_id" not in result:
        # Check if there's a session_id in data (for session_start)
        if (
            "data" in result
            and isinstance(result["data"], dict)
            and "session_id" in result["data"]
        ):
            result["session_id"] = result["data"]["session_id"]
        else:
            result["session_id"] = sid
    # Don't modify tuple results - they'll be converted to dict format later
    return result


def _record_execution_history(
    session_context,
    operation_name: str,
    args: dict[str, Any],
    result: dict[str, Any] | tuple,
) -> None:
    """Record execution step in history."""
    if session_context and hasattr(session_context, "record_execution_step"):
        # Handle both dict and tuple response formats
        if isinstance(result, tuple):
            # For tuple format, assume (success_flag, data_or_error)
            success = result[0] if len(result) > 0 else False
            error_msg = str(result[1]) if len(result) > 1 and not success else None
        else:
            # Dict format - MCP responses use "success" boolean field
            success = result.get("success", False)
            error_msg = result.get("error", {}).get("message") if not success else None

        session_context.record_execution_step(
            action=operation_name,
            params=args.get(ParamName.ACTION)
            or args.get(ParamName.TARGET)
            or args.get(ParamName.EXPRESSION),
            result=("success" if success else "error"),
            error_message=error_msg,
        )


def _synchronize_execution_state(
    session_context,
    operation_name: str,
    result: dict[str, Any],
    session,
) -> None:
    """Synchronize session context with execution state."""
    if session_context and operation_name in ["step", "execute", "run_until"]:
        # Check for execution state in result data
        if "data" in result:
            data = result["data"]
            if "stopped" in data:
                session_context.is_paused = data["stopped"]
                session_context.at_breakpoint = data["stopped"]
                session_context.is_running = not data["stopped"]

        # Check for actual session state from Session
        has_state = session and hasattr(session, "state")
        if has_state and hasattr(session.state, "is_paused"):
            is_paused = session.state.is_paused()
            session_context.is_paused = is_paused
            session_context.at_breakpoint = is_paused
            session_context.is_running = (
                not is_paused and not session.state.is_terminated()
            )
            logger.debug(
                "Synchronized session context state: paused=%s",
                is_paused,
            )


def _track_variable_changes(
    session_context,
    args: dict[str, Any],
    result: dict[str, Any],
    after_context: dict[str, Any],
    operation_name: str,
) -> None:
    """Track variable changes for inspect operations."""
    if not (session_context and hasattr(session_context, "variable_tracker")):
        return

    target = args.get(ParamName.TARGET) or args.get(ParamName.EXPRESSION)
    location = after_context.get("current_location")

    # Helper to add changes to result
    def add_changes_if_any(changes):
        if changes and (changes["added"] or changes["removed"] or changes["modified"]):
            result["data"]["variable_changes"] = changes

    if target in ["locals", "locals()", "__locals__"]:
        locals_data = result.get("data", {}).get("locals")
        if locals_data:
            var_dict = _convert_variables_to_dict(locals_data)
            changes = session_context.variable_tracker.track_locals(
                var_dict,
                operation=operation_name,
                location=location,
            )
            add_changes_if_any(changes)

    elif target in ["globals", "globals()", "__globals__"]:
        globals_data = result.get("data", {}).get("globals")
        if globals_data:
            var_dict = _convert_variables_to_dict(globals_data)
            changes = session_context.variable_tracker.track_globals(
                var_dict,
                operation=operation_name,
                location=location,
            )
            add_changes_if_any(changes)


def _add_location_to_result(
    result: dict[str, Any],
    after_context: dict[str, Any],
) -> None:
    """Add current location to result."""
    if after_context["current_location"]:
        result["data"]["current_location"] = after_context["current_location"]
        result["data"]["execution_state"] = after_context["execution_state"]

        # Update summary with location
        location = after_context["current_location"]
        location_str = format_location_summary(location)

        # Append location to existing summary
        if "summary" in result and location_str not in result["summary"]:
            result["summary"] = f"{result['summary']} at {location_str}"


def _should_include_stack(
    before_context: dict[str, Any] | None,
    after_context: dict[str, Any],
) -> bool:
    """Check if stack info should be included."""
    if not after_context["stack_frames"]:
        return False

    if before_context:
        before_depth = len(before_context.get("stack_frames", []))
        after_depth = len(after_context["stack_frames"])
        return before_depth != after_depth
    return True


def _add_execution_context_to_result(
    result: dict[str, Any],
    after_context: dict[str, Any],
    before_context: dict[str, Any] | None,
) -> None:
    """Add execution context information to result."""
    # Ensure data dict exists
    if "data" not in result:
        result["data"] = {}

    # Add current location
    _add_location_to_result(result, after_context)

    # Add context diff if we have before state
    if before_context:
        diff = compute_context_diff(before_context, after_context)
        if diff:
            result["data"]["context_changes"] = diff

    # Add breakpoint info if available
    if after_context["breakpoints_active"]:
        result["data"]["breakpoints_active"] = after_context["breakpoints_active"]

    # Add stack info if changed significantly
    if _should_include_stack(before_context, after_context):
        result["data"]["stack_depth"] = len(after_context["stack_frames"])


def _standardize_session_response(
    result: dict[str, Any],
    func,
    session_id: str | None,
    session_context,
    args: dict[str, Any],
) -> None:
    """Standardize session operation responses."""
    operation_name = func.__name__.replace("handle_", "")
    session_operations = {
        "session",
        "session_start",
        "session_stop",
        "session_restart",
        "session_switch",
    }

    if operation_name in session_operations and session_id and session_context:
        session_info = {
            "id": session_id,
            "started": session_context.session_started,
            "paused": session_context.at_breakpoint or bool(session_context.error_info),
            "terminated": False,
            "language": (
                session_context.session_info.language
                if session_context.session_info
                else args.get(ParamName.LANGUAGE, "python")
            ),
            "target": (
                session_context.session_info.target
                if session_context.session_info
                else None
            ),
        }

        # Add stopped reason if paused
        if session_info["paused"]:
            if session_context.error_info:
                session_info["stopped_reason"] = "error"
            elif session_context.at_breakpoint:
                session_info["stopped_reason"] = "breakpoint"
            else:
                session_info["stopped_reason"] = "step"

        result["session"] = session_info
