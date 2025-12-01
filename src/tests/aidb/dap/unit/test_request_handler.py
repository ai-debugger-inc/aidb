"""Unit tests for RequestHandler.

Tests the DAP request/response handling including sequence numbering, request tracking,
timeout handling, and retry logic.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.common.errors import DebugConnectionError, DebugTimeoutError
from aidb.dap.client.request_handler import RequestHandler
from aidb.dap.protocol.base import Request, Response


class TestRequestHandlerInit:
    """Tests for RequestHandler initialization."""

    def test_init_with_transport(self, mock_ctx, mock_transport):
        """RequestHandler initializes with transport."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        assert handler.transport == mock_transport
        assert handler._seq == 0
        assert handler._pending_requests == {}
        assert handler.retry_manager is None

    def test_init_with_retry_manager(self, mock_ctx, mock_transport):
        """RequestHandler accepts optional retry manager."""
        retry_manager = MagicMock()
        handler = RequestHandler(
            transport=mock_transport,
            ctx=mock_ctx,
            retry_manager=retry_manager,
        )

        assert handler.retry_manager == retry_manager

    def test_set_event_processor(self, mock_ctx, mock_transport):
        """set_event_processor stores reference."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        event_processor = MagicMock()

        handler.set_event_processor(event_processor)

        assert handler._event_processor == event_processor


class TestSequenceNumbering:
    """Tests for sequence number generation."""

    @pytest.mark.asyncio
    async def test_get_next_seq_increments(self, mock_ctx, mock_transport):
        """get_next_seq returns incrementing values."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        seq1 = await handler.get_next_seq()
        seq2 = await handler.get_next_seq()
        seq3 = await handler.get_next_seq()

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    @pytest.mark.asyncio
    async def test_get_current_sequence(self, mock_ctx, mock_transport):
        """get_current_sequence returns current value."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        await handler.get_next_seq()
        await handler.get_next_seq()
        current = await handler.get_current_sequence()

        assert current == 2

    def test_initialize_sequence_sets_to_one(self, mock_ctx, mock_transport):
        """initialize_sequence sets seq to 1 if 0."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        assert handler._seq == 0

        handler.initialize_sequence()

        assert handler._seq == 1

    def test_initialize_sequence_noop_if_not_zero(self, mock_ctx, mock_transport):
        """initialize_sequence does nothing if seq > 0."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        handler._seq = 5

        handler.initialize_sequence()

        assert handler._seq == 5


class TestSendRequest:
    """Tests for send_request method."""

    @pytest.mark.asyncio
    async def test_send_request_success(self, mock_ctx, mock_transport):
        """send_request sends and returns response."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        request = Request(seq=0, command="test")

        async def simulate_response():
            await asyncio.sleep(0.01)
            await handler.handle_response(
                {
                    "seq": 1,
                    "request_seq": 1,
                    "success": True,
                    "command": "test",
                    "type": "response",
                }
            )

        asyncio.create_task(simulate_response())
        response = await handler.send_request(request, timeout=1.0)

        assert response.success is True
        assert response.command == "test"
        mock_transport.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_request_not_connected_raises(self, mock_ctx, mock_transport):
        """send_request raises DebugConnectionError when not connected."""
        mock_transport.is_connected.return_value = False

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        with pytest.raises(DebugConnectionError, match="Not connected"):
            await handler.send_request(request)

    @pytest.mark.asyncio
    async def test_send_request_timeout_raises(self, mock_ctx, mock_transport):
        """send_request raises DebugTimeoutError on timeout."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        with pytest.raises(DebugTimeoutError, match="Timeout"):
            await handler.send_request(request, timeout=0.05)

    @pytest.mark.asyncio
    async def test_send_request_transport_error(self, mock_ctx, mock_transport):
        """send_request raises DebugConnectionError on transport failure."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock(side_effect=OSError("Connection lost"))

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        with pytest.raises(DebugConnectionError, match="Failed to send"):
            await handler.send_request(request)


class TestSendRequestNoWait:
    """Tests for send_request_no_wait method."""

    @pytest.mark.asyncio
    async def test_send_request_no_wait_returns_seq(self, mock_ctx, mock_transport):
        """send_request_no_wait sends and returns sequence number."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)

        assert seq == 1
        mock_transport.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_request_no_wait_not_connected(self, mock_ctx, mock_transport):
        """send_request_no_wait raises when not connected."""
        mock_transport.is_connected.return_value = False

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        with pytest.raises(DebugConnectionError, match="Not connected"):
            await handler.send_request_no_wait(request)

    @pytest.mark.asyncio
    async def test_send_request_no_wait_creates_pending(self, mock_ctx, mock_transport):
        """send_request_no_wait creates pending future for later retrieval."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)

        assert seq in handler._pending_requests
        assert isinstance(handler._pending_requests[seq], asyncio.Future)


