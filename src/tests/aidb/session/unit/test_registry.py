"""Unit tests for SessionRegistry.

Tests the singleton session registry for session registration, lookup, child management
delegation, and cleanup coordination.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.session.registry import SessionRegistry


@pytest.fixture
def fresh_registry(mock_ctx):
    """Create a fresh SessionRegistry instance for testing.

    Uses reset() to clear singleton and get a fresh instance.
    """
    SessionRegistry.reset()
    registry = SessionRegistry(ctx=mock_ctx)
    yield registry
    SessionRegistry.reset()


class TestSessionRegistryInit:
    """Tests for SessionRegistry initialization."""

    def test_init_creates_empty_sessions(self, fresh_registry):
        """SessionRegistry initializes with empty sessions dict."""
        assert fresh_registry._sessions == {}

    def test_init_creates_child_manager(self, fresh_registry):
        """SessionRegistry creates child session registry."""
        assert fresh_registry._child_manager is not None

    def test_init_creates_cleanup_manager(self, fresh_registry):
        """SessionRegistry creates cleanup manager."""
        assert fresh_registry._cleanup_manager is not None

    def test_singleton_returns_same_instance(self, mock_ctx):
        """SessionRegistry returns the same instance (singleton)."""
        SessionRegistry.reset()
        try:
            registry1 = SessionRegistry(ctx=mock_ctx)
            registry2 = SessionRegistry(ctx=mock_ctx)

            assert registry1 is registry2
        finally:
            SessionRegistry.reset()


class TestSessionRegistryRegistration:
    """Tests for session registration operations."""

    def test_register_session_adds_to_sessions(self, fresh_registry):
        """register_session adds session to internal dict."""
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        mock_session.language = "python"
        mock_session.is_child = False

        fresh_registry.register_session(mock_session)

        assert fresh_registry._sessions["test-session-id"] == mock_session

    def test_unregister_session_removes_from_sessions(self, fresh_registry):
        """unregister_session removes session from internal dict."""
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        fresh_registry._sessions["test-session-id"] = mock_session

        fresh_registry.unregister_session("test-session-id")

        assert "test-session-id" not in fresh_registry._sessions

    def test_unregister_nonexistent_session_no_error(self, fresh_registry):
        """unregister_session does not raise for unknown session."""
        fresh_registry.unregister_session("nonexistent")

    def test_get_session_returns_registered(self, fresh_registry):
        """get_session returns registered session."""
        mock_session = MagicMock()
        mock_session.id = "test-session-id"
        fresh_registry._sessions["test-session-id"] = mock_session

        result = fresh_registry.get_session("test-session-id")

        assert result == mock_session

    def test_get_session_returns_none_for_unknown(self, fresh_registry):
        """get_session returns None for unknown session ID."""
        result = fresh_registry.get_session("unknown")

        assert result is None

    def test_get_all_sessions_returns_list(self, fresh_registry):
        """get_all_sessions returns list of all sessions."""
        session1 = MagicMock()
        session1.id = "session-1"
        session2 = MagicMock()
        session2.id = "session-2"
        fresh_registry._sessions = {"session-1": session1, "session-2": session2}

        result = fresh_registry.get_all_sessions()

        assert len(result) == 2
        assert session1 in result
        assert session2 in result


class TestSessionRegistryChildDelegation:
    """Tests for child management delegation."""

    def test_register_parent_child_delegates(self, fresh_registry):
        """register_parent_child delegates to child manager."""
        fresh_registry._child_manager = MagicMock()

        fresh_registry.register_parent_child("parent-id", "child-id")

        fresh_registry._child_manager.register_parent_child.assert_called_once_with(
            "parent-id", "child-id"
        )

    def test_get_children_delegates(self, fresh_registry):
        """get_children delegates to child manager."""
        fresh_registry._child_manager = MagicMock()
        fresh_registry._child_manager.get_children.return_value = []

        fresh_registry.get_children("parent-id")

        fresh_registry._child_manager.get_children.assert_called_once_with(
            "parent-id", fresh_registry._sessions
        )

    def test_set_active_child_delegates(self, fresh_registry):
        """set_active_child delegates to child manager."""
        fresh_registry._child_manager = MagicMock()

        fresh_registry.set_active_child("parent-id", "child-id")

        fresh_registry._child_manager.set_active_child.assert_called_once_with(
            "parent-id", "child-id"
        )

    def test_get_active_child_delegates(self, fresh_registry):
        """get_active_child delegates to child manager."""
        fresh_registry._child_manager = MagicMock()
        fresh_registry._child_manager.get_active_child.return_value = "child-id"

        result = fresh_registry.get_active_child("parent-id")

        fresh_registry._child_manager.get_active_child.assert_called_once_with(
            "parent-id"
        )
        assert result == "child-id"

    def test_resolve_active_session_delegates(self, fresh_registry):
        """resolve_active_session delegates to child manager."""
        fresh_registry._child_manager = MagicMock()
        mock_session = MagicMock()
        fresh_registry._child_manager.resolve_active_session.return_value = mock_session

        result = fresh_registry.resolve_active_session(mock_session)

        fresh_registry._child_manager.resolve_active_session.assert_called_once()
        assert result == mock_session


class TestSessionRegistryUtility:
    """Tests for utility methods."""

    def test_count_sessions_returns_correct_counts(self, fresh_registry):
        """count_sessions returns breakdown of session types."""
        parent = MagicMock()
        parent.is_child = False
        child = MagicMock()
        child.is_child = True
        fresh_registry._sessions = {"parent": parent, "child": child}

        counts = fresh_registry.count_sessions()

        assert counts["total"] == 2
        assert counts["parents"] == 1
        assert counts["children"] == 1

    def test_count_sessions_empty_registry(self, fresh_registry):
        """count_sessions returns zeros for empty registry."""
        fresh_registry._sessions = {}

        counts = fresh_registry.count_sessions()

        assert counts["total"] == 0
        assert counts["parents"] == 0
        assert counts["children"] == 0

    def test_get_sessions_by_language_filters(self, fresh_registry):
        """get_sessions_by_language returns only matching sessions."""
        python_session = MagicMock()
        python_session.language = "python"
        js_session = MagicMock()
        js_session.language = "javascript"
        fresh_registry._sessions = {"py": python_session, "js": js_session}

        result = fresh_registry.get_sessions_by_language("python")

        assert len(result) == 1
        assert result[0] == python_session

    def test_get_sessions_by_language_no_matches(self, fresh_registry):
        """get_sessions_by_language returns empty list when no matches."""
        python_session = MagicMock()
        python_session.language = "python"
        fresh_registry._sessions = {"py": python_session}

        result = fresh_registry.get_sessions_by_language("java")

        assert result == []

    def test_repr_shows_session_counts(self, fresh_registry):
        """__repr__ shows session count information."""
        session = MagicMock()
        session.is_child = False
        fresh_registry._sessions = {"test": session}

        result = repr(fresh_registry)

        assert "SessionRegistry" in result
        assert "1 sessions" in result


class TestSessionRegistryCleanup:
    """Tests for cleanup management delegation."""

    @pytest.mark.asyncio
    async def test_cleanup_session_delegates(self, fresh_registry):
        """cleanup_session delegates to cleanup manager."""
        fresh_registry._cleanup_manager = MagicMock()
        fresh_registry._cleanup_manager.cleanup_session = AsyncMock()

        await fresh_registry.cleanup_session("session-id")

        fresh_registry._cleanup_manager.cleanup_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_all_delegates(self, fresh_registry):
        """cleanup_all delegates to cleanup manager."""
        fresh_registry._cleanup_manager = MagicMock()
        fresh_registry._cleanup_manager.cleanup_all = AsyncMock()

        await fresh_registry.cleanup_all()

        fresh_registry._cleanup_manager.cleanup_all.assert_called_once()


class TestSessionRegistryGetActiveSession:
    """Tests for get_active_session by language."""

    def test_get_active_session_delegates(self, fresh_registry):
        """get_active_session delegates to child manager."""
        fresh_registry._child_manager = MagicMock()
        mock_session = MagicMock()
        fresh_registry._child_manager.get_active_session_for_language.return_value = (
            mock_session
        )

        result = fresh_registry.get_active_session("python")

        fresh_registry._child_manager.get_active_session_for_language.assert_called_once_with(
            "python", fresh_registry._sessions
        )
        assert result == mock_session
