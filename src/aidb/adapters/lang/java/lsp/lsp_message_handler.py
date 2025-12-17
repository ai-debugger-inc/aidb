"""LSP message handler for reading and routing messages.

This module handles the message reading loop, parsing LSP wire format, and routing
incoming messages (requests, responses, notifications).
"""

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

from aidb.common.constants import EVENT_QUEUE_POLL_TIMEOUT_S, THREAD_JOIN_TIMEOUT_S
from aidb.patterns.base import Obj

from .lsp_protocol import LSPMessage, LSPProtocol


class LSPMessageHandler(Obj):
    """Message handler for reading and routing LSP messages.

    Handles:
    - Message reading loop from stdout
    - LSP wire format parsing (Content-Length headers)
    - Message routing (responses, requests, notifications)
    - Special event handling (ServiceReady, progress, diagnostics)
    """

    def __init__(self, protocol: LSPProtocol, ctx=None):
        """Initialize the message handler.

        Parameters
        ----------
        protocol : LSPProtocol
            The protocol layer for sending responses
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self.protocol = protocol
        self._reader_task: asyncio.Task | None = None
        self._stderr_drain_task: asyncio.Task | None = None
        self._stop_reader = asyncio.Event()
        self._initialized = asyncio.Event()
        self._service_ready = asyncio.Event()
        self._notifications: list[LSPMessage] = []

        # Work-done progress tracking
        self._progress_by_token: dict[Any, dict[str, Any]] = {}
        self._progress_update = asyncio.Event()

        # Diagnostics tracking for compilation completion
        self._diagnostics_by_uri: dict[str, asyncio.Event] = {}

    async def start(self):
        """Start the message reading loop and stderr drain."""
        if self._reader_task is None or self._reader_task.done():
            self._reader_task = asyncio.create_task(self._read_messages())

        # Start stderr drain to prevent pipe deadlock
        # JDTLS writes errors/diagnostics to stderr - must be consumed
        if self._stderr_drain_task is None or self._stderr_drain_task.done():
            self._stderr_drain_task = asyncio.create_task(self._drain_stderr())

    async def stop(self):
        """Stop the message reading loop and stderr drain."""
        from aidb_common.io.subprocess import close_subprocess_transports

        self._stop_reader.set()
        if self._reader_task and not self._reader_task.done():
            try:
                await asyncio.wait_for(self._reader_task, timeout=THREAD_JOIN_TIMEOUT_S)
            except asyncio.TimeoutError:
                self._reader_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._reader_task

        # Stop stderr drain task
        if self._stderr_drain_task and not self._stderr_drain_task.done():
            self._stderr_drain_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_drain_task

        # Close all subprocess transports to avoid ResourceWarnings
        await close_subprocess_transports(
            self.protocol.process,
            self.ctx,
            "LSP client",
        )

    async def _read_messages(self):
        """Read and process LSP messages from stdout."""
        buffer = b""

        while not self._stop_reader.is_set():
            try:
                # Read available data
                if self.protocol.process.stdout is None:
                    break

                try:
                    chunk = await asyncio.wait_for(
                        self.protocol.process.stdout.read(1024),
                        timeout=EVENT_QUEUE_POLL_TIMEOUT_S,
                    )
                except asyncio.TimeoutError:
                    # Check if we should continue or exit
                    continue

                if not chunk:
                    break

                buffer += chunk

                # Process complete messages
                while True:
                    message, remaining = self._extract_message(buffer)
                    if message is None:
                        break

                    buffer = remaining
                    self._handle_message(message)

            except Exception as e:
                self.ctx.error(f"Error reading LSP messages: {e}")
                break

    async def _drain_stderr(self):
        """Drain stderr to prevent pipe deadlock.

        JDTLS writes diagnostic messages to stderr. If not consumed, the pipe buffer
        fills (~64KB) and JDTLS blocks on write(), causing workspace/executeCommand to
        hang indefinitely.

        This task continuously drains stderr and logs errors for debugging.
        """
        if self.protocol.process.stderr is None:
            return

        lines_logged = 0
        max_initial_lines = 5

        try:
            while not self._stop_reader.is_set():
                try:
                    line = await asyncio.wait_for(
                        self.protocol.process.stderr.readline(),
                        timeout=EVENT_QUEUE_POLL_TIMEOUT_S,
                    )

                    if not line:
                        # Only treat as EOF if process actually terminated
                        if self.protocol.process.returncode is not None:
                            break  # Process ended, true EOF
                        # Empty read but process alive - continue draining
                        continue

                    line_str = line.decode("utf-8", errors="replace").strip()

                    # Log initial output for debugging
                    if lines_logged < max_initial_lines and line_str:
                        self.ctx.debug(
                            f"JDTLS stderr (line {lines_logged + 1}): {line_str}",
                        )
                        lines_logged += 1

                    # Log errors at warning level
                    if "error" in line_str.lower():
                        self.ctx.warning(f"JDTLS stderr ERROR: {line_str}")

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    self.ctx.debug(f"Error draining stderr: {e}")
                    break

        except Exception as e:
            self.ctx.error(f"Fatal error in stderr drain task: {e}")
        finally:
            self.ctx.debug("Stopped JDTLS stderr drain")

    def _extract_message(self, buffer: bytes) -> tuple[dict[str, Any] | None, bytes]:
        """Extract a complete LSP message from the buffer.

        LSP messages use HTTP-like headers with Content-Length.

        Parameters
        ----------
        buffer : bytes
            The current buffer of data

        Returns
        -------
        tuple[Optional[Dict[str, Any]], bytes]
            The extracted message (if complete) and remaining buffer
        """
        # Look for Content-Length header
        header_end = buffer.find(b"\r\n\r\n")
        if header_end == -1:
            return None, buffer

        headers = buffer[:header_end].decode("utf-8")
        content_length = None

        for line in headers.split("\r\n"):
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())
                break

        if content_length is None:
            self.ctx.error("No Content-Length header found")
            return None, buffer[header_end + 4 :]

        # Check if we have the complete message
        content_start = header_end + 4
        content_end = content_start + content_length

        if len(buffer) < content_end:
            return None, buffer  # Need more data

        # Extract and parse the JSON content
        content = buffer[content_start:content_end].decode("utf-8")
        try:
            message = json.loads(content)
            return message, buffer[content_end:]
        except json.JSONDecodeError as e:
            self.ctx.error(f"Failed to parse LSP message: {e}")
            return None, buffer[content_end:]

    def _handle_message(self, data: dict[str, Any]):
        """Handle an incoming LSP message.

        Parameters
        ----------
        data : Dict[str, Any]
            The parsed LSP message
        """
        message = LSPMessage.from_dict(data)

        # Log full LSP messages at TRACE level (protocol-level detail)
        self.ctx.trace(f"LSP message received: {json.dumps(data, indent=2)}")

        if message.id is not None and message.method is None:
            # Response to our request
            self.protocol.register_response(message)
        elif message.method:
            if message.id is not None:
                # Request from server - we need to respond
                self._handle_request(message)
            else:
                # Notification from server
                self._handle_notification(message)

    def _handle_request(self, message: LSPMessage):
        """Handle an incoming request from the server.

        Parameters
        ----------
        message : LSPMessage
            The request message
        """
        self.ctx.debug(f"Received request from server: {message.method}")

        # JDT LS may send various requests that require responses
        result: Any = None

        if message.method == "workspace/configuration":
            # Server is asking for configuration settings
            params = message.params or {}
            items = params.get("items", [])
            result = [None] * len(items)
        elif message.method == "client/registerCapability":
            # Server wants to register a capability
            result = None
        elif message.method == "window/workDoneProgress/create":
            # Server wants to create a progress indicator
            params = message.params or {}
            token = params.get("token")
            if token is not None and token not in self._progress_by_token:
                self._progress_by_token[token] = {
                    "title": None,
                    "active": False,
                    "ended": asyncio.Event(),
                }
            result = None
        elif message.method == "workspace/applyEdit":
            # Server wants to apply an edit - not supported
            result = {"applied": False}
        else:
            # Unknown request
            self.ctx.warning(
                f"Unhandled LSP request from server: {message.method}",
            )
            result = None

        # Send response back to server
        if message.id is not None:
            asyncio.create_task(self.protocol._send_response(message.id, result))

    def _handle_notification(self, message: LSPMessage):
        """Handle an incoming notification from the server.

        Parameters
        ----------
        message : LSPMessage
            The notification message
        """
        self._notifications.append(message)

        # Special handling for initialized notification
        if message.method == "initialized":
            self._initialized.set()

        # Special handling for ServiceReady notification (JDT LS specific)
        if message.method == "language/status":
            params = message.params or {}
            if params.get("type") == "ServiceReady":
                self._service_ready.set()
                self.ctx.debug("JDT LS ServiceReady notification received")

        # Handle $/progress notifications (LSP work-done progress)
        if message.method == "$/progress":
            params = message.params or {}
            token = params.get("token")
            value = params.get("value", {}) or {}
            kind = value.get("kind")
            entry = None
            if token is not None:
                entry = self._progress_by_token.setdefault(
                    token,
                    {"title": None, "active": False, "ended": asyncio.Event()},
                )
            # Update entry based on kind
            if entry is not None:
                if kind == "begin":
                    entry["title"] = value.get("title") or entry.get("title")
                    entry["active"] = True
                elif kind == "report":
                    pass  # Nothing to do for minimal handler
                elif kind == "end":
                    entry["active"] = False
                    ended: asyncio.Event = entry["ended"]
                    if not ended.is_set():
                        ended.set()
            # Notify waiters
            if not self._progress_update.is_set():
                self._progress_update.set()

        # Handle textDocument/publishDiagnostics (compilation complete)
        if message.method == "textDocument/publishDiagnostics":
            params = message.params or {}
            uri = params.get("uri")
            if uri and uri in self._diagnostics_by_uri:
                self._diagnostics_by_uri[uri].set()
                self.ctx.debug(f"Received diagnostics for: {uri}")

        # Filter noisy LSP notifications (window/logMessage, language/progressReport)
        # These spam the logs with hundreds of messages
        if message.method not in ("window/logMessage", "language/progressReport"):
            self.ctx.debug(f"Received notification: {message.method}")

    async def wait_for_service_ready(self, timeout: float = 30.0) -> bool:
        """Wait for JDT LS to send ServiceReady notification.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if ServiceReady was received, False if timeout
        """
        try:
            await asyncio.wait_for(self._service_ready.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            self.ctx.warning(
                f"Timeout waiting for JDT LS ServiceReady after {timeout}s",
            )
            return False

    async def wait_for_diagnostics(
        self,
        file_path: str,
        timeout: float = 5.0,
    ) -> bool:
        """Wait for textDocument/publishDiagnostics after opening a file.

        This indicates JDT LS has completed compilation/analysis of the file.

        Parameters
        ----------
        file_path : str
            Path to the file (will be converted to file:// URI)
        timeout : float
            Maximum seconds to wait

        Returns
        -------
        bool
            True if diagnostics received, False if timeout
        """
        # Normalize to file:// URI for matching
        if not file_path.startswith("file://"):
            file_uri = Path(file_path).as_uri()
        else:
            file_uri = file_path

        # Create event for this URI
        event = asyncio.Event()
        self._diagnostics_by_uri[file_uri] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            # Cleanup
            if file_uri in self._diagnostics_by_uri:
                del self._diagnostics_by_uri[file_uri]

    async def wait_for_maven_import_complete(self, timeout: float = 60.0) -> bool:
        """Wait until an "Importing Maven project(s)" progress completes.

        This uses LSP $/progress notifications if available.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if Maven import completed, False if timeout
        """
        import time

        title_sub = "importing maven project"
        end_time = time.time() + timeout

        # Helper to find matching token entry
        def _find_matching_entry() -> tuple[Any | None, dict[str, Any] | None]:
            for token, entry in self._progress_by_token.items():
                title = (entry.get("title") or "").lower()
                if title_sub in title:
                    return token, entry
            return None, None

        # Fast path: already seen and ended
        _, entry = _find_matching_entry()
        if entry:
            ended_event = entry.get("ended")
            if (
                entry.get("active") is False
                and ended_event is not None
                and ended_event.is_set()
            ):
                return True

        # Wait until begin/end observed or timeout
        while time.time() < end_time:
            # Check for a matching entry
            token, entry = _find_matching_entry()
            if entry:
                ended_event = entry.get("ended")
                if (
                    entry.get("active") is False
                    and ended_event is not None
                    and ended_event.is_set()
                ):
                    return True
                # Wait for this specific token to end
                remaining = max(0.0, end_time - time.time())
                try:
                    await asyncio.wait_for(entry["ended"].wait(), timeout=remaining)
                    return True
                except asyncio.TimeoutError:
                    return False

            # Otherwise wait for any progress update and retry
            remaining = max(0.0, end_time - time.time())
            try:
                await asyncio.wait_for(self._progress_update.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return False
            finally:
                # Reset the update flag for subsequent waits
                if self._progress_update.is_set():
                    self._progress_update.clear()

        return False

    async def reset_session_state(self) -> None:
        """Reset session-specific state for a new debug session.

        Clears:
        - Notifications list
        - Does NOT clear progress or diagnostics (those are stateful)
        """
        notification_count = len(self._notifications)

        self.ctx.debug(
            f"Resetting LSP message handler session state: "
            f"{notification_count} notifications",
        )

        # Clear accumulated state from previous session
        self._notifications.clear()

        self.ctx.debug(
            "LSP message handler session state reset complete",
        )