class TestWaitForResponse:
    """Tests for wait_for_response method."""

    @pytest.mark.asyncio
    async def test_wait_for_response_success(self, mock_ctx, mock_transport):
        """wait_for_response returns response when future completes."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)

        async def simulate_response():
            await asyncio.sleep(0.01)
            await handler.handle_response(
                {
                    "seq": 1,
                    "request_seq": seq,
                    "success": True,
                    "command": "test",
                    "type": "response",
                }
            )

        asyncio.create_task(simulate_response())
        response = await handler.wait_for_response(seq, timeout=1.0)

        assert response.success is True

    @pytest.mark.asyncio
    async def test_wait_for_response_timeout(self, mock_ctx, mock_transport):
        """wait_for_response raises DebugTimeoutError on timeout."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)

        with pytest.raises(DebugTimeoutError, match="Timeout waiting"):
            await handler.wait_for_response(seq, timeout=0.05)

    @pytest.mark.asyncio
    async def test_wait_for_response_unknown_seq(self, mock_ctx, mock_transport):
        """wait_for_response raises ValueError for unknown sequence."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        with pytest.raises(ValueError, match="No pending request"):
            await handler.wait_for_response(999)


class TestHandleResponse:
    """Tests for handle_response method."""

    @pytest.mark.asyncio
    async def test_handle_response_completes_future(self, mock_ctx, mock_transport):
        """handle_response completes the pending future."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)
        future = handler._pending_requests[seq]

        await handler.handle_response(
            {
                "seq": 1,
                "request_seq": seq,
                "success": True,
                "command": "test",
                "type": "response",
            }
        )

        assert future.done()
        result = future.result()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_response_no_request_seq_ignored(
        self, mock_ctx, mock_transport
    ):
        """handle_response ignores messages without request_seq."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        await handler.handle_response({"type": "event", "event": "stopped"})

    @pytest.mark.asyncio
    async def test_handle_response_unknown_seq_logged(self, mock_ctx, mock_transport):
        """handle_response logs warning for unknown sequence."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        await handler.handle_response(
            {
                "seq": 1,
                "request_seq": 999,
                "success": True,
                "command": "test",
                "type": "response",
            }
        )

    @pytest.mark.asyncio
    async def test_handle_response_error_response(self, mock_ctx, mock_transport):
        """handle_response handles error responses."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="test")

        seq = await handler.send_request_no_wait(request)

        await handler.handle_response(
            {
                "seq": 1,
                "request_seq": seq,
                "success": False,
                "command": "test",
                "message": "Test error",
                "type": "response",
            }
        )

        future = handler._pending_requests.get(seq)
        assert future is not None
        result = future.result()
        assert result.success is False
        assert result.message == "Test error"


class TestClearPendingRequests:
    """Tests for clear_pending_requests method."""

    @pytest.mark.asyncio
    async def test_clear_pending_requests_cancels_futures(
        self,
        mock_ctx,
        mock_transport,
    ):
        """clear_pending_requests cancels all pending futures."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        seq1 = await handler.send_request_no_wait(Request(seq=0, command="test1"))
        seq2 = await handler.send_request_no_wait(Request(seq=0, command="test2"))

        future1 = handler._pending_requests[seq1]
        future2 = handler._pending_requests[seq2]

        await handler.clear_pending_requests()

        assert future1.cancelled()
        assert future2.cancelled()
        assert len(handler._pending_requests) == 0

    @pytest.mark.asyncio
    async def test_clear_pending_requests_with_error(self, mock_ctx, mock_transport):
        """clear_pending_requests sets exception on futures when error provided."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        seq = await handler.send_request_no_wait(Request(seq=0, command="test"))
        future = handler._pending_requests[seq]

        error = DebugConnectionError("Connection lost")
        await handler.clear_pending_requests(error)

        with pytest.raises(DebugConnectionError):
            future.result()

    @pytest.mark.asyncio
    async def test_clear_all_pending_requests(self, mock_ctx, mock_transport):
        """clear_all_pending_requests clears and cancels all."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        await handler.send_request_no_wait(Request(seq=0, command="test1"))
        await handler.send_request_no_wait(Request(seq=0, command="test2"))

        assert await handler.get_pending_request_count() == 2

        await handler.clear_all_pending_requests()

        assert await handler.get_pending_request_count() == 0


