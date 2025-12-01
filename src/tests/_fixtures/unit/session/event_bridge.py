"""Mock event bridge for unit tests.

Provides mock implementations of EventBridge for testing event forwarding between parent
and child debug sessions.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.dap.protocol.base import Event


@pytest.fixture
def mock_event_bridge() -> MagicMock:
    """Create a mock EventBridge.

    The mock simulates EventBridge for testing event forwarding
    between parent and child sessions.

    Returns
    -------
    MagicMock
        Mock event bridge with common methods
    """
    bridge = MagicMock()

    # Internal storage
    bridge._parent_to_children = {}
    bridge._child_to_parent = {}
    bridge._forwarded_event_types = {"stopped", "continued"}
    bridge._subscriptions = {}

    # Async methods
    bridge.setup_parent_subscriptions = AsyncMock()
    bridge.cleanup_parent_subscriptions = AsyncMock()
    bridge.register_child = AsyncMock()
    bridge.unregister_child = AsyncMock()

    # Sync methods
    bridge.forward_event_to_children = MagicMock()
    bridge._forward_event_to_child = MagicMock()

    return bridge


@pytest.fixture
def mock_event_bridge_with_children() -> MagicMock:
    """Create a mock EventBridge with pre-registered children.

    Returns
    -------
    MagicMock
        Mock event bridge with parent-child relationships configured
    """
    bridge = MagicMock()

    # Pre-configured parent-child relationship
    bridge._parent_to_children = {"parent-1": {"child-1", "child-2"}}
    bridge._child_to_parent = {"child-1": "parent-1", "child-2": "parent-1"}
    bridge._forwarded_event_types = {"stopped", "continued"}
    bridge._subscriptions = {"parent-1": {"sub-1", "sub-2"}}

    # Async methods
    bridge.setup_parent_subscriptions = AsyncMock()
    bridge.cleanup_parent_subscriptions = AsyncMock()
    bridge.register_child = AsyncMock()
    bridge.unregister_child = AsyncMock()

    # Sync methods
    bridge.forward_event_to_children = MagicMock()
    bridge._forward_event_to_child = MagicMock()

    return bridge


class MockEventBridge:
    """Event bridge mock with tracking.

    Use this when you need to verify event forwarding patterns.

    Examples
    --------
    >>> bridge = MockEventBridge()
    >>> await bridge.register_child("parent-1", "child-1")
    >>> assert bridge.get_children("parent-1") == {"child-1"}
    """

    def __init__(self) -> None:
        """Initialize the mock event bridge."""
        self._parent_to_children: dict[str, set[str]] = {}
        self._child_to_parent: dict[str, str] = {}
        self._forwarded_event_types = {"stopped", "continued"}
        self._subscriptions: dict[str, set[str]] = {}

        # Tracking for test verification
        self.forwarded_events: list[dict[str, Any]] = []
        self.subscription_setups: list[str] = []
        self.subscription_cleanups: list[str] = []

    async def setup_parent_subscriptions(self, parent_session: Any) -> None:
        """Mock setting up parent subscriptions."""
        parent_id = (
            parent_session.id if hasattr(parent_session, "id") else str(parent_session)
        )
        self.subscription_setups.append(parent_id)
        if parent_id not in self._subscriptions:
            self._subscriptions[parent_id] = set()
        self._subscriptions[parent_id].add(f"sub-{len(self._subscriptions[parent_id])}")

    async def cleanup_parent_subscriptions(self, parent_id: str) -> None:
        """Mock cleaning up parent subscriptions."""
        self.subscription_cleanups.append(parent_id)
        self._subscriptions.pop(parent_id, None)

    async def register_child(self, parent_id: str, child_id: str) -> None:
        """Register a child session with its parent."""
        if parent_id not in self._parent_to_children:
            self._parent_to_children[parent_id] = set()
        self._parent_to_children[parent_id].add(child_id)
        self._child_to_parent[child_id] = parent_id

    async def unregister_child(self, child_id: str) -> None:
        """Unregister a child session."""
        parent_id = self._child_to_parent.pop(child_id, None)
        if parent_id and parent_id in self._parent_to_children:
            self._parent_to_children[parent_id].discard(child_id)
            if not self._parent_to_children[parent_id]:
                del self._parent_to_children[parent_id]

    def forward_event_to_children(
        self,
        parent_session: Any,
        event: Event,
    ) -> None:
        """Track event forwarding for verification."""
        if event.event not in self._forwarded_event_types:
            return

        parent_id = (
            parent_session.id if hasattr(parent_session, "id") else str(parent_session)
        )
        child_ids = self._parent_to_children.get(parent_id, set())

        for child_id in child_ids:
            self.forwarded_events.append(
                {
                    "parent_id": parent_id,
                    "child_id": child_id,
                    "event_type": event.event,
                    "event": event,
                }
            )

    def _forward_event_to_child(self, child: Any, event: Event) -> None:
        """Track individual child forwarding."""
        child_id = child.id if hasattr(child, "id") else str(child)
        self.forwarded_events.append(
            {
                "child_id": child_id,
                "event_type": event.event,
                "event": event,
            }
        )

    def get_children(self, parent_id: str) -> set[str]:
        """Get child IDs for a parent."""
        return self._parent_to_children.get(parent_id, set())

    def get_parent(self, child_id: str) -> str | None:
        """Get parent ID for a child."""
        return self._child_to_parent.get(child_id)

    def reset(self) -> None:
        """Reset bridge state."""
        self._parent_to_children.clear()
        self._child_to_parent.clear()
        self._subscriptions.clear()
        self.forwarded_events.clear()
        self.subscription_setups.clear()
        self.subscription_cleanups.clear()


@pytest.fixture
def mock_event_bridge_tracking() -> MockEventBridge:
    """Create an event bridge that tracks operations.

    Returns
    -------
    MockEventBridge
        Mock with operation tracking for verification
    """
    return MockEventBridge()
