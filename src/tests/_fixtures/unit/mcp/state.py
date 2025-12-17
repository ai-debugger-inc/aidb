"""Global state reset fixtures for MCP unit testing."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def reset_mcp_session_state() -> Generator[None, None, None]:
    """Reset all MCP global state before and after each test.

    This fixture is auto-used to ensure test isolation for all MCP session tests.
    It clears the global dictionaries and resets the default session ID.

    Yields
    ------
    None
        Control returns to test after state is cleared
    """
    import aidb_mcp.session.manager_core as core
    import aidb_mcp.session.manager_lifecycle as lifecycle
    import aidb_mcp.session.manager_shared as shared
    import aidb_mcp.session.manager_state as state
    from aidb_mcp.session.manager_shared import (
        _DEBUG_SERVICES,
        _DEBUG_SESSIONS,
        _SESSION_CONTEXTS,
    )

    # Clear before test
    _DEBUG_SERVICES.clear()
    _DEBUG_SESSIONS.clear()
    _SESSION_CONTEXTS.clear()
    shared._DEFAULT_SESSION_ID = None
    lifecycle._DEFAULT_SESSION_ID = None
    core._DEFAULT_SESSION_ID = None
    state._DEFAULT_SESSION_ID = None

    yield

    # Clear after test
    _DEBUG_SERVICES.clear()
    _DEBUG_SESSIONS.clear()
    _SESSION_CONTEXTS.clear()
    shared._DEFAULT_SESSION_ID = None
    lifecycle._DEFAULT_SESSION_ID = None
    core._DEFAULT_SESSION_ID = None
    state._DEFAULT_SESSION_ID = None


@pytest.fixture
def populated_session_state(
    mock_debug_service: MagicMock,
    mock_mcp_session_context: MagicMock,
) -> tuple[str, MagicMock, MagicMock]:
    """Populate the global state with a test session.

    Cleanup is handled by the autouse reset_mcp_session_state fixture.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Mock DebugService fixture
    mock_mcp_session_context : MagicMock
        Mock MCPSessionContext fixture

    Returns
    -------
    tuple[str, MagicMock, MagicMock]
        Tuple of (session_id, api, context)
    """
    import aidb_mcp.session.manager_core as core
    import aidb_mcp.session.manager_lifecycle as lifecycle
    import aidb_mcp.session.manager_shared as shared
    import aidb_mcp.session.manager_state as state
    from aidb_mcp.session.manager_shared import (
        _DEBUG_SESSIONS,
        _SESSION_CONTEXTS,
    )

    session_id = "test-session-001"
    _DEBUG_SESSIONS[session_id] = mock_debug_service
    _SESSION_CONTEXTS[session_id] = mock_mcp_session_context
    shared._DEFAULT_SESSION_ID = session_id
    lifecycle._DEFAULT_SESSION_ID = session_id
    core._DEFAULT_SESSION_ID = session_id
    state._DEFAULT_SESSION_ID = session_id

    return session_id, mock_debug_service, mock_mcp_session_context


@pytest.fixture
def populated_session_with_service(
    mock_mcp_session_context: MagicMock,
) -> tuple[str, MagicMock, MagicMock]:
    """Populate the global state with a test session including DebugService.

    Cleanup is handled by the autouse reset_mcp_session_state fixture.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Mock MCPSessionContext fixture

    Returns
    -------
    tuple[str, MagicMock, MagicMock]
        Tuple of (session_id, service, context)
    """
    import aidb_mcp.session.manager_core as core
    import aidb_mcp.session.manager_lifecycle as lifecycle
    import aidb_mcp.session.manager_shared as shared
    import aidb_mcp.session.manager_state as state
    from aidb_mcp.session.manager_shared import _DEBUG_SERVICES, _SESSION_CONTEXTS

    session_id = "test-session-001"

    # Create mock service
    service = MagicMock()
    service.session = MagicMock()
    service.session.started = True
    service.session.id = session_id

    _DEBUG_SERVICES[session_id] = service
    _SESSION_CONTEXTS[session_id] = mock_mcp_session_context
    shared._DEFAULT_SESSION_ID = session_id
    lifecycle._DEFAULT_SESSION_ID = session_id
    core._DEFAULT_SESSION_ID = session_id
    state._DEFAULT_SESSION_ID = session_id

    return session_id, service, mock_mcp_session_context


@pytest.fixture
def multiple_sessions_state(
    mock_debug_service: MagicMock,
    mock_mcp_session_context: MagicMock,
) -> list[tuple[str, MagicMock, MagicMock]]:
    """Populate the global state with multiple test sessions.

    Cleanup is handled by the autouse reset_mcp_session_state fixture.

    Parameters
    ----------
    mock_debug_service : MagicMock
        Mock DebugService fixture (used as template)
    mock_mcp_session_context : MagicMock
        Mock MCPSessionContext fixture (used as template)

    Returns
    -------
    list[tuple[str, MagicMock, MagicMock]]
        List of tuples (session_id, service, context) for each session
    """
    import aidb_mcp.session.manager_core as core
    import aidb_mcp.session.manager_lifecycle as lifecycle
    import aidb_mcp.session.manager_shared as shared
    import aidb_mcp.session.manager_state as state
    from aidb_mcp.session.manager_shared import (
        _DEBUG_SESSIONS,
        _SESSION_CONTEXTS,
    )

    sessions = []
    for i in range(3):
        session_id = f"test-session-{i:03d}"
        # Create fresh mocks for each session matching DebugService structure
        service = MagicMock()
        service.session = MagicMock()
        service.session.started = True
        service.session.info = MagicMock(id=session_id)
        service.execution = MagicMock()
        # AsyncMock for stop() since it's called with run_until_complete()
        service.execution.stop = AsyncMock()

        context = MagicMock()
        context.breakpoints_set = []
        context.variables_tracked = {}
        context.session_started = True
        context.session_info = MagicMock(id=session_id)

        _DEBUG_SESSIONS[session_id] = service
        _SESSION_CONTEXTS[session_id] = context
        sessions.append((session_id, service, context))

    # Set first session as default (all modules)
    shared._DEFAULT_SESSION_ID = sessions[0][0]
    lifecycle._DEFAULT_SESSION_ID = sessions[0][0]
    core._DEFAULT_SESSION_ID = sessions[0][0]
    state._DEFAULT_SESSION_ID = sessions[0][0]

    return sessions


@pytest.fixture
def multiple_sessions_with_services(
    mock_mcp_session_context: MagicMock,
) -> list[tuple[str, MagicMock, MagicMock]]:
    """Populate the global state with multiple test sessions including DebugService.

    Cleanup is handled by the autouse reset_mcp_session_state fixture.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Mock MCPSessionContext fixture (used as template)

    Returns
    -------
    list[tuple[str, MagicMock, MagicMock]]
        List of tuples (session_id, service, context) for each session
    """
    import aidb_mcp.session.manager_core as core
    import aidb_mcp.session.manager_lifecycle as lifecycle
    import aidb_mcp.session.manager_shared as shared
    import aidb_mcp.session.manager_state as state
    from aidb_mcp.session.manager_shared import _DEBUG_SERVICES, _SESSION_CONTEXTS

    sessions = []
    for i in range(3):
        session_id = f"test-session-{i:03d}"

        # Create mock service
        service = MagicMock()
        service.session = MagicMock()
        service.session.started = True
        service.session.id = session_id

        context = MagicMock()
        context.breakpoints_set = []
        context.variables_tracked = {}
        context.session_started = True
        context.session_info = MagicMock(id=session_id)

        _DEBUG_SERVICES[session_id] = service
        _SESSION_CONTEXTS[session_id] = context
        sessions.append((session_id, service, context))

    # Set first session as default (all modules)
    shared._DEFAULT_SESSION_ID = sessions[0][0]
    lifecycle._DEFAULT_SESSION_ID = sessions[0][0]
    core._DEFAULT_SESSION_ID = sessions[0][0]
    state._DEFAULT_SESSION_ID = sessions[0][0]

    return sessions


@pytest.fixture
def mock_logging_functions():
    """Mock the aidb_logging functions used in session management.

    Yields
    ------
    dict[str, MagicMock]
        Dictionary with mocks for set_session_id, clear_session_id, get_session_id
    """
    with (
        patch("aidb_mcp.session.manager_core.set_session_id") as mock_set,
        patch("aidb_mcp.session.manager_lifecycle.clear_session_id") as mock_clear,
        patch(
            "aidb_mcp.session.manager_lifecycle.get_session_id_from_context"
        ) as mock_get,
    ):
        yield {
            "set_session_id": mock_set,
            "clear_session_id": mock_clear,
            "get_session_id": mock_get,
        }


__all__ = [
    "reset_mcp_session_state",
    "populated_session_state",
    "populated_session_with_service",
    "multiple_sessions_state",
    "multiple_sessions_with_services",
    "mock_logging_functions",
]
