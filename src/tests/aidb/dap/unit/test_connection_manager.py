"""Unit tests for ConnectionManager.

Tests the DAP connection lifecycle including connection establishment, disconnection,
reconnection, and status monitoring.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.common.errors import DebugConnectionError, DebugTimeoutError
from aidb.dap.client.connection_manager import ConnectionManager
from aidb.dap.client.state import SessionState


class TestConnectionManagerInit:
    """Tests for ConnectionManager initialization."""

    def test_init_with_transport_and_state(self, mock_ctx, mock_transport):
        """ConnectionManager initializes with transport and state."""
        state = SessionState()
        manager = ConnectionManager(
            transport=mock_transport,
            state=state,
            ctx=mock_ctx,
        )

        assert manager.transport == mock_transport
        assert manager.state == state
        assert manager._receiver is None
        assert manager._request_handler is None
        assert manager._event_processor is None


class TestSetComponents:
    """Tests for set_components method."""

    def test_set_receiver(self, mock_ctx, mock_transport):
        """set_components sets receiver reference."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        receiver = MagicMock()

        manager.set_components(receiver=receiver)

        assert manager._receiver == receiver

    def test_set_request_handler(self, mock_ctx, mock_transport):
        """set_components sets request handler reference."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        handler = MagicMock()

        manager.set_components(request_handler=handler)

        assert manager._request_handler == handler

    def test_set_event_processor(self, mock_ctx, mock_transport):
        """set_components sets event processor reference."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        processor = MagicMock()

        manager.set_components(event_processor=processor)

        assert manager._event_processor == processor

    def test_set_multiple_components(self, mock_ctx, mock_transport):
        """set_components sets multiple components at once."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        receiver = MagicMock()
        handler = MagicMock()

        manager.set_components(receiver=receiver, request_handler=handler)

        assert manager._receiver == receiver
        assert manager._request_handler == handler


class TestConnect:
    """Tests for connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_ctx, mock_transport):
        """Connect establishes connection successfully."""
        state = SessionState()
        # Transport starts disconnected, then connects
        mock_transport.is_connected.side_effect = [False, True]
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        await manager.connect(timeout=5.0)

        mock_transport.connect.assert_awaited_once()
        assert state.connected is True
        assert state.connection_start_time is not None

    @pytest.mark.asyncio
    async def test_connect_initializes_sequence(self, mock_ctx, mock_transport):
        """Connect initializes sequence numbering."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = MagicMock()
        manager.set_components(request_handler=request_handler)

        await manager.connect()

        request_handler.initialize_sequence.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_retries_on_failure(self, mock_ctx):
        """Connect retries when initial connection fails."""
        state = SessionState()

        transport = MagicMock()
        transport.connect = AsyncMock(
            side_effect=[DebugConnectionError("Failed"), None]
        )
        # is_connected: check fails first time, then succeeds after retry
        transport.is_connected = MagicMock(side_effect=[False, False, True])

        manager = ConnectionManager(transport, state, mock_ctx)

        with patch("aidb.dap.client.connection_manager.asyncio.sleep"):
            await manager.connect(timeout=5.0)

        assert transport.connect.await_count == 2
        assert state.connected is True

    @pytest.mark.asyncio
    async def test_connect_timeout(self, mock_ctx):
        """Connect raises DebugTimeoutError on timeout."""
        state = SessionState()

        transport = MagicMock()
        transport.connect = AsyncMock(side_effect=DebugConnectionError("Failed"))
        transport.is_connected = MagicMock(return_value=False)

        manager = ConnectionManager(transport, state, mock_ctx)

        with patch("aidb.dap.client.connection_manager.time.time") as mock_time:
            mock_time.side_effect = [0, 0, 10]
            with patch("aidb.dap.client.connection_manager.asyncio.sleep"):
                with pytest.raises(DebugTimeoutError, match="timeout"):
                    await manager.connect(timeout=5.0)

    @pytest.mark.asyncio
    async def test_connect_updates_response_time(self, mock_ctx, mock_transport):
        """Connect updates last_response_time."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        before = time.time()
        await manager.connect()
        after = time.time()

        assert state.last_response_time >= before
        assert state.last_response_time <= after


