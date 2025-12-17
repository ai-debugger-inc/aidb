"""DAP transport layer for asyncio stream communication."""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.constants import RECEIVE_POLL_TIMEOUT_S
from aidb.common.errors import DebugConnectionError
from aidb.dap.protocol.base import ProtocolMessage
from aidb.patterns import Obj
from aidb_common.io import is_event_loop_error

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

# DAP protocol constants
RECEIVE_BUFFER_SIZE = 4096
DAP_HEADER_TERMINATOR = b"\r\n\r\n"

# Maximum time to wait for a partial message to complete before giving up
# This prevents infinite hangs when the adapter crashes mid-message
PARTIAL_MESSAGE_TIMEOUT_S = 10.0


class DAPTransport(Obj):
    """Handles raw asyncio stream communication for DAP protocol.

    This class is responsible for:
    - Establishing and maintaining asyncio stream connections
    - Sending DAP messages with proper framing
    - Receiving and parsing DAP messages
    - Async-safe message transmission
    """

    def __init__(self, host: str, port: int, ctx: Optional["IContext"] = None):
        """Initialize DAP transport.

        Parameters
        ----------
        host : str
            Host to connect to
        port : int
            Port to connect to
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._receive_buffer = b""

    async def connect(self, timeout: float = 5.0) -> None:
        """Establish socket connection.

        Parameters
        ----------
        timeout : float
            Connection timeout in seconds

        Raises
        ------
        DebugConnectionError
            If connection cannot be established
        """
        # Try IPv4 first, then IPv6 if it fails
        last_error = None

        # If host is "localhost", try both 127.0.0.1 and ::1
        hosts_to_try = []
        if self._host in ("localhost", "127.0.0.1", "::1"):
            hosts_to_try = ["127.0.0.1", "::1"]
        else:
            hosts_to_try = [self._host]

        for host in hosts_to_try:
            try:
                self.ctx.debug(f"Attempting connection to {host}:{self._port}")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(host, self._port),
                    timeout=timeout,
                )
                self.ctx.debug(f"Connected to DAP adapter at {host}:{self._port}")
                return  # Success!
            except (OSError, asyncio.TimeoutError) as e:
                last_error = e
                self.ctx.debug(f"Failed to connect to {host}:{self._port}: {e}")
                continue

        # If we get here, all attempts failed
        tried = ", ".join(hosts_to_try)
        msg = (
            f"Failed to connect to {self._host}:{self._port} "
            f"(tried {tried}): {last_error}"
        )
        raise DebugConnectionError(msg, summary="Connection failed") from last_error

    async def disconnect(self) -> None:
        """Close stream connection.

        Uses async_lock to prevent racing with send_message() during cleanup. Explicitly
        closes both writer and reader transports to avoid ResourceWarnings about
        unclosed sockets when the event loop closes.

        This method is resilient to event loop mismatches that can occur during
        pytest-xdist parallel test execution - if async lock acquisition fails,
        it falls back to synchronous cleanup.
        """
        # Try async cleanup first, fall back to sync if event loop is mismatched
        try:
            async with self.async_lock:
                await self._close_streams()
        except RuntimeError as e:
            if is_event_loop_error(e):
                # Event loop mismatch - do sync cleanup without lock
                self._close_streams_sync()
            else:
                raise

    async def _close_streams(self) -> None:
        """Close streams asynchronously (requires valid event loop)."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception as e:
                self.ctx.debug(f"Failed to close DAP transport writer: {e}")
            self._writer = None

        self._close_reader_transport()

    def _close_streams_sync(self) -> None:
        """Close streams synchronously (event loop unavailable)."""
        if self._writer:
            try:
                self._writer.close()
                # Can't await wait_closed() without event loop - just close
            except Exception as e:
                self.ctx.debug(f"Failed to close DAP transport writer (sync): {e}")
            self._writer = None

        self._close_reader_transport()

    def _close_reader_transport(self) -> None:
        """Close reader's underlying transport (works sync or async)."""
        if self._reader:
            try:
                # Access the underlying transport from the StreamReader
                transport = getattr(self._reader, "_transport", None)
                if transport and not transport.is_closing():
                    transport.close()
            except Exception as e:
                self.ctx.debug(f"Failed to close reader transport: {e}")
            self._reader = None

    async def send_message(self, message: ProtocolMessage) -> None:
        """Send a DAP protocol message.

        Async-safe message sending with proper DAP framing.

        Parameters
        ----------
        message : ProtocolMessage
            Message to send

        Raises
        ------
        DebugConnectionError
            If not connected or send fails
        """
        if not self._writer:
            msg = "Not connected to DAP adapter"
            raise DebugConnectionError(msg)

        async with self.async_lock:
            try:
                dap_bytes = message.to_dap_message()
                self._writer.write(dap_bytes)
                await self._writer.drain()
                self.ctx.debug(f"Sent DAP message: {message.to_json()}")
            except Exception as e:
                msg = f"Failed to send message: {e}"
                raise DebugConnectionError(msg, summary="Send failed") from e

    async def _read_chunk_with_timeout(self) -> bytes | None:
        """Read a chunk of data with timeout.

        Returns
        -------
        Optional[bytes]
            Chunk of data or None if timeout

        Raises
        ------
        DebugConnectionError
            If reader is closed or connection error
        """
        if not self._reader:
            msg = "Reader closed during receive"
            raise DebugConnectionError(msg)

        try:
            chunk = await asyncio.wait_for(
                self._reader.read(RECEIVE_BUFFER_SIZE),
                timeout=RECEIVE_POLL_TIMEOUT_S,
            )
            if not chunk:
                msg = "Connection closed by remote"
                raise DebugConnectionError(msg)
            return chunk
        except asyncio.TimeoutError:
            return None  # Timeout is OK, just means no data available

    def _handle_timeout_state(self) -> dict[str, Any] | None:
        """Handle timeout state by checking buffer.

        Returns
        -------
        Optional[dict]
            Message if found in buffer, None otherwise

        Raises
        ------
        DebugConnectionError
            If timeout with no partial message
        """
        # Check buffer one more time in case we have a complete message
        message = self._try_parse_message()
        if message:
            return message

        # No complete message and no new data
        if not self._receive_buffer:
            msg = "Receive timeout"
            raise DebugConnectionError(msg)

        # If we have a partial message, keep waiting
        return None

    async def receive_message(self) -> dict[str, Any]:
        """Receive and parse a DAP message.

        Blocking receive that waits for a complete DAP message.

        Returns
        -------
        dict
            Parsed message as dictionary

        Raises
        ------
        DebugConnectionError
            If not connected or receive fails
        """
        if not self._reader:
            msg = "Not connected to DAP adapter"
            raise DebugConnectionError(msg)

        # ALWAYS check buffer first - there might already be a complete message!
        message = self._try_parse_message()
        if message:
            return message

        # Track when we first started waiting for a partial message to complete
        # This prevents infinite hangs if the adapter crashes mid-message
        partial_message_start: float | None = None

        while True:
            # Read next chunk
            try:
                chunk = await self._read_chunk_with_timeout()

                if chunk is None:
                    # No new data received - check for partial message timeout
                    if self._receive_buffer:
                        # We have partial data but no new data arrived
                        if partial_message_start is None:
                            partial_message_start = time.monotonic()
                        elif (
                            time.monotonic() - partial_message_start
                            > PARTIAL_MESSAGE_TIMEOUT_S
                        ):
                            buffer_preview = self._receive_buffer[:100]
                            msg = (
                                f"Partial message timeout after "
                                f"{PARTIAL_MESSAGE_TIMEOUT_S}s - adapter may have "
                                f"crashed mid-message. Buffer: {buffer_preview!r}"
                            )
                            self.ctx.warning(msg)
                            raise DebugConnectionError(
                                msg,
                                summary="Partial message timeout",
                            )

                    # Timeout occurred - check if we have a complete message
                    message = self._handle_timeout_state()
                    if message:
                        return message
                    continue

                # Got new data - reset partial message timeout tracker
                partial_message_start = None

                # Add chunk to buffer
                self._receive_buffer += chunk

                # Try to parse after receiving new data
                message = self._try_parse_message()
                if message:
                    return message

            except (OSError, AttributeError) as e:
                # AttributeError can happen if reader becomes None
                msg = f"Failed to receive message: {e}"
                raise DebugConnectionError(msg, summary="Receive failed") from e

    def _parse_content_length(self, header: str, header_end: int) -> int | None:
        """Parse Content-Length from header.

        Parameters
        ----------
        header : str
            The header string
        header_end : int
            End position of header in buffer

        Returns
        -------
        int or None
            Content length or None if invalid
        """
        for line in header.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    return int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    self.ctx.error(f"Invalid Content-Length header: {line}")
                    # Skip this malformed message
                    self._receive_buffer = self._receive_buffer[header_end + 4 :]
                    return None

        # No Content-Length found
        self.ctx.error("Missing Content-Length header")
        self._receive_buffer = self._receive_buffer[header_end + 4 :]
        return None

    def _log_received_message(self, message: dict[str, Any]) -> None:
        """Log details about received message.

        Parameters
        ----------
        message : dict
            The received message
        """
        msg_type = message.get("type", "unknown")

        if msg_type == "response":
            self.ctx.debug(
                f"Transport received response: {message.get('command', 'unknown')} "
                f"(seq: {message.get('request_seq', '?')}, "
                f"success: {message.get('success', '?')})",
            )
            # Log full payload at TRACE level
            self.ctx.trace(f"Full response: {json.dumps(message, indent=2)}")
        elif msg_type == "event":
            event_name = message.get("event", "unknown")
            self.ctx.debug(f"Transport received event: {event_name}")
            # Log full payload at TRACE level
            self.ctx.trace(f"Full event: {json.dumps(message, indent=2)}")
            if event_name == "initialized":
                self.ctx.info("TRANSPORT: Got initialized event from debugpy!")
        else:
            self.ctx.debug(f"Transport received {msg_type}")
            # Log full payload at TRACE level
            self.ctx.trace(f"Full message: {json.dumps(message, indent=2)}")

    def _try_parse_message(self) -> dict[str, Any] | None:
        """Try to parse a complete message from the buffer.

        Returns
        -------
        dict or None
            Parsed message or None if incomplete
        """
        # Look for header terminator
        header_end = self._receive_buffer.find(DAP_HEADER_TERMINATOR)
        if header_end == -1:
            return None

        # Parse header
        header = self._receive_buffer[:header_end].decode("utf-8")
        content_length = self._parse_content_length(header, header_end)
        if content_length is None:
            return None

        # Check if we have the complete body
        body_start = header_end + 4
        if len(self._receive_buffer) < body_start + content_length:
            # Need more data
            return None

        # Extract and parse body
        body_bytes = self._receive_buffer[body_start : body_start + content_length]
        self._receive_buffer = self._receive_buffer[body_start + content_length :]

        try:
            message = json.loads(body_bytes.decode("utf-8"))
            self._log_received_message(message)
            return message
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self.ctx.error(f"Failed to parse message body: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if transport is connected.

        Returns
        -------
        bool
            True if connected and writer is not closed
        """
        return self._writer is not None and not self._writer.is_closing()

    def clear_buffer(self) -> None:
        """Clear the receive buffer."""
        self._receive_buffer = b""
