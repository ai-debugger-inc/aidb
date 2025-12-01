"""Mock port management for unit tests.

Provides mock implementations of PortManager and PortRegistry for testing adapter port
allocation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_port_manager() -> MagicMock:
    """Create a mock PortManager.

    The mock simulates PortManager for testing adapter
    components without actual port allocation.

    Returns
    -------
    MagicMock
        Mock port manager with common methods
    """
    manager = MagicMock()

    # Port allocation
    manager.acquire_port = AsyncMock(return_value=7000)
    manager.release_port = MagicMock(return_value=True)

    # State
    manager.get_port = MagicMock(return_value=7000)
    manager.has_port = MagicMock(return_value=True)

    return manager


@pytest.fixture
def mock_port_manager_no_port() -> MagicMock:
    """Create a mock PortManager with no allocated port.

    Returns
    -------
    MagicMock
        Mock port manager simulating unallocated state
    """
    manager = MagicMock()
    manager.acquire_port = AsyncMock(return_value=7000)
    manager.release_port = MagicMock(return_value=True)
    manager.get_port = MagicMock(return_value=None)
    manager.has_port = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_port_registry() -> MagicMock:
    """Create a mock PortRegistry.

    The mock simulates PortRegistry for testing port
    allocation without actual socket binding.

    Returns
    -------
    MagicMock
        Mock port registry with common methods
    """
    registry = MagicMock()

    # Port allocation counter for unique ports
    port_counter = [7000]

    def get_next_port() -> int:
        port = port_counter[0]
        port_counter[0] += 1
        return port

    # Port management
    registry.acquire_port = AsyncMock(side_effect=lambda: get_next_port())
    registry.release_port = MagicMock(return_value=True)
    registry.release_reserved_port = MagicMock(return_value=True)

    # Queries
    registry.get_port_count = MagicMock(return_value=0)
    registry.is_port_reserved = MagicMock(return_value=False)

    return registry


@pytest.fixture
def mock_port_registry_exhausted() -> MagicMock:
    """Create a mock PortRegistry that fails to allocate.

    Returns
    -------
    MagicMock
        Mock registry that simulates port exhaustion
    """
    from aidb.common.errors import AidbError

    registry = MagicMock()
    registry.acquire_port = AsyncMock(side_effect=AidbError("No available ports"))
    registry.release_port = MagicMock(return_value=True)
    registry.get_port_count = MagicMock(return_value=100)
    return registry


class MockPortRegistry:
    """Port registry mock with tracking.

    Use this when you need to verify port allocation patterns.

    Examples
    --------
    >>> registry = MockPortRegistry()
    >>> port = await registry.acquire_port()
    >>> assert port == 7000
    >>> assert registry.allocated_ports == {7000}
    """

    def __init__(self, start_port: int = 7000) -> None:
        """Initialize the mock registry."""
        self._next_port = start_port
        self.allocated_ports: set[int] = set()
        self.released_ports: set[int] = set()

    async def acquire_port(self) -> int:
        """Allocate a port."""
        port = self._next_port
        self._next_port += 1
        self.allocated_ports.add(port)
        return port

    def release_port(self, port: int) -> bool:
        """Release a port."""
        if port in self.allocated_ports:
            self.allocated_ports.discard(port)
            self.released_ports.add(port)
            return True
        return False

    def release_reserved_port(self, port: int) -> bool:
        """Release a reserved port."""
        return self.release_port(port)

    def get_port_count(self) -> int:
        """Get count of allocated ports."""
        return len(self.allocated_ports)

    def reset(self) -> None:
        """Reset state for test isolation."""
        self.allocated_ports.clear()
        self.released_ports.clear()


@pytest.fixture
def mock_port_registry_tracking() -> MockPortRegistry:
    """Create a port registry that tracks allocations.

    Returns
    -------
    MockPortRegistry
        Mock with allocation tracking for verification
    """
    return MockPortRegistry()
