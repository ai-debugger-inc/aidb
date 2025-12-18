"""Resource listing for MCP debugging resources.

This module provides functions to list available MCP resources for sessions,
breakpoints, and watch expressions.
"""

from __future__ import annotations

from mcp.types import AnyUrl, Resource

from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import DebugURI
from ...core.serialization import to_jsonable
from ...session.manager import _DEBUG_SESSIONS, _SESSION_CONTEXTS, _state_lock

logger = get_logger(__name__)


def get_session_resources() -> list[Resource]:
    """Get all debug sessions as MCP resources.

    Returns
    -------
    List[Resource]
        List of session resources
    """
    logger.debug("Getting session resources")
    resources = []

    with _state_lock:
        session_count = len(_DEBUG_SESSIONS)
        logger.debug(
            "Processing debug sessions for resources",
            extra={"session_count": session_count},
        )

        for session_id, api in _DEBUG_SESSIONS.items():
            context = _SESSION_CONTEXTS.get(session_id)
            if not context:
                logger.debug(
                    "Skipping session without context",
                    extra={"session_id": session_id},
                )
                continue

            metadata = {
                "session_id": session_id,
                "started": context.session_started,
                "language": getattr(context, "language", None),
                "target": getattr(context, "target", None),
            }

            if context.session_started and api and api.session:
                try:
                    session_info = api.session.info
                    if session_info:
                        metadata["status"] = to_jsonable(session_info.status)
                        metadata["pid"] = getattr(session_info, "pid", None)
                except Exception:
                    logger.debug("Failed to get session info for %s", session_id)

            target_name = metadata.get("target", "unknown target")
            resources.append(
                Resource(
                    uri=AnyUrl(f"{DebugURI.SESSION_PREFIX}{session_id}"),
                    name=f"Debug Session: {session_id}",
                    description=f"Debug session for {target_name}",
                    mimeType="application/json",
                ),
            )

            logger.debug(
                "Added session resource",
                extra={
                    "session_id": session_id,
                    "target": metadata.get("target"),
                    "language": metadata.get("language"),
                    "started": metadata.get("started"),
                },
            )

    logger.info(
        "Retrieved session resources %s",
        extra={"resource_count": len(resources)},
    )
    return resources


def get_breakpoint_resources(session_id: str | None = None) -> list[Resource]:
    """Get all breakpoints as MCP resources.

    Parameters
    ----------
    session_id : str, optional
        Specific session to get breakpoints for. If None, gets all.

    Returns
    -------
    List[Resource]
        List of breakpoint resources
    """
    logger.debug(
        "Getting breakpoint resources",
        extra={"session_id": session_id or "all"},
    )
    resources = []

    with _state_lock:
        sessions_to_check = []
        if session_id and session_id in _DEBUG_SESSIONS:
            sessions_to_check = [(session_id, _DEBUG_SESSIONS[session_id])]
            logger.debug(
                "Checking single session for breakpoints",
                extra={"session_id": session_id},
            )
        else:
            sessions_to_check = list(_DEBUG_SESSIONS.items())
            logger.debug(
                "Checking all sessions for breakpoints",
                extra={"session_count": len(sessions_to_check)},
            )

        for sid, _api in sessions_to_check:
            context = _SESSION_CONTEXTS.get(sid)
            if not context:
                continue

            if hasattr(context, "breakpoints"):
                for bp_location in context.breakpoints:
                    bp_id = f"{sid}:{bp_location}"

                    metadata = {
                        "session_id": sid,
                        "location": bp_location,
                        "enabled": True,
                    }

                    if ":" in bp_location:
                        file_path, line = bp_location.rsplit(":", 1)
                        metadata["file"] = file_path
                        metadata["line"] = int(line)

                    resources.append(
                        Resource(
                            uri=AnyUrl(f"{DebugURI.BREAKPOINT_PREFIX}{bp_id}"),
                            name=f"AidbBreakpoint: {bp_location}",
                            description=f"AidbBreakpoint in session {sid}",
                            mimeType="application/json",
                        ),
                    )

    return resources


def get_watch_resources(session_id: str | None = None) -> list[Resource]:
    """Get all watch expressions as MCP resources.

    Parameters
    ----------
    session_id : str, optional
        Specific session to get watches for. If None, gets all.

    Returns
    -------
    List[Resource]
        List of watch expression resources
    """
    resources = []

    with _state_lock:
        sessions_to_check = []
        if session_id and session_id in _DEBUG_SESSIONS:
            sessions_to_check = [(session_id, _DEBUG_SESSIONS[session_id])]
        else:
            sessions_to_check = list(_DEBUG_SESSIONS.items())

        for sid, api in sessions_to_check:
            context = _SESSION_CONTEXTS.get(sid)
            if not context:
                continue

            if hasattr(context, "watches"):
                for watch_expr in context.watches:
                    watch_id = f"{sid}:{watch_expr}"

                    metadata = {
                        "session_id": sid,
                        "expression": watch_expr,
                    }

                    if context.session_started and api:
                        try:
                            import asyncio

                            result = asyncio.get_event_loop().run_until_complete(
                                api.variables.evaluate(watch_expr),
                            )
                            if result.success:
                                metadata["current_value"] = result.value
                                metadata["type"] = result.type
                        except Exception:
                            metadata["current_value"] = None

                    resources.append(
                        Resource(
                            uri=AnyUrl(f"{DebugURI.WATCH_PREFIX}{watch_id}"),
                            name=f"Watch: {watch_expr}",
                            description=f"Watch expression in session {sid}",
                            mimeType="application/json",
                        ),
                    )

    return resources


def get_all_resources() -> list[Resource]:
    """Get all debugging resources.

    Returns
    -------
    List[Resource]
        Combined list of all resource types
    """
    logger.debug("Getting all debugging resources")
    resources = []
    resources.extend(get_session_resources())
    resources.extend(get_breakpoint_resources())
    resources.extend(get_watch_resources())

    logger.info(
        "Retrieved all debugging resources",
        extra={
            "total_resources": len(resources),
        },
    )
    return resources
