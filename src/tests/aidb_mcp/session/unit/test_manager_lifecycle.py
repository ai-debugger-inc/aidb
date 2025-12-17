"""Unit tests for MCP session lifecycle management.

Tests for manager_lifecycle.py functions:
- _attempt_graceful_shutdown
- _cleanup_session_context
- _cleanup_registries
- cleanup_session
- cleanup_session_async
- cleanup_all_sessions
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestAttemptGracefulShutdown:
    """Tests for _attempt_graceful_shutdown function."""

    def test_attempt_graceful_shutdown_success(
        self,
        mock_debug_service: MagicMock,
    ) -> None:
        """Test that graceful shutdown succeeds on first try when
        service.execution.stop() works."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 3
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service,
                session_id="test-session",
                timeout=5.0,
                force=False,
            )

            assert result is True
            mock_debug_service.execution.stop.assert_called_once()

    def test_attempt_graceful_shutdown_retry_success(
        self,
        mock_debug_service: MagicMock,
    ) -> None:
        """Test that graceful shutdown succeeds after retry."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        # Fail first, succeed second - need to create new AsyncMock with side_effect
        mock_debug_service.execution.stop = AsyncMock(
            side_effect=[RuntimeError("First fail"), None]
        )

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 3
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service,
                session_id="test-session",
                timeout=5.0,
                force=False,
            )

            assert result is True
            assert mock_debug_service.execution.stop.call_count == 2

    def test_attempt_graceful_shutdown_max_retries_exceeded(
        self,
        mock_debug_service_stop_fails: MagicMock,
    ) -> None:
        """Test that shutdown fails after max retries with force=False."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 2
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service_stop_fails,
                session_id="test-session",
                timeout=10.0,
                force=False,
            )

            assert result is False
            assert mock_debug_service_stop_fails.execution.stop.call_count == 2

    def test_attempt_graceful_shutdown_max_retries_forced(
        self,
        mock_debug_service_stop_fails: MagicMock,
    ) -> None:
        """Test that shutdown returns True after max retries with force=True."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 2
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service_stop_fails,
                session_id="test-session",
                timeout=10.0,
                force=True,
            )

            assert result is True

    def test_attempt_graceful_shutdown_timeout_exceeded(
        self,
        mock_debug_service: MagicMock,
    ) -> None:
        """Test that shutdown fails when timeout is exceeded with force=False."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        # Make stop take longer than timeout by sleeping
        async def slow_stop():
            await asyncio.sleep(0.2)
            msg = "Slow stop failed"
            raise RuntimeError(msg)

        mock_debug_service.execution.stop = AsyncMock(side_effect=slow_stop)

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 10
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service,
                session_id="test-session",
                timeout=0.1,
                force=False,
            )

            assert result is False

    def test_attempt_graceful_shutdown_timeout_forced(
        self,
        mock_debug_service: MagicMock,
    ) -> None:
        """Test that shutdown returns True on timeout with force=True."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        # Make stop take longer than timeout
        async def slow_stop():
            await asyncio.sleep(0.2)
            msg = "Slow stop failed"
            raise RuntimeError(msg)

        mock_debug_service.execution.stop = AsyncMock(side_effect=slow_stop)

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.max_retry_attempts = 10
            mock_config.session.retry_delay = 0.01

            result = _attempt_graceful_shutdown(
                service=mock_debug_service,
                session_id="test-session",
                timeout=0.1,
                force=True,
            )

            assert result is True

    def test_attempt_graceful_shutdown_retry_delay(
        self,
        mock_debug_service: MagicMock,
    ) -> None:
        """Test that retry delay is applied between attempts."""
        from aidb_mcp.session.manager_lifecycle import _attempt_graceful_shutdown

        # Fail twice, then succeed - need to create new AsyncMock
        mock_debug_service.execution.stop = AsyncMock(
            side_effect=[
                RuntimeError("First fail"),
                RuntimeError("Second fail"),
                None,
            ]
        )

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.time.sleep") as mock_sleep,
        ):
            mock_config.session.max_retry_attempts = 5
            mock_config.session.retry_delay = 0.5

            result = _attempt_graceful_shutdown(
                service=mock_debug_service,
                session_id="test-session",
                timeout=10.0,
                force=False,
            )

            assert result is True
            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(0.5)


class TestCleanupSessionContext:
    """Tests for _cleanup_session_context function."""

    def test_cleanup_session_context_clears_breakpoints(
        self,
        mock_mcp_session_context_with_breakpoints: MagicMock,
    ) -> None:
        """Test that breakpoints_set is cleared."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_session_context

        assert len(mock_mcp_session_context_with_breakpoints.breakpoints_set) > 0

        _cleanup_session_context(
            mock_mcp_session_context_with_breakpoints,
            "test-session",
        )

        assert len(mock_mcp_session_context_with_breakpoints.breakpoints_set) == 0

    def test_cleanup_session_context_clears_variables(
        self,
        mock_mcp_session_context_with_variables: MagicMock,
    ) -> None:
        """Test that variables_tracked is cleared."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_session_context

        assert len(mock_mcp_session_context_with_variables.variables_tracked) > 0

        _cleanup_session_context(
            mock_mcp_session_context_with_variables,
            "test-session",
        )

        assert len(mock_mcp_session_context_with_variables.variables_tracked) == 0

    def test_cleanup_session_context_handles_none(self) -> None:
        """Test that None context doesn't raise."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_session_context

        # Should not raise
        _cleanup_session_context(None, "test-session")


