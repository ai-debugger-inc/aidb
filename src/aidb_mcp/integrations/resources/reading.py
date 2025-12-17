"""Resource reading for MCP debugging resources.

This module provides functions to read the contents of MCP resources by their URI.
"""

from __future__ import annotations

import json

from mcp.types import AnyUrl, ResourceContents, TextResourceContents

from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import DebugURI
from ...core.serialization import to_jsonable
from ...session.manager import _DEBUG_SESSIONS, _SESSION_CONTEXTS, _state_lock

logger = get_logger(__name__)


def _parse_resource_uri(uri: str) -> tuple[str, str]:
    """Parse a resource URI into type and ID.

    Parameters
    ----------
    uri : str
        Resource URI to parse

    Returns
    -------
    tuple[str, str]
        Resource type and ID

    Raises
    ------
    ValueError
        If URI is invalid
    """
    if not uri.startswith(DebugURI.SCHEME):
        msg = f"Invalid debug resource URI: {uri}"
        raise ValueError(msg)

    parts = uri[len(DebugURI.SCHEME) :].split("/", 1)
    if len(parts) != 2:
        msg = f"Invalid debug resource URI format: {uri}"
        raise ValueError(msg)

    return parts[0], parts[1]


def _read_session_resource(resource_id: str, uri: str) -> ResourceContents:
    """Read a session resource.

    Parameters
    ----------
    resource_id : str
        Session ID
    uri : str
        Original URI

    Returns
    -------
    ResourceContents
        Session resource content

    Raises
    ------
    ValueError
        If session not found
    """
    if resource_id not in _DEBUG_SESSIONS:
        msg = f"Session not found: {resource_id}"
        raise ValueError(msg)

    api = _DEBUG_SESSIONS[resource_id]
    context = _SESSION_CONTEXTS.get(resource_id)
    if not context:
        msg = f"Session context not found: {resource_id}"
        raise ValueError(msg)

    content = {
        "session_id": resource_id,
        "active": context.session_started,
        "language": getattr(context, "language", None),
        "target": getattr(context, "target", None),
        "breakpoints": list(getattr(context, "breakpoints", set())),
        "watches": list(getattr(context, "watches", set())),
    }

    if context.session_started and api:
        try:
            session_info = api.session.info if api.session else None
            if session_info:
                content["status"] = to_jsonable(session_info.status)
                content["session_info"] = to_jsonable(session_info)
        except Exception:
            content["status"] = "error retrieving status"

    logger.info(
        "Read session resource",
        extra={
            "session_id": resource_id,
            "active": content["active"],
            "language": content["language"],
        },
    )

    return TextResourceContents(
        uri=AnyUrl(uri),
        text=json.dumps(content, indent=2),
        mimeType="application/json",
    )


def _read_breakpoint_resource(resource_id: str, uri: str) -> ResourceContents:
    """Read a breakpoint resource.

    Parameters
    ----------
    resource_id : str
        Breakpoint ID (session_id:location)
    uri : str
        Original URI

    Returns
    -------
    ResourceContents
        Breakpoint resource content

    Raises
    ------
    ValueError
        If breakpoint not found
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

    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        msg = f"Session context not found: {session_id}"
        raise ValueError(msg)

    if not hasattr(context, "breakpoints") or location not in context.breakpoints:
        msg = f"AidbBreakpoint not found: {location}"
        raise ValueError(msg)

    content = {
        "session_id": session_id,
        "location": location,
        "enabled": True,
    }

    if ":" in location:
        file_path, line = location.rsplit(":", 1)
        content["file"] = file_path
        content["line"] = int(line)

    return TextResourceContents(
        uri=AnyUrl(uri),
        text=json.dumps(content, indent=2),
        mimeType="application/json",
    )


def _read_watch_resource(resource_id: str, uri: str) -> ResourceContents:
    """Read a watch resource.

    Parameters
    ----------
    resource_id : str
        Watch ID (session_id:expression)
    uri : str
        Original URI

    Returns
    -------
    ResourceContents
        Watch resource content

    Raises
    ------
    ValueError
        If watch not found
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

    api = _DEBUG_SESSIONS[session_id]
    context = _SESSION_CONTEXTS.get(session_id)
    if not context:
        msg = f"Session context not found: {session_id}"
        raise ValueError(msg)

    if not hasattr(context, "watches") or expression not in context.watches:
        msg = f"Watch expression not found: {expression}"
        raise ValueError(msg)

    content = {
        "session_id": session_id,
        "expression": expression,
    }

    if context.session_started and api:
        try:
            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                api.variables.evaluate(expression),
            )
            if result.success:
                content["value"] = result.value
                content["type"] = result.type
            else:
                content["error"] = result.error
        except Exception as e:
            content["error"] = str(e)
    else:
        content["error"] = "Session not active"

    return TextResourceContents(
        uri=AnyUrl(uri),
        text=json.dumps(content, indent=2),
        mimeType="application/json",
    )


def read_resource(uri: str) -> ResourceContents:
    """Read a debugging resource by URI.

    Parameters
    ----------
    uri : str
        Resource URI to read

    Returns
    -------
    ResourceContents
        Resource content

    Raises
    ------
    ValueError
        If resource not found or invalid URI
    """
    from . import ResourceType

    logger.debug("Reading resource %s", extra={"uri": uri})

    resource_type, resource_id = _parse_resource_uri(uri)

    with _state_lock:
        resource_handlers = {
            ResourceType.SESSION: _read_session_resource,
            ResourceType.BREAKPOINT: _read_breakpoint_resource,
            ResourceType.WATCH: _read_watch_resource,
        }

        handler = resource_handlers.get(resource_type)
        if not handler:
            msg = f"Unknown resource type: {resource_type}"
            raise ValueError(msg)

        return handler(resource_id, uri)
