"""Session state introspection and context management.

This module handles breakpoint parsing, location tracking, and code context preparation
for debug sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb_logging import get_mcp_logger as get_logger

from ...core.performance import timed

if TYPE_CHECKING:
    from aidb import DebugService
    from aidb.session import Session

    from ...core.types import BreakpointSpec

logger = get_logger(__name__)


def _parse_string_breakpoint(bp: str) -> dict[str, Any]:
    """Parse string breakpoint format like 'file.py:10' or 'file.py:10:5'."""
    parts = bp.split(":")
    bp_info: dict[str, Any] = {
        "location": bp,
        "verified": True,
        "state": "active",
    }

    if len(parts) >= 2:
        bp_info["file"] = parts[0]
        if parts[1].isdigit():
            bp_info["line"] = int(parts[1])
        else:
            bp_info["line"] = parts[1]

    if len(parts) >= 3:
        if parts[2].isdigit():
            bp_info["column"] = int(parts[2])
        else:
            bp_info["column"] = parts[2]

    return bp_info


def _parse_dict_breakpoint(bp: dict[str, Any] | BreakpointSpec) -> dict[str, Any]:
    """Parse dict breakpoint with optional fields."""
    bp_dict_info: dict[str, Any] = {
        "location": bp.get(
            "location",
            f"{bp.get('file', 'unknown')}:{bp.get('line', 0)}",
        ),
        "verified": bp.get("verified", True),
        "state": bp.get("state", "active"),
    }

    # Add optional fields only if they have values
    optional_fields = [
        ("file", lambda v: str(v)),
        ("line", lambda v: v),
        ("column", lambda v: v),
        ("condition", lambda v: str(v)),
        ("hit_condition", lambda v: str(v)),
        ("log_message", lambda v: str(v)),
    ]

    for field, converter in optional_fields:
        value = bp.get(field)
        if value is not None and (field not in ["line", "column"] or value):
            bp_dict_info[field] = converter(value)

    return bp_dict_info


def _store_breakpoints_in_context(
    session_context: Any,
    breakpoints_parsed: list[BreakpointSpec],
) -> None:
    """Store breakpoints in session context for later retrieval.

    Parameters
    ----------
    session_context : Any
        Session context object
    breakpoints_parsed : list[BreakpointSpec]
        Parsed breakpoint specifications
    """
    if not breakpoints_parsed or not hasattr(session_context, "breakpoints_set"):
        return

    # Convert breakpoints to a comprehensive format that can be stored
    for bp in breakpoints_parsed:
        if isinstance(bp, str):
            bp_info = _parse_string_breakpoint(bp)
            session_context.breakpoints_set.append(bp_info)
        elif isinstance(bp, dict):
            bp_dict_info = _parse_dict_breakpoint(bp)
            session_context.breakpoints_set.append(bp_dict_info)


async def _fetch_location_from_stack(
    service: DebugService,
    session_context: Any,
    session_id: str,
) -> None:
    """Actively fetch current location from stack trace.

    Uses the DebugService layer for stack introspection.

    Parameters
    ----------
    service : DebugService
        Debug service instance
    session_context : Any
        Session context to update
    session_id : str
        Session identifier
    """
    try:
        # Get threads using the service layer
        threads_response = await service.stack.threads()
        if not threads_response.success or not threads_response.threads:
            return

        thread_id = threads_response.threads[0].id

        # Get stack trace using the service layer
        callstack_response = await service.stack.callstack(thread_id)
        if not callstack_response.success or not callstack_response.frames:
            return

        top_frame = callstack_response.frames[0]
        if top_frame.source and top_frame.source.path:
            session_context.current_file = top_frame.source.path
            session_context.current_line = top_frame.line
            logger.debug(
                "Actively fetched location from stack",
                extra={
                    "file": top_frame.source.path,
                    "line": top_frame.line,
                    "session_id": session_id,
                },
            )
    except Exception as e:
        logger.debug(
            "Failed to actively fetch location",
            extra={"error": str(e), "session_id": session_id},
        )


async def _sync_location_from_dap_state(
    session: Session,
    service: DebugService,
    session_context: Any,
    session_id: str,
) -> None:
    """Sync location from DAP client state to MCP session context.

    Parameters
    ----------
    session : Session
        Debug session instance
    service : DebugService
        Debug service instance
    session_context : Any
        Session context to update
    session_id : str
        Session identifier
    """
    if not session:
        return

    # Resolve to active session (handles languages with parent/child patterns)
    active_session = session
    if hasattr(session, "registry") and session.registry:
        resolved = session.registry.resolve_active_session(session)
        if resolved:
            active_session = resolved

    # Use the resolved session's public API to get current location
    current_file, current_line = active_session.get_current_location()
    if current_file and current_line:
        session_context.current_file = current_file
        session_context.current_line = current_line
        logger.debug(
            "Synced location from DAP state",
            extra={
                "file": current_file,
                "line": current_line,
                "session_id": session_id,
            },
        )
    else:
        # DAP state doesn't have location yet, actively fetch it
        await _fetch_location_from_stack(service, session_context, session_id)


@timed
async def _prepare_code_context_and_location(
    session: Session,
    service: DebugService,
    session_context: Any,
    session_id: str,
    is_paused: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    """Prepare code context and location information for paused session.

    Parameters
    ----------
    session : Session
        Debug session instance
    service : DebugService
        Debug service instance
    session_context : Any
        Session context
    session_id : str
        Session identifier
    is_paused : bool
        Whether session is paused

    Returns
    -------
    tuple
        (code_context, location)
    """
    if not is_paused or not session_context:
        return None, None

    # Sync location from DAP state to MCP context
    await _sync_location_from_dap_state(session, service, session_context, session_id)

    # Get location from context
    location = None
    if session_context.current_file:
        location = f"{session_context.current_file}:{session_context.current_line}"

    # Get code snapshot using session
    from ...core.context_utils import get_code_snapshot_if_paused

    code_context = await get_code_snapshot_if_paused(
        session,
        session_context,
    )

    return code_context, location
