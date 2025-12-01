"""Session component mocks for unit testing.

Provides mock implementations of session components for testing at the component level
rather than full session integration.
"""

from tests._fixtures.unit.session.child_manager import (
    MockChildSessionManager,
    mock_child_session_manager,
    mock_child_session_manager_failing,
    mock_child_session_manager_tracking,
    mock_child_session_manager_with_child,
)
from tests._fixtures.unit.session.client import mock_dap_client_for_session
from tests._fixtures.unit.session.event_bridge import (
    MockEventBridge,
    mock_event_bridge,
    mock_event_bridge_tracking,
    mock_event_bridge_with_children,
)
from tests._fixtures.unit.session.lifecycle import mock_session_lifecycle
from tests._fixtures.unit.session.registry import (
    MockSessionRegistry,
    mock_child_session_registry,
    mock_session_registry,
    mock_session_registry_full,
    mock_session_registry_with_session,
)
from tests._fixtures.unit.session.state import mock_session_state

__all__ = [
    # State and lifecycle
    "mock_session_state",
    "mock_session_lifecycle",
    "mock_dap_client_for_session",
    # Registry mocks
    "mock_session_registry",
    "mock_session_registry_with_session",
    "mock_session_registry_full",
    "mock_child_session_registry",
    "MockSessionRegistry",
    # Child manager mocks
    "mock_child_session_manager",
    "mock_child_session_manager_with_child",
    "mock_child_session_manager_failing",
    "mock_child_session_manager_tracking",
    "MockChildSessionManager",
    # Event bridge mocks
    "mock_event_bridge",
    "mock_event_bridge_with_children",
    "mock_event_bridge_tracking",
    "MockEventBridge",
]
