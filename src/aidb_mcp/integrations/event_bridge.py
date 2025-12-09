"""Bridge between DAP PublicEventAPI and MCP NotificationManager.

This module provides direct event propagation from DAP to MCP, eliminating the need for
polling. It uses the public Session.events API to subscribe to DAP events without
accessing internal implementation details.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aidb.dap.client.constants import EventType as DAPEventType
from aidb.dap.client.constants import StopReason as DAPStopReason
from aidb.dap.protocol.events import (
    BreakpointEvent,
    StoppedEvent,
    TerminatedEvent,
    ThreadEvent,
)
from aidb_logging import get_mcp_logger as get_logger

from ..core.constants import EventType as MCPEventType
from .notifications import get_notification_manager

if TYPE_CHECKING:
    from aidb.dap.client.public_events import PublicEventAPI, StubPublicEventAPI
    from aidb.dap.protocol.base import Event

logger = get_logger(__name__)


class DAPToMCPEventBridge:
    """Bridges DAP events directly to MCP notifications."""

    def __init__(self, session_id: str):
        """Initialize the event bridge.

        Parameters
        ----------
        session_id : str
            The session ID for this bridge
        """
        self.session_id = session_id
        self._loop = asyncio.get_event_loop()

    def create_dap_listener(self, event_type: str) -> Any:
        """Create a DAP event listener that forwards to MCP.

        Parameters
        ----------
        event_type : str
            The DAP event type to listen for

        Returns
        -------
        callable
            A callback function for the DAP EventProcessor
        """

        def listener(event: Event) -> None:
            """Forward DAP event to MCP notification system."""
            # Run the async notification in the event loop
            asyncio.create_task(self._forward_event(event_type, event))

        return listener

    async def _forward_event(self, event_type: str, event: Event) -> None:
        """Forward a DAP event to MCP notifications.

        Parameters
        ----------
        event_type : str
            The DAP event type
        event : Event
            The DAP event to forward
        """
        try:
            # Map DAP event to MCP notification
            is_stopped = event_type == DAPEventType.STOPPED.value
            is_breakpoint = event_type == DAPEventType.BREAKPOINT.value
            is_terminated = event_type == DAPEventType.TERMINATED.value
            is_thread = event_type == DAPEventType.THREAD.value

            if is_stopped and isinstance(event, StoppedEvent):
                await self._handle_stopped_event(event)
            elif is_breakpoint and isinstance(event, BreakpointEvent):
                await self._handle_breakpoint_event(event)
            elif is_terminated and isinstance(event, TerminatedEvent):
                await self._handle_terminated_event(event)
            elif is_thread and isinstance(event, ThreadEvent):
                await self._handle_thread_event(event)
        except Exception as e:
            logger.error("Error forwarding DAP event to MCP: %s", e)

    async def _handle_stopped_event(self, event: StoppedEvent) -> None:
        """Handle a stopped event (usually breakpoint hit).

        Parameters
        ----------
        event : StoppedEvent
            The stopped event from DAP
        """
        if event.body and event.body.reason == DAPStopReason.BREAKPOINT.value:
            # This is a breakpoint hit
            location = (
                event.body.hitBreakpointIds[0]
                if event.body.hitBreakpointIds
                else "unknown"
            )

            # Get the notification manager and emit directly
            manager = get_notification_manager()
            await manager.emit(
                MCPEventType.BREAKPOINT_HIT.value,
                {
                    "session_id": self.session_id,
                    "location": f"Breakpoint {location}",
                    "thread_id": event.body.threadId,
                    "reason": event.body.reason,
                    "description": event.body.description,
                    "message": f"Breakpoint hit in thread {event.body.threadId}",
                    "all_threads_stopped": event.body.allThreadsStopped,
                    "preserve_focus_hint": event.body.preserveFocusHint,
                },
            )
            logger.info("Notified MCP about breakpoint hit: %s", location)

        elif event.body and event.body.reason == DAPStopReason.EXCEPTION.value:
            # Exception occurred
            await self._handle_exception_from_stopped(event)

    async def _handle_exception_from_stopped(self, event: StoppedEvent) -> None:
        """Handle an exception from a stopped event.

        Parameters
        ----------
        event : StoppedEvent
            The stopped event with exception reason
        """
        manager = get_notification_manager()
        await manager.emit(
            MCPEventType.EXCEPTION.value,
            {
                "session_id": self.session_id,
                "exception_type": "Exception",
                "message": (
                    event.body.description if event.body else "Exception occurred"
                ),
                "thread_id": event.body.threadId if event.body else None,
                "reason": (
                    event.body.reason if event.body else DAPStopReason.EXCEPTION.value
                ),
                "all_threads_stopped": (
                    event.body.allThreadsStopped if event.body else False
                ),
            },
        )
        logger.info(
            "Notified MCP about exception: %s",
            event.body.description if event.body else "unknown",
        )

    async def _handle_breakpoint_event(self, event: BreakpointEvent) -> None:
        """Handle a breakpoint event (breakpoint added/removed/changed).

        Parameters
        ----------
        event : BreakpointEvent
            The breakpoint event from DAP
        """
        # This is for breakpoint state changes, not hits
        logger.debug("Breakpoint event: %s", event.body if event.body else "no body")

    async def _handle_terminated_event(self, event: TerminatedEvent) -> None:
        """Handle a terminated event (program ended).

        Parameters
        ----------
        event : TerminatedEvent
            The terminated event from DAP
        """
        manager = get_notification_manager()
        await manager.emit(
            MCPEventType.TERMINATED.value,
            {
                "session_id": self.session_id,
                "message": "Program terminated",
                "restart": event.restart if hasattr(event, "restart") else False,
            },
        )
        logger.info(
            "Notified MCP about program termination for session %s",
            self.session_id,
        )

    async def _handle_thread_event(self, event: ThreadEvent) -> None:
        """Handle a thread event.

        Parameters
        ----------
        event : ThreadEvent
            The thread event from DAP
        """
        manager = get_notification_manager()
        await manager.emit(
            MCPEventType.THREAD_EVENT.value,
            {
                "session_id": self.session_id,
                "thread_id": event.body.threadId if event.body else None,
                "reason": event.body.reason if event.body else None,
                "message": (
                    f"Thread {event.body.threadId if event.body else 'unknown'} "
                    f"{event.body.reason if event.body else 'unknown'}"
                ),
            },
        )
        logger.debug("Thread event: %s", event.body if event.body else "no body")


async def register_event_bridge(
    session_id: str,
    events: PublicEventAPI | StubPublicEventAPI,
) -> tuple[DAPToMCPEventBridge, list[str]]:
    """Register event bridge between DAP and MCP using the public event API.

    This function creates a bridge and registers listeners using the session's
    public event API, avoiding direct access to internal EventProcessor.

    Parameters
    ----------
    session_id : str
        The session ID
    events : PublicEventAPI | StubPublicEventAPI
        The session's public event API (from session.events)

    Returns
    -------
    tuple[DAPToMCPEventBridge, list[str]]
        The created bridge instance and list of subscription IDs for cleanup
    """
    bridge = DAPToMCPEventBridge(session_id)
    subscription_ids: list[str] = []

    # Register listeners for important event types
    # Always include "terminated" for auto-subscription
    event_types = [
        DAPEventType.STOPPED.value,
        DAPEventType.BREAKPOINT.value,
        DAPEventType.TERMINATED.value,
        DAPEventType.THREAD.value,
    ]

    for event_type in event_types:
        listener = bridge.create_dap_listener(event_type)
        sub_id = await events.subscribe_to_event(event_type, listener)
        subscription_ids.append(sub_id)
        logger.info(
            "Registered MCP bridge for %s events in session %s (sub_id=%s)",
            event_type,
            session_id,
            sub_id,
        )

    return bridge, subscription_ids
