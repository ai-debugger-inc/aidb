"""Session state tracking and default session management."""

from __future__ import annotations

from typing import Any

from aidb_logging import (
    get_mcp_logger as get_logger,
)

from .manager_shared import (
    _DEBUG_SESSIONS,
    _DEFAULT_SESSION_ID,
    _SESSION_CONTEXTS,
    _state_lock,
)

logger = get_logger(__name__)


def set_default_session(session_id: str) -> str | None:
    """Set the default session ID.

    Parameters
    ----------
    session_id : str
        Session ID to set as default

    Returns
    -------
    str, optional
        Previous default session ID, or None if no previous default
    """
    global _DEFAULT_SESSION_ID

    with _state_lock:
        previous_default = _DEFAULT_SESSION_ID
        _DEFAULT_SESSION_ID = session_id
        logger.debug("Default session changed: %s -> %s", previous_default, session_id)
        return previous_default


def get_last_active_session() -> str | None:
    """Get the last active session ID.

    Returns
    -------
    Optional[str]
        The session ID of the last active session, or None if no sessions exist
    """
    with _state_lock:
        # First check for the default session (highest priority)
        if _DEFAULT_SESSION_ID and _DEFAULT_SESSION_ID in _DEBUG_SESSIONS:
            return _DEFAULT_SESSION_ID

        # Then check for any session with a started session context
        for sid in _DEBUG_SESSIONS:
            context = _SESSION_CONTEXTS.get(sid)
            if context and context.session_started:
                return sid

        # Finally, just return the most recent session
        if _DEBUG_SESSIONS:
            return list(_DEBUG_SESSIONS.keys())[-1]

        return None


def get_session_id_from_args(
    args: dict[str, Any],
    param_name: str = "session_id",
) -> str | None:
    """Get session ID from args or fall back to last active session.

    This is a common pattern in handlers that accept an optional session_id parameter
    but fall back to the last active session if not provided.

    Parameters
    ----------
    args : dict[str, Any]
        Handler arguments dictionary
    param_name : str, optional
        Parameter name to look for, default "session_id"

    Returns
    -------
    str | None
        Session ID from args or last active session, None if neither exists
    """
    session_id = args.get(param_name)
    if not session_id:
        session_id = get_last_active_session()
    return session_id


def list_sessions() -> list[dict[str, Any]]:
    """List all active debug sessions.

    Returns
    -------
    List[Dict[str, Any]]
        List of session information
    """
    with _state_lock:
        sessions: list[dict[str, Any]] = []
        for sid, api in _DEBUG_SESSIONS.items():
            session_info = {
                "session_id": sid,
                "is_default": sid == _DEFAULT_SESSION_ID,
                "active": api.started if api else False,
            }

            if api and api.session_info:
                session_info.update(
                    {
                        "target": api.session_info.target,
                        "language": api.session_info.language,
                        "status": api.session_info.status.name.lower(),
                        "port": api.session_info.port,
                        "target_pid": api.session_info.pid,
                    },
                )

            context = _SESSION_CONTEXTS.get(sid)
            if context:
                session_info["breakpoints"] = len(context.breakpoints_set)

            sessions.append(session_info)

        return sessions
