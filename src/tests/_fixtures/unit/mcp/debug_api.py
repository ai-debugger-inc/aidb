"""Mock DebugAPI fixtures for MCP unit testing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_debug_api() -> MagicMock:
    """Mock DebugAPI for testing MCP session management.

    Returns
    -------
    MagicMock
        A mock DebugAPI with common attributes configured:
        - started: True
        - session_info: Mock with id, target, language, status, port, pid
        - session: Mock with reconnect method
        - stop: Mock method
    """
    from aidb import DebugAPI

    api = MagicMock(spec=DebugAPI)
    api.started = True
    api.session_info = MagicMock(
        id="session-123",
        target="test.py",
        language="python",
        status=MagicMock(name="RUNNING"),
        port=5678,
        pid=12345,
    )
    api.session = MagicMock()
    api.session.reconnect = MagicMock()
    api.stop = MagicMock()
    return api


@pytest.fixture
def mock_debug_api_not_started(mock_debug_api: MagicMock) -> MagicMock:
    """Mock DebugAPI that hasn't been started.

    Parameters
    ----------
    mock_debug_api : MagicMock
        Base mock debug API fixture

    Returns
    -------
    MagicMock
        A mock DebugAPI with started=False
    """
    mock_debug_api.started = False
    return mock_debug_api


@pytest.fixture
def mock_debug_api_no_session_info(mock_debug_api: MagicMock) -> MagicMock:
    """Mock DebugAPI with no session_info.

    Parameters
    ----------
    mock_debug_api : MagicMock
        Base mock debug API fixture

    Returns
    -------
    MagicMock
        A mock DebugAPI with session_info=None
    """
    mock_debug_api.session_info = None
    return mock_debug_api


@pytest.fixture
def mock_debug_api_stop_fails(mock_debug_api: MagicMock) -> MagicMock:
    """Mock DebugAPI where stop() raises an exception.

    Parameters
    ----------
    mock_debug_api : MagicMock
        Base mock debug API fixture

    Returns
    -------
    MagicMock
        A mock DebugAPI where stop() raises RuntimeError
    """
    mock_debug_api.stop.side_effect = RuntimeError("Stop failed")
    return mock_debug_api


@pytest.fixture
def mock_debug_api_reconnect_fails(mock_debug_api: MagicMock) -> MagicMock:
    """Mock DebugAPI where reconnect() raises an exception.

    Parameters
    ----------
    mock_debug_api : MagicMock
        Base mock debug API fixture

    Returns
    -------
    MagicMock
        A mock DebugAPI where session.reconnect() raises RuntimeError
    """
    mock_debug_api.session.reconnect.side_effect = RuntimeError("Reconnect failed")
    return mock_debug_api


__all__ = [
    "mock_debug_api",
    "mock_debug_api_not_started",
    "mock_debug_api_no_session_info",
    "mock_debug_api_stop_fails",
    "mock_debug_api_reconnect_fails",
]
