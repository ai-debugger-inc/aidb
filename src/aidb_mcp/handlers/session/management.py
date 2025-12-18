"""Session management handlers.

Handles session status, list, and stop operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb.common.capabilities import DAPCapability
from aidb.session.state import SessionStatus
from aidb_logging import get_mcp_logger as get_logger

from ...core import (
    SessionAction,
    ToolName,
)
from ...core.constants import DefaultValue, ParamName, StopReason
from ...core.decorators import mcp_tool
from ...core.performance import timed
from ...responses.helpers import (
    internal_error,
    no_session,
)
from ...responses.session import (
    SessionListResponse,
    SessionStatusResponse,
    SessionStopResponse,
)
from ...session import (
    get_session_id_from_args,
    list_sessions,
)
from ...session.manager_core import (
    get_service,
    get_session,
)
from ...session.manager_core import (
    get_session_id as get_session_context,
)

if TYPE_CHECKING:
    from ...core.types import BreakpointSpec

logger = get_logger(__name__)


@timed
async def _get_session_state(session) -> tuple[str, bool, bool]:
    """Get session language, terminated and paused state.

    Parameters
    ----------
    session : Session | None
        Session instance

    Returns
    -------
    tuple[str, bool, bool]
        (language, terminated, paused)
    """
    language = DefaultValue.UNKNOWN
    terminated = False
    paused = False

    if not session:
        return language, True, False

    if not session.started:
        return language, True, False

    # Get language from session
    language = getattr(session, "language", DefaultValue.UNKNOWN)

    # Get the actual session status
    if hasattr(session, "status"):
        status = session.status
        if status:
            if status == SessionStatus.TERMINATED:
                terminated = True
            elif status == SessionStatus.PAUSED:
                paused = True
            elif status == SessionStatus.ERROR:
                terminated = True

    return language, terminated, paused


def _format_session_for_list(s) -> dict[str, Any]:
    """Format a session for list response."""
    if isinstance(s, dict):
        # It's already a dict from list_sessions
        return {
            "session_id": s.get("session_id", DefaultValue.UNKNOWN),
            "state": s.get("status", DefaultValue.UNKNOWN),
            "language": s.get("language", DefaultValue.UNKNOWN),
            "active": s.get("active", False),
            "is_default": s.get("is_default", False),
        }
    # Fallback for object format (shouldn't happen)
    return {
        "session_id": getattr(s, "session_id", DefaultValue.UNKNOWN),
        "state": (
            s.get_state().value if hasattr(s, "get_state") else DefaultValue.UNKNOWN
        ),
        "language": getattr(s, "language", DefaultValue.UNKNOWN),
    }


async def _handle_session_status(args: dict[str, Any]) -> dict[str, Any]:
    """Handle session status action."""
    session_id = get_session_id_from_args(args, ParamName.SESSION_ID)

    if not session_id:
        return SessionStatusResponse(
            session_id="",
            terminated=True,
        ).to_mcp_response()

    # Get the session using public interface
    session = get_session(session_id)
    if session is None:
        return no_session(operation="status")

    language, terminated, paused = await _get_session_state(session)

    # Get additional context information using public interface
    context = get_session_context(session_id)
    current_location = None
    breakpoint_count = 0
    stopped_reason = None

    if context:
        # Build current_location from context
        if context.current_file and context.current_line:
            current_location = f"{context.current_file}:{context.current_line}"
        elif context.current_file:
            current_location = context.current_file

        # Get breakpoint count
        breakpoint_count = len(context.breakpoints_set)

        # Infer stopped_reason
        if context.at_breakpoint:
            stopped_reason = StopReason.BREAKPOINT
        elif paused and context.last_operation:
            stopped_reason = context.last_operation

    return SessionStatusResponse(
        session_id=session_id,
        started=session.started if session else False,
        paused=paused,
        terminated=terminated,
        language=language if language != DefaultValue.UNKNOWN else None,
        current_location=current_location,
        breakpoint_count=breakpoint_count,
        stopped_reason=stopped_reason,
    ).to_mcp_response()


async def _handle_session_list(_args: dict[str, Any]) -> dict[str, Any]:
    """Handle session list action."""
    sessions = list_sessions()
    formatted_sessions = [_format_session_for_list(s) for s in sessions]
    return SessionListResponse(sessions=formatted_sessions).to_mcp_response()


async def _handle_session_stop(args: dict[str, Any]) -> dict[str, Any]:
    """Handle session stop action."""
    from ...session.manager_lifecycle import cleanup_session_async

    session_id = get_session_id_from_args(args, ParamName.SESSION_ID)
    if not session_id:
        return no_session(operation="stop")

    # Get the session using public interface
    session = get_session(session_id)

    # Check if session is already terminated
    # Even if terminated, we still need to call stop() to run cleanup hooks
    if session and hasattr(session, "status"):
        status = session.status
        if status and status == SessionStatus.TERMINATED:
            logger.debug(
                "Session already terminated, but still calling stop for cleanup",
                extra={"session_id": session_id},
            )

    # Call stop() to ensure adapter cleanup hooks run (DAP disconnect, etc.)
    # This is critical for pooled resources like JDT LS bridges
    if session and hasattr(session, "stop"):
        await session.stop()

    # Clean up session from MCP registries to prevent orphaned receivers
    # This removes the session from _DEBUG_SERVICES and _SESSION_CONTEXTS,
    # ensuring all resources (including background receivers) are released
    await cleanup_session_async(session_id, force=True)

    return SessionStopResponse(
        session_id=session_id,
        terminated_reason="User requested stop",
    ).to_mcp_response()


async def _try_native_restart(
    session: Any,
    service: Any,
    session_id: str,
    keep_breakpoints: bool,
) -> dict[str, Any] | None:
    """Attempt native restart if supported.

    Returns response dict if successful, None to fall back to emulated restart.
    """
    if not (
        session
        and hasattr(session, "has_capability")
        and session.has_capability(DAPCapability.RESTART)
    ):
        return None

    try:
        logger.info("Using native restart", extra={"session_id": session_id})
        await service.execution.restart()

        from ...responses.session import SessionRestartResponse

        return SessionRestartResponse(
            session_id=session_id,
            method="native",
            kept_breakpoints=keep_breakpoints,
        ).to_mcp_response()
    except Exception as e:
        logger.warning(
            "Native restart failed, falling back to emulated restart",
            extra={"session_id": session_id, "error": str(e)},
        )
        return None


def _convert_breakpoints_for_restart(
    breakpoints: list[BreakpointSpec],
) -> list[BreakpointSpec]:
    """Convert breakpoints to BreakpointSpec format for restart.

    Parameters
    ----------
    breakpoints : list[BreakpointSpec]
        Breakpoints from session context

    Returns
    -------
    list[BreakpointSpec]
        Validated breakpoint specifications
    """
    result: list[BreakpointSpec] = []
    for bp in breakpoints:
        bp_spec: BreakpointSpec = {"file": bp["file"], "line": bp["line"]}

        # Add optional fields if present
        if bp.get("column"):
            bp_spec["column"] = bp["column"]
        if bp.get("condition"):
            bp_spec["condition"] = bp["condition"]
        if bp.get("hit_condition"):
            bp_spec["hit_condition"] = bp["hit_condition"]
        if bp.get("log_message"):
            bp_spec["log_message"] = bp["log_message"]

        result.append(bp_spec)
    return result


async def _emulated_restart(
    session: Any,
    session_id: str,
    session_context: Any,
    keep_breakpoints: bool,
) -> dict[str, Any]:
    """Perform emulated restart via stop + start."""
    logger.info(
        "Using emulated restart (stop + start)",
        extra={"session_id": session_id},
    )

    # Capture current breakpoints if keeping them
    current_breakpoints = []
    if keep_breakpoints and session_context.breakpoints_set:
        current_breakpoints = session_context.breakpoints_set.copy()

    # Get launch params
    launch_params = session_context.launch_params.copy()
    if not launch_params:
        return internal_error(
            operation="restart",
            exception=ValueError("No launch params stored - cannot restart"),
        )

    # Stop current session
    if session and hasattr(session, "stop"):
        await session.stop()

    # Merge breakpoints if keeping them
    if keep_breakpoints and current_breakpoints:
        breakpoints_for_restart = _convert_breakpoints_for_restart(current_breakpoints)
        launch_params[ParamName.BREAKPOINTS] = breakpoints_for_restart

    # Use the same session_id for continuity
    launch_params[ParamName.SESSION_ID] = session_id

    # Start the new session
    from .lifecycle import handle_session_start

    start_response = await handle_session_start(launch_params)

    # Annotate response to indicate it was a restart
    if start_response.get("success"):
        from ...responses.session import SessionRestartResponse

        return SessionRestartResponse(
            session_id=session_id,
            method="emulated",
            kept_breakpoints=keep_breakpoints,
            breakpoint_count=len(current_breakpoints) if keep_breakpoints else 0,
        ).to_mcp_response()

    return start_response


async def _handle_session_restart(args: dict[str, Any]) -> dict[str, Any]:
    """Handle session restart action.

    Attempts native restart if adapter supports it, otherwise emulates by stopping and
    starting a new session with the same configuration.
    """
    session_id = get_session_id_from_args(args, ParamName.SESSION_ID)
    if not session_id:
        return no_session(operation="restart")

    # Get session and service using public interfaces
    session = get_session(session_id)
    service = get_service(session_id)
    if session is None:
        return no_session(operation="restart")

    # Get session context using public interface
    session_context = get_session_context(session_id)
    if not session_context:
        return internal_error(
            operation="restart",
            exception=ValueError("Session context not found"),
        )

    keep_breakpoints = args.get(ParamName.KEEP_BREAKPOINTS, True)

    # Try native restart first
    native_result = await _try_native_restart(
        session,
        service,
        session_id,
        keep_breakpoints,
    )
    if native_result:
        return native_result

    # Fall back to emulated restart
    return await _emulated_restart(
        session,
        session_id,
        session_context,
        keep_breakpoints,
    )


@mcp_tool(require_session=False, include_after=False, record_history=False)
async def handle_session_management(args: dict[str, Any]) -> dict[str, Any]:
    """Handle session management operations (status, list, cleanup, etc)."""
    from ..dispatch import dispatch_action

    action_str = args.get(ParamName.ACTION, SessionAction.STATUS.value)
    logger.info(
        "Session management handler invoked",
        extra={
            "action": action_str,
            "default_action": SessionAction.STATUS.name,
            "tool": ToolName.SESSION,
        },
    )

    action_handlers = {
        SessionAction.STATUS: _handle_session_status,
        SessionAction.LIST: _handle_session_list,
        SessionAction.STOP: _handle_session_stop,
        SessionAction.RESTART: _handle_session_restart,
    }

    handler, error, handler_args = dispatch_action(
        args,
        SessionAction,
        action_handlers,
        default_action=SessionAction.STATUS,
        tool_name=ToolName.SESSION,
    )

    if error or handler is None:
        return error or internal_error(
            operation="session",
            exception="No handler found",
        )

    try:
        return await handler(*handler_args)
    except Exception as e:
        action = args.get(ParamName.ACTION, SessionAction.STATUS.value)
        logger.error("Session management failed: %s", e)
        return internal_error(operation=f"session_{action}", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.SESSION: handle_session_management,
}