class TestCleanupRegistries:
    """Tests for _cleanup_registries function."""

    def test_cleanup_registries_removes_from_debug_sessions(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that session is removed from _DEBUG_SESSIONS."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        session_id, _, _ = populated_session_state
        assert session_id in _DEBUG_SESSIONS

        with patch("aidb_mcp.session.manager_lifecycle.clear_session_id"):
            with patch(
                "aidb_mcp.session.manager_lifecycle.get_session_id_from_context"
            ):
                result = _cleanup_registries(session_id, force=False)

        assert result is True
        assert session_id not in _DEBUG_SESSIONS

    def test_cleanup_registries_removes_from_session_contexts(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that context is removed from _SESSION_CONTEXTS."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries
        from aidb_mcp.session.manager_shared import _SESSION_CONTEXTS

        session_id, _, _ = populated_session_state
        assert session_id in _SESSION_CONTEXTS

        with patch("aidb_mcp.session.manager_lifecycle.clear_session_id"):
            with patch(
                "aidb_mcp.session.manager_lifecycle.get_session_id_from_context"
            ):
                result = _cleanup_registries(session_id, force=False)

        assert result is True
        assert session_id not in _SESSION_CONTEXTS

    def test_cleanup_registries_resets_default_if_current(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that _DEFAULT_SESSION_ID is reset if cleaning up default session."""
        import aidb_mcp.session.manager_lifecycle as lifecycle_module
        import aidb_mcp.session.manager_shared as shared
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries

        session_id, _, _ = populated_session_state
        assert session_id == shared._DEFAULT_SESSION_ID

        with patch("aidb_mcp.session.manager_lifecycle.clear_session_id"):
            with patch(
                "aidb_mcp.session.manager_lifecycle.get_session_id_from_context"
            ):
                _cleanup_registries(session_id, force=False)

        # The lifecycle module uses its own import of _DEFAULT_SESSION_ID
        # So we need to check that the cleanup actually worked
        # by verifying the session is no longer the default when looking up
        assert lifecycle_module._DEFAULT_SESSION_ID is None

    def test_cleanup_registries_clears_session_id_context(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that clear_session_id() is called when cleaning up current session."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries

        session_id, _, _ = populated_session_state

        with patch("aidb_mcp.session.manager_lifecycle.clear_session_id") as mock_clear:
            with patch(
                "aidb_mcp.session.manager_lifecycle.get_session_id_from_context",
                return_value=session_id,
            ):
                _cleanup_registries(session_id, force=False)

        # Called twice: once for default reset, once for context clear
        assert mock_clear.call_count >= 1

    def test_cleanup_registries_error_without_force(self) -> None:
        """Test that cleanup returns False on error without force."""
        import aidb_mcp.session.manager_shared as shared
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        # Add a session that will cause KeyError when deleted
        _DEBUG_SESSIONS["test-session"] = MagicMock()

        # Make del raise an exception by removing the key first
        del _DEBUG_SESSIONS["test-session"]

        result = _cleanup_registries("test-session", force=False)

        # Should return False because session not found
        assert result is False

    def test_cleanup_registries_error_with_force(self) -> None:
        """Test that cleanup returns True on error with force=True."""
        from aidb_mcp.session.manager_lifecycle import _cleanup_registries

        # Try to clean up non-existent session with force
        result = _cleanup_registries("nonexistent-session", force=True)

        # Force cleanup should still succeed (via pop with default)
        assert result is True


class TestCleanupSession:
    """Tests for cleanup_session function."""

    def test_cleanup_session_not_found(self) -> None:
        """Test that cleanup returns False for non-existent session."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session

        result = cleanup_session("nonexistent-session")

        assert result is False

    def test_cleanup_session_full_success(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that cleanup succeeds when all phases complete."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id, service, _ = populated_session_state

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.clear_session_id"),
            patch("aidb_mcp.session.manager_lifecycle.get_session_id_from_context"),
        ):
            mock_config.session.default_cleanup_timeout = 5.0
            mock_config.session.max_retry_attempts = 3
            mock_config.session.retry_delay = 0.01

            result = cleanup_session(session_id)

        assert result is True
        assert session_id not in _DEBUG_SESSIONS
        assert session_id not in _SESSION_CONTEXTS
        service.execution.stop.assert_called()

    def test_cleanup_session_graceful_shutdown_fails_without_force(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that cleanup returns False when graceful shutdown fails."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        session_id, service, _ = populated_session_state
        service.execution.stop = AsyncMock(side_effect=RuntimeError("Stop failed"))

        with patch("aidb_mcp.session.manager_lifecycle.config") as mock_config:
            mock_config.session.default_cleanup_timeout = 0.1
            mock_config.session.max_retry_attempts = 1
            mock_config.session.retry_delay = 0.01

            result = cleanup_session(session_id, force=False)

        assert result is False
        # Session should still be in registry since cleanup failed
        assert session_id in _DEBUG_SESSIONS

    def test_cleanup_session_graceful_shutdown_fails_with_force(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that cleanup continues and returns True with force=True."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id, service, _ = populated_session_state
        service.execution.stop = AsyncMock(side_effect=RuntimeError("Stop failed"))

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.clear_session_id"),
            patch("aidb_mcp.session.manager_lifecycle.get_session_id_from_context"),
        ):
            mock_config.session.default_cleanup_timeout = 0.1
            mock_config.session.max_retry_attempts = 1
            mock_config.session.retry_delay = 0.01

            result = cleanup_session(session_id, force=True)

        assert result is True
        assert session_id not in _DEBUG_SESSIONS
        assert session_id not in _SESSION_CONTEXTS

    def test_cleanup_session_uses_config_timeout(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that default_cleanup_timeout is used when timeout is None."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session

        session_id, service, _ = populated_session_state

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.clear_session_id"),
            patch("aidb_mcp.session.manager_lifecycle.get_session_id_from_context"),
            patch(
                "aidb_mcp.session.manager_lifecycle._attempt_graceful_shutdown"
            ) as mock_shutdown,
        ):
            mock_config.session.default_cleanup_timeout = 7.5
            mock_config.session.max_retry_attempts = 3
            mock_config.session.retry_delay = 0.01
            mock_shutdown.return_value = True

            cleanup_session(session_id, timeout=None)

            # Verify the timeout passed to _attempt_graceful_shutdown
            mock_shutdown.assert_called_once()
            call_args = mock_shutdown.call_args
            assert call_args.kwargs.get("timeout") == 7.5 or call_args[0][2] == 7.5

    def test_cleanup_session_service_not_started(
        self,
        mock_debug_service_not_started: MagicMock,
        mock_mcp_session_context: MagicMock,
    ) -> None:
        """Test that cleanup skips graceful shutdown if service.session.started is
        False."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id = "test-not-started"
        _DEBUG_SESSIONS[session_id] = mock_debug_service_not_started
        _SESSION_CONTEXTS[session_id] = mock_mcp_session_context

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.clear_session_id"),
            patch("aidb_mcp.session.manager_lifecycle.get_session_id_from_context"),
        ):
            mock_config.session.default_cleanup_timeout = 5.0
            result = cleanup_session(session_id)

        assert result is True
        # stop() should not be called since service.session.started is False
        mock_debug_service_not_started.execution.stop.assert_not_called()


class TestCleanupSessionAsync:
    """Tests for cleanup_session_async function."""

    async def test_cleanup_session_async_delegates_to_sync(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that async version delegates to sync cleanup."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session_async

        session_id, _, _ = populated_session_state

        with (
            patch("aidb_mcp.session.manager_lifecycle.cleanup_session") as mock_cleanup,
        ):
            mock_cleanup.return_value = True

            result = await cleanup_session_async(session_id, timeout=3.0, force=True)

            assert result is True
            mock_cleanup.assert_called_once_with(session_id, 3.0, True)

    async def test_cleanup_session_async_returns_result(self) -> None:
        """Test that async version returns the cleanup result."""
        from aidb_mcp.session.manager_lifecycle import cleanup_session_async

        with patch(
            "aidb_mcp.session.manager_lifecycle.cleanup_session"
        ) as mock_cleanup:
            mock_cleanup.return_value = False

            result = await cleanup_session_async("test-session")

            assert result is False


class TestCleanupAllSessions:
    """Tests for cleanup_all_sessions function."""

    def test_cleanup_all_sessions_cleans_all(
        self,
        multiple_sessions_state: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that all sessions are cleaned up."""
        from aidb_mcp.session.manager_lifecycle import cleanup_all_sessions
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        assert len(_DEBUG_SESSIONS) == 3

        with (
            patch("aidb_mcp.session.manager_lifecycle.config") as mock_config,
            patch("aidb_mcp.session.manager_lifecycle.clear_session_id"),
            patch("aidb_mcp.session.manager_lifecycle.get_session_id_from_context"),
        ):
            mock_config.session.default_cleanup_timeout = 1.0
            mock_config.session.max_retry_attempts = 1
            mock_config.session.retry_delay = 0.01

            cleanup_all_sessions()

        assert len(_DEBUG_SESSIONS) == 0

    def test_cleanup_all_sessions_empty(self) -> None:
        """Test that cleanup_all_sessions handles empty state."""
        from aidb_mcp.session.manager_lifecycle import cleanup_all_sessions
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        assert len(_DEBUG_SESSIONS) == 0

        # Should not raise
        cleanup_all_sessions()

        assert len(_DEBUG_SESSIONS) == 0
