"""Session lifecycle management for MCP debugging.

This package handles all aspects of debug session management including creation,
monitoring, health checks, and cleanup.
"""

from __future__ import annotations

from .health import (
    check_connection_health,
    start_health_monitoring,
    stop_health_monitoring,
)
from .manager import (
    _state_lock,
    cleanup_session,
    get_last_active_session,
    get_or_create_session,
    get_session_id_from_args,
    list_sessions,
    set_default_session,
)

__all__ = [
    # Session management
    "get_or_create_session",
    "get_last_active_session",
    "get_session_id_from_args",
    "list_sessions",
    "cleanup_session",
    "set_default_session",
    "_state_lock",
    # Health monitoring
    "check_connection_health",
    "start_health_monitoring",
    "stop_health_monitoring",
]
