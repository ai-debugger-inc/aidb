"""Unit tests for DAPClient.

Tests the main DAPClient class including initialization, connection management, request
handling, event methods, and context manager behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.dap.client.client import DAPClient
from aidb.dap.client.state import SessionState
from aidb.dap.protocol.base import Request
from aidb.dap.protocol.requests import (
    ContinueRequest,
    NextRequest,
    StepInRequest,
    StepOutRequest,
)


class TestDAPClientInit:
    """Tests for DAPClient initialization."""

    def test_init_creates_transport(self, mock_ctx):
        """DAPClient creates transport with host and port."""
        with patch("aidb.dap.client.client.DAPTransport") as mock_transport_cls:
            client = DAPClient(
                ctx=mock_ctx,
                adapter_host="127.0.0.1",
                adapter_port=5678,
            )

            mock_transport_cls.assert_called_once_with("127.0.0.1", 5678, mock_ctx)
            assert client._transport == mock_transport_cls.return_value

    def test_init_creates_session_state(self, mock_ctx):
        """DAPClient creates SessionState."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)

            assert isinstance(client._state, SessionState)

    def test_init_creates_event_processor(self, mock_ctx):
        """DAPClient creates EventProcessor."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.EventProcessor") as mock_ep_cls:
                client = DAPClient(ctx=mock_ctx)

                mock_ep_cls.assert_called_once()
                assert client._event_processor == mock_ep_cls.return_value

    def test_init_creates_request_handler(self, mock_ctx):
        """DAPClient creates RequestHandler."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.RequestHandler") as mock_rh_cls:
                client = DAPClient(ctx=mock_ctx)

                mock_rh_cls.assert_called_once()
                assert client._request_handler == mock_rh_cls.return_value

    def test_init_creates_connection_manager(self, mock_ctx):
        """DAPClient creates ConnectionManager."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                client = DAPClient(ctx=mock_ctx)

                mock_cm_cls.assert_called_once()
                assert client._connection_manager == mock_cm_cls.return_value

    def test_init_with_log_prefix(self, mock_ctx):
        """DAPClient applies log prefix when provided."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.PrefixedLogger") as mock_prefix_cls:
                client = DAPClient(ctx=mock_ctx, log_prefix="[TEST]")

                mock_prefix_cls.assert_called_once_with(mock_ctx, "[TEST]")
                assert client.ctx == mock_prefix_cls.return_value

    def test_init_with_event_bridge(self, mock_ctx):
        """DAPClient stores event bridge reference."""
        with patch("aidb.dap.client.client.DAPTransport"):
            event_bridge = MagicMock()
            parent_session = MagicMock()

            client = DAPClient(
                ctx=mock_ctx,
                event_bridge=event_bridge,
                parent_session=parent_session,
            )

            assert client._event_bridge == event_bridge
            assert client._parent_session == parent_session

    def test_init_no_retry_manager_by_default(self, mock_ctx):
        """DAPClient initializes without retry manager."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)

            assert client._retry_manager is None


class TestConnect:
    """Tests for connect method."""

    @pytest.mark.asyncio
    async def test_connect_delegates_to_connection_manager(self, mock_ctx):
        """Connect calls ConnectionManager.connect."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_start.return_value = MagicMock(is_running=True)

                    client = DAPClient(ctx=mock_ctx)
                    await client.connect(timeout=10.0)

                    mock_cm.connect.assert_awaited_once_with(10.0)

    @pytest.mark.asyncio
    async def test_connect_starts_receiver(self, mock_ctx):
        """Connect starts message receiver."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_receiver = MagicMock(is_running=True)
                    mock_start.return_value = mock_receiver

                    client = DAPClient(ctx=mock_ctx)
                    await client.connect()

                    mock_start.assert_awaited_once_with(client)
                    assert client._receiver == mock_receiver

    @pytest.mark.asyncio
    async def test_connect_skips_receiver_if_running(self, mock_ctx):
        """Connect does not restart receiver if already running."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_receiver = MagicMock(is_running=True)
                    mock_start.return_value = mock_receiver

                    client = DAPClient(ctx=mock_ctx)
                    client._receiver = mock_receiver

                    await client.connect()

                    mock_start.assert_not_awaited()


class TestDisconnect:
    """Tests for disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_delegates_to_connection_manager(self, mock_ctx):
        """Disconnect calls ConnectionManager.disconnect."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_cm = AsyncMock()
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)
                await client.disconnect(
                    terminate_debuggee=True,
                    restart=False,
                )

                mock_cm.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_events(self, mock_ctx):
        """Disconnect cleans up public events."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.PublicEventAPI") as mock_pe_cls:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_pe = AsyncMock()
                    mock_pe_cls.return_value = mock_pe

                    client = DAPClient(ctx=mock_ctx)
                    await client.disconnect()

                    mock_pe.cleanup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_clears_receiver(self, mock_ctx):
        """Disconnect clears receiver reference."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_cm = AsyncMock()
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)
                client._receiver = MagicMock()

                await client.disconnect()

                assert client._receiver is None


