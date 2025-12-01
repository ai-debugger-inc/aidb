"""Unit tests for DAPTransport.

Tests the low-level DAP transport layer including connection establishment, message
sending/receiving, and buffer management.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.common.errors import DebugConnectionError
from aidb.dap.client.transport import (
    DAP_HEADER_TERMINATOR,
    RECEIVE_BUFFER_SIZE,
    DAPTransport,
)


class TestDAPTransportInit:
    """Tests for DAPTransport initialization."""

    def test_init_stores_host_and_port(self, mock_ctx):
        """DAPTransport stores host and port."""
        transport = DAPTransport(host="127.0.0.1", port=5678, ctx=mock_ctx)

        assert transport._host == "127.0.0.1"
        assert transport._port == 5678

    def test_init_reader_writer_none(self, mock_ctx):
        """DAPTransport initializes reader/writer as None."""
        transport = DAPTransport(host="127.0.0.1", port=5678, ctx=mock_ctx)

        assert transport._reader is None
        assert transport._writer is None

    def test_init_buffer_empty(self, mock_ctx):
        """DAPTransport initializes receive buffer empty."""
        transport = DAPTransport(host="127.0.0.1", port=5678, ctx=mock_ctx)

        assert transport._receive_buffer == b""


class TestConnect:
    """Tests for connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_ctx):
        """Connect establishes connection successfully."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False

        with patch(
            "aidb.dap.client.transport.asyncio.wait_for",
            new_callable=AsyncMock,
        ) as mock_wait:
            mock_wait.return_value = (mock_reader, mock_writer)
            await transport.connect()

        assert transport._reader == mock_reader
        assert transport._writer == mock_writer

    @pytest.mark.asyncio
    async def test_connect_tries_ipv6_on_ipv4_failure(self, mock_ctx):
        """Connect tries IPv6 when IPv4 fails for localhost."""
        transport = DAPTransport("localhost", 5678, mock_ctx)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False

        # First attempt (IPv4) fails, second (IPv6) succeeds
        with patch(
            "aidb.dap.client.transport.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=[OSError("IPv4 failed"), (mock_reader, mock_writer)],
        ):
            await transport.connect()

        assert transport._reader is not None
        assert transport._writer is not None

    @pytest.mark.asyncio
    async def test_connect_raises_on_all_failures(self, mock_ctx):
        """Connect raises DebugConnectionError when all attempts fail."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        with patch(
            "aidb.dap.client.transport.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=OSError("Connection refused"),
        ):
            with pytest.raises(DebugConnectionError, match="Failed to connect"):
                await transport.connect()

    @pytest.mark.asyncio
    async def test_connect_timeout(self, mock_ctx):
        """Connect raises DebugConnectionError on timeout."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        with patch(
            "aidb.dap.client.transport.asyncio.wait_for",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            with pytest.raises(DebugConnectionError, match="Failed to connect"):
                await transport.connect(timeout=1.0)


class TestDisconnect:
    """Tests for disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_closes_writer(self, mock_ctx):
        """Disconnect closes writer properly."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        transport._writer = mock_writer
        transport._reader = MagicMock()

        await transport.disconnect()

        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_awaited_once()
        assert transport._writer is None
        assert transport._reader is None

    @pytest.mark.asyncio
    async def test_disconnect_handles_error(self, mock_ctx):
        """Disconnect handles close errors gracefully."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock(side_effect=RuntimeError("Close failed"))
        transport._writer = mock_writer

        await transport.disconnect()

        assert transport._writer is None

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, mock_ctx):
        """Disconnect handles already disconnected state."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        await transport.disconnect()


class TestSendMessage:
    """Tests for send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_ctx):
        """send_message sends properly formatted message."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        transport._writer = mock_writer

        message = MagicMock()
        message.to_dap_message.return_value = b'Content-Length: 10\r\n\r\n{"test":1}'
        message.to_json.return_value = '{"test":1}'

        await transport.send_message(message)

        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_not_connected(self, mock_ctx):
        """send_message raises when not connected."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        message = MagicMock()

        with pytest.raises(DebugConnectionError, match="Not connected"):
            await transport.send_message(message)

    @pytest.mark.asyncio
    async def test_send_message_write_error(self, mock_ctx):
        """send_message raises on write error."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.write = MagicMock(side_effect=OSError("Write failed"))
        transport._writer = mock_writer

        message = MagicMock()
        message.to_dap_message.return_value = b"test"

        with pytest.raises(DebugConnectionError, match="Failed to send"):
            await transport.send_message(message)


class TestReceiveMessage:
    """Tests for receive_message method."""

    @pytest.mark.asyncio
    async def test_receive_message_not_connected(self, mock_ctx):
        """receive_message raises when not connected."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        with pytest.raises(DebugConnectionError, match="Not connected"):
            await transport.receive_message()

    @pytest.mark.asyncio
    async def test_receive_message_from_buffer(self, mock_ctx):
        """receive_message parses complete message from buffer."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._reader = MagicMock()

        body = json.dumps({"type": "response", "command": "test"}).encode()
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        transport._receive_buffer = header + body

        result = await transport.receive_message()

        assert result["type"] == "response"
        assert result["command"] == "test"

    @pytest.mark.asyncio
    async def test_receive_message_waits_for_data(self, mock_ctx):
        """receive_message waits for data when buffer incomplete."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        mock_reader = AsyncMock()
        body = json.dumps({"type": "event", "event": "stopped"}).encode()
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        mock_reader.read = AsyncMock(return_value=header + body)
        transport._reader = mock_reader

        with patch(
            "aidb.dap.client.transport.asyncio.wait_for",
            new_callable=AsyncMock,
            return_value=header + body,
        ):
            result = await transport.receive_message()

        assert result["type"] == "event"
        assert result["event"] == "stopped"


