"""Resource deletion for MCP debugging resources.

This module provides functions to delete MCP resources by their URI.
"""

from __future__ import annotations

from aidb_logging import get_mcp_logger as get_logger

from ...session.manager import (
    _DEBUG_SESSIONS,
    _SESSION_CONTEXTS,
    _state_lock,
    cleanup_session,
)
from .reading import _parse_resource_uri

logger = get_logger(__name__)


def _delete_session_resource(resource_id: str) -> bool:
    """Delete a session resource.

    Parameters
    ----------
    resource_id : str
        Session ID

    Returns
    -------
    bool
        True if deleted successfully

    Raises
    ------
    ValueError
        If session not found
    """
    if resource_id not in _DEBUG_SESSIONS:
        msg = f"Session not found: {resource_id}"
        raise ValueError(msg)

    result = cleanup_session(resource_id)
    logger.info(
        "Deleted session resource",
        extra={"session_id": resource_id, "success": result},
    )
    return result


def _delete_breakpoint_resource(resource_id: str) -> bool:
    """Delete a breakpoint resource.

    Parameters
    ----------
    resource_id : str
        Breakpoint ID (session_id:location)

    Returns
    -------
    bool
        True if deleted, False if not found

    Raises
    ------
    ValueError
        If invalid breakpoint ID format
    """
    if ":" not in resource_id:
        msg = f"Invalid breakpoint ID: {resource_id}"
        raise ValueError(msg)

    parts = resource_id.split(":", 1)
    session_id = parts[0]
    location = parts[1]

    if session_id not in _DEBUG_SESSIONS:
        msg = f"Session not found: {session_id}"
        raise ValueError(msg)

    api = _DEBUG_SESSIONS[session_id]
    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        return False

    if not hasattr(context, "breakpoints_set"):
        return False

    if not any(bp.get("location") == location for bp in context.breakpoints_set):
        return False

    if context.session_started and api:
        try:
            import asyncio

            if ":" in location:
                file_path = location.rsplit(":", 1)[0]
                asyncio.get_event_loop().run_until_complete(
                    api.breakpoints.clear(source_path=file_path),
                )
        except Exception as e:
            msg = f"Failed to clear breakpoints for {location}: {e}"
            logger.debug(msg)

    context.breakpoints_set = [
        bp for bp in context.breakpoints_set if bp.get("location") != location
    ]
    return True


def _delete_watch_resource(resource_id: str) -> bool:
    """Delete a watch resource.

    Parameters
    ----------
    resource_id : str
        Watch ID (session_id:expression)

    Returns
    -------
    bool
        True if deleted, False if not found

    Raises
    ------
    ValueError
        If invalid watch ID format
    """
    if ":" not in resource_id:
        msg = f"Invalid watch ID: {resource_id}"
        raise ValueError(msg)

    parts = resource_id.split(":", 1)
    session_id = parts[0]
    expression = parts[1]

    if session_id not in _DEBUG_SESSIONS:
        msg = f"Session not found: {session_id}"
        raise ValueError(msg)

    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        return False

    if hasattr(context, "watches") and expression in context.watches:
        context.watches.discard(expression)
        return True

    return False


def delete_resource(uri: str) -> bool:
    """Delete a debugging resource.

    Parameters
    ----------
    uri : str
        Resource URI to delete

    Returns
    -------
    bool
        True if deleted successfully

    Raises
    ------
    ValueError
        If resource not found or cannot be deleted
    """
    from . import ResourceType

    logger.debug("Deleting resource %s", extra={"uri": uri})

    resource_type, resource_id = _parse_resource_uri(uri)

    logger.debug(
        "Parsed resource URI for deletion",
        extra={"resource_type": resource_type, "resource_id": resource_id},
    )

    with _state_lock:
        delete_handlers = {
            ResourceType.SESSION: _delete_session_resource,
            ResourceType.BREAKPOINT: _delete_breakpoint_resource,
            ResourceType.WATCH: _delete_watch_resource,
        }

        handler = delete_handlers.get(resource_type)
        if not handler:
            msg = f"Unknown resource type: {resource_type}"
            raise ValueError(msg)

        return handler(resource_id)
