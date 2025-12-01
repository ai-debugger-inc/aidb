"""Unit tests for MessageReceiver.

Tests the background message receiver including task lifecycle, message handling, and
error recovery.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from aidb.common.errors import DebugConnectionError
from aidb.dap.client.receiver import MessageReceiver, start_receiver
from aidb.dap.client.state import SessionState


class MockDAPClient:
    """Mock DAP client for receiver tests."""

    def __init__(self, ctx):
        """Initialize mock client."""
        self.ctx = ctx
        self.state = SessionState()
        self.transport = MagicMock()
        self.transport.is_connected.return_value = True
        self.transport.receive_message = AsyncMock()
        self.process_message = AsyncMock()
        self._receiver = None

    @property
    def is_terminated(self):
        """Check if session is terminated."""
        return self.state.terminated


class TestMessageReceiverInit:
    """Tests for MessageReceiver initialization."""

    def test_init_stores_client(self, mock_ctx):
        """MessageReceiver stores client reference."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        assert receiver._client == client

    def test_init_not_running(self, mock_ctx):
        """MessageReceiver initializes not running."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        assert receiver._running is False
        assert receiver._task is None

    def test_init_stop_event_cleared(self, mock_ctx):
        """MessageReceiver stop event starts cleared."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        assert not receiver._stop_event.is_set()


class TestStart:
    """Tests for start method."""

    @pytest.mark.asyncio
    async def test_start_creates_task(self, mock_ctx):
        """Start creates asyncio task."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()

        assert receiver._task is not None
        assert receiver._running is True

        # Clean shutdown - task will exit immediately since is_connected=False
        await receiver.stop(timeout=0.1)

    @pytest.mark.asyncio
    async def test_start_idempotent(self, mock_ctx):
        """Start is idempotent when already running."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()
        first_task = receiver._task

        await receiver.start()

        assert receiver._task == first_task

        await receiver.stop(timeout=0.1)

    @pytest.mark.asyncio
    async def test_start_clears_stop_event(self, mock_ctx):
        """Start clears stop event."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)
        receiver._stop_event.set()

        await receiver.start()

        assert not receiver._stop_event.is_set()

        await receiver.stop(timeout=0.1)


class TestStop:
    """Tests for stop method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, mock_ctx):
        """Stop is safe when not running."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_event(self, mock_ctx):
        """Stop sets stop event."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()
        await receiver.stop(timeout=0.1)

        assert receiver._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_waits_for_task(self, mock_ctx):
        """Stop waits for task to complete."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()
        await receiver.stop(timeout=1.0)

        assert receiver._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_on_timeout(self, mock_ctx):
        """Stop cancels task on timeout."""
        client = MockDAPClient(mock_ctx)

        receive_started = asyncio.Event()

        async def slow_receive():
            receive_started.set()
            # Block until cancelled - no arbitrary sleep
            await asyncio.Event().wait()
            return {"type": "event"}

        client.transport.receive_message.side_effect = slow_receive
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()
        # Wait for receive to actually start before stopping
        await asyncio.wait_for(receive_started.wait(), timeout=1.0)
        await receiver.stop(timeout=0.1)


class TestReceiveLoop:
    """Tests for receive loop behavior."""

    @pytest.mark.asyncio
    async def test_receive_loop_processes_messages(self, mock_ctx):
        """Receive loop processes incoming messages."""
        client = MockDAPClient(mock_ctx)

        message_count = 0
        messages_processed = asyncio.Event()

        original_process = client.process_message

        async def track_process(msg):
            await original_process(msg)
            nonlocal message_count
            message_count += 1
            if message_count >= 2:
                messages_processed.set()

        client.process_message = AsyncMock(side_effect=track_process)

        async def receive_then_disconnect():
            if message_count >= 2:
                # After 2 messages, disconnect
                client.transport.is_connected.return_value = False
                msg = "Disconnected"
                raise DebugConnectionError(msg)
            return {"type": "event", "event": "stopped"}

        client.transport.receive_message.side_effect = receive_then_disconnect

        receiver = MessageReceiver(client, mock_ctx)
        await receiver.start()

        # Wait for messages to be processed or timeout
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(messages_processed.wait(), timeout=1.0)

        await receiver.stop(timeout=0.5)

        assert client.process_message.await_count >= 1

    @pytest.mark.asyncio
    async def test_receive_loop_stops_on_terminated(self, mock_ctx):
        """Receive loop stops when session terminated."""
        client = MockDAPClient(mock_ctx)

        message_processed = asyncio.Event()

        original_process = client.process_message

        async def track_and_terminate(msg):
            await original_process(msg)
            # Set terminated flag after processing
            client.state.terminated = True
            message_processed.set()

        client.process_message = AsyncMock(side_effect=track_and_terminate)

        async def receive_once():
            if client.state.terminated:
                # After termination, disconnect to stop loop
                client.transport.is_connected.return_value = False
                msg = "Disconnected after terminate"
                raise DebugConnectionError(msg)
            return {"type": "event", "event": "terminated"}

        client.transport.receive_message.side_effect = receive_once

        receiver = MessageReceiver(client, mock_ctx)
        await receiver.start()

        # Wait for message to be processed
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(message_processed.wait(), timeout=1.0)

        await receiver.stop(timeout=0.5)

        # Verify we processed the terminated event
        assert client.process_message.await_count >= 1


class TestHandleMessage:
    """Tests for _handle_message method."""

    @pytest.mark.asyncio
    async def test_handle_message_passes_to_client(self, mock_ctx):
        """_handle_message passes message to client."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        message = {"type": "event", "event": "stopped"}
        await receiver._handle_message(message)

        client.process_message.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_handle_message_resets_failure_count(self, mock_ctx):
        """_handle_message resets consecutive failure count."""
        client = MockDAPClient(mock_ctx)
        client.state.consecutive_failures = 5
        receiver = MessageReceiver(client, mock_ctx)

        message = {"type": "event", "event": "output"}
        await receiver._handle_message(message)

        assert client.state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_handle_message_catches_error(self, mock_ctx):
        """_handle_message catches processing errors."""
        client = MockDAPClient(mock_ctx)
        client.process_message.side_effect = RuntimeError("Process failed")
        receiver = MessageReceiver(client, mock_ctx)

        message = {"type": "event", "event": "stopped"}
        await receiver._handle_message(message)


