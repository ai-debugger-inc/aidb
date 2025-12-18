"""Session management for MCP debugging tools.

This module handles multi-session support, session lifecycle, and state management for
concurrent debugging sessions.
"""

from __future__ import annotations

from aidb_logging import (
    get_mcp_logger as get_logger,
)

from ..core.config import get_config
from .manager_core import (
    clear_service,
    get_or_create_session,
    get_service,
    get_session,
    get_session_id,
    set_service,
)
from .manager_lifecycle import (
    cleanup_all_sessions,
    cleanup_session,
    cleanup_session_async,
)
from .manager_shared import (
    _DEBUG_SERVICES,
    _DEBUG_SESSIONS,
    _DEFAULT_SESSION_ID,
    _SESSION_CONTEXTS,
    _state_lock,
)
from .manager_state import (
    get_last_active_session,
    get_session_id_from_args,
    list_sessions,
    set_default_session,
)

logger = get_logger(__name__)

# Get configuration
config = get_config()

# Re-export for backward compatibility
__all__ = [
    "get_or_create_session",
    "get_session",
    "get_session_id",
    "set_default_session",
    "get_last_active_session",
    "get_session_id_from_args",
    "list_sessions",
    "cleanup_session",
    "cleanup_session_async",
    "cleanup_all_sessions",
    # DebugService management
    "get_service",
    "set_service",
    "clear_service",
    "_state_lock",
    "_DEBUG_SERVICES",
    "_DEBUG_SESSIONS",  # deprecated - use _DEBUG_SERVICES
    "_SESSION_CONTEXTS",
    "_DEFAULT_SESSION_ID",
]
