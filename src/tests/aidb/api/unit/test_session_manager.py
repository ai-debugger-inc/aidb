"""Unit tests for SessionManager and ResourceTracker.

Tests session lifecycle management, resource tracking, and cleanup.
"""

from unittest.mock import MagicMock, patch

import pytest

from aidb.api.session_manager import ResourceTracker, SessionManager
from aidb.common.errors import AidbError


class TestResourceTrackerInit:
    """Tests for ResourceTracker initialization."""

    def test_init_creates_empty_state(self, mock_ctx):
        """ResourceTracker initializes with empty tracking state."""
        tracker = ResourceTracker(ctx=mock_ctx)

        assert tracker._session_resources == {}
        assert tracker._resource_owners == {}

    def test_init_without_context(self):
        """ResourceTracker can initialize without context."""
        tracker = ResourceTracker()

        assert tracker.ctx is None
        assert tracker._session_resources == {}


class TestResourceTrackerTracking:
    """Tests for ResourceTracker resource tracking."""

    def test_track_resource_adds_to_session(self, mock_ctx):
        """track_resource adds resource to session tracking."""
        tracker = ResourceTracker(ctx=mock_ctx)

        tracker.track_resource("port", 5678, "session-1")

        assert "session-1" in tracker._session_resources
        assert "port" in tracker._session_resources["session-1"]
        assert 5678 in tracker._session_resources["session-1"]["port"]

    def test_track_resource_updates_reverse_lookup(self, mock_ctx):
        """track_resource updates reverse lookup map."""
        tracker = ResourceTracker(ctx=mock_ctx)

        tracker.track_resource("port", 5678, "session-1")

        assert tracker._resource_owners[("port", 5678)] == "session-1"

    def test_track_multiple_resources_same_type(self, mock_ctx):
        """Multiple resources of same type are tracked."""
        tracker = ResourceTracker(ctx=mock_ctx)

        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("port", 5679, "session-1")

        assert len(tracker._session_resources["session-1"]["port"]) == 2

    def test_track_multiple_resource_types(self, mock_ctx):
        """Multiple resource types are tracked separately."""
        tracker = ResourceTracker(ctx=mock_ctx)

        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("process", 1234, "session-1")

        assert "port" in tracker._session_resources["session-1"]
        assert "process" in tracker._session_resources["session-1"]


class TestResourceTrackerUntracking:
    """Tests for ResourceTracker resource untracking."""

    def test_untrack_resource_removes_tracking(self, mock_ctx):
        """untrack_resource removes resource from tracking."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")

        tracker.untrack_resource("port", 5678)

        assert ("port", 5678) not in tracker._resource_owners
        # Session entry may be removed if empty
        if "session-1" in tracker._session_resources:
            assert 5678 not in tracker._session_resources["session-1"].get("port", [])

    def test_untrack_resource_returns_session_id(self, mock_ctx):
        """untrack_resource returns the session that owned the resource."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")

        result = tracker.untrack_resource("port", 5678)

        assert result == "session-1"

    def test_untrack_unknown_resource_returns_none(self, mock_ctx):
        """untrack_resource returns None for unknown resource."""
        tracker = ResourceTracker(ctx=mock_ctx)

        result = tracker.untrack_resource("port", 9999)

        assert result is None


class TestResourceTrackerQueries:
    """Tests for ResourceTracker query methods."""

    def test_get_session_resources_returns_copy(self, mock_ctx):
        """get_session_resources returns a copy of resources dict."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")

        resources = tracker.get_session_resources("session-1")

        assert resources["port"] == [5678]
        # Verify the outer dict is a copy (modifying dict doesn't affect tracker)
        resources["new_type"] = ["new_value"]
        assert "new_type" not in tracker._session_resources["session-1"]

    def test_get_session_resources_unknown_session(self, mock_ctx):
        """get_session_resources returns empty dict for unknown session."""
        tracker = ResourceTracker(ctx=mock_ctx)

        resources = tracker.get_session_resources("unknown")

        assert resources == {}

    def test_get_resource_owner_returns_correct_session(self, mock_ctx):
        """get_resource_owner returns the owning session."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("port", 5679, "session-2")

        owner1 = tracker.get_resource_owner("port", 5678)
        owner2 = tracker.get_resource_owner("port", 5679)

        assert owner1 == "session-1"
        assert owner2 == "session-2"

    def test_get_resource_owner_unknown_returns_none(self, mock_ctx):
        """get_resource_owner returns None for unknown resource."""
        tracker = ResourceTracker(ctx=mock_ctx)

        owner = tracker.get_resource_owner("port", 9999)

        assert owner is None


