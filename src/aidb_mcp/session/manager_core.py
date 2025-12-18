"""Core session CRUD operations and API management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from aidb_logging import (
    get_mcp_logger as get_logger,
)
from aidb_logging import (
    set_session_id,
)

if TYPE_CHECKING:
    from aidb import DebugService
    from aidb.session import Session

    from .context import MCPSessionContext

from .manager_shared import (
    _DEBUG_SERVICES,
    _DEFAULT_SESSION_ID,
    _SESSION_CONTEXTS,
    _state_lock,
)

logger = get_logger(__name__)


def get_or_create_session(
    session_id: str | None = None,
) -> tuple[str, MCPSessionContext]:
    """Get existing session context or create new one.

    Parameters
    ----------
    session_id : str, optional
        Session ID to get or create. If None, uses/creates default session.

    Returns
    -------
    tuple[str, MCPSessionContext]
        Session ID and session context
    """
    global _DEFAULT_SESSION_ID

    with _state_lock:
        # Use provided session_id or default
        if session_id is None:
            if _DEFAULT_SESSION_ID is None:
                _DEFAULT_SESSION_ID = str(uuid.uuid4())  # Use full UUID for consistency
            session_id = _DEFAULT_SESSION_ID

        # Get or create session context
        if session_id not in _SESSION_CONTEXTS:
            # Import here to avoid circular dependency
            from .context import MCPSessionContext

            _SESSION_CONTEXTS[session_id] = MCPSessionContext()
            # Set the session context for logging
            set_session_id(session_id)
            # Set as default session if no default exists
            if _DEFAULT_SESSION_ID is None:
                _DEFAULT_SESSION_ID = session_id
            logger.info("Created new debug session: %s", session_id)
        else:
            # Switch to existing session context
            set_session_id(session_id)
            logger.debug("Switched to existing session: %s", session_id)

        return session_id, _SESSION_CONTEXTS[session_id]


def get_session_id(
    session_id: str | None = None,
) -> MCPSessionContext | None:
    """Get session context for a specific session.

    Parameters
    ----------
    session_id : str, optional
        Session ID. If None, uses default session.

    Returns
    -------
    Optional[MCPSessionContext]
        Session context or None if not found
    """
    with _state_lock:
        if session_id is None:
            session_id = _DEFAULT_SESSION_ID
        return _SESSION_CONTEXTS.get(session_id) if session_id else None


def set_service(session_id: str, service: DebugService) -> None:
    """Store DebugService for a session.

    Parameters
    ----------
    session_id : str
        Session ID to associate with the service
    service : DebugService
        DebugService instance to store
    """
    with _state_lock:
        _DEBUG_SERVICES[session_id] = service
        logger.debug("Stored DebugService for session: %s", session_id)


def get_service(session_id: str | None = None) -> DebugService | None:
    """Get DebugService for a specific session.

    Parameters
    ----------
    session_id : str, optional
        Session ID. If None, uses default session.

    Returns
    -------
    Optional[DebugService]
        DebugService instance or None if not found
    """
    with _state_lock:
        if session_id is None:
            session_id = _DEFAULT_SESSION_ID
        return _DEBUG_SERVICES.get(session_id) if session_id else None


def clear_service(session_id: str) -> None:
    """Remove DebugService for a session.

    Parameters
    ----------
    session_id : str
        Session ID to clear
    """
    with _state_lock:
        if session_id in _DEBUG_SERVICES:
            del _DEBUG_SERVICES[session_id]
            logger.debug("Cleared DebugService for session: %s", session_id)


def get_session(session_id: str | None = None) -> Session | None:
    """Get Session for a specific session ID.

    This is a convenience function that returns the underlying Session
    from the DebugService. Use this for accessing session properties
    like status, started, info, etc.

    Parameters
    ----------
    session_id : str, optional
        Session ID. If None, uses default session.

    Returns
    -------
    Session | None
        Session instance or None if not found
    """
    service = get_service(session_id)
    return service.session if service else None
