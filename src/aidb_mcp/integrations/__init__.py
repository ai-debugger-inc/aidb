"""MCP service utilities.

This module provides services for resources, notifications, and serialization.
"""

from __future__ import annotations

from ..core.serialization import to_jsonable
from .notifications import (
    NotificationManager,
    get_notification_manager,
    notify_breakpoint_hit,
    notify_exception,
    notify_session_state_changed,
    notify_thread_event,
    notify_watch_changed,
    start_event_monitoring,
    stop_event_monitoring,
)
from .resources import (
    delete_resource,
    get_all_resources,
    get_breakpoint_resources,
    get_session_resources,
    get_watch_resources,
    read_resource,
)

__all__ = [
    # Serialization
    "to_jsonable",
    # Resources
    "get_session_resources",
    "get_breakpoint_resources",
    "get_watch_resources",
    "get_all_resources",
    "read_resource",
    "delete_resource",
    # Notifications
    "NotificationManager",
    "get_notification_manager",
    "notify_breakpoint_hit",
    "notify_exception",
    "notify_session_state_changed",
    "notify_thread_event",
    "notify_watch_changed",
    "start_event_monitoring",
    "stop_event_monitoring",
]
