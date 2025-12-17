"""Unit tests for MCP session state tracking.

Tests for manager_state.py functions:
- set_default_session
- get_last_active_session
- get_session_id_from_args
- list_sessions
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestSetDefaultSession:
    """Tests for set_default_session function."""

    def test_set_default_session_returns_previous(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that set_default_session returns previous default."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_state import set_default_session

        existing_id, _, _ = populated_session_state

        # Set a new default
        previous = set_default_session("new-default-session")

        assert previous == existing_id
        assert state_module._DEFAULT_SESSION_ID == "new-default-session"

    def test_set_default_session_returns_none_when_no_previous(self) -> None:
        """Test that set_default_session returns None when no previous default."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_state import set_default_session

        state_module._DEFAULT_SESSION_ID = None

        previous = set_default_session("first-session")

        assert previous is None
        assert state_module._DEFAULT_SESSION_ID == "first-session"

    def test_set_default_session_updates_global(self) -> None:
        """Test that set_default_session updates _DEFAULT_SESSION_ID."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_state import set_default_session

        set_default_session("session-1")
        assert state_module._DEFAULT_SESSION_ID == "session-1"

        set_default_session("session-2")
        assert state_module._DEFAULT_SESSION_ID == "session-2"

    def test_set_default_session_thread_safe(self) -> None:
        """Test that set_default_session operates under _state_lock."""
        from aidb_mcp.session.manager_shared import _state_lock
        from aidb_mcp.session.manager_state import set_default_session

        # Verify lock is usable (RLock allows reentry)
        with _state_lock:
            pass

        # Should work after lock is released
        set_default_session("thread-safe-test")


class TestGetLastActiveSession:
    """Tests for get_last_active_session function."""

    def test_get_last_active_session_returns_default(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_last_active_session returns default session if exists."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_state import get_last_active_session

        existing_id, _, _ = populated_session_state
        state_module._DEFAULT_SESSION_ID = existing_id

        result = get_last_active_session()

        assert result == existing_id

    def test_get_last_active_session_returns_started_session(self) -> None:
        """Test that get_last_active_session returns a started session."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )
        from aidb_mcp.session.manager_state import get_last_active_session

        state_module._DEFAULT_SESSION_ID = None

        # Add a session that's not started
        api1 = MagicMock()
        ctx1 = MagicMock()
        ctx1.session_started = False
        _DEBUG_SESSIONS["session-not-started"] = api1
        _SESSION_CONTEXTS["session-not-started"] = ctx1

        # Add a session that IS started
        api2 = MagicMock()
        ctx2 = MagicMock()
        ctx2.session_started = True
        _DEBUG_SESSIONS["session-started"] = api2
        _SESSION_CONTEXTS["session-started"] = ctx2

        result = get_last_active_session()

        assert result == "session-started"

    def test_get_last_active_session_returns_most_recent_if_none_started(self) -> None:
        """Test that get_last_active_session returns most recent if none started."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )
        from aidb_mcp.session.manager_state import get_last_active_session

        state_module._DEFAULT_SESSION_ID = None

        # Add sessions that are not started
        for i in range(3):
            api = MagicMock()
            ctx = MagicMock()
            ctx.session_started = False
            _DEBUG_SESSIONS[f"session-{i}"] = api
            _SESSION_CONTEXTS[f"session-{i}"] = ctx

        result = get_last_active_session()

        # Should return the last added session
        assert result == "session-2"

    def test_get_last_active_session_returns_none_if_no_sessions(self) -> None:
        """Test that get_last_active_session returns None with no sessions."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_state import get_last_active_session

        state_module._DEFAULT_SESSION_ID = None

        result = get_last_active_session()

        assert result is None

    def test_get_last_active_session_ignores_invalid_default(self) -> None:
        """Test that get_last_active_session ignores default not in sessions."""
        import aidb_mcp.session.manager_state as state_module
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )
        from aidb_mcp.session.manager_state import get_last_active_session

        # Set default that doesn't exist in sessions
        state_module._DEFAULT_SESSION_ID = "nonexistent-session"

        # Add a valid session
        api = MagicMock()
        ctx = MagicMock()
        ctx.session_started = True
        _DEBUG_SESSIONS["valid-session"] = api
        _SESSION_CONTEXTS["valid-session"] = ctx

        result = get_last_active_session()

        assert result == "valid-session"

    def test_get_last_active_session_thread_safe(self) -> None:
        """Test that get_last_active_session operates under _state_lock."""
        from aidb_mcp.session.manager_shared import _state_lock
        from aidb_mcp.session.manager_state import get_last_active_session

        with _state_lock:
            pass

        # Should work after lock is released
        result = get_last_active_session()
        assert result is None  # No sessions


