"""Unit tests for SessionManager."""

from unittest.mock import MagicMock, patch

import pytest

from aidb.api.session_manager import SessionManager
from aidb.common.errors import AidbError


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_init_creates_empty_state(self, mock_ctx):
        """SessionManager initializes with empty session state."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)

            assert manager._active_sessions == 0
            assert manager._current_session is None

    def test_init_creates_registry(self, mock_ctx):
        """SessionManager creates registry."""
        with patch("aidb.api.session_manager.SessionRegistry") as mock_registry_cls:
            manager = SessionManager(ctx=mock_ctx)

            mock_registry_cls.assert_called_once_with(ctx=mock_ctx)
            assert manager._registry is not None


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

    def test_create_session_sets_current(self, mock_ctx):
        """create_session sets the current session."""
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

                result = manager.create_session(
                    target="/path/to/script.py", language="python"
                )

                assert manager._current_session == mock_session
                assert result == mock_session


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

    def test_destroy_session_does_not_go_negative(self, mock_ctx):
        """destroy_session does not allow negative session count."""
        with patch("aidb.api.session_manager.SessionRegistry"):
            manager = SessionManager(ctx=mock_ctx)
            manager._active_sessions = 0

            manager.destroy_session()
            manager.destroy_session()  # Call twice

            assert manager._active_sessions == 0


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
