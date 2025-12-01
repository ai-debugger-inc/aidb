"""Mock DAP client for session unit tests.

Provides lightweight mock DAP client for testing session components without full DAP
client infrastructure.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.dap.protocol.types import Capabilities


@pytest.fixture
def mock_dap_client_for_session() -> MagicMock:
    """Create a lightweight DAP client mock for session tests.

    This mock provides the minimal interface needed by session
    components without the full DAP client complexity.

    Returns
    -------
    MagicMock
        Mock DAP client with common methods
    """
    client = MagicMock()

    # Connection state
    client.is_connected = True

    # Request sending
    client.send_request = AsyncMock()

    # Capabilities
    client.capabilities = Capabilities(
        supportsConfigurationDoneRequest=True,
        supportsConditionalBreakpoints=True,
    )

    # Event processor access
    client.event_processor = MagicMock()
    client.event_processor.subscribe = MagicMock()
    client.event_processor.unsubscribe = MagicMock()

    # State
    client.state = MagicMock()
    client.state.is_paused = False
    client.state.thread_id = 1
    client.state.frame_id = 0

    return client


@pytest.fixture
def mock_dap_client_paused() -> MagicMock:
    """Create a DAP client mock in paused state.

    Returns
    -------
    MagicMock
        Mock DAP client simulating paused debuggee
    """
    client = MagicMock()
    client.is_connected = True
    client.send_request = AsyncMock()
    client.capabilities = Capabilities(supportsConfigurationDoneRequest=True)
    client.event_processor = MagicMock()
    client.state = MagicMock()
    client.state.is_paused = True
    client.state.thread_id = 1
    client.state.frame_id = 0
    return client


@pytest.fixture
def mock_dap_client_disconnected() -> MagicMock:
    """Create a DAP client mock in disconnected state.

    Returns
    -------
    MagicMock
        Mock DAP client simulating disconnected state
    """
    from aidb.common.errors import DebugConnectionError

    client = MagicMock()
    client.is_connected = False
    client.send_request = AsyncMock(side_effect=DebugConnectionError("Not connected"))
    client.capabilities = None
    return client


class MockDAPClientResponder:
    """DAP client mock with configurable responses.

    Use this when you need to set up specific response sequences
    for testing request/response flows.

    Examples
    --------
    >>> client = MockDAPClientResponder()
    >>> client.queue_response("initialize", {"supportsConfigurationDoneRequest": True})
    >>> response = await client.send_request(init_request)
    """

    def __init__(self) -> None:
        """Initialize the mock client."""
        self.is_connected = True
        self._responses: dict[str, list[dict[str, Any]]] = {}
        self._requests: list[dict[str, Any]] = []
        self.capabilities = Capabilities(supportsConfigurationDoneRequest=True)

    def queue_response(self, command: str, body: dict[str, Any]) -> None:
        """Queue a response for a specific command."""
        if command not in self._responses:
            self._responses[command] = []
        self._responses[command].append(body)

    async def send_request(self, request: Any) -> dict[str, Any]:
        """Send a request and return queued response."""
        command = request.command if hasattr(request, "command") else str(request)
        self._requests.append({"command": command, "request": request})

        if command in self._responses and self._responses[command]:
            body = self._responses[command].pop(0)
            return {
                "success": True,
                "command": command,
                "body": body,
            }

        return {
            "success": True,
            "command": command,
            "body": {},
        }

    def get_requests(self, command: str | None = None) -> list[dict[str, Any]]:
        """Get recorded requests, optionally filtered by command."""
        if command is None:
            return self._requests
        return [r for r in self._requests if r["command"] == command]


@pytest.fixture
def mock_dap_client_responder() -> MockDAPClientResponder:
    """Create a DAP client that returns queued responses.

    Returns
    -------
    MockDAPClientResponder
        Mock with configurable response sequences
    """
    return MockDAPClientResponder()
