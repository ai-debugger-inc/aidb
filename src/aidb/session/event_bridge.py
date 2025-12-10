"""Event synchronization bridge for parent-child session communication.

This module provides the EventBridge class that synchronizes DAP events between parent
and child debug sessions, particularly for adapters like vscode-js-debug that use
separate DAP connections for child sessions.
"""

import asyncio
import threading
from typing import TYPE_CHECKING

from aidb.dap.client.constants import EventType
from aidb.dap.protocol.base import Event
from aidb.patterns import Obj
from aidb_logging.utils import LogOnce

if TYPE_CHECKING:
    from aidb.session import Session


class EventBridge(Obj):
    """Synchronizes DAP events between parent and child debug sessions.

    The EventBridge solves the critical issue where child sessions with separate
    DAP connections don't receive stopped events from the parent session. It:

        1. Forwards key events (stopped, continued, terminated) from parent to
           child
        2. Updates child DAP client state to maintain correct thread/frame
           tracking
        3. Enables proper introspection (locals, variables) in child sessions

    This is essential for JavaScript debugging where vscode-js-debug creates
    child sessions with their own DAP connections via startDebugging requests.
    """

    def __init__(self, ctx=None):
        """Initialize the EventBridge.

        Parameters
        ----------
        ctx : Context, optional
            The context for logging and debugging
        """
        super().__init__(ctx)
        # Use asyncio.Lock for async methods to avoid holding lock during await
        self._async_lock = asyncio.Lock()
        # Use threading.RLock for synchronous operations (forward_event_to_children)
        self._sync_lock = threading.RLock()

        # Map parent session IDs to their active child sessions
        self._parent_to_children: dict[str, set[str]] = {}

        # Map child session IDs to their parent
        self._child_to_parent: dict[str, str] = {}

        # Event types to forward from parent to child
        # Note: 'terminated' is NOT forwarded because child sessions have
        # independent lifecycles and should only terminate when THEIR OWN
        # DAP connection terminates
        self._forwarded_event_types = {
            EventType.STOPPED.value,
            EventType.CONTINUED.value,
        }

        # Track subscription IDs for cleanup
        self._subscriptions: dict[str, set[str]] = {}  # parent_id -> subscription_ids

        LogOnce.info(
            self.ctx,
            "event_bridge_init",
            "EventBridge initialized for parent-child event synchronization",
        )

    async def setup_parent_subscriptions(self, parent_session: "Session") -> None:
        """Set up event subscriptions for a parent session.

        This uses the new subscription-based approach to listen for events
        that need to be forwarded to child sessions.

        Parameters
        ----------
        parent_session : Session
            The parent session to subscribe to
        """
        if not parent_session.events:
            self.ctx.warning(
                f"Parent session {parent_session.id} has no events API, "
                "skipping subscription setup",
            )
            return

        parent_id = parent_session.id

        # Clean up any existing subscriptions for this parent
        await self.cleanup_parent_subscriptions(parent_id)

        # Create new subscriptions
        if parent_id not in self._subscriptions:
            self._subscriptions[parent_id] = set()

        # Create a handler factory function
        def make_handler(session: "Session", _event_name: str):
            def handler(event: Event) -> None:
                self.forward_event_to_children(session, event)

            return handler

        # Subscribe to each event type we need to forward
        for event_type in self._forwarded_event_types:
            handler = make_handler(parent_session, event_type)
            subscription_id = await parent_session.events.subscribe_to_event(
                event_type,
                handler,
            )
            self._subscriptions[parent_id].add(subscription_id)

        self.ctx.debug(
            f"Set up {len(self._subscriptions[parent_id])} event subscriptions "
            f"for parent session {parent_id}",
        )

    async def cleanup_parent_subscriptions(self, parent_id: str) -> None:
        """Clean up event subscriptions for a parent session.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        """
        if parent_id not in self._subscriptions:
            return

        # Get the parent session to unsubscribe
        from aidb.session.registry import SessionRegistry

        registry = SessionRegistry(ctx=self.ctx)
        parent = registry.get_session(parent_id)

        if parent and parent.events:
            for subscription_id in self._subscriptions[parent_id]:
                await parent.events.unsubscribe_from_event(subscription_id)

        del self._subscriptions[parent_id]
        self.ctx.debug(f"Cleaned up event subscriptions for parent {parent_id}")

    async def register_child(self, parent_id: str, child_id: str) -> None:
        """Register a child session with its parent for event forwarding.

        Parameters
        ----------
        parent_id : str
            The parent session ID
        child_id : str
            The child session ID
        """
        async with self._async_lock:
            need_setup = parent_id not in self._parent_to_children
            if need_setup:
                self._parent_to_children[parent_id] = set()

            # Update both locks' data structures atomically
            with self._sync_lock:
                self._parent_to_children[parent_id].add(child_id)
                self._child_to_parent[child_id] = parent_id

        # Set up subscriptions outside the lock to avoid holding during await
        if need_setup:
            from aidb.session.registry import SessionRegistry

            registry = SessionRegistry(ctx=self.ctx)
            parent = registry.get_session(parent_id)
            if parent:
                await self.setup_parent_subscriptions(parent)

        self.ctx.debug(
            f"Registered child {child_id} with parent {parent_id} for event bridging",
        )

    async def unregister_child(self, child_id: str) -> None:
        """Unregister a child session from event forwarding.

        Parameters
        ----------
        child_id : str
            The child session ID to unregister
        """
        need_cleanup = False
        parent_id_to_cleanup = None

        async with self._async_lock:
            with self._sync_lock:
                parent_id = self._child_to_parent.pop(child_id, None)
                if parent_id and parent_id in self._parent_to_children:
                    self._parent_to_children[parent_id].discard(child_id)

                    # Check if we need to clean up empty parent entries
                    if not self._parent_to_children[parent_id]:
                        del self._parent_to_children[parent_id]
                        need_cleanup = True
                        parent_id_to_cleanup = parent_id

        # Clean up subscriptions outside the lock to avoid holding during await
        if need_cleanup and parent_id_to_cleanup:
            await self.cleanup_parent_subscriptions(parent_id_to_cleanup)

        if parent_id:
            self.ctx.debug(f"Unregistered child {child_id} from event bridging")

    def forward_event_to_children(
        self,
        parent_session: "Session",
        event: Event,
    ) -> None:
        """Forward a DAP event from parent to all active child sessions.

        This is called when the parent session receives an event that should be
        synchronized to child sessions. Only specific event types are forwarded.

        Parameters
        ----------
        parent_session : Session
            The parent session that received the event
        event : Event
            The DAP event to potentially forward
        """
        # Only forward specific event types
        if event.event not in self._forwarded_event_types:
            return

        with self._sync_lock:
            child_ids = self._parent_to_children.get(parent_session.id, set()).copy()

        if not child_ids:
            return

        self.ctx.debug(
            f"Forwarding {event.event} event from parent {parent_session.id} "
            f"to {len(child_ids)} child session(s)",
        )

        # Get registry to look up child sessions
        from aidb.session.registry import SessionRegistry

        registry = SessionRegistry(ctx=self.ctx)

        for child_id in child_ids:
            child = registry.get_session(child_id)
            if not child:
                self.ctx.warning(f"Child session {child_id} not found in registry")
                continue

            # Forward the event to the child's DAP client if it has one
            if child.connector._dap and child.connector._dap._event_processor:
                self._forward_event_to_child(child, event)

    def _forward_event_to_child(self, child: "Session", event: Event) -> None:
        """Forward a specific event to a child session's DAP client.

        Parameters
        ----------
        child : Session
            The child session to receive the event
        event : Event
            The event to forward
        """
        try:
            child.dap.ingest_synthetic_event(event)

            self.ctx.debug(f"Forwarded {event.event} event to child {child.id}")

        except Exception as e:
            self.ctx.error(
                f"Failed to forward {event.event} event to child {child.id}: {e}",
            )