class TestReconnect:
    """Tests for reconnect method."""

    @pytest.mark.asyncio
    async def test_reconnect_success(self, mock_ctx):
        """Reconnect returns True on success."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm.reconnect.return_value = True
                    mock_cm_cls.return_value = mock_cm
                    mock_start.return_value = MagicMock(is_running=True)

                    client = DAPClient(ctx=mock_ctx)
                    result = await client.reconnect(timeout=5.0)

                    assert result is True
                    mock_cm.reconnect.assert_awaited_once_with(5.0)

    @pytest.mark.asyncio
    async def test_reconnect_failure(self, mock_ctx):
        """Reconnect returns False on failure."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_cm = AsyncMock()
                mock_cm.reconnect.return_value = False
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)
                result = await client.reconnect()

                assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_restarts_receiver(self, mock_ctx):
        """Reconnect restarts receiver on success."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm.reconnect.return_value = True
                    mock_cm_cls.return_value = mock_cm

                    old_receiver = AsyncMock()
                    new_receiver = MagicMock(is_running=True)
                    mock_start.return_value = new_receiver

                    client = DAPClient(ctx=mock_ctx)
                    client._receiver = old_receiver

                    await client.reconnect()

                    old_receiver.stop.assert_awaited_once()
                    mock_start.assert_awaited_once()
                    assert client._receiver == new_receiver


class TestIsExecutionCommand:
    """Tests for _is_execution_command method."""

    def test_continue_is_execution_command(self, mock_ctx):
        """ContinueRequest is identified as execution command."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            request = MagicMock(spec=ContinueRequest)

            assert client._is_execution_command(request) is True

    def test_next_is_execution_command(self, mock_ctx):
        """NextRequest is identified as execution command."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            request = MagicMock(spec=NextRequest)

            assert client._is_execution_command(request) is True

    def test_step_in_is_execution_command(self, mock_ctx):
        """StepInRequest is identified as execution command."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            request = MagicMock(spec=StepInRequest)

            assert client._is_execution_command(request) is True

    def test_step_out_is_execution_command(self, mock_ctx):
        """StepOutRequest is identified as execution command."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            request = MagicMock(spec=StepOutRequest)

            assert client._is_execution_command(request) is True

    def test_generic_request_not_execution_command(self, mock_ctx):
        """Generic Request is not execution command."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            request = Request(seq=1, command="threads")

            assert client._is_execution_command(request) is False


class TestSendRequest:
    """Tests for send_request method."""

    @pytest.mark.asyncio
    async def test_send_request_standard(self, mock_ctx):
        """send_request uses standard path for non-execution requests."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.RequestHandler") as mock_rh_cls:
                mock_rh = AsyncMock()
                mock_rh_cls.return_value = mock_rh

                client = DAPClient(ctx=mock_ctx)
                request = Request(seq=1, command="threads")

                await client.send_request(request)

                mock_rh.send_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_request_execution(self, mock_ctx):
        """send_request uses execution path for execution requests."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.RequestHandler") as mock_rh_cls:
                mock_rh = AsyncMock()
                mock_rh_cls.return_value = mock_rh

                client = DAPClient(ctx=mock_ctx)
                request = MagicMock(spec=NextRequest)
                request.command = "next"

                await client.send_request(request)

                mock_rh.send_execution_request.assert_awaited_once()


