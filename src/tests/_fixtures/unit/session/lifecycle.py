"""Mock session lifecycle for unit tests.

Provides mock implementations of SessionLifecycle for testing components that depend on
session start/stop operations.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_session_lifecycle() -> MagicMock:
    """Create a mock session lifecycle manager.

    The mock simulates SessionLifecycleMixin operations
    for testing components that depend on lifecycle management.

    Returns
    -------
    MagicMock
        Mock lifecycle with async start/stop methods
    """
    lifecycle = MagicMock()

    # Lifecycle methods
    lifecycle.start = AsyncMock()
    lifecycle.stop = AsyncMock()
    lifecycle.restart = AsyncMock()

    # State queries
    lifecycle.is_running = MagicMock(return_value=False)
    lifecycle.is_stopping = MagicMock(return_value=False)

    return lifecycle


@pytest.fixture
def mock_session_lifecycle_running() -> MagicMock:
    """Create a mock lifecycle in running state.

    Returns
    -------
    MagicMock
        Mock lifecycle simulating active session
    """
    lifecycle = MagicMock()
    lifecycle.start = AsyncMock()
    lifecycle.stop = AsyncMock()
    lifecycle.restart = AsyncMock()
    lifecycle.is_running = MagicMock(return_value=True)
    lifecycle.is_stopping = MagicMock(return_value=False)
    return lifecycle


@pytest.fixture
def mock_session_lifecycle_start_fails() -> MagicMock:
    """Create a mock lifecycle that fails on start.

    Returns
    -------
    MagicMock
        Mock lifecycle that raises on start
    """
    from aidb.common.errors import AidbError

    lifecycle = MagicMock()
    lifecycle.start = AsyncMock(side_effect=AidbError("Start failed"))
    lifecycle.stop = AsyncMock()
    lifecycle.is_running = MagicMock(return_value=False)
    lifecycle.is_stopping = MagicMock(return_value=False)
    return lifecycle
