"""Mock child session manager for unit tests.

Provides mock implementations of ChildSessionManager for testing parent-child session
creation and management.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_child_session_manager() -> MagicMock:
    """Create a mock ChildSessionManager.

    The mock simulates child session creation for testing
    multi-session scenarios like JS/TS debugging.

    Returns
    -------
    MagicMock
        Mock child manager with async create methods
    """
    manager = MagicMock()

    # Async methods
    manager.create_child_session = AsyncMock(return_value="child-session-1")

    # Event bridge reference
    manager.event_bridge = MagicMock()

    # Registry reference
    manager.registry = MagicMock()

    # Callback
    manager._on_child_created_callback = None

    return manager


@pytest.fixture
def mock_child_session_manager_with_child() -> MagicMock:
    """Create a mock manager that returns a pre-configured child.

    Returns
    -------
    MagicMock
        Mock manager with child session creation configured
    """
    manager = MagicMock()

    # Create mock child session
    mock_child = MagicMock()
    mock_child.id = "child-session-1"
    mock_child.language = "javascript"
    mock_child.is_child = True
    mock_child.parent_id = "parent-session-1"

    manager.create_child_session = AsyncMock(return_value=mock_child.id)
    manager._last_created_child = mock_child

    manager.event_bridge = MagicMock()
    manager.registry = MagicMock()

    return manager


@pytest.fixture
def mock_child_session_manager_failing() -> MagicMock:
    """Create a mock manager that fails to create children.

    Returns
    -------
    MagicMock
        Mock manager that raises on child creation
    """
    manager = MagicMock()

    manager.create_child_session = AsyncMock(
        side_effect=RuntimeError("Child session creation failed")
    )
    manager.event_bridge = MagicMock()
    manager.registry = MagicMock()

    return manager


class MockChildSessionManager:
    """Child session manager mock with tracking.

    Use this when you need to verify child session creation.

    Examples
    --------
    >>> manager = MockChildSessionManager()
    >>> child_id = await manager.create_child_session(parent, config)
    >>> assert len(manager.created_children) == 1
    """

    def __init__(self) -> None:
        """Initialize the mock manager."""
        self.created_children: list[dict[str, Any]] = []
        self.event_bridge = MagicMock()
        self.registry = MagicMock()
        self._child_counter = 0
        self._on_child_created_callback = None

    async def create_child_session(
        self,
        parent: Any,
        config: dict[str, Any],
    ) -> str:
        """Create a mock child session."""
        self._child_counter += 1
        child_id = f"child-{self._child_counter}"

        self.created_children.append(
            {
                "child_id": child_id,
                "parent_id": parent.id if hasattr(parent, "id") else str(parent),
                "config": config,
            }
        )

        if self._on_child_created_callback:
            mock_child = MagicMock()
            mock_child.id = child_id
            self._on_child_created_callback(mock_child)

        return child_id

    def set_callback(self, callback) -> None:
        """Set the child created callback."""
        self._on_child_created_callback = callback

    def reset(self) -> None:
        """Reset manager state."""
        self.created_children.clear()
        self._child_counter = 0


@pytest.fixture
def mock_child_session_manager_tracking() -> MockChildSessionManager:
    """Create a child manager that tracks creations.

    Returns
    -------
    MockChildSessionManager
        Mock with creation tracking for verification
    """
    return MockChildSessionManager()
