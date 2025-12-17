"""Mock DebugService fixtures for MCP unit testing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_debug_service() -> MagicMock:
    """Mock DebugService for testing MCP session management.

    Returns
    -------
    MagicMock
        A mock DebugService with common attributes configured:
        - session.started: True
        - session.info: Mock with id, target, language, status, port, pid
        - session.reconnect: Mock method
        - execution.stop: AsyncMock method (called with run_until_complete)
    """
    from aidb import DebugService

    service = MagicMock(spec=DebugService)

    # Configure session sub-object
    service.session = MagicMock()
    service.session.started = True
    service.session.info = MagicMock(
        id="session-123",
        target="test.py",
        language="python",
        status=MagicMock(name="RUNNING"),
        port=5678,
        pid=12345,
    )
    service.session.reconnect = MagicMock()

    # Configure execution sub-object with AsyncMock for stop()
    # since it's called with asyncio.get_event_loop().run_until_complete()
    service.execution = MagicMock()
    service.execution.stop = AsyncMock()

    # Configure variables sub-object (for evaluate)
    service.variables = MagicMock()

    # Configure breakpoints sub-object
    service.breakpoints = MagicMock()

    return service


@pytest.fixture
def mock_debug_service_not_started(mock_debug_service: MagicMock) -> MagicMock:
    """Mock DebugService that hasn't been started.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Base mock debug service fixture

    Returns
    -------
    MagicMock
        A mock DebugService with session.started=False
    """
    mock_debug_service.session.started = False
    return mock_debug_service


@pytest.fixture
def mock_debug_service_no_session_info(mock_debug_service: MagicMock) -> MagicMock:
    """Mock DebugService with no session info.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Base mock debug service fixture

    Returns
    -------
    MagicMock
        A mock DebugService with session.info=None
    """
    mock_debug_service.session.info = None
    return mock_debug_service


@pytest.fixture
def mock_debug_service_stop_fails(mock_debug_service: MagicMock) -> MagicMock:
    """Mock DebugService where stop() raises an exception.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Base mock debug service fixture

    Returns
    -------
    MagicMock
        A mock DebugService where execution.stop() raises RuntimeError
    """
    # AsyncMock needs side_effect set this way for async errors
    mock_debug_service.execution.stop = AsyncMock(
        side_effect=RuntimeError("Stop failed")
    )
    return mock_debug_service


@pytest.fixture
def mock_debug_service_reconnect_fails(mock_debug_service: MagicMock) -> MagicMock:
    """Mock DebugService where reconnect() raises an exception.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Base mock debug service fixture

    Returns
    -------
    MagicMock
        A mock DebugService where session.reconnect() raises RuntimeError
    """
    mock_debug_service.session.reconnect.side_effect = RuntimeError("Reconnect failed")
    return mock_debug_service


__all__ = [
    "mock_debug_service",
    "mock_debug_service_not_started",
    "mock_debug_service_no_session_info",
    "mock_debug_service_stop_fails",
    "mock_debug_service_reconnect_fails",
]
