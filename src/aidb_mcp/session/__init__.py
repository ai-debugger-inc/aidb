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
    clear_service,
    get_last_active_session,
    get_or_create_session,
    get_session_id_from_args,
    list_sessions,
    set_default_session,
    set_service,
)
from .manager_core import get_service, get_session

__all__ = [
    # Session management
    "get_or_create_session",
    "get_last_active_session",
    "get_session_id_from_args",
    "get_service",
    "get_session",
    "list_sessions",
    "cleanup_session",
    "set_default_session",
    "_state_lock",
    # DebugService management
    "set_service",
    "clear_service",
    # Health monitoring
    "check_connection_health",
    "start_health_monitoring",
    "stop_health_monitoring",
]
