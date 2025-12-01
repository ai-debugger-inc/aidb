"""Public notification API for debugging events.

This module provides convenience functions for emitting various types of debugging
notifications.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import EventType
from ...core.serialization import to_jsonable
from .manager import NotificationManager

logger = get_logger(__name__)


async def notify_breakpoint_hit(
    session_id: str,
    location: str,
    thread_id: int | None = None,
    frame: dict[str, Any] | None = None,
) -> None:
    """Notify that a breakpoint was hit.

    Parameters
    ----------
    session_id : str
        Session ID
    location : str
        AidbBreakpoint location
    thread_id : int, optional
        AidbThread that hit the breakpoint
    frame : dict, optional
        Stack frame information
    """
    await NotificationManager().emit(
        EventType.BREAKPOINT_HIT.value,
        {
            "session_id": session_id,
            "location": location,
            "thread_id": thread_id,
            "frame": to_jsonable(frame) if frame else None,
            "message": f"AidbBreakpoint hit at {location}",
        },
    )


async def notify_exception(
    session_id: str,
    exception_type: str,
    message: str,
    location: str | None = None,
    stack_trace: list[dict[str, Any]] | None = None,
) -> None:
    """Notify that an exception occurred.

    Parameters
    ----------
    session_id : str
        Session ID
    exception_type : str
        Type of exception
    message : str
        Exception message
    location : str, optional
        Where exception occurred
    stack_trace : list, optional
        Stack trace information
    """
    await NotificationManager().emit(
        EventType.EXCEPTION.value,
        {
            "session_id": session_id,
            "exception_type": exception_type,
            "message": message,
            "location": location,
            "stack_trace": to_jsonable(stack_trace) if stack_trace else None,
            "severity": "error",
        },
    )


async def notify_session_state_changed(
    session_id: str,
    old_state: str,
    new_state: str,
    reason: str | None = None,
) -> None:
    """Notify that session state has changed.

    Parameters
    ----------
    session_id : str
        Session ID
    old_state : str
        Previous state
    new_state : str
        New state
    reason : str, optional
        Reason for state change
    """
    await NotificationManager().emit(
        EventType.SESSION_STATE_CHANGED.value,
        {
            "session_id": session_id,
            "old_state": old_state,
            "new_state": new_state,
            "reason": reason,
            "message": f"Session {session_id} changed from {old_state} to {new_state}",
        },
    )


async def notify_watch_changed(
    session_id: str,
    expression: str,
    old_value: Any,
    new_value: Any,
    value_type: str | None = None,
) -> None:
    """Notify that a watched expression value changed.

    Parameters
    ----------
    session_id : str
        Session ID
    expression : str
        Watch expression
    old_value : Any
        Previous value
    new_value : Any
        New value
    value_type : str, optional
        Type of the value
    """
    await NotificationManager().emit(
        EventType.WATCH_CHANGED.value,
        {
            "session_id": session_id,
            "expression": expression,
            "old_value": to_jsonable(old_value),
            "new_value": to_jsonable(new_value),
            "type": value_type,
            "message": f"Watch '{expression}' changed from {old_value} to {new_value}",
        },
    )


async def notify_thread_event(
    session_id: str,
    thread_id: int,
    event: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Notify about thread events (created, exited, etc).

    Parameters
    ----------
    session_id : str
        Session ID
    thread_id : int
        AidbThread ID
    event : str
        Event type (created, exited, suspended, resumed)
    details : dict, optional
        Additional event details
    """
    await NotificationManager().emit(
        EventType.THREAD_EVENT.value,
        {
            "session_id": session_id,
            "thread_id": thread_id,
            "event": event,
            "details": to_jsonable(details) if details else None,
            "message": f"AidbThread {thread_id} {event}",
        },
    )


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager.

    Returns
    -------
    NotificationManager
        The notification manager instance
    """
    return NotificationManager()