class TestTryParseMessage:
    """Tests for _try_parse_message method."""

    def test_try_parse_message_incomplete_header(self, mock_ctx):
        """_try_parse_message returns None for incomplete header."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"Content-Length: 10"

        result = transport._try_parse_message()

        assert result is None

    def test_try_parse_message_incomplete_body(self, mock_ctx):
        """_try_parse_message returns None for incomplete body."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"Content-Length: 100\r\n\r\n{}"

        result = transport._try_parse_message()

        assert result is None

    def test_try_parse_message_success(self, mock_ctx):
        """_try_parse_message parses complete message."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        body = b'{"type":"response"}'
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        transport._receive_buffer = header + body

        result = transport._try_parse_message()

        assert result == {"type": "response"}
        assert transport._receive_buffer == b""

    def test_try_parse_message_preserves_remaining(self, mock_ctx):
        """_try_parse_message preserves remaining data in buffer."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        body1 = b'{"seq":1}'
        body2 = b'{"seq":2}'
        header1 = f"Content-Length: {len(body1)}\r\n\r\n".encode()
        header2 = f"Content-Length: {len(body2)}\r\n\r\n".encode()
        transport._receive_buffer = header1 + body1 + header2 + body2

        result1 = transport._try_parse_message()
        result2 = transport._try_parse_message()

        assert result1 == {"seq": 1}
        assert result2 == {"seq": 2}

    def test_try_parse_message_invalid_json(self, mock_ctx):
        """_try_parse_message returns None for invalid JSON."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        body = b"not valid json"
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        transport._receive_buffer = header + body

        result = transport._try_parse_message()

        assert result is None


class TestParseContentLength:
    """Tests for _parse_content_length method."""

    def test_parse_content_length_success(self, mock_ctx):
        """_parse_content_length extracts length from header."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"Content-Length: 42\r\n\r\nbody"

        result = transport._parse_content_length("Content-Length: 42", 18)

        assert result == 42

    def test_parse_content_length_missing(self, mock_ctx):
        """_parse_content_length returns None for missing header."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"Other-Header: value\r\n\r\n"

        result = transport._parse_content_length("Other-Header: value", 19)

        assert result is None

    def test_parse_content_length_invalid(self, mock_ctx):
        """_parse_content_length returns None for invalid value."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"Content-Length: abc\r\n\r\n"

        result = transport._parse_content_length("Content-Length: abc", 19)

        assert result is None


class TestIsConnected:
    """Tests for is_connected method."""

    def test_is_connected_true(self, mock_ctx):
        """is_connected returns True when connected."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        transport._writer = mock_writer

        assert transport.is_connected() is True

    def test_is_connected_false_no_writer(self, mock_ctx):
        """is_connected returns False when no writer."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)

        assert transport.is_connected() is False

    def test_is_connected_false_closing(self, mock_ctx):
        """is_connected returns False when writer closing."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = True
        transport._writer = mock_writer

        assert transport.is_connected() is False


class TestClearBuffer:
    """Tests for clear_buffer method."""

    def test_clear_buffer_empties(self, mock_ctx):
        """clear_buffer empties the receive buffer."""
        transport = DAPTransport("127.0.0.1", 5678, mock_ctx)
        transport._receive_buffer = b"some data in buffer"

        transport.clear_buffer()

        assert transport._receive_buffer == b""


class TestConstants:
    """Tests for module constants."""

    def test_receive_buffer_size(self):
        """RECEIVE_BUFFER_SIZE is reasonable."""
        assert RECEIVE_BUFFER_SIZE == 4096

    def test_dap_header_terminator(self):
        """DAP_HEADER_TERMINATOR is correct."""
        assert DAP_HEADER_TERMINATOR == b"\r\n\r\n"
