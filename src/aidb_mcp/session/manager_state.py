"""Session state tracking and default session management."""

from __future__ import annotations

from typing import Any

from aidb_logging import (
    get_mcp_logger as get_logger,
)

from .manager_shared import (
    _DEBUG_SESSIONS,
    _DEFAULT_SESSION_ID,
    _INIT_CONTEXT,
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
    *,
    check_internal: bool = True,
) -> str | None:
    """Get session ID from args or fall back to last active session.

    This is the canonical pattern for session ID resolution. All handlers should
    use this function instead of manually checking args.

    Resolution order:
    1. args[param_name] (e.g., "session_id")
    2. args["_session_id"] (decorator-injected, if check_internal=True)
    3. Last active session via get_last_active_session()

    Parameters
    ----------
    args : dict[str, Any]
        Handler arguments dictionary
    param_name : str, optional
        Parameter name to look for, default "session_id"
    check_internal : bool, optional
        Whether to check "_session_id" (decorator-injected), default True

    Returns
    -------
    str | None
        Session ID from args or last active session, None if neither exists
    """
    session_id = args.get(param_name)
    if not session_id and check_internal:
        session_id = args.get("_session_id")
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
        for sid, service in _DEBUG_SESSIONS.items():
            session = service.session if service else None
            session_info = {
                "session_id": sid,
                "is_default": sid == _DEFAULT_SESSION_ID,
                "active": session.started if session else False,
            }

            if session:
                try:
                    info = session.info
                    if info:
                        session_info.update(
                            {
                                "target": info.target,
                                "language": info.language,
                                "status": info.status.name.lower(),
                                "port": info.port,
                                "target_pid": info.pid,
                            },
                        )
                except Exception:
                    logger.debug("Failed to get session info for %s", sid)

            context = _SESSION_CONTEXTS.get(sid)
            if context:
                session_info["breakpoints"] = len(context.breakpoints_set)

            sessions.append(session_info)

        return sessions


# ============================================================================
# Init Context Management (Thread-Safe)
# ============================================================================


def get_init_context() -> dict[str, bool | str | None]:
    """Get a copy of the init context (thread-safe).

    Returns
    -------
    dict[str, bool | str | None]
        Copy of the current init context with keys:
        - initialized: bool
        - language: str | None
        - framework: str | None
        - mode: str | None
    """
    with _state_lock:
        return _INIT_CONTEXT.copy()


def is_initialized() -> bool:
    """Check if init has been called (thread-safe).

    Returns
    -------
    bool
        True if init has been called, False otherwise
    """
    with _state_lock:
        return bool(_INIT_CONTEXT["initialized"])


def get_init_language() -> str | None:
    """Get the language from init context (thread-safe).

    Returns
    -------
    str | None
        The language set during init, or None if not initialized
    """
    with _state_lock:
        lang = _INIT_CONTEXT["language"]
        return str(lang) if lang else None


def set_init_context(
    *,
    initialized: bool = False,
    language: str | None = None,
    framework: str | None = None,
    mode: str | None = None,
) -> None:
    """Update the init context (thread-safe).

    Parameters
    ----------
    initialized : bool
        Whether init has been called
    language : str, optional
        The programming language
    framework : str, optional
        The framework (pytest, jest, etc.)
    mode : str, optional
        The debug mode (launch, attach, etc.)
    """
    with _state_lock:
        _INIT_CONTEXT["initialized"] = initialized
        _INIT_CONTEXT["language"] = language
        _INIT_CONTEXT["framework"] = framework
        _INIT_CONTEXT["mode"] = mode
        logger.debug(
            "Init context updated: initialized=%s, language=%s, framework=%s, mode=%s",
            initialized,
            language,
            framework,
            mode,
        )


def reset_init_context() -> None:
    """Reset the init context to default state (thread-safe).

    Used by tests for isolation.
    """
    set_init_context(initialized=False, language=None, framework=None, mode=None)