class TestSendRequestNoWait:
    """Tests for send_request_no_wait method."""

    @pytest.mark.asyncio
    async def test_send_request_no_wait_delegates(self, mock_ctx):
        """send_request_no_wait delegates to request handler."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.RequestHandler") as mock_rh_cls:
                mock_rh = AsyncMock()
                mock_rh.send_request_no_wait.return_value = 5
                mock_rh_cls.return_value = mock_rh

                client = DAPClient(ctx=mock_ctx)
                request = Request(seq=0, command="test")

                seq = await client.send_request_no_wait(request)

                assert seq == 5
                mock_rh.send_request_no_wait.assert_awaited_once_with(request)


class TestWaitMethods:
    """Tests for wait_for_* methods."""

    @pytest.mark.asyncio
    async def test_wait_for_stopped(self, mock_ctx):
        """wait_for_stopped delegates to public events."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.PublicEventAPI") as mock_pe_cls:
                mock_pe = AsyncMock()
                # wait_for_stopped_async returns a future that resolves to bool
                inner_future: asyncio.Future[bool] = asyncio.Future()
                inner_future.set_result(True)
                mock_pe.wait_for_stopped_async.return_value = inner_future
                mock_pe_cls.return_value = mock_pe

                client = DAPClient(ctx=mock_ctx)
                result = await client.wait_for_stopped(timeout=5.0)

                assert result is True
                mock_pe.wait_for_stopped_async.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_wait_for_stopped_or_terminated(self, mock_ctx):
        """wait_for_stopped_or_terminated delegates to public events."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.PublicEventAPI") as mock_pe_cls:
                mock_pe = AsyncMock()
                mock_pe.wait_for_stopped_or_terminated_async.return_value = "stopped"
                mock_pe_cls.return_value = mock_pe

                client = DAPClient(ctx=mock_ctx)
                result = await client.wait_for_stopped_or_terminated(timeout=5.0)

                assert result == "stopped"

    @pytest.mark.asyncio
    async def test_wait_for_event(self, mock_ctx):
        """wait_for_event delegates to public events."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.PublicEventAPI") as mock_pe_cls:
                mock_pe = AsyncMock()
                mock_pe.wait_for_event_async.return_value = MagicMock()
                mock_pe_cls.return_value = mock_pe

                client = DAPClient(ctx=mock_ctx)
                result = await client.wait_for_event("stopped", timeout=5.0)

                assert result is True
                mock_pe.wait_for_event_async.assert_awaited_once_with("stopped", 5.0)


class TestEventMethods:
    """Tests for event-related methods."""

    def test_clear_event_clears_flag(self, mock_ctx):
        """clear_event clears the event flag."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.EventProcessor") as mock_ep_cls:
                mock_ep = MagicMock()
                mock_event = MagicMock()
                mock_ep._event_received = {"stopped": mock_event}
                mock_ep_cls.return_value = mock_ep

                client = DAPClient(ctx=mock_ctx)
                client.clear_event("stopped")

                mock_event.clear.assert_called_once()

    def test_get_stop_reason_from_state(self, mock_ctx):
        """get_stop_reason returns reason from state."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            client._state.stop_reason = "breakpoint"

            assert client.get_stop_reason() == "breakpoint"

    def test_get_stop_reason_none_when_not_stopped(self, mock_ctx):
        """get_stop_reason returns None when not stopped."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            client._state.stop_reason = None

            assert client.get_stop_reason() is None


class TestProperties:
    """Tests for property methods."""

    def test_is_connected(self, mock_ctx):
        """is_connected delegates to connection manager."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_cm = MagicMock()
                mock_cm.is_connected = True
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)

                assert client.is_connected is True

    def test_is_stopped(self, mock_ctx):
        """is_stopped returns state from event processor."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.EventProcessor") as mock_ep_cls:
                mock_ep = MagicMock()
                mock_ep._state.stopped = True
                mock_ep_cls.return_value = mock_ep

                client = DAPClient(ctx=mock_ctx)

                assert client.is_stopped is True

    def test_is_terminated(self, mock_ctx):
        """is_terminated returns state from event processor."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.EventProcessor") as mock_ep_cls:
                mock_ep = MagicMock()
                mock_ep._state.terminated = True
                mock_ep_cls.return_value = mock_ep

                client = DAPClient(ctx=mock_ctx)

                assert client.is_terminated is True

    def test_state_property(self, mock_ctx):
        """State property returns session state."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)

            assert isinstance(client.state, SessionState)

    def test_events_property(self, mock_ctx):
        """Events property returns public event API."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)

            assert client.events == client._public_events

    def test_adapter_port_property(self, mock_ctx):
        """adapter_port returns transport port."""
        with patch("aidb.dap.client.client.DAPTransport") as mock_t_cls:
            mock_t = MagicMock()
            mock_t._port = 7890
            mock_t_cls.return_value = mock_t

            client = DAPClient(ctx=mock_ctx)

            assert client.adapter_port == 7890


