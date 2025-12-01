"""Unit tests for ChildSessionRegistry.

Tests parent-child session relationship management, active child tracking, and session
resolution.
"""

from unittest.mock import MagicMock

import pytest

from aidb.models import SessionStatus


@pytest.fixture
def child_registry(mock_ctx: MagicMock):
    """Create a ChildSessionRegistry instance for testing."""
    from aidb.session.child_registry import ChildSessionRegistry

    return ChildSessionRegistry(ctx=mock_ctx)


@pytest.fixture
def mock_sessions() -> dict[str, MagicMock]:
    """Create a dict of mock sessions for testing."""
    parent = MagicMock()
    parent.id = "parent-123"
    parent.language = "javascript"
    parent.status = SessionStatus.RUNNING

    child1 = MagicMock()
    child1.id = "child-456"
    child1.language = "javascript"
    child1.status = SessionStatus.PAUSED

    child2 = MagicMock()
    child2.id = "child-789"
    child2.language = "javascript"
    child2.status = SessionStatus.RUNNING

    return {
        "parent-123": parent,
        "child-456": child1,
        "child-789": child2,
    }


class TestChildRegistryRelationships:
    """Tests for parent-child relationship management."""

    def test_register_parent_child_stores_mapping(
        self,
        child_registry,
    ) -> None:
        """register_parent_child stores parent-child mapping."""
        child_registry.register_parent_child("parent-123", "child-456")

        assert "parent-123" in child_registry._parent_child_map
        assert "child-456" in child_registry._parent_child_map["parent-123"]

    def test_register_parent_child_allows_multiple_children(
        self,
        child_registry,
    ) -> None:
        """register_parent_child allows multiple children per parent."""
        child_registry.register_parent_child("parent-123", "child-456")
        child_registry.register_parent_child("parent-123", "child-789")

        assert len(child_registry._parent_child_map["parent-123"]) == 2

    def test_get_children_returns_sessions(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_children returns list of child session objects."""
        child_registry.register_parent_child("parent-123", "child-456")

        result = child_registry.get_children("parent-123", mock_sessions)

        assert len(result) == 1
        assert result[0].id == "child-456"

    def test_get_children_returns_empty_list(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_children returns empty list when no children."""
        result = child_registry.get_children("nonexistent", mock_sessions)

        assert result == []

    def test_get_children_filters_missing_sessions(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_children filters out child IDs not in sessions dict."""
        child_registry.register_parent_child("parent-123", "child-456")
        child_registry.register_parent_child("parent-123", "missing-child")

        result = child_registry.get_children("parent-123", mock_sessions)

        assert len(result) == 1
        assert result[0].id == "child-456"

    def test_get_child_ids_returns_ids(
        self,
        child_registry,
    ) -> None:
        """get_child_ids returns list of child IDs."""
        child_registry.register_parent_child("parent-123", "child-456")
        child_registry.register_parent_child("parent-123", "child-789")

        result = child_registry.get_child_ids("parent-123")

        assert "child-456" in result
        assert "child-789" in result

    def test_get_child_ids_returns_empty_list(
        self,
        child_registry,
    ) -> None:
        """get_child_ids returns empty list for unknown parent."""
        result = child_registry.get_child_ids("nonexistent")

        assert result == []

    def test_has_children_returns_true(
        self,
        child_registry,
    ) -> None:
        """has_children returns True when children exist."""
        child_registry.register_parent_child("parent-123", "child-456")

        assert child_registry.has_children("parent-123") is True

    def test_has_children_returns_false(
        self,
        child_registry,
    ) -> None:
        """has_children returns False when no children."""
        assert child_registry.has_children("nonexistent") is False


class TestChildRegistryActive:
    """Tests for active child management."""

    def test_set_active_child_stores_id(
        self,
        child_registry,
    ) -> None:
        """set_active_child stores active child ID."""
        child_registry.set_active_child("parent-123", "child-456")

        assert child_registry._active_child_map["parent-123"] == "child-456"

    def test_set_active_child_overwrites_previous(
        self,
        child_registry,
    ) -> None:
        """set_active_child overwrites previous active child."""
        child_registry.set_active_child("parent-123", "child-456")
        child_registry.set_active_child("parent-123", "child-789")

        assert child_registry._active_child_map["parent-123"] == "child-789"

    def test_get_active_child_returns_id(
        self,
        child_registry,
    ) -> None:
        """get_active_child returns active child ID."""
        child_registry.set_active_child("parent-123", "child-456")

        result = child_registry.get_active_child("parent-123")

        assert result == "child-456"

    def test_get_active_child_returns_none(
        self,
        child_registry,
    ) -> None:
        """get_active_child returns None when no active child."""
        result = child_registry.get_active_child("nonexistent")

        assert result is None

    def test_resolve_active_session_returns_child(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """resolve_active_session returns active child when available."""
        child_registry.set_active_child("parent-123", "child-456")

        parent = mock_sessions["parent-123"]
        result = child_registry.resolve_active_session(parent, mock_sessions)

        assert result.id == "child-456"

    def test_resolve_active_session_returns_parent(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """resolve_active_session returns parent when no active child."""
        parent = mock_sessions["parent-123"]

        result = child_registry.resolve_active_session(parent, mock_sessions)

        assert result.id == "parent-123"

    def test_resolve_active_session_returns_parent_when_child_missing(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """resolve_active_session returns parent when child not in sessions."""
        child_registry.set_active_child("parent-123", "missing-child")

        parent = mock_sessions["parent-123"]
        result = child_registry.resolve_active_session(parent, mock_sessions)

        assert result.id == "parent-123"


class TestChildRegistryLanguage:
    """Tests for language-based session resolution."""

    def test_get_active_session_for_language_finds_parent(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_active_session_for_language finds parent session."""
        result = child_registry.get_active_session_for_language(
            "javascript", mock_sessions
        )

        assert result is not None
        assert result.language == "javascript"

    def test_get_active_session_for_language_returns_active_child(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_active_session_for_language returns active child."""
        child_registry.set_active_child("parent-123", "child-456")

        result = child_registry.get_active_session_for_language(
            "javascript", mock_sessions
        )

        assert result.id == "child-456"

    def test_get_active_session_for_language_finds_paused_child(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_active_session_for_language prefers paused child."""
        child_registry.register_parent_child("parent-123", "child-456")
        child_registry.register_parent_child("parent-123", "child-789")

        result = child_registry.get_active_session_for_language(
            "javascript", mock_sessions
        )

        # child-456 is PAUSED, child-789 is RUNNING
        assert result.id == "child-456"

    def test_get_active_session_for_language_returns_none(
        self,
        child_registry,
        mock_sessions: dict[str, MagicMock],
    ) -> None:
        """get_active_session_for_language returns None for unknown language."""
        result = child_registry.get_active_session_for_language("python", mock_sessions)

        assert result is None


class TestChildRegistryCleanup:
    """Tests for cleanup operations."""

    def test_remove_parent_child_mapping_removes_mapping(
        self,
        child_registry,
    ) -> None:
        """remove_parent_child_mapping removes parent-child mapping."""
        child_registry.register_parent_child("parent-123", "child-456")
        child_registry.set_active_child("parent-123", "child-456")

        child_registry.remove_parent_child_mapping("parent-123")

        assert "parent-123" not in child_registry._parent_child_map
        assert "parent-123" not in child_registry._active_child_map

    def test_remove_parent_child_mapping_handles_missing(
        self,
        child_registry,
    ) -> None:
        """remove_parent_child_mapping handles non-existent parent."""
        # Should not raise
        child_registry.remove_parent_child_mapping("nonexistent")

    def test_clear_removes_all(
        self,
        child_registry,
    ) -> None:
        """Clear removes all mappings."""
        child_registry.register_parent_child("parent-1", "child-1")
        child_registry.register_parent_child("parent-2", "child-2")
        child_registry.set_active_child("parent-1", "child-1")

        child_registry.clear()

        assert len(child_registry._parent_child_map) == 0
        assert len(child_registry._active_child_map) == 0
