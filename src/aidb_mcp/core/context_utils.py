"""Context gathering utilities for MCP handlers.

This module provides centralized context gathering for debugging sessions, ensuring
consistent location and state information across all MCP tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aidb.common.code_context import CodeContext
from aidb.dap.client.constants import StopReason as DAPStopReason
from aidb.models import SessionStatus
from aidb_common.config.runtime import ConfigManager
from aidb_logging import get_mcp_logger as get_logger

from ..session import get_or_create_session
from .constants import DetailedExecutionStatus, ExecutionState
from .response_limiter import ResponseLimiter

if TYPE_CHECKING:
    from aidb import DebugService
    from aidb.common.code_context import CodeContextResult
    from aidb.session import Session

    from ..session.context import MCPSessionContext

logger = get_logger(__name__)


def sync_position_from_execution_state(
    context: MCPSessionContext,
    execution_state: Any | None,
) -> None:
    """Synchronize MCP context position from core execution state.

    The core orchestration layer is the authoritative source for execution
    position. This function keeps MCP context in sync with the core layer.

    Parameters
    ----------
    context : MCPSessionContext
        MCP session context to update
    execution_state : Any | None
        Execution state from core layer (ExecutionState object)

    Notes
    -----
    This function extracts position information (current_file, current_line)
    from the core ExecutionState and updates the MCP context fields. This
    ensures a single source of truth for position tracking.
    """
    if not execution_state:
        return

    # Sync position fields if available
    if hasattr(execution_state, "current_file") and execution_state.current_file:
        context.current_file = execution_state.current_file
        context.current_line = getattr(execution_state, "current_line", None)

        logger.debug(
            "Synced MCP context from execution state",
            extra={
                "file": context.current_file,
                "line": context.current_line,
            },
        )

    # Sync thread ID if available
    if hasattr(execution_state, "thread_id") and execution_state.thread_id is not None:
        context.current_thread_id = execution_state.thread_id


def _get_execution_state(session_context: Any | None) -> str:
    """Get execution state from session context.

    Parameters
    ----------
    session_context : Optional[Any]
        The session context

    Returns
    -------
    str
        The execution state value
    """
    if not session_context:
        return ExecutionState.UNKNOWN.value

    if session_context.is_paused:
        return ExecutionState.PAUSED.value
    if session_context.is_running:
        return ExecutionState.RUNNING.value

    return ExecutionState.UNKNOWN.value


async def _gather_stack_info(service: DebugService | None) -> dict[str, Any]:
    """Gather stack trace information.

    Parameters
    ----------
    service : DebugService | None
        The debug service instance

    Returns
    -------
    dict[str, Any]
        Dictionary with current_location (LocationDict),
        stack_frames (list[StackFrameDict]), and thread_info (dict with id,
        name, count)
    """
    result: dict[str, Any] = {
        "current_location": None,
        "stack_frames": [],
        "thread_info": None,
    }

    if not service:
        return result

    try:
        stack_response = await service.stack.callstack()
        if not stack_response or not stack_response.frames:
            return result

        current_frame = stack_response.frames[0]

        result["current_location"] = {
            "file": current_frame.source.path if current_frame.source else None,
            "line": current_frame.line,
            "function": current_frame.name,
            "frame_id": current_frame.id,
        }

        # Convert frames to dicts first
        all_frames = [
            {
                "level": i,
                "function": frame.name,
                "file": frame.source.path if frame.source else None,
                "line": frame.line,
            }
            for i, frame in enumerate(stack_response.frames)
        ]

        # Apply stack frame limits to the dict representation
        limited_frames, was_truncated = ResponseLimiter.limit_stack_frames(all_frames)
        if was_truncated:
            logger.debug(
                "Truncated stack from %d to %d frames",
                len(all_frames),
                len(limited_frames),
            )

        result["stack_frames"] = limited_frames

        if current_frame.thread_id:
            result["thread_info"] = {
                "id": current_frame.thread_id,
                "name": f"Thread {current_frame.thread_id}",
                "count": 1,
            }
    except Exception as e:
        logger.debug("Could not get stack trace: %s", e)

    return result


async def _gather_breakpoint_info(
    service: DebugService | None,
) -> list[dict[str, int | bool | str | None]]:
    """Gather active breakpoint information.

    Parameters
    ----------
    service : DebugService | None
        The debug service instance

    Returns
    -------
    list[dict[str, int | bool | str | None]]
        List of active breakpoint info
    """
    if not service:
        return []

    try:
        response = await service.breakpoints.list()
        if not response or not response.breakpoints:
            return []

        return [
            {
                "id": bp_id,
                "verified": bp.verified,
                "line": bp.line,
                "source": bp.source_path,
            }
            for bp_id, bp in response.breakpoints.items()
        ]
    except Exception:
        # Best effort - don't fail context gathering
        return []


async def gather_execution_context(
    session: Session | None,
    service: DebugService | None,
    session_id: str,
    session_context: Any | None = None,
) -> dict[str, Any]:
    """Gather current execution context from debug session.

    Parameters
    ----------
    session : Session | None
        The debug session instance
    service : DebugService | None
        The debug service instance
    session_id : str
        The session ID
    session_context : Optional[Any]
        The session context (if available)

    Returns
    -------
    Dict[str, Any]
        Context dictionary containing:
        - current_location: Current file, line, function
        - execution_state: Running or paused
        - stack_frames: Top 5 stack frames
        - thread_info: Active thread information
        - breakpoints_active: Currently set breakpoints
    """
    context: dict[str, Any] = {
        "current_location": None,
        "execution_state": ExecutionState.UNKNOWN.value,
        "stack_frames": [],
        "thread_info": None,
        "breakpoints_active": [],
    }

    if not session or not session.started:
        logger.debug("No active debug session for context gathering: %s", session_id)
        return context

    try:
        if not session_context:
            _, session_context = get_or_create_session(session_id)

        context["execution_state"] = _get_execution_state(session_context)

        stack_info = await _gather_stack_info(service)
        context.update(stack_info)

        context["breakpoints_active"] = await _gather_breakpoint_info(service)

    except Exception as e:
        logger.warning("Error gathering execution context: %s", e)

    return context


def compute_context_diff(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, dict[str, str | int | None]]:
    """Compute differences between two context states.

    Parameters
    ----------
    before : dict[str, Any]
        Context before operation
    after : dict[str, Any]
        Context after operation

    Returns
    -------
    dict[str, dict[str, str | int | None]]
        Dictionary of changes between contexts
    """
    changes = {}

    before_loc = before.get("current_location")
    after_loc = after.get("current_location")

    if before_loc and after_loc:
        if before_loc["line"] != after_loc["line"]:
            changes["line_changed"] = {
                "from": before_loc["line"],
                "to": after_loc["line"],
            }
        if before_loc["function"] != after_loc["function"]:
            changes["function_changed"] = {
                "from": before_loc["function"],
                "to": after_loc["function"],
            }
        if before_loc["file"] != after_loc["file"]:
            changes["file_changed"] = {
                "from": before_loc["file"],
                "to": after_loc["file"],
            }

    if before.get("execution_state") != after.get("execution_state"):
        changes["state_changed"] = {
            "from": before.get("execution_state"),
            "to": after.get("execution_state"),
        }

    before_depth = len(before.get("stack_frames", []))
    after_depth = len(after.get("stack_frames", []))
    if before_depth != after_depth:
        changes["stack_depth_changed"] = {
            "from": before_depth,
            "to": after_depth,
        }

    return changes


def format_location_summary(location: dict[str, Any]) -> str:
    """Format location dict into readable summary.

    Parameters
    ----------
    location : Dict[str, Any]
        Location dictionary with file, line, function

    Returns
    -------
    str
        Formatted location string like "function_name (file.py:42)"
    """
    if not location:
        return "unknown location"

    function = location.get("function", "?")
    file = location.get("file", "?")
    line = location.get("line", "?")

    if file and "/" in file:
        file = file.split("/")[-1]

    return f"{function} ({file}:{line})"


def _map_session_status_to_detailed_status(
    session_status: SessionStatus,
    breakpoints_set: bool = False,
    stop_reason: DAPStopReason | str | None = None,
) -> DetailedExecutionStatus:
    """Map core SessionStatus to DetailedExecutionStatus.

    Parameters
    ----------
    session_status : SessionStatus
        Core session status from AIDB session layer
    breakpoints_set : bool, optional
        Whether breakpoints are set (for RUNNING refinement)
    stop_reason : DAPStopReason | str | None, optional
        Stop reason for PAUSED refinement

    Returns
    -------
    DetailedExecutionStatus
        Mapped detailed status
    """
    # Direct mappings from core status
    if session_status == SessionStatus.INITIALIZED:
        return DetailedExecutionStatus.INITIALIZED  # Session ready but not started
    if session_status == SessionStatus.INITIALIZING:
        return DetailedExecutionStatus.INITIALIZED  # Still setting up
    if session_status == SessionStatus.TERMINATED:
        return DetailedExecutionStatus.TERMINATED
    if session_status == SessionStatus.ERROR:
        return DetailedExecutionStatus.UNKNOWN  # Keep as fallback for errors
    if session_status == SessionStatus.RUNNING:
        # Refine RUNNING based on breakpoints
        if breakpoints_set:
            return DetailedExecutionStatus.RUNNING_TO_BREAKPOINT
        return DetailedExecutionStatus.RUNNING
    if session_status == SessionStatus.PAUSED:
        # Refine PAUSED based on stop reason
        reason_str = None
        if stop_reason:
            if hasattr(stop_reason, "value"):
                reason_str = stop_reason.value
            else:
                reason_str = str(stop_reason).lower()

        if reason_str == DAPStopReason.BREAKPOINT.value:
            return DetailedExecutionStatus.STOPPED_AT_BREAKPOINT
        if reason_str == DAPStopReason.EXCEPTION.value:
            return DetailedExecutionStatus.STOPPED_AT_EXCEPTION
        if reason_str == DAPStopReason.STEP.value:
            return DetailedExecutionStatus.STOPPED_AFTER_STEP
        return DetailedExecutionStatus.PAUSED

    # Fallback - should not reach here for valid sessions
    return DetailedExecutionStatus.UNKNOWN


def determine_detailed_status(
    session: Session | None,
    context: MCPSessionContext | None,
    stop_reason: DAPStopReason | str | None,
) -> DetailedExecutionStatus:
    """Determine detailed execution status using core session status as primary source.

    This function now trusts the core AIDB session layer for status management
    and only refines the status based on additional context.

    Parameters
    ----------
    session : Session | None
        Debug session instance to check session state
    context : MCPSessionContext | None
        Session context with current state
    stop_reason : DAPStopReason | str | None
        Stop reason from execution result

    Returns
    -------
    DetailedExecutionStatus
        Combined status for clear messaging
    """
    # Try to get status from core session first (primary source)
    if session:
        core_status = session.status
        breakpoints_set = bool(context.breakpoints_set) if context else False
        return _map_session_status_to_detailed_status(
            core_status,
            breakpoints_set,
            stop_reason,
        )

    # Fallback to MCP context (when api.session is not available)
    if not context:
        return DetailedExecutionStatus.UNKNOWN

    # MCP context-based checks as fallback
    if context.is_paused:
        reason_str = None
        if stop_reason:
            if hasattr(stop_reason, "value"):
                reason_str = stop_reason.value
            else:
                reason_str = str(stop_reason).lower()

        if reason_str == DAPStopReason.BREAKPOINT.value:
            return DetailedExecutionStatus.STOPPED_AT_BREAKPOINT
        if reason_str == DAPStopReason.EXCEPTION.value:
            return DetailedExecutionStatus.STOPPED_AT_EXCEPTION
        if reason_str == DAPStopReason.STEP.value:
            return DetailedExecutionStatus.STOPPED_AFTER_STEP
        return DetailedExecutionStatus.PAUSED

    if context.is_running:
        if context.breakpoints_set:
            return DetailedExecutionStatus.RUNNING_TO_BREAKPOINT
        return DetailedExecutionStatus.RUNNING

    # Should only reach here for truly uninitialized cases
    return DetailedExecutionStatus.UNKNOWN


def get_next_action_guidance(
    status: DetailedExecutionStatus,
    has_breakpoints: bool = False,
) -> str:
    """Generate contextual guidance for next actions based on status.

    Parameters
    ----------
    status : DetailedExecutionStatus
        Current detailed execution status
    has_breakpoints : bool
        Whether breakpoints are currently set

    Returns
    -------
    str
        Guidance message for the next actions
    """
    guidance_map = {
        DetailedExecutionStatus.STOPPED_AT_BREAKPOINT: (
            "Use inspect to examine state, step to advance, "
            "or continue to next breakpoint"
        ),
        DetailedExecutionStatus.STOPPED_AT_EXCEPTION: (
            "Use inspect to examine exception, variable to check values, "
            "or step out to exit frame"
        ),
        DetailedExecutionStatus.STOPPED_AFTER_STEP: (
            "Inspect current state, continue stepping, or continue execution"
        ),
        DetailedExecutionStatus.RUNNING_TO_BREAKPOINT: (
            "Program running, will pause when breakpoint hit"
        ),
        DetailedExecutionStatus.RUNNING: (
            "Program running"
            + (", breakpoints active" if has_breakpoints else ", no breakpoints set")
        ),
        DetailedExecutionStatus.TERMINATED: (
            "Session ended - restart or start new session"
        ),
        DetailedExecutionStatus.PAUSED: ("Use inspect/step commands to explore state"),
        DetailedExecutionStatus.UNKNOWN: ("Check session status"),
    }

    return guidance_map.get(status, "Check session status")


async def get_code_snapshot_if_paused(
    session: Session | None,
    context: MCPSessionContext | None,
) -> CodeContextResult | None:
    """Get code snapshot if debugger is paused.

    Parameters
    ----------
    session : Session | None
        Debug session instance
    context : MCPSessionContext | None
        Session context with current location

    Returns
    -------
    CodeContextResult | None
        Code context with pointer to current line, or None if not paused
    """
    if not context or not context.is_paused or not context.current_file:
        logger.debug(
            "Skipping code snapshot - missing requirements",
            extra={
                "has_context": bool(context),
                "is_paused": context.is_paused if context else None,
                "current_file": context.current_file if context else None,
            },
        )
        return None

    try:
        # Get source path resolver from adapter if available
        source_path_resolver = None
        if session and session.adapter:
            source_path_resolver = session.adapter.source_path_resolver

        # Create CodeContext instance with source paths for remote debugging
        source_paths = context.source_paths if context else []
        code_ctx = CodeContext(
            ctx=None,
            source_paths=source_paths,
            source_path_resolver=source_path_resolver,
        )

        # Get configured context lines from config
        breadth = ConfigManager().get_mcp_code_context_lines()

        # Extract context around current line
        context_result = code_ctx.extract_context(
            file_path=context.current_file,
            line=context.current_line or 1,
            breadth=breadth,
        )

        logger.debug(
            "Extracted code snapshot",
            extra={
                "file": context.current_file,
                "line": context.current_line,
                "context_lines": len(context_result["lines"]),
            },
        )

        return context_result

    except Exception as e:
        logger.debug(
            "Could not extract code snapshot: %s",
            e,
            extra={
                "file": context.current_file,
                "line": context.current_line,
            },
        )
        return None


def build_error_execution_state(
    session: Session | None,
    context: MCPSessionContext | None,
    include_error_context: bool = False,
) -> dict[str, Any]:
    """Build execution state dictionary for error responses.

    This provides a consistent structure for execution state in error responses
    across different MCP handlers.

    Parameters
    ----------
    session : Session | None
        Debug session instance
    context : MCPSessionContext | None
        Session context
    include_error_context : bool
        If True, includes "error_context": True in the result

    Returns
    -------
    dict[str, Any]
        Execution state dictionary with status, session_state, current_location,
        and breakpoints_active fields
    """
    try:
        detailed_status = determine_detailed_status(session, context, None)
        state: dict[str, Any] = {
            "status": detailed_status.value,
            "session_state": (
                ExecutionState.PAUSED.value
                if context and context.is_paused
                else ExecutionState.RUNNING.value
                if context and context.is_running
                else ExecutionState.UNKNOWN.value
            ),
            "current_location": (
                f"{context.current_file}:{context.current_line}"
                if context and context.current_file
                else None
            ),
            "breakpoints_active": bool(context.breakpoints_set) if context else False,
        }
        if include_error_context:
            state["error_context"] = True
        return state
    except Exception as state_error:
        logger.debug("Could not build execution state: %s", state_error)
        return {}


@dataclass
class ResponseContext:
    """Common context fields for execution response building.

    This dataclass consolidates the common fields used across different execution
    response types (execute, step, run_until).
    """

    location: str | None
    """Current file:line location, or None if not available."""

    detailed_status: str
    """Detailed execution status value."""

    has_breakpoints: bool
    """Whether breakpoints are currently set."""

    code_context: Any | None
    """Code snapshot at current location, or None."""


async def build_response_context(
    session: Session | None,
    context: MCPSessionContext | None,
    stop_reason: str | None = None,
    is_paused: bool = True,
) -> ResponseContext:
    """Build common context fields for execution responses.

    This helper consolidates the common pattern used across execute, step,
    and run_until handlers for building response context.

    Parameters
    ----------
    session : Session | None
        Debug session instance
    context : MCPSessionContext | None
        Session context with current location and state
    stop_reason : str | None
        Stop reason for status determination (e.g., "step", "breakpoint")
    is_paused : bool
        Whether the debugger is paused (for code snapshot retrieval)

    Returns
    -------
    ResponseContext
        Dataclass with location, detailed_status, has_breakpoints, code_context
    """
    # Build location from context
    location = None
    if context and context.current_file:
        location = f"{context.current_file}:{context.current_line}"

    # Determine detailed status
    detailed_status = determine_detailed_status(session, context, stop_reason)

    # Check for breakpoints
    has_breakpoints = bool(context.breakpoints_set) if context else False

    # Get code snapshot if paused
    code_context = None
    if is_paused and context:
        code_context = await get_code_snapshot_if_paused(session, context)

    return ResponseContext(
        location=location,
        detailed_status=detailed_status.value,
        has_breakpoints=has_breakpoints,
        code_context=code_context,
    )
