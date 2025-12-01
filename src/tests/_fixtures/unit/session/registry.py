"""Mock session registry for unit tests.

Provides mock implementations of SessionRegistry and ChildSessionRegistry for testing
session registration and tracking.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_session_registry() -> MagicMock:
    """Create a mock SessionRegistry.

    The mock simulates SessionRegistry for testing session
    management without the singleton infrastructure.

    Returns
    -------
    MagicMock
        Mock session registry with common methods
    """
    registry = MagicMock()

    # Internal storage
    registry._sessions = {}

    # Core methods
    registry.register_session = MagicMock()
    registry.unregister_session = MagicMock()
    registry.get_session = MagicMock(return_value=None)
    registry.get_all_sessions = MagicMock(return_value=[])
    registry.get_session_count = MagicMock(return_value=0)

    # Child management delegation
    registry.register_child = MagicMock()
    registry.get_children = MagicMock(return_value=[])
    registry.get_parent = MagicMock(return_value=None)

    # Cleanup delegation
    registry.cleanup_session = MagicMock()
    registry.cleanup_all = MagicMock()

    return registry


@pytest.fixture
def mock_session_registry_with_session() -> MagicMock:
    """Create a mock registry with a pre-registered session.

    Returns
    -------
    MagicMock
        Mock registry with one session registered
    """
    registry = MagicMock()

    # Create a mock session
    mock_session = MagicMock()
    mock_session.id = "test-session-1"
    mock_session.language = "python"
    mock_session.is_child = False

    registry._sessions = {"test-session-1": mock_session}
    registry.get_session = MagicMock(
        side_effect=lambda sid: registry._sessions.get(sid)
    )
    registry.get_all_sessions = MagicMock(
        return_value=list(registry._sessions.values())
    )
    registry.get_session_count = MagicMock(return_value=1)

    return registry


@pytest.fixture
def mock_child_session_registry() -> MagicMock:
    """Create a mock ChildSessionRegistry.

    The mock simulates parent-child relationship tracking
    for testing multi-session scenarios (e.g., JS/TS debugging).

    Returns
    -------
    MagicMock
        Mock child registry with relationship methods
    """
    registry = MagicMock()

    # Internal storage
    registry._parent_to_children = {}
    registry._child_to_parent = {}

    # Relationship methods
    registry.register_child = MagicMock()
    registry.unregister_child = MagicMock()
    registry.get_children = MagicMock(return_value=[])
    registry.get_parent_id = MagicMock(return_value=None)
    registry.is_child = MagicMock(return_value=False)
    registry.has_children = MagicMock(return_value=False)

    return registry


class MockSessionRegistry:
    """Session registry mock with actual storage.

    Use this when you need to verify session registration patterns.

    Examples
    --------
    >>> registry = MockSessionRegistry()
    >>> registry.register_session(mock_session)
    >>> assert registry.get_session("session-1") is mock_session
    """

    def __init__(self) -> None:
        """Initialize the mock registry."""
        self._sessions: dict[str, Any] = {}
        self._parent_to_children: dict[str, set[str]] = {}
        self._child_to_parent: dict[str, str] = {}

    def register_session(self, session: Any) -> None:
        """Register a session."""
        self._sessions[session.id] = session

    def unregister_session(self, session_id: str) -> None:
        """Unregister a session."""
        self._sessions.pop(session_id, None)

    def get_session(self, session_id: str) -> Any | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[Any]:
        """Get all registered sessions."""
        return list(self._sessions.values())

    def get_session_count(self) -> int:
        """Get count of registered sessions."""
        return len(self._sessions)

    def register_child(self, parent_id: str, child_id: str) -> None:
        """Register a parent-child relationship."""
        if parent_id not in self._parent_to_children:
            self._parent_to_children[parent_id] = set()
        self._parent_to_children[parent_id].add(child_id)
        self._child_to_parent[child_id] = parent_id

    def get_children(self, parent_id: str) -> list[str]:
        """Get child session IDs for a parent."""
        return list(self._parent_to_children.get(parent_id, set()))

    def get_parent_id(self, child_id: str) -> str | None:
        """Get parent ID for a child session."""
        return self._child_to_parent.get(child_id)

    def reset(self) -> None:
        """Reset registry state."""
        self._sessions.clear()
        self._parent_to_children.clear()
        self._child_to_parent.clear()


@pytest.fixture
def mock_session_registry_full() -> MockSessionRegistry:
    """Create a full-featured mock session registry.

    Returns
    -------
    MockSessionRegistry
        Mock with actual storage for verification
    """
    return MockSessionRegistry()