class TestContextManager:
    """Tests for context manager methods."""

    @pytest.mark.asyncio
    async def test_aenter_connects(self, mock_ctx):
        """__aenter__ calls connect."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_start.return_value = MagicMock(is_running=True)

                    client = DAPClient(ctx=mock_ctx)

                    async with client as c:
                        assert c is client

    @pytest.mark.asyncio
    async def test_aexit_disconnects(self, mock_ctx):
        """__aexit__ calls disconnect."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm_cls.return_value = mock_cm
                    mock_start.return_value = MagicMock(is_running=True)

                    client = DAPClient(ctx=mock_ctx)

                    async with client:
                        pass

                    mock_cm.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aexit_handles_error(self, mock_ctx):
        """__aexit__ handles disconnect errors gracefully."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                with patch("aidb.dap.client.client.start_receiver") as mock_start:
                    mock_cm = AsyncMock()
                    mock_cm.disconnect.side_effect = RuntimeError("Disconnect failed")
                    mock_cm_cls.return_value = mock_cm
                    mock_start.return_value = MagicMock(is_running=True)

                    client = DAPClient(ctx=mock_ctx)

                    async with client:
                        pass


class TestEventForwarding:
    """Tests for event forwarding methods."""

    def test_enable_event_forwarding(self, mock_ctx):
        """enable_event_forwarding sets bridge and parent."""
        with patch("aidb.dap.client.client.DAPTransport"):
            client = DAPClient(ctx=mock_ctx)
            event_bridge = MagicMock()
            parent_session = MagicMock()
            parent_session.id = "test-session"

            client.enable_event_forwarding(event_bridge, parent_session)

            assert client._event_bridge == event_bridge
            assert client._parent_session == parent_session

    def test_ingest_synthetic_event_processes_event(self, mock_ctx):
        """ingest_synthetic_event passes event to processor."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.EventProcessor") as mock_ep_cls:
                mock_ep = MagicMock()
                mock_ep_cls.return_value = mock_ep

                client = DAPClient(ctx=mock_ctx)
                event = MagicMock()
                event.event = "stopped"
                event.body = MagicMock()
                event.body.threadId = 1

                client.ingest_synthetic_event(event)

                mock_ep.process_event.assert_called_once_with(event)


class TestUpdateAdapterPort:
    """Tests for update_adapter_port method."""

    @pytest.mark.asyncio
    async def test_update_adapter_port_no_change(self, mock_ctx):
        """update_adapter_port does nothing if port unchanged."""
        with patch("aidb.dap.client.client.DAPTransport") as mock_t_cls:
            mock_t = MagicMock()
            mock_t._port = 5678
            mock_t_cls.return_value = mock_t

            client = DAPClient(ctx=mock_ctx)
            await client.update_adapter_port(5678)

    @pytest.mark.asyncio
    async def test_update_adapter_port_when_not_connected(self, mock_ctx):
        """update_adapter_port updates port when not connected."""
        with patch("aidb.dap.client.client.DAPTransport") as mock_t_cls:
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_t = MagicMock()
                mock_t._port = 5678
                mock_t_cls.return_value = mock_t
                mock_cm = MagicMock()
                mock_cm.is_connected = False
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)
                await client.update_adapter_port(9999)

                assert mock_t._port == 9999


class TestSetSessionCreationCallback:
    """Tests for set_session_creation_callback method."""

    def test_set_session_creation_callback(self, mock_ctx):
        """set_session_creation_callback sets callback on reverse handler."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ReverseRequestHandler") as mock_rr_cls:
                mock_rr = MagicMock()
                mock_rr_cls.return_value = mock_rr

                client = DAPClient(ctx=mock_ctx)
                callback = MagicMock()

                client.set_session_creation_callback(callback)

                assert mock_rr._session_creation_callback == callback


class TestProcessMessage:
    """Tests for process_message method."""

    @pytest.mark.asyncio
    async def test_process_message_delegates_to_router(self, mock_ctx):
        """process_message delegates to message router."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.MessageRouter") as mock_mr_cls:
                mock_mr = AsyncMock()
                mock_mr_cls.return_value = mock_mr

                client = DAPClient(ctx=mock_ctx)
                message = {"type": "event", "event": "stopped"}

                await client.process_message(message)

                mock_mr.process_message.assert_awaited_once_with(message)


class TestGetConnectionStatus:
    """Tests for get_connection_status method."""

    @pytest.mark.asyncio
    async def test_get_connection_status_delegates(self, mock_ctx):
        """get_connection_status delegates to connection manager."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.ConnectionManager") as mock_cm_cls:
                mock_cm = AsyncMock()
                mock_cm.get_connection_status.return_value = {"connected": True}
                mock_cm_cls.return_value = mock_cm

                client = DAPClient(ctx=mock_ctx)
                status = await client.get_connection_status()

                assert status == {"connected": True}
                mock_cm.get_connection_status.assert_awaited_once()


class TestGetNextSeq:
    """Tests for get_next_seq method."""

    @pytest.mark.asyncio
    async def test_get_next_seq_delegates(self, mock_ctx):
        """get_next_seq delegates to request handler."""
        with patch("aidb.dap.client.client.DAPTransport"):
            with patch("aidb.dap.client.client.RequestHandler") as mock_rh_cls:
                mock_rh = AsyncMock()
                mock_rh.get_next_seq.return_value = 42
                mock_rh_cls.return_value = mock_rh

                client = DAPClient(ctx=mock_ctx)
                seq = await client.get_next_seq()

                assert seq == 42
                mock_rh.get_next_seq.assert_awaited_once()
