"""Mock MCPSessionContext fixtures for MCP unit testing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_mcp_session_context() -> MagicMock:
    """Mock MCPSessionContext for testing MCP session management.

    Returns
    -------
    MagicMock
        A mock MCPSessionContext with common attributes configured:
        - breakpoints_set: Empty list (mutable)
        - variables_tracked: Empty dict (mutable)
        - session_started: True
        - session_info: Mock with id
    """
    from aidb_mcp.session.context import MCPSessionContext

    context = MagicMock(spec=MCPSessionContext)
    # Use actual mutable containers for clear() testing
    context.breakpoints_set = []
    context.variables_tracked = {}
    context.session_started = True
    context.session_info = MagicMock(id="session-123")
    return context


@pytest.fixture
def mock_mcp_session_context_not_started(
    mock_mcp_session_context: MagicMock,
) -> MagicMock:
    """Mock MCPSessionContext that hasn't been started.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Base mock session context fixture

    Returns
    -------
    MagicMock
        A mock MCPSessionContext with session_started=False
    """
    mock_mcp_session_context.session_started = False
    return mock_mcp_session_context


@pytest.fixture
def mock_mcp_session_context_no_session_info(
    mock_mcp_session_context: MagicMock,
) -> MagicMock:
    """Mock MCPSessionContext with no session_info.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Base mock session context fixture

    Returns
    -------
    MagicMock
        A mock MCPSessionContext with session_info=None
    """
    mock_mcp_session_context.session_info = None
    return mock_mcp_session_context


@pytest.fixture
def mock_mcp_session_context_with_breakpoints(
    mock_mcp_session_context: MagicMock,
) -> MagicMock:
    """Mock MCPSessionContext with some breakpoints set.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Base mock session context fixture

    Returns
    -------
    MagicMock
        A mock MCPSessionContext with breakpoints_set populated
    """
    mock_mcp_session_context.breakpoints_set = [
        MagicMock(file="test.py", line=10),
        MagicMock(file="test.py", line=20),
    ]
    return mock_mcp_session_context


@pytest.fixture
def mock_mcp_session_context_with_variables(
    mock_mcp_session_context: MagicMock,
) -> MagicMock:
    """Mock MCPSessionContext with some tracked variables.

    Parameters
    ----------
    mock_mcp_session_context : MagicMock
        Base mock session context fixture

    Returns
    -------
    MagicMock
        A mock MCPSessionContext with variables_tracked populated
    """
    mock_mcp_session_context.variables_tracked = {
        "x": [MagicMock(value=10)],
        "y": [MagicMock(value=20)],
    }
    return mock_mcp_session_context


__all__ = [
    "mock_mcp_session_context",
    "mock_mcp_session_context_not_started",
    "mock_mcp_session_context_no_session_info",
    "mock_mcp_session_context_with_breakpoints",
    "mock_mcp_session_context_with_variables",
]