class TestDisconnect:
    """Tests for disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_sends_request(self, mock_ctx, mock_transport):
        """Disconnect sends DisconnectRequest when connected."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        await manager.disconnect()

        request_handler.send_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_skips_request_when_skip_request_true(
        self,
        mock_ctx,
        mock_transport,
    ):
        """Disconnect skips DisconnectRequest when skip_request is True."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        await manager.disconnect(skip_request=True)

        request_handler.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_closes_transport(self, mock_ctx, mock_transport):
        """Disconnect closes transport."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        await manager.disconnect()

        mock_transport.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_stops_receiver(self, mock_ctx, mock_transport):
        """Disconnect stops receiver if running."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        receiver = AsyncMock()
        manager.set_components(receiver=receiver)

        await manager.disconnect()

        receiver.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_clears_pending_requests(self, mock_ctx, mock_transport):
        """Disconnect clears pending requests."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        await manager.disconnect()

        request_handler.clear_pending_requests.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self, mock_ctx, mock_transport):
        """Disconnect resets session state."""
        state = SessionState()
        state.connected = True
        state.initialized = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        await manager.disconnect()

        assert state.connected is False
        assert state.initialized is False

    @pytest.mark.asyncio
    async def test_disconnect_with_terminate_debuggee(self, mock_ctx, mock_transport):
        """Disconnect passes terminate_debuggee to request."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        await manager.disconnect(terminate_debuggee=False)

        args = request_handler.send_request.call_args[0]
        assert args[0].arguments.terminateDebuggee is False

    @pytest.mark.asyncio
    async def test_disconnect_handles_timeout(self, mock_ctx, mock_transport):
        """Disconnect handles DisconnectRequest timeout gracefully."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        request_handler = AsyncMock()
        request_handler.send_request.side_effect = asyncio.TimeoutError()
        manager.set_components(request_handler=request_handler)

        await manager.disconnect()

        mock_transport.disconnect.assert_awaited_once()


class TestReconnect:
    """Tests for reconnect method."""

    @pytest.mark.asyncio
    async def test_reconnect_success(self, mock_ctx, mock_transport):
        """Reconnect returns True on success."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        with patch.object(manager, "connect", new_callable=AsyncMock):
            result = await manager.reconnect(timeout=5.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_reconnect_disconnects_first(self, mock_ctx, mock_transport):
        """Reconnect disconnects before reconnecting."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        with patch.object(manager, "connect", new_callable=AsyncMock):
            await manager.reconnect()

        mock_transport.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconnect_stops_receiver(self, mock_ctx, mock_transport):
        """Reconnect stops receiver before reconnecting."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        receiver = AsyncMock()
        manager.set_components(receiver=receiver)

        with patch.object(manager, "connect", new_callable=AsyncMock):
            await manager.reconnect()

        receiver.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconnect_clears_pending_requests(self, mock_ctx, mock_transport):
        """Reconnect clears pending requests."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        with patch.object(manager, "connect", new_callable=AsyncMock):
            await manager.reconnect()

        request_handler.clear_pending_requests.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reconnect_resets_state(self, mock_ctx, mock_transport):
        """Reconnect resets state before reconnecting."""
        state = SessionState()
        state.connected = True
        state.terminated = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        with patch.object(manager, "connect", new_callable=AsyncMock):
            await manager.reconnect()

        assert state.terminated is False

    @pytest.mark.asyncio
    async def test_reconnect_failure(self, mock_ctx, mock_transport):
        """Reconnect returns False on failure."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        with patch.object(
            manager,
            "connect",
            new_callable=AsyncMock,
            side_effect=DebugConnectionError("Failed"),
        ):
            result = await manager.reconnect()

        assert result is False


class TestHandleConnectionLost:
    """Tests for handle_connection_lost method."""

    @pytest.mark.asyncio
    async def test_handle_connection_lost_marks_disconnected(
        self,
        mock_ctx,
        mock_transport,
    ):
        """handle_connection_lost marks state as disconnected."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        await manager.handle_connection_lost("next", RuntimeError("Lost"))

        assert state.connected is False

    @pytest.mark.asyncio
    async def test_handle_connection_lost_clears_pending(
        self,
        mock_ctx,
        mock_transport,
    ):
        """handle_connection_lost clears pending requests."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = AsyncMock()
        manager.set_components(request_handler=request_handler)

        await manager.handle_connection_lost("next", RuntimeError("Lost"))

        request_handler.clear_pending_requests.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_connection_lost_during_disconnect(
        self,
        mock_ctx,
        mock_transport,
    ):
        """handle_connection_lost is expected during disconnect."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        await manager.handle_connection_lost("disconnect", RuntimeError("Lost"))


