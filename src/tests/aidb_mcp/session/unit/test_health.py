"""Unit tests for MCP session health monitoring.

Tests for health.py functions:
- check_connection_health
- heartbeat_monitor
- attempt_recovery
- start_health_monitoring
- stop_health_monitoring
- get_health_status
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestCheckConnectionHealth:
    """Tests for check_connection_health function."""

    def test_check_connection_health_all_healthy(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that health check returns True when all sessions are healthy."""
        from aidb_mcp.session.health import check_connection_health

        _, api, _ = populated_session_state
        # Ensure session_info access doesn't raise
        api.session_info = MagicMock(id="test-123")

        result = check_connection_health()

        assert result is True

    def test_check_connection_health_specific_session(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that health check can target a specific session."""
        from aidb_mcp.session.health import check_connection_health

        session_id, api, _ = populated_session_state
        api.session_info = MagicMock(id="test-123")

        result = check_connection_health(session_id=session_id)

        assert result is True

    def test_check_connection_health_not_started(
        self,
        mock_debug_api_not_started: MagicMock,
        mock_mcp_session_context: MagicMock,
    ) -> None:
        """Test that health check skips sessions where api.started=False."""
        from aidb_mcp.session.health import check_connection_health
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id = "not-started-session"
        _DEBUG_SESSIONS[session_id] = mock_debug_api_not_started
        _SESSION_CONTEXTS[session_id] = mock_mcp_session_context

        result = check_connection_health()

        # Should return True since session is skipped (not started)
        assert result is True

    def test_check_connection_health_exception(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that health check handles api.session_info exception."""
        from aidb_mcp.session.health import check_connection_health

        _, api, _ = populated_session_state
        # Make session_info access raise
        type(api).session_info = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("Connection lost"))
        )

        result = check_connection_health()

        assert result is False

    def test_check_connection_health_updates_heartbeat(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that health check updates _last_heartbeat on success."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import check_connection_health

        _, api, _ = populated_session_state
        api.session_info = MagicMock(id="test-123")

        initial_heartbeat = health_module._last_heartbeat

        result = check_connection_health()

        assert result is True
        assert health_module._last_heartbeat >= initial_heartbeat

    def test_check_connection_health_empty_sessions(self) -> None:
        """Test that health check returns True with no sessions."""
        from aidb_mcp.session.health import check_connection_health

        result = check_connection_health()

        assert result is True

    def test_check_connection_health_mixed_health(
        self,
        multiple_sessions_state: list[tuple[str, MagicMock, MagicMock]],
    ) -> None:
        """Test that health check returns False if any session is unhealthy."""
        from aidb_mcp.session.health import check_connection_health

        # Make one session unhealthy
        _, api, _ = multiple_sessions_state[1]
        type(api).session_info = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("Connection lost"))
        )

        result = check_connection_health()

        assert result is False


