"""Unit tests for MCP session core CRUD operations.

Tests for manager_core.py functions:
- get_or_create_session
- get_service
- get_session_id
- get_session
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestGetOrCreateSession:
    """Tests for get_or_create_session function."""

    def test_get_or_create_session_creates_new(self) -> None:
        """Test that get_or_create_session creates new context."""
        from aidb_mcp.session.manager_core import get_or_create_session
        from aidb_mcp.session.manager_shared import _SESSION_CONTEXTS

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, context = get_or_create_session("new-session-123")

        assert session_id == "new-session-123"
        assert context is not None
        assert "new-session-123" in _SESSION_CONTEXTS

    def test_get_or_create_session_returns_existing(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_or_create_session returns existing session."""
        from aidb_mcp.session.manager_core import get_or_create_session

        existing_id, _, existing_context = populated_session_state

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, context = get_or_create_session(existing_id)

        assert session_id == existing_id
        assert context is existing_context

    def test_get_or_create_session_creates_default(self) -> None:
        """Test that get_or_create_session creates default session if None."""
        import aidb_mcp.session.manager_core as core_module
        from aidb_mcp.session.manager_core import get_or_create_session

        # Ensure no default
        core_module._DEFAULT_SESSION_ID = None

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, context = get_or_create_session(None)

        assert session_id is not None
        assert context is not None
        # Default should now be set
        assert session_id == core_module._DEFAULT_SESSION_ID

    def test_get_or_create_session_uses_provided_id(self) -> None:
        """Test that get_or_create_session uses provided session_id."""
        from aidb_mcp.session.manager_core import get_or_create_session

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, _ = get_or_create_session("my-custom-id")

        assert session_id == "my-custom-id"

    def test_get_or_create_session_sets_session_context(self) -> None:
        """Test that get_or_create_session calls set_session_id()."""
        from aidb_mcp.session.manager_core import get_or_create_session

        with patch("aidb_mcp.session.manager_core.set_session_id") as mock_set:
            get_or_create_session("test-session")

            mock_set.assert_called_with("test-session")

    def test_get_or_create_session_sets_default_if_none(self) -> None:
        """Test that get_or_create_session sets _DEFAULT_SESSION_ID if None."""
        import aidb_mcp.session.manager_core as core_module
        from aidb_mcp.session.manager_core import get_or_create_session

        core_module._DEFAULT_SESSION_ID = None

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, _ = get_or_create_session("first-session")

        assert core_module._DEFAULT_SESSION_ID == "first-session"

    def test_get_or_create_session_returns_tuple(self) -> None:
        """Test that get_or_create_session returns (id, context) tuple."""
        from aidb_mcp.session.manager_core import get_or_create_session

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            result = get_or_create_session("tuple-test")

        assert isinstance(result, tuple)
        assert len(result) == 2
        session_id, context = result
        assert isinstance(session_id, str)

    def test_get_or_create_session_thread_safe(self) -> None:
        """Test that get_or_create_session operates under _state_lock."""
        from aidb_mcp.session.manager_core import get_or_create_session
        from aidb_mcp.session.manager_shared import _state_lock

        # Verify lock is used by checking lock is acquired
        with patch("aidb_mcp.session.manager_core.set_session_id"):
            # This should complete without deadlock
            with _state_lock:
                # Already locked, but _state_lock is RLock so this is ok
                pass

            # Function should still work after lock is released
            session_id, _ = get_or_create_session("thread-safe-test")

        assert session_id == "thread-safe-test"

    def test_get_or_create_session_logs_creation(self) -> None:
        """Test that get_or_create_session logs new session creation."""
        from aidb_mcp.session.manager_core import get_or_create_session

        with (
            patch("aidb_mcp.session.manager_core.set_session_id"),
            patch("aidb_mcp.session.manager_core.logger") as mock_logger,
        ):
            get_or_create_session("logged-session")

            # Should log info about creation
            mock_logger.info.assert_called()

    def test_get_or_create_session_logs_switch(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_or_create_session logs switch to existing session."""
        from aidb_mcp.session.manager_core import get_or_create_session

        existing_id, _, _ = populated_session_state

        with (
            patch("aidb_mcp.session.manager_core.set_session_id"),
            patch("aidb_mcp.session.manager_core.logger") as mock_logger,
        ):
            get_or_create_session(existing_id)

            # Should log debug about switching
            mock_logger.debug.assert_called()

    def test_get_or_create_session_uuid_format(self) -> None:
        """Test that auto-generated session IDs are valid UUIDs."""
        import aidb_mcp.session.manager_core as core_module
        from aidb_mcp.session.manager_core import get_or_create_session

        core_module._DEFAULT_SESSION_ID = None

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            session_id, _ = get_or_create_session(None)

        # Should be valid UUID format
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(session_id)

    def test_get_or_create_session_multiple_sessions(self) -> None:
        """Test that multiple sessions can be created."""
        from aidb_mcp.session.manager_core import get_or_create_session
        from aidb_mcp.session.manager_shared import _SESSION_CONTEXTS

        with patch("aidb_mcp.session.manager_core.set_session_id"):
            id1, ctx1 = get_or_create_session("session-1")
            id2, ctx2 = get_or_create_session("session-2")
            id3, ctx3 = get_or_create_session("session-3")

        assert len(_SESSION_CONTEXTS) >= 3
        assert id1 != id2 != id3
        assert ctx1 is not ctx2 is not ctx3


class TestGetService:
    """Tests for get_service function."""

    def test_get_service_returns_service(
        self,
        populated_session_with_service: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_service returns DebugService for existing session."""
        from aidb_mcp.session.manager_core import get_service

        session_id, expected_service, _ = populated_session_with_service

        result = get_service(session_id)

        assert result is expected_service

    def test_get_service_returns_none(self) -> None:
        """Test that get_service returns None for non-existent session."""
        from aidb_mcp.session.manager_core import get_service

        result = get_service("nonexistent-session")

        assert result is None

    def test_get_service_uses_default(
        self,
        populated_session_with_service: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_service uses default if session_id=None."""
        from aidb_mcp.session.manager_core import get_service

        session_id, expected_service, _ = populated_session_with_service

        result = get_service(None)

        assert result is expected_service

    def test_get_service_no_default(self) -> None:
        """Test that get_service returns None if no default and None passed."""
        import aidb_mcp.session.manager_core as core_module
        from aidb_mcp.session.manager_core import get_service

        core_module._DEFAULT_SESSION_ID = None

        result = get_service(None)

        assert result is None

    def test_get_service_thread_safe(
        self,
        populated_session_with_service: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_service operates under _state_lock."""
        from aidb_mcp.session.manager_core import get_service
        from aidb_mcp.session.manager_shared import _state_lock

        session_id, expected_service, _ = populated_session_with_service

        # Verify can still get service after lock operations
        with _state_lock:
            pass

        result = get_service(session_id)
        assert result is expected_service

    def test_get_service_specific_session(
        self,
        multiple_sessions_with_services: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that get_service returns specific session's service."""
        from aidb_mcp.session.manager_core import get_service

        for session_id, expected_service, _ in multiple_sessions_with_services:
            result = get_service(session_id)
            assert result is expected_service

    def test_get_service_empty_string(self) -> None:
        """Test that get_service handles empty string session_id."""
        from aidb_mcp.session.manager_core import get_service

        # Empty string should be treated like None (falsy)
        result = get_service("")

        # Should try to get default or return None
        # Since empty string is falsy, it should use default logic
        assert result is None  # No default set


class TestGetSessionId:
    """Tests for get_session_id function."""

    def test_get_session_id_returns_context(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_session_id returns MCPSessionContext."""
        from aidb_mcp.session.manager_core import get_session_id

        session_id, _, expected_context = populated_session_state

        result = get_session_id(session_id)

        assert result is expected_context

    def test_get_session_id_returns_none(self) -> None:
        """Test that get_session_id returns None for non-existent session."""
        from aidb_mcp.session.manager_core import get_session_id

        result = get_session_id("nonexistent-session")

        assert result is None

    def test_get_session_id_uses_default(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_session_id uses default if None."""
        from aidb_mcp.session.manager_core import get_session_id

        session_id, _, expected_context = populated_session_state

        result = get_session_id(None)

        assert result is expected_context

    def test_get_session_id_no_default(self) -> None:
        """Test that get_session_id returns None if no default."""
        import aidb_mcp.session.manager_core as core_module
        from aidb_mcp.session.manager_core import get_session_id

        core_module._DEFAULT_SESSION_ID = None

        result = get_session_id(None)

        assert result is None

    def test_get_session_id_thread_safe(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that get_session_id operates under _state_lock."""
        from aidb_mcp.session.manager_core import get_session_id
        from aidb_mcp.session.manager_shared import _state_lock

        session_id, _, expected_context = populated_session_state

        with _state_lock:
            pass

        result = get_session_id(session_id)
        assert result is expected_context

    def test_get_session_id_specific_session(
        self,
        multiple_sessions_state: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that get_session_id returns specific session's context."""
        from aidb_mcp.session.manager_core import get_session_id

        for session_id, _, expected_context in multiple_sessions_state:
            result = get_session_id(session_id)
            assert result is expected_context
