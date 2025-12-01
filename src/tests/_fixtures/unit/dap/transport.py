"""Mock DAP transport for unit tests.

Provides mock implementations of DAPTransport for testing components that depend on
transport without actual socket I/O.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_transport() -> MagicMock:
    """Create a mock DAP transport.

    The mock simulates the DAPTransport interface with configurable
    behavior for testing transport-dependent components.

    Returns
    -------
    MagicMock
        Mock transport with async connect/disconnect and send methods
    """
    transport = MagicMock()

    # Connection methods
    transport.connect = AsyncMock()
    transport.disconnect = AsyncMock()

    # Connection state - use MagicMock for method that returns bool
    transport.is_connected = MagicMock(return_value=True)

    # Message sending
    transport.send_message = AsyncMock()

    # Message receiving (for when receiver needs raw message)
    transport.receive_message = AsyncMock(return_value=None)

    # Host/port info
    transport._host = "127.0.0.1"
    transport._port = 7000

    return transport


@pytest.fixture
def mock_transport_disconnected() -> MagicMock:
    """Create a mock transport in disconnected state.

    Returns
    -------
    MagicMock
        Mock transport that simulates disconnected state
    """
    transport = MagicMock()
    transport.connect = AsyncMock()
    transport.disconnect = AsyncMock()
    transport.is_connected = MagicMock(return_value=False)
    transport.send_message = AsyncMock()
    transport._host = "127.0.0.1"
    transport._port = 7000
    return transport


@pytest.fixture
def mock_transport_failing() -> MagicMock:
    """Create a mock transport that fails on connect.

    Returns
    -------
    MagicMock
        Mock transport that raises on connect
    """
    from aidb.common.errors import DebugConnectionError

    transport = MagicMock()
    transport.connect = AsyncMock(
        side_effect=DebugConnectionError("Connection refused")
    )
    transport.disconnect = AsyncMock()
    transport.is_connected = MagicMock(return_value=False)
    transport._host = "127.0.0.1"
    transport._port = 7000
    return transport


class MockTransportRecorder:
    """Transport mock that records sent messages.

    Use this when you need to verify what messages were sent
    through the transport layer.

    Examples
    --------
    >>> transport = MockTransportRecorder()
    >>> await transport.send_message({"command": "initialize"})
    >>> assert len(transport.sent_messages) == 1
    """

    def __init__(self) -> None:
        """Initialize the recorder."""
        self.sent_messages: list[dict[str, Any]] = []
        self._connected = True
        self._host = "127.0.0.1"
        self._port = 7000

    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected

    async def connect(self, timeout: float = 5.0) -> None:
        """Simulate connection."""
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def send_message(self, message: dict[str, Any]) -> None:
        """Record sent message."""
        self.sent_messages.append(message)

    def clear(self) -> None:
        """Clear recorded messages."""
        self.sent_messages.clear()

    def get_messages_by_command(self, command: str) -> list[dict[str, Any]]:
        """Get all messages for a specific command."""
        return [m for m in self.sent_messages if m.get("command") == command]


@pytest.fixture
def mock_transport_recorder() -> MockTransportRecorder:
    """Create a transport that records all sent messages.

    Returns
    -------
    MockTransportRecorder
        Transport mock that stores sent messages for verification
    """
    return MockTransportRecorder()