class TestHeartbeatMonitor:
    """Tests for heartbeat_monitor function."""

    async def test_heartbeat_monitor_calls_check_health(self) -> None:
        """Test that heartbeat monitor calls check_connection_health periodically."""
        from aidb_mcp.session.health import heartbeat_monitor

        with (
            patch("aidb_mcp.session.health.check_connection_health") as mock_check,
            patch("aidb_mcp.session.health._heartbeat_interval", 0.01),
        ):
            mock_check.return_value = True

            # Run monitor briefly then cancel
            task = asyncio.create_task(heartbeat_monitor())
            await asyncio.sleep(0.05)
            task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await task

            assert mock_check.call_count >= 1

    async def test_heartbeat_monitor_attempts_recovery_on_failure(self) -> None:
        """Test that heartbeat monitor calls attempt_recovery for unhealthy sessions."""
        from aidb_mcp.session.health import heartbeat_monitor
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        # Add a session that will fail health check
        api = MagicMock()
        api.started = True
        _DEBUG_SESSIONS["test-session"] = api

        with (
            patch(
                "aidb_mcp.session.health.check_connection_health",
                side_effect=[False, False, True],
            ),
            patch(
                "aidb_mcp.session.health.attempt_recovery",
                new_callable=AsyncMock,
            ) as mock_recovery,
            patch("aidb_mcp.session.health._heartbeat_interval", 0.01),
        ):
            mock_recovery.return_value = True

            # Run monitor briefly
            task = asyncio.create_task(heartbeat_monitor())
            await asyncio.sleep(0.05)
            task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await task

            # Recovery should have been attempted at least once
            assert mock_recovery.call_count >= 1

    async def test_heartbeat_monitor_handles_cancelled_error(self) -> None:
        """Test that heartbeat monitor exits gracefully on cancel."""
        from aidb_mcp.session.health import heartbeat_monitor

        with patch("aidb_mcp.session.health._heartbeat_interval", 0.01):
            task = asyncio.create_task(heartbeat_monitor())
            await asyncio.sleep(0.02)
            task.cancel()

            # Should not raise
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_heartbeat_monitor_continues_on_exception(self) -> None:
        """Test that heartbeat monitor continues monitoring after error."""
        from aidb_mcp.session.health import heartbeat_monitor

        call_count = 0

        def check_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "First check failed"
                raise RuntimeError(msg)
            return True

        with (
            patch(
                "aidb_mcp.session.health.check_connection_health",
                side_effect=check_with_error,
            ),
            patch("aidb_mcp.session.health._heartbeat_interval", 0.01),
        ):
            task = asyncio.create_task(heartbeat_monitor())
            await asyncio.sleep(0.05)
            task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await task

            # Should have continued after first error
            assert call_count >= 2


