"""Mock session state for unit tests.

Provides mock implementations of SessionState for testing components that depend on
session state tracking.
"""

from unittest.mock import MagicMock

import pytest

from aidb.models import SessionStatus


@pytest.fixture
def mock_session_state() -> MagicMock:
    """Create a mock session state manager.

    The mock simulates SessionState with configurable status
    and initialization states.

    Returns
    -------
    MagicMock
        Mock session state with common methods and properties
    """
    state = MagicMock()

    # State properties
    state._error = None
    state._initialized = False

    # Methods
    state.set_error = MagicMock()
    state.clear_error = MagicMock()
    state.set_initialized = MagicMock()
    state.is_initialized = MagicMock(return_value=False)
    state.has_error = MagicMock(return_value=False)
    state.get_error = MagicMock(return_value=None)
    state.get_status = MagicMock(return_value=SessionStatus.STARTING)

    return state


@pytest.fixture
def mock_session_state_running() -> MagicMock:
    """Create a mock session state in running state.

    Returns
    -------
    MagicMock
        Mock session state simulating active session
    """
    state = MagicMock()
    state._error = None
    state._initialized = True
    state.is_initialized = MagicMock(return_value=True)
    state.has_error = MagicMock(return_value=False)
    state.get_error = MagicMock(return_value=None)
    state.get_status = MagicMock(return_value=SessionStatus.RUNNING)
    return state


@pytest.fixture
def mock_session_state_paused() -> MagicMock:
    """Create a mock session state in paused state.

    Returns
    -------
    MagicMock
        Mock session state simulating paused session
    """
    state = MagicMock()
    state._error = None
    state._initialized = True
    state.is_initialized = MagicMock(return_value=True)
    state.has_error = MagicMock(return_value=False)
    state.get_error = MagicMock(return_value=None)
    state.get_status = MagicMock(return_value=SessionStatus.PAUSED)
    return state


@pytest.fixture
def mock_session_state_error() -> MagicMock:
    """Create a mock session state in error state.

    Returns
    -------
    MagicMock
        Mock session state simulating error condition
    """
    state = MagicMock()
    error = RuntimeError("Session error")
    state._error = error
    state._initialized = False
    state.is_initialized = MagicMock(return_value=False)
    state.has_error = MagicMock(return_value=True)
    state.get_error = MagicMock(return_value=error)
    state.get_status = MagicMock(return_value=SessionStatus.FAILED)
    return state
