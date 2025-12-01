"""Mock DAP message receiver for unit tests.

Provides mock implementations of MessageReceiver for testing components that depend on
background message receiving.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_receiver() -> MagicMock:
    """Create a mock DAP message receiver.

    The mock simulates the MessageReceiver interface for testing
    components that depend on background message processing.

    Returns
    -------
    MagicMock
        Mock receiver with async start/stop methods
    """
    receiver = MagicMock()

    # Lifecycle methods
    receiver.start = AsyncMock()
    receiver.stop = AsyncMock()

    # State
    receiver._running = False
    receiver._stopping = False

    # Property for running state
    type(receiver).is_running = property(lambda self: self._running)

    return receiver


@pytest.fixture
def mock_receiver_running() -> MagicMock:
    """Create a mock receiver in running state.

    Returns
    -------
    MagicMock
        Mock receiver that simulates active state
    """
    receiver = MagicMock()
    receiver.start = AsyncMock()
    receiver.stop = AsyncMock()
    receiver._running = True
    receiver._stopping = False
    return receiver


@pytest.fixture
def mock_receiver_error() -> MagicMock:
    """Create a mock receiver that fails on start.

    Returns
    -------
    MagicMock
        Mock receiver that raises on start
    """
    receiver = MagicMock()
    receiver.start = AsyncMock(side_effect=RuntimeError("Receiver start failed"))
    receiver.stop = AsyncMock()
    receiver._running = False
    return receiver