class TestResourceTrackerClear:
    """Tests for ResourceTracker clear operations."""

    def test_clear_session_resources_removes_all(self, mock_ctx):
        """clear_session_resources removes all resources for session."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("process", 1234, "session-1")

        counts = tracker.clear_session_resources("session-1")

        assert counts == {"port": 1, "process": 1}
        assert "session-1" not in tracker._session_resources
        assert ("port", 5678) not in tracker._resource_owners
        assert ("process", 1234) not in tracker._resource_owners

    def test_clear_session_resources_unknown_session(self, mock_ctx):
        """clear_session_resources returns empty dict for unknown session."""
        tracker = ResourceTracker(ctx=mock_ctx)

        counts = tracker.clear_session_resources("unknown")

        assert counts == {}


class TestResourceTrackerLeakDetection:
    """Tests for ResourceTracker leak detection."""

    def test_detect_leaks_returns_sessions_with_resources(self, mock_ctx):
        """detect_leaks returns sessions that still have resources."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("process", 1234, "session-2")

        leaks = tracker.detect_leaks()

        assert "session-1" in leaks
        assert "session-2" in leaks
        assert "port" in leaks["session-1"]
        assert "process" in leaks["session-2"]

    def test_detect_leaks_empty_when_no_resources(self, mock_ctx):
        """detect_leaks returns empty dict when no resources tracked."""
        tracker = ResourceTracker(ctx=mock_ctx)

        leaks = tracker.detect_leaks()

        assert leaks == {}

    def test_get_all_resources(self, mock_ctx):
        """get_all_resources returns all tracked resources."""
        tracker = ResourceTracker(ctx=mock_ctx)
        tracker.track_resource("port", 5678, "session-1")
        tracker.track_resource("process", 1234, "session-2")

        all_resources = tracker.get_all_resources()

        assert "session-1" in all_resources
        assert "session-2" in all_resources


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_init_creates_empty_state(self, mock_ctx):
        """SessionManager initializes with empty session state."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)

            assert manager._active_sessions == 0
            assert manager._current_session is None

    def test_init_creates_registry_and_tracker(self, mock_ctx):
        """SessionManager creates registry and resource tracker."""
        with patch("aidb.api.session_manager.SessionRegistry") as mock_registry_cls:
            manager = SessionManager(ctx=mock_ctx)

            mock_registry_cls.assert_called_once_with(ctx=mock_ctx)
            assert manager._resource_tracker is not None


class TestSessionManagerProperties:
    """Tests for SessionManager properties."""

    def test_active_sessions_count_returns_count(self, mock_ctx):
        """active_sessions_count returns current count."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._active_sessions = 3

            assert manager.active_sessions_count == 3

    def test_current_session_returns_session(self, mock_ctx, mock_session):
        """current_session returns the current session."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._current_session = mock_session

            assert manager.current_session == mock_session

    def test_get_active_session_returns_none_when_no_session(self, mock_ctx):
        """get_active_session returns None when no current session."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)

            assert manager.get_active_session() is None

    def test_get_active_session_resolves_child(self, mock_ctx, mock_session):
        """get_active_session resolves through registry."""
        with patch("aidb.api.session_manager.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.resolve_active_session.return_value = mock_session
            mock_registry_cls.return_value = mock_registry

            manager = SessionManager(ctx=mock_ctx)
            manager._current_session = mock_session

            result = manager.get_active_session()

            mock_registry.resolve_active_session.assert_called_once_with(mock_session)
            assert result == mock_session


class TestSessionManagerCreateSession:
    """Tests for SessionManager.create_session."""

    def test_create_session_increments_count(self, mock_ctx):
        """create_session increments active session count."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            with patch("aidb.api.session_manager.SessionBuilder") as mock_builder_cls:
                mock_builder = MagicMock()
                mock_session = MagicMock()
                mock_session.id = "test-id"
                mock_builder.build.return_value = mock_session
                mock_builder.with_launch_config.return_value = mock_builder
                mock_builder.with_target.return_value = mock_builder
                mock_builder.with_language.return_value = mock_builder
                mock_builder.with_adapter.return_value = mock_builder
                mock_builder.with_breakpoints.return_value = mock_builder
                mock_builder.with_project.return_value = mock_builder
                mock_builder.with_timeout.return_value = mock_builder
                mock_builder.with_kwargs.return_value = mock_builder
                mock_builder_cls.return_value = mock_builder

                manager = SessionManager(ctx=mock_ctx)

                manager.create_session(target="/path/to/script.py", language="python")

                assert manager._active_sessions == 1

    def test_create_session_exceeds_limit_raises(self, mock_ctx):
        """create_session raises when session limit exceeded."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._active_sessions = 10  # MAX_CONCURRENT_SESSIONS

            with pytest.raises(AidbError, match="Maximum concurrent sessions"):
                manager.create_session(target="/path/to/script.py")

    def test_create_session_tracks_resource(self, mock_ctx):
        """create_session tracks the session as a resource."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            with patch("aidb.api.session_manager.SessionBuilder") as mock_builder_cls:
                mock_builder = MagicMock()
                mock_session = MagicMock()
                mock_session.id = "test-session-id"
                mock_builder.build.return_value = mock_session
                mock_builder.with_launch_config.return_value = mock_builder
                mock_builder.with_target.return_value = mock_builder
                mock_builder.with_language.return_value = mock_builder
                mock_builder.with_adapter.return_value = mock_builder
                mock_builder.with_breakpoints.return_value = mock_builder
                mock_builder.with_project.return_value = mock_builder
                mock_builder.with_timeout.return_value = mock_builder
                mock_builder.with_kwargs.return_value = mock_builder
                mock_builder_cls.return_value = mock_builder

                manager = SessionManager(ctx=mock_ctx)

                manager.create_session(target="/path/to/script.py", language="python")

                resources = manager.get_session_resources("test-session-id")
                assert "session" in resources


class TestSessionManagerDestroySession:
    """Tests for SessionManager.destroy_session."""

    def test_destroy_session_decrements_count(self, mock_ctx, mock_session):
        """destroy_session decrements active session count."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._current_session = mock_session
            manager._active_sessions = 2

            manager.destroy_session()

            assert manager._active_sessions == 1

    def test_destroy_session_clears_current(self, mock_ctx, mock_session):
        """destroy_session clears current session reference."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._current_session = mock_session
            manager._active_sessions = 1

            manager.destroy_session()

            assert manager._current_session is None

    def test_destroy_session_handles_no_session(self, mock_ctx):
        """destroy_session handles case when no session exists."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._active_sessions = 0

            manager.destroy_session()

            assert manager._active_sessions == 0

    def test_destroy_session_clears_resources(self, mock_ctx, mock_session):
        """destroy_session clears tracked resources."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._current_session = mock_session
            manager._active_sessions = 1
            manager._resource_tracker.track_resource(
                "session", mock_session.id, mock_session.id
            )

            manager.destroy_session()

            resources = manager.get_session_resources(mock_session.id)
            assert resources == {}


class TestSessionManagerResourceSummary:
    """Tests for SessionManager resource summary."""

    def test_get_resource_summary(self, mock_ctx):
        """get_resource_summary returns comprehensive summary."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._active_sessions = 2
            manager._resource_tracker.track_resource("port", 5678, "session-1")

            summary = manager.get_resource_summary()

            assert summary["active_sessions"] == 2
            assert summary["total_resources"] == 1
            assert "session-1" in summary["resources_by_session"]

    def test_detect_resource_leaks(self, mock_ctx):
        """detect_resource_leaks delegates to tracker."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._resource_tracker.track_resource("port", 5678, "session-1")

            leaks = manager.detect_resource_leaks()

            assert "session-1" in leaks


class TestSessionManagerGetLaunchConfig:
    """Tests for SessionManager.get_launch_config."""

    def test_get_launch_config_returns_config(self, mock_ctx, sample_launch_config):
        """get_launch_config returns config from builder."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            builder = MagicMock()
            builder._launch_config = sample_launch_config

            result = manager.get_launch_config(builder)

            assert result == sample_launch_config

    def test_get_launch_config_returns_none_when_missing(self, mock_ctx):
        """get_launch_config returns None when no config."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            builder = MagicMock()
            builder._launch_config = None

            result = manager.get_launch_config(builder)

            assert result is None
