"""Core session CRUD operations and API management."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from aidb import DebugAPI
from aidb_logging import (
    get_mcp_logger as get_logger,
)
from aidb_logging import (
    set_session_id,
)

if TYPE_CHECKING:
    from .context import MCPSessionContext

from .manager_shared import (
    _DEBUG_SESSIONS,
    _DEFAULT_SESSION_ID,
    _SESSION_CONTEXTS,
    _state_lock,
)

logger = get_logger(__name__)


def get_or_create_session(
    session_id: str | None = None,
) -> tuple[str, DebugAPI, MCPSessionContext]:
    """Get existing session or create new one.

    Parameters
    ----------
    session_id : str, optional
        Session ID to get or create. If None, uses/creates default session.

    Returns
    -------
    Tuple[str, DebugAPI, MCPSessionContext]
        Session ID, Debug API instance, and session context
    """
    global _DEFAULT_SESSION_ID

    with _state_lock:
        # Use provided session_id or default
        if session_id is None:
            if _DEFAULT_SESSION_ID is None:
                _DEFAULT_SESSION_ID = str(uuid.uuid4())  # Use full UUID for consistency
            session_id = _DEFAULT_SESSION_ID

        # Get or create session
        if session_id not in _DEBUG_SESSIONS:
            _DEBUG_SESSIONS[session_id] = DebugAPI()
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

        return session_id, _DEBUG_SESSIONS[session_id], _SESSION_CONTEXTS[session_id]


def get_session_api(session_id: str | None = None) -> DebugAPI | None:
    """Get API for a specific session.

    Parameters
    ----------
    session_id : str, optional
        Session ID. If None, uses default session.

    Returns
    -------
    Optional[DebugAPI]
        Debug API instance or None if not found
    """
    with _state_lock:
        if session_id is None:
            session_id = _DEFAULT_SESSION_ID
        return _DEBUG_SESSIONS.get(session_id) if session_id else None


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