class TestAttemptRecovery:
    """Tests for attempt_recovery function."""

    async def test_attempt_recovery_no_context(
        self,
        mock_debug_api: MagicMock,
    ) -> None:
        """Test that recovery returns False if no context."""
        from aidb_mcp.session.health import attempt_recovery
        from aidb_mcp.session.manager_shared import _DEBUG_SESSIONS

        session_id = "no-context-session"
        _DEBUG_SESSIONS[session_id] = mock_debug_api
        # Don't add to _SESSION_CONTEXTS

        result = await attempt_recovery(session_id)

        assert result is False

    async def test_attempt_recovery_not_started(
        self,
        mock_debug_api: MagicMock,
        mock_mcp_session_context_not_started: MagicMock,
    ) -> None:
        """Test that recovery returns False if session_started=False."""
        from aidb_mcp.session.health import attempt_recovery
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id = "not-started-session"
        _DEBUG_SESSIONS[session_id] = mock_debug_api
        _SESSION_CONTEXTS[session_id] = mock_mcp_session_context_not_started

        result = await attempt_recovery(session_id)

        assert result is False

    async def test_attempt_recovery_no_session_info(
        self,
        mock_debug_api: MagicMock,
        mock_mcp_session_context_no_session_info: MagicMock,
    ) -> None:
        """Test that recovery returns False if no session_info."""
        from aidb_mcp.session.health import attempt_recovery
        from aidb_mcp.session.manager_shared import (
            _DEBUG_SESSIONS,
            _SESSION_CONTEXTS,
        )

        session_id = "no-info-session"
        _DEBUG_SESSIONS[session_id] = mock_debug_api
        _SESSION_CONTEXTS[session_id] = mock_mcp_session_context_no_session_info

        result = await attempt_recovery(session_id)

        assert result is False

    async def test_attempt_recovery_reconnect_success(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that recovery calls reconnect and returns True on success."""
        from aidb_mcp.session.health import attempt_recovery

        session_id, api, context = populated_session_state
        context.session_started = True
        context.session_info = MagicMock(id="original-id")
        api.session = MagicMock()
        api.session.reconnect = MagicMock()

        result = await attempt_recovery(session_id)

        assert result is True
        api.session.reconnect.assert_called_once()

    async def test_attempt_recovery_reconnect_failure(
        self,
        populated_session_state: tuple[str, MagicMock, MagicMock],
    ) -> None:
        """Test that recovery marks session dead on reconnect failure."""
        from aidb_mcp.session.health import attempt_recovery

        session_id, api, context = populated_session_state
        context.session_started = True
        context.session_info = MagicMock(id="original-id")
        api.session = MagicMock()
        api.session.reconnect.side_effect = RuntimeError("Reconnect failed")

        result = await attempt_recovery(session_id)

        assert result is False
        assert context.session_started is False


class TestStartStopHealthMonitoring:
    """Tests for start_health_monitoring and stop_health_monitoring functions."""

    def test_start_health_monitoring_creates_task(self) -> None:
        """Test that start_health_monitoring creates an asyncio task."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import start_health_monitoring

        # Reset task state
        health_module._health_check_task = None

        with patch("aidb_mcp.session.health.heartbeat_monitor"):
            mock_task = MagicMock()
            mock_task.done.return_value = False

            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.create_task.return_value = mock_task

                start_health_monitoring()

                mock_loop.return_value.create_task.assert_called_once()

    def test_start_health_monitoring_no_duplicate(self) -> None:
        """Test that start_health_monitoring doesn't create duplicate task."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import start_health_monitoring

        # Set up existing running task
        existing_task = MagicMock()
        existing_task.done.return_value = False
        health_module._health_check_task = existing_task

        with patch("asyncio.get_event_loop") as mock_loop:
            start_health_monitoring()

            # Should not create new task
            mock_loop.return_value.create_task.assert_not_called()

        # Reset
        health_module._health_check_task = None

    def test_start_health_monitoring_no_event_loop(self) -> None:
        """Test that start_health_monitoring handles RuntimeError gracefully."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import start_health_monitoring

        # Reset task state
        health_module._health_check_task = None

        with patch(
            "asyncio.get_event_loop",
            side_effect=RuntimeError("No event loop"),
        ):
            # Should not raise
            start_health_monitoring()

        # Reset
        health_module._health_check_task = None

    def test_stop_health_monitoring_cancels_task(self) -> None:
        """Test that stop_health_monitoring cancels running task."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import stop_health_monitoring

        # Set up running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        health_module._health_check_task = mock_task

        stop_health_monitoring()

        mock_task.cancel.assert_called_once()

        # Reset
        health_module._health_check_task = None


class TestGetHealthStatus:
    """Tests for get_health_status function."""

    def test_get_health_status_returns_dict(self) -> None:
        """Test that get_health_status returns expected structure."""
        from aidb_mcp.session.health import get_health_status

        result = get_health_status()

        assert isinstance(result, dict)
        assert "healthy" in result
        assert "last_heartbeat" in result
        assert "heartbeat_interval" in result
        assert "monitoring_active" in result
        assert "time_since_heartbeat" in result

    def test_get_health_status_monitoring_inactive(self) -> None:
        """Test health status when monitoring is not active."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import get_health_status

        health_module._health_check_task = None

        result = get_health_status()

        assert result["monitoring_active"] is False

    def test_get_health_status_monitoring_active(self) -> None:
        """Test health status when monitoring is active."""
        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import get_health_status

        mock_task = MagicMock()
        mock_task.done.return_value = False
        health_module._health_check_task = mock_task

        result = get_health_status()

        assert result["monitoring_active"] is True

        # Reset
        health_module._health_check_task = None

    def test_get_health_status_time_since_heartbeat(self) -> None:
        """Test that time_since_heartbeat is calculated correctly."""
        import time

        import aidb_mcp.session.health as health_module
        from aidb_mcp.session.health import get_health_status

        # Set a known heartbeat time
        health_module._last_heartbeat = time.time() - 5.0

        result = get_health_status()

        # Should be approximately 5 seconds
        assert result["time_since_heartbeat"] is not None
        assert result["time_since_heartbeat"] >= 5.0
        assert result["time_since_heartbeat"] < 6.0

        # Reset
        health_module._last_heartbeat = 0
