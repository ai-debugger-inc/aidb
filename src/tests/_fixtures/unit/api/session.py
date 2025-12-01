"""Mock session fixtures for API unit tests.

Provides mock Session and SessionManager objects for testing the API layer without
requiring actual debug adapter connections.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock Session for API tests.

    Returns
    -------
    MagicMock
        Mock session with id, language, is_child, started, and config attributes
    """
    session = MagicMock()
    session.id = "test-session-id"
    session.language = "python"
    session.is_child = False
    session.started = False
    session._attach_params = None
    session._launch_config = None
    return session


@pytest.fixture
def mock_session_manager(mock_ctx: MagicMock) -> MagicMock:
    """Mock SessionManager for API tests.

    Parameters
    ----------
    mock_ctx : MagicMock
        Mock context fixture (from shared fixtures)

    Returns
    -------
    MagicMock
        Mock session manager with spec matching SessionManager
    """
    from aidb.api.session_manager import SessionManager

    manager = MagicMock(spec=SessionManager)
    manager.ctx = mock_ctx
    manager._active_sessions = 0
    manager._current_session = None
    manager.active_sessions_count = 0
    manager.current_session = None
    return manager