class TestAttemptRecovery:
    """Tests for attempt_recovery method."""

    @pytest.mark.asyncio
    async def test_attempt_recovery_success(self, mock_ctx):
        """attempt_recovery succeeds on first try."""
        state = SessionState()
        transport = MagicMock()
        transport.disconnect = AsyncMock()
        transport.connect = AsyncMock()

        manager = ConnectionManager(transport, state, mock_ctx)

        with patch("aidb.dap.client.connection_manager.asyncio.sleep"):
            await manager.attempt_recovery()

        assert state.connected is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_retries(self, mock_ctx):
        """attempt_recovery retries on failure."""
        state = SessionState()
        transport = MagicMock()
        transport.disconnect = AsyncMock()
        transport.connect = AsyncMock(
            side_effect=[DebugConnectionError("Failed"), None]
        )

        manager = ConnectionManager(transport, state, mock_ctx)

        with patch("aidb.dap.client.connection_manager.asyncio.sleep"):
            await manager.attempt_recovery()

        assert transport.connect.await_count == 2
        assert state.connected is True

    @pytest.mark.asyncio
    async def test_attempt_recovery_max_attempts(self, mock_ctx):
        """attempt_recovery stops after max attempts."""
        state = SessionState()
        transport = MagicMock()
        transport.disconnect = AsyncMock()
        transport.connect = AsyncMock(side_effect=DebugConnectionError("Failed"))

        manager = ConnectionManager(transport, state, mock_ctx)

        with patch("aidb.dap.client.connection_manager.asyncio.sleep"):
            await manager.attempt_recovery()

        assert transport.connect.await_count == 3
        assert state.connected is False


class TestGetConnectionStatus:
    """Tests for get_connection_status method."""

    @pytest.mark.asyncio
    async def test_get_connection_status_basic(self, mock_ctx, mock_transport):
        """get_connection_status returns basic diagnostics."""
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        status = await manager.get_connection_status()

        assert "connected" in status
        assert "healthy" in status
        assert "transport_connected" in status

    @pytest.mark.asyncio
    async def test_get_connection_status_includes_pending_count(
        self,
        mock_ctx,
        mock_transport,
    ):
        """get_connection_status includes pending request count."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = AsyncMock()
        request_handler.get_pending_request_count.return_value = 5
        manager.set_components(request_handler=request_handler)

        status = await manager.get_connection_status()

        assert status["pending_requests"] == 5

    @pytest.mark.asyncio
    async def test_get_connection_status_includes_sequence(
        self,
        mock_ctx,
        mock_transport,
    ):
        """get_connection_status includes sequence number."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        request_handler = AsyncMock()
        request_handler.get_current_sequence.return_value = 42
        manager.set_components(request_handler=request_handler)

        status = await manager.get_connection_status()

        assert status["sequence_number"] == 42

    @pytest.mark.asyncio
    async def test_get_connection_status_includes_receiver_status(
        self,
        mock_ctx,
        mock_transport,
    ):
        """get_connection_status includes receiver running status."""
        state = SessionState()
        manager = ConnectionManager(mock_transport, state, mock_ctx)
        receiver = MagicMock()
        receiver.is_running = True
        manager.set_components(receiver=receiver)

        status = await manager.get_connection_status()

        assert status["receiver_running"] is True

    @pytest.mark.asyncio
    async def test_get_connection_status_calculates_success_rate(
        self,
        mock_ctx,
        mock_transport,
    ):
        """get_connection_status calculates success rate."""
        state = SessionState()
        state.total_requests_sent = 10
        state.total_responses_received = 8
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        status = await manager.get_connection_status()

        assert status["success_rate"] == 0.8
        assert abs(status["error_rate"] - 0.2) < 0.001


class TestIsConnected:
    """Tests for is_connected property."""

    def test_is_connected_true(self, mock_ctx, mock_transport):
        """is_connected returns True when transport and state connected."""
        mock_transport.is_connected.return_value = True
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        assert manager.is_connected is True

    def test_is_connected_false_transport(self, mock_ctx, mock_transport):
        """is_connected returns False when transport disconnected."""
        mock_transport.is_connected.return_value = False
        state = SessionState()
        state.connected = True
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        assert manager.is_connected is False

    def test_is_connected_false_state(self, mock_ctx, mock_transport):
        """is_connected returns False when state disconnected."""
        mock_transport.is_connected.return_value = True
        state = SessionState()
        state.connected = False
        manager = ConnectionManager(mock_transport, state, mock_ctx)

        assert manager.is_connected is False