class TestRetryLogic:
    """Tests for request retry logic."""

    @pytest.mark.asyncio
    async def test_should_retry_false_when_already_retry(
        self,
        mock_ctx,
        mock_transport,
    ):
        """_should_retry returns False when is_retry is True."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=1, command="test")

        result = await handler._should_retry(request, is_retry=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_false_no_retry_manager(
        self,
        mock_ctx,
        mock_transport,
    ):
        """_should_retry returns False when no retry manager."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=1, command="test")

        result = await handler._should_retry(request, is_retry=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_false_when_terminated(self, mock_ctx, mock_transport):
        """_should_retry returns False when session terminated."""
        retry_manager = MagicMock()
        handler = RequestHandler(
            transport=mock_transport,
            ctx=mock_ctx,
            retry_manager=retry_manager,
        )

        event_processor = MagicMock()
        event_processor._state = MagicMock()
        event_processor._state.terminated = True
        handler.set_event_processor(event_processor)

        request = Request(seq=1, command="test")
        result = await handler._should_retry(request, is_retry=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_false_when_disconnected(
        self,
        mock_ctx,
        mock_transport,
    ):
        """_should_retry returns False when transport disconnected."""
        mock_transport.is_connected.return_value = False
        retry_manager = MagicMock()

        handler = RequestHandler(
            transport=mock_transport,
            ctx=mock_ctx,
            retry_manager=retry_manager,
        )

        request = Request(seq=1, command="test")
        result = await handler._should_retry(request, is_retry=False)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_retry_checks_retry_config(self, mock_ctx, mock_transport):
        """_should_retry returns True when retry config exists."""
        mock_transport.is_connected.return_value = True
        retry_manager = MagicMock()
        retry_manager.get_retry_config.return_value = {"max_retries": 1}

        handler = RequestHandler(
            transport=mock_transport,
            ctx=mock_ctx,
            retry_manager=retry_manager,
        )

        request = Request(seq=1, command="test")
        result = await handler._should_retry(request, is_retry=False)

        assert result is True
        retry_manager.get_retry_config.assert_called_once_with("test", None)


class TestSendExecutionRequest:
    """Tests for send_execution_request method."""

    @pytest.mark.asyncio
    async def test_send_execution_request_not_connected(
        self,
        mock_ctx,
        mock_transport,
    ):
        """send_execution_request raises when not connected."""
        mock_transport.is_connected.return_value = False

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=0, command="next")

        with pytest.raises(DebugConnectionError, match="Not connected"):
            await handler.send_execution_request(request)

    @pytest.mark.asyncio
    async def test_send_execution_request_continue_returns_immediately(
        self,
        mock_ctx,
        mock_transport,
    ):
        """send_execution_request for continue returns synthetic response."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        from tests._fixtures.unit.builders import DAPRequestBuilder

        request = DAPRequestBuilder.continue_request(thread_id=1)
        response = await handler.send_execution_request(request)

        assert response.success is True
        assert response.message == "Continue sent"

    @pytest.mark.asyncio
    async def test_send_execution_request_waits_for_stopped(
        self,
        mock_ctx,
        mock_transport,
    ):
        """send_execution_request waits for stopped event."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        event_processor = MagicMock()
        stopped_future: asyncio.Future = asyncio.Future()
        terminated_future: asyncio.Future = asyncio.Future()
        event_processor.register_stopped_listener.return_value = stopped_future
        event_processor.register_terminated_listener.return_value = terminated_future
        handler.set_event_processor(event_processor)

        request = Request(seq=0, command="next")

        async def signal_stopped():
            await asyncio.sleep(0.01)
            stopped_future.set_result(MagicMock())

        asyncio.create_task(signal_stopped())

        response = await handler.send_execution_request(request, timeout=1.0)

        assert response.success is True
        assert response.message == "Execution stopped"


class TestSyntheticResponses:
    """Tests for synthetic response creation."""

    def test_create_terminated_response(self, mock_ctx, mock_transport):
        """_create_terminated_response creates correct response."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=5, command="continue")

        response = handler._create_terminated_response(request)

        assert response.success is True
        assert response.request_seq == 5
        assert response.command == "continue"
        assert response.message == "Session terminated"

    def test_create_stopped_response(self, mock_ctx, mock_transport):
        """_create_stopped_response creates correct response."""
        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)
        request = Request(seq=5, command="next")

        response = handler._create_stopped_response(request)

        assert response.success is True
        assert response.request_seq == 5
        assert response.command == "next"
        assert response.message == "Execution stopped"


class TestPendingRequestCount:
    """Tests for pending request tracking."""

    @pytest.mark.asyncio
    async def test_get_pending_request_count(self, mock_ctx, mock_transport):
        """get_pending_request_count returns correct count."""
        mock_transport.is_connected.return_value = True
        mock_transport.send_message = AsyncMock()

        handler = RequestHandler(transport=mock_transport, ctx=mock_ctx)

        assert await handler.get_pending_request_count() == 0

        await handler.send_request_no_wait(Request(seq=0, command="test1"))
        assert await handler.get_pending_request_count() == 1

        await handler.send_request_no_wait(Request(seq=0, command="test2"))
        assert await handler.get_pending_request_count() == 2
