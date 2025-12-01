"""Unit tests for context handler state synchronization."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from aidb.models import SessionStatus
from aidb_mcp.core.constants import ConnectionStatus, ExecutionState
from aidb_mcp.handlers.context.handler import (
    _get_session_execution_state,
    handle_context,
)
from aidb_mcp.session.context import MCPSessionContext


class TestSessionExecutionState:
    """Test _get_session_execution_state function."""

    def test_returns_terminated_when_no_api(self):
        """Should return TERMINATED when debug_api is None."""
        state, is_paused = _get_session_execution_state(None)
        assert state == ExecutionState.TERMINATED.value
        assert is_paused is False

    def test_returns_terminated_when_not_started(self):
        """Should return TERMINATED when session not started."""
        debug_api = Mock()
        debug_api.started = False

        state, is_paused = _get_session_execution_state(debug_api)
        assert state == ExecutionState.TERMINATED.value
        assert is_paused is False

    def test_returns_terminated_when_status_is_terminated(self):
        """Should return TERMINATED when session.status is TERMINATED."""
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.TERMINATED

        state, is_paused = _get_session_execution_state(debug_api)
        assert state == ExecutionState.TERMINATED.value
        assert is_paused is False

    def test_returns_terminated_when_status_is_error(self):
        """Should return TERMINATED when session.status is ERROR."""
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.ERROR

        state, is_paused = _get_session_execution_state(debug_api)
        assert state == ExecutionState.TERMINATED.value
        assert is_paused is False

    def test_returns_paused_when_status_is_paused(self):
        """Should return PAUSED when session.status is PAUSED."""
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.PAUSED
        debug_api.get_active_session.return_value = debug_api.session

        state, is_paused = _get_session_execution_state(debug_api)
        assert state == ExecutionState.PAUSED.value
        assert is_paused is True

    def test_returns_running_when_status_is_running(self):
        """Should return RUNNING when session.status is RUNNING."""
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.RUNNING
        debug_api.get_active_session.return_value = debug_api.session

        state, is_paused = _get_session_execution_state(debug_api)
        assert state == ExecutionState.RUNNING.value
        assert is_paused is False


@pytest.mark.asyncio
class TestHandleContext:
    """Test handle_context function with state synchronization."""

    async def test_context_returns_terminated_when_session_terminated(self):
        """Should return execution_state=terminated when session terminates."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.TERMINATED
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"

        session_context = MCPSessionContext()
        session_context.session_started = True

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Verify response
        assert result["success"] is True
        context_data = result["data"]["context"]

        # Check execution state
        assert context_data["execution_state"] == ExecutionState.TERMINATED.value
        # Check connection status is inactive for terminated sessions
        assert context_data["status"] == ConnectionStatus.INACTIVE.value

    async def test_context_returns_paused_when_session_paused(self):
        """Should return execution_state=paused when session is paused."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.PAUSED
        debug_api.session.dap = Mock()
        debug_api.session.dap.is_stopped = True
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"
        debug_api.get_active_session.return_value = debug_api.session

        # Mock introspection for paused state
        debug_api.introspection = Mock()
        debug_api.introspection.callstack = AsyncMock()
        debug_api.introspection.callstack.return_value = Mock(frames=[])

        session_context = MCPSessionContext()
        session_context.session_started = True

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Verify response
        assert result["success"] is True
        context_data = result["data"]["context"]

        # Check execution state
        assert context_data["execution_state"] == ExecutionState.PAUSED.value
        # Check connection status is active for paused sessions
        assert context_data["status"] == ConnectionStatus.ACTIVE.value

    async def test_context_returns_running_when_session_running(self):
        """Should return execution_state=running when session is running."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.RUNNING
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"
        debug_api.get_active_session.return_value = debug_api.session

        session_context = MCPSessionContext()
        session_context.session_started = True

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Verify response
        assert result["success"] is True
        context_data = result["data"]["context"]

        # Check execution state
        assert context_data["execution_state"] == ExecutionState.RUNNING.value
        # Check connection status is active for running sessions
        assert context_data["status"] == ConnectionStatus.ACTIVE.value

    async def test_breakpoints_marked_inactive_when_session_terminated(self):
        """Should mark breakpoints as inactive when session is terminated."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.TERMINATED
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"
        debug_api.get_active_session.return_value = debug_api.session

        session_context = MCPSessionContext()
        session_context.session_started = True
        session_context.breakpoints_set = [
            {"file": "test.py", "line": 10, "location": "test.py:10"},
            {"file": "test.py", "line": 20, "location": "test.py:20"},
        ]

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Verify response
        assert result["success"] is True
        context_data = result["data"]["context"]

        # Check breakpoints are marked inactive
        assert context_data["breakpoints"]["status"] == "inactive"
        assert context_data["breakpoints"]["count"] == 2
        assert len(context_data["breakpoints"]["active"]) == 2

    async def test_breakpoints_marked_active_when_session_running(self):
        """Should mark breakpoints as active when session is running."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.RUNNING
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"
        debug_api.get_active_session.return_value = debug_api.session

        session_context = MCPSessionContext()
        session_context.session_started = True
        session_context.breakpoints_set = [
            {"file": "test.py", "line": 10, "location": "test.py:10"},
        ]

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Verify response
        assert result["success"] is True
        context_data = result["data"]["context"]

        # Check breakpoints are marked active
        assert context_data["breakpoints"]["status"] == "active"
        assert context_data["breakpoints"]["count"] == 1

    async def test_state_consistency_across_terminated_session(self):
        """Should have consistent state for terminated session across all fields."""
        # Setup mocks
        debug_api = Mock()
        debug_api.started = True
        debug_api.session = Mock()
        debug_api.session.status = SessionStatus.TERMINATED
        debug_api.session_info = Mock()
        debug_api.session_info.target = "test.py"
        debug_api.session_info.language = "python"

        session_context = MCPSessionContext()
        session_context.session_started = True
        session_context.breakpoints_set = [{"file": "test.py", "line": 10}]

        args = {
            "_session_id": "test-session",
            "_api": debug_api,
            "_context": session_context,
        }

        # Call handler
        result = await handle_context(args)

        # Parse response
        context_data = result["data"]["context"]

        # Verify all state indicators are consistent
        assert context_data["execution_state"] == ExecutionState.TERMINATED.value
        assert context_data["status"] == ConnectionStatus.INACTIVE.value
        assert context_data["breakpoints"]["status"] == "inactive"

        # These should all indicate a terminated session
        assert context_data["execution_state"] == "terminated"
        assert context_data["status"] == "inactive"
        assert context_data["breakpoints"]["status"] == "inactive"
