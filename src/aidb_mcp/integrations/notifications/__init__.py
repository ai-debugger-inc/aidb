"""MCP Notifications for debugging events.

This package provides notification support for debugging events like breakpoint hits,
exceptions, and session state changes.
"""

from __future__ import annotations

from .api import (
    get_notification_manager,
    notify_breakpoint_hit,
    notify_exception,
    notify_session_state_changed,
    notify_thread_event,
    notify_watch_changed,
)
from .manager import NotificationManager
from .monitor import (
    DebugEventMonitor,
    start_event_monitoring,
    stop_event_monitoring,
)

__all__ = [
    "NotificationManager",
    "DebugEventMonitor",
    "get_notification_manager",
    "notify_breakpoint_hit",
    "notify_exception",
    "notify_session_state_changed",
    "notify_watch_changed",
    "notify_thread_event",
    "start_event_monitoring",
    "stop_event_monitoring",
]