class TestGetSessionIdFromArgs:
    """Tests for get_session_id_from_args function."""

    def test_get_session_id_from_args_returns_provided_id(self) -> None:
        """Test that get_session_id_from_args returns session_id from args."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        args = {"session_id": "my-session"}

        result = get_session_id_from_args(args)

        assert result == "my-session"

    def test_get_session_id_from_args_falls_back_to_last_active(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_session_id_from_args falls back to last active."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        existing_id, _, _ = populated_session_state
        args: dict = {}

        result = get_session_id_from_args(args)

        assert result == existing_id

    def test_get_session_id_from_args_returns_none_if_no_session(self) -> None:
        """Test that get_session_id_from_args returns None if no session exists."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        args: dict = {}

        result = get_session_id_from_args(args)

        assert result is None

    def test_get_session_id_from_args_custom_param_name(self) -> None:
        """Test that get_session_id_from_args uses custom param_name."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        args = {"target_session": "custom-session"}

        result = get_session_id_from_args(args, param_name="target_session")

        assert result == "custom-session"

    def test_get_session_id_from_args_empty_string_falls_back(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that empty string session_id falls back to last active."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        existing_id, _, _ = populated_session_state
        args = {"session_id": ""}

        result = get_session_id_from_args(args)

        assert result == existing_id

    def test_get_session_id_from_args_none_value_falls_back(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that None session_id falls back to last active."""
        from aidb_mcp.session.manager_state import get_session_id_from_args

        existing_id, _, _ = populated_session_state
        args = {"session_id": None}

        result = get_session_id_from_args(args)

        assert result == existing_id


class TestListSessions:
    """Tests for list_sessions function."""

    def test_list_sessions_empty(self) -> None:
        """Test that list_sessions returns empty list with no sessions."""
        from aidb_mcp.session.manager_state import list_sessions

        result = list_sessions()

        assert result == []

    def test_list_sessions_single_session(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that list_sessions returns single session info."""
        from aidb_mcp.session.manager_state import list_sessions

        session_id, service, context = populated_session_state

        # Set up mock data for DebugService structure
        service.session.started = True
        service.session.info = MagicMock()
        service.session.info.target = "/path/to/script.py"
        service.session.info.language = "python"
        service.session.info.status = MagicMock()
        service.session.info.status.name = "RUNNING"
        service.session.info.port = 5678
        service.session.info.pid = 12345
        context.breakpoints_set = [1, 2, 3]

        result = list_sessions()

        assert len(result) == 1
        session = result[0]
        assert session["session_id"] == session_id
        assert session["is_default"] is True
        assert session["active"] is True
        assert session["target"] == "/path/to/script.py"
        assert session["language"] == "python"
        assert session["status"] == "running"
        assert session["port"] == 5678
        assert session["target_pid"] == 12345
        assert session["breakpoints"] == 3

    def test_list_sessions_multiple_sessions(
        self,
        multiple_sessions_state: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that list_sessions returns all sessions."""
        from aidb_mcp.session.manager_state import list_sessions

        result = list_sessions()

        assert len(result) == 3
        session_ids = [s["session_id"] for s in result]
        assert "test-session-000" in session_ids
        assert "test-session-001" in session_ids
        assert "test-session-002" in session_ids

    def test_list_sessions_marks_default(
        self,
        multiple_sessions_state: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that list_sessions correctly marks default session."""
        from aidb_mcp.session.manager_state import list_sessions

        result = list_sessions()

        # First session should be default
        default_sessions = [s for s in result if s["is_default"]]
        assert len(default_sessions) == 1
        assert default_sessions[0]["session_id"] == "test-session-000"

    def test_list_sessions_handles_no_session_info(self) -> None:
        """Test that list_sessions handles sessions without session info."""
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )
        from aidb_mcp.session.manager_state import list_sessions

        service = MagicMock()
        service.session = MagicMock()
        service.session.started = True
        service.session.info = None
        ctx = MagicMock()
        ctx.breakpoints_set = []

        _DEBUG_SESSIONS["no-info-session"] = service
        _SESSION_CONTEXTS["no-info-session"] = ctx

        result = list_sessions()

        assert len(result) == 1
        session = result[0]
        assert session["session_id"] == "no-info-session"
        assert session["active"] is True
        assert "target" not in session
        assert "language" not in session

    def test_list_sessions_handles_no_context(self) -> None:
        """Test that list_sessions handles sessions without context."""
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS
        from aidb_mcp.session.manager_state import list_sessions

        service = MagicMock()
        service.session = MagicMock()
        service.session.started = False
        service.session.info = None

        _DEBUG_SESSIONS["no-context-session"] = service
        # Don't add to _SESSION_CONTEXTS

        result = list_sessions()

        assert len(result) == 1
        session = result[0]
        assert session["session_id"] == "no-context-session"
        assert session["active"] is False
        assert "breakpoints" not in session

    def test_list_sessions_thread_safe(self) -> None:
        """Test that list_sessions operates under _state_lock."""
        from aidb_mcp.session.manager_shared import _state_lock
        from aidb_mcp.session.manager_state import list_sessions

        with _state_lock:
            pass

        # Should work after lock is released
        result = list_sessions()
        assert isinstance(result, list)