class TestHandleConnectionError:
    """Tests for _handle_connection_error method."""

    def test_handle_connection_error_stopping(self, mock_ctx):
        """_handle_connection_error during stopping returns True."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)
        receiver._stopping = True

        error = DebugConnectionError("Disconnected")
        result = receiver._handle_connection_error(error)

        assert result is True

    def test_handle_connection_error_timeout(self, mock_ctx):
        """_handle_connection_error on timeout returns False."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        error = DebugConnectionError("timeout occurred")
        result = receiver._handle_connection_error(error)

        assert result is False

    def test_handle_connection_error_marks_disconnected(self, mock_ctx):
        """_handle_connection_error marks client disconnected."""
        client = MockDAPClient(mock_ctx)
        client.state.connected = True
        receiver = MessageReceiver(client, mock_ctx)

        error = DebugConnectionError("Connection lost")
        receiver._handle_connection_error(error)

        assert client.state.connected is False


class TestHandleGeneralError:
    """Tests for _handle_general_error method."""

    @pytest.mark.asyncio
    async def test_handle_general_error_during_stopping(self, mock_ctx):
        """_handle_general_error during stopping returns True."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)
        receiver._stopping = True

        result = await receiver._handle_general_error(RuntimeError("Test"))

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_general_error_increments_failures(self, mock_ctx):
        """_handle_general_error increments failure count."""
        client = MockDAPClient(mock_ctx)
        client.state.consecutive_failures = 0
        receiver = MessageReceiver(client, mock_ctx)

        await receiver._handle_general_error(RuntimeError("Test"))

        assert client.state.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_handle_general_error_stops_after_max_failures(self, mock_ctx):
        """_handle_general_error stops after max consecutive failures."""
        client = MockDAPClient(mock_ctx)
        client.state.consecutive_failures = 4
        receiver = MessageReceiver(client, mock_ctx)

        result = await receiver._handle_general_error(RuntimeError("Test"))

        assert result is True


class TestIsRunning:
    """Tests for is_running property."""

    def test_is_running_false_initially(self, mock_ctx):
        """is_running is False initially."""
        client = MockDAPClient(mock_ctx)
        receiver = MessageReceiver(client, mock_ctx)

        assert receiver.is_running is False

    @pytest.mark.asyncio
    async def test_is_running_true_when_started(self, mock_ctx):
        """is_running is True when task running."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False
        receiver = MessageReceiver(client, mock_ctx)

        await receiver.start()

        assert receiver.is_running is True

        await receiver.stop()


class TestStartReceiver:
    """Tests for start_receiver helper function."""

    @pytest.mark.asyncio
    async def test_start_receiver_creates_and_starts(self, mock_ctx):
        """start_receiver creates and starts receiver."""
        client = MockDAPClient(mock_ctx)
        client.transport.is_connected.return_value = False

        receiver = await start_receiver(client)

        assert receiver is not None
        assert client._receiver == receiver

        await receiver.stop()

    @pytest.mark.asyncio
    async def test_start_receiver_extracts_context(self, mock_ctx):
        """start_receiver extracts context from prefixed logger."""
        mock_prefixed = MagicMock()
        mock_prefixed.ctx = mock_ctx

        client = MockDAPClient(mock_prefixed)
        client.transport.is_connected.return_value = False

        receiver = await start_receiver(client)

        await receiver.stop()
