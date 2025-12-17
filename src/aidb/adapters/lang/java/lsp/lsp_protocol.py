"""LSP protocol layer for low-level communication.

This module handles the wire protocol for LSP (Language Server Protocol) communication,
including message serialization, request/response correlation, and connection lifecycle.
"""

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from aidb.common.constants import LSP_SHUTDOWN_TIMEOUT_S
from aidb.common.errors import AidbError
from aidb.patterns.base import Obj


@dataclass
class LSPMessage:
    """Represents an LSP message (request, response, or notification)."""

    jsonrpc: str = "2.0"
    id: int | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        msg: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            msg["id"] = self.id
        if self.method:
            msg["method"] = self.method
        if self.params is not None:
            msg["params"] = self.params
        if self.result is not None:
            msg["result"] = self.result
        if self.error is not None:
            msg["error"] = self.error
        return msg

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LSPMessage":
        """Create from dictionary."""
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )


class LSPProtocol(Obj):
    """Low-level LSP protocol communication layer.

    Handles:
    - Request/response correlation with IDs
    - Message serialization to LSP wire format
    - Sending requests and notifications
    - LSP lifecycle (initialize, shutdown, exit)
    """

    def __init__(self, process: asyncio.subprocess.Process, ctx=None):
        """Initialize the LSP protocol handler.

        Parameters
        ----------
        process : asyncio.subprocess.Process
            The LSP server process with stdin/stdout streams
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self.process = process
        self._next_id = 1
        # Store (event, loop) so responses can signal on the correct event loop
        self._pending_requests: dict[
            int,
            tuple[asyncio.Event, asyncio.AbstractEventLoop],
        ] = {}
        self._responses: dict[int, LSPMessage] = {}

    async def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> Any | None:
        """Send a request and wait for response.

        Parameters
        ----------
        method : str
            The LSP method name
        params : Optional[Dict[str, Any]]
            The request parameters
        timeout : float
            Timeout in seconds to wait for response

        Returns
        -------
        Optional[Any]
            The response result, or None if error/timeout

        Raises
        ------
        AidbError
            If the request fails or times out
        """
        # Allow global LSP timeout override for CI environments with slower I/O
        from aidb_common.env import reader

        effective_timeout = (
            reader.read_float("AIDB_JAVA_LSP_TIMEOUT", timeout) or timeout
        )

        request_id = self._next_id
        self._next_id += 1

        # Create request message
        message = LSPMessage(id=request_id, method=method, params=params or {})

        # Register pending request
        event = asyncio.Event()
        loop = asyncio.get_running_loop()
        self._pending_requests[request_id] = (event, loop)

        # Optional diagnostic logging
        diag_enabled = os.environ.get("AIDB_JAVA_DIAG", "0") == "1"
        start_ts = time.monotonic()
        if diag_enabled:
            self.ctx.info(f"[LSP] -> {method} (id={request_id}) start")

        # Send the request
        await self._send_message(message)

        # Wait for response
        try:
            await asyncio.wait_for(event.wait(), timeout=effective_timeout)
        except asyncio.TimeoutError as e:
            del self._pending_requests[request_id]
            elapsed = time.monotonic() - start_ts
            msg = (
                f"LSP request '{method}' timed out after "
                f"{elapsed:.2f}/{effective_timeout:.2f}s"
            )
            self.ctx.error(msg)
            raise AidbError(msg) from e

        # Get and process response
        response = self._responses.pop(request_id)
        del self._pending_requests[request_id]

        if response.error:
            msg = (
                f"LSP request failed: {response.error.get('message', 'Unknown error')}"
            )
            raise AidbError(
                msg,
            )

        if diag_enabled:
            elapsed = time.monotonic() - start_ts
            self.ctx.info(
                f"[LSP] <- {method} (id={request_id}) done in {elapsed:.2f}s",
            )

        return response.result

    async def send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ):
        """Send a notification (no response expected).

        Parameters
        ----------
        method : str
            The LSP method name
        params : Optional[Dict[str, Any]]
            The notification parameters
        """
        message = LSPMessage(method=method, params=params or {})
        await self._send_message(message)

    async def _send_message(self, message: LSPMessage):
        """Send an LSP message to the server.

        Parameters
        ----------
        message : LSPMessage
            The message to send
        """
        # Convert to JSON
        content = json.dumps(message.to_dict())
        content_bytes = content.encode("utf-8")

        # Create LSP wire format with headers
        headers = f"Content-Length: {len(content_bytes)}\r\n\r\n"
        data = headers.encode("utf-8") + content_bytes

        # Send to process stdin
        try:
            if self.process.stdin is None:
                msg = "Process stdin is not available"
                raise AidbError(msg)
            self.process.stdin.write(data)
            await self.process.stdin.drain()

            self.ctx.debug(f"LSP message sent: {content}")
        except Exception as e:
            self.ctx.error(f"Failed to send LSP message: {e}")
            msg = f"Failed to send LSP message: {e}"
            raise AidbError(msg) from e

    async def _send_response(
        self,
        request_id: int,
        result: Any | None = None,
        error: dict[str, Any] | None = None,
    ):
        """Send a response to a server request.

        Parameters
        ----------
        request_id : int
            The ID of the request being responded to
        result : Optional[Any]
            The result to send back
        error : Optional[Dict[str, Any]]
            Error information if the request failed
        """
        message = LSPMessage(id=request_id, result=result, error=error)
        await self._send_message(message)

    async def initialize(
        self,
        root_uri: str,
        initialization_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send initialize request to the language server.

        Parameters
        ----------
        root_uri : str
            The root URI of the workspace
        initialization_options : Optional[Dict[str, Any]]
            Server-specific initialization options

        Returns
        -------
        Dict[str, Any]
            The server capabilities
        """
        params = {
            "processId": None,
            "rootUri": root_uri,
            "capabilities": {
                # Minimal client capabilities
                "workspace": {
                    "executeCommand": {"dynamicRegistration": False},
                    "workspaceFolders": True,
                },
                "textDocument": {},
            },
        }

        if initialization_options:
            params["initializationOptions"] = initialization_options

        result = await self.send_request("initialize", params)

        # Send initialized notification
        await self.send_notification("initialized")

        return result if result is not None else {}

    async def shutdown(self):
        """Send shutdown request to the language server."""
        try:
            await self.send_request("shutdown", timeout=LSP_SHUTDOWN_TIMEOUT_S)
        except Exception as e:
            self.ctx.warning(f"Shutdown request failed: {e}")

    async def exit(self):
        """Send exit notification to the language server."""
        await self.send_notification("exit")

    def register_response(self, message: LSPMessage):
        """Register a response from the message handler.

        This is called by the message handler when it receives a response
        to correlate it with the pending request.

        Parameters
        ----------
        message : LSPMessage
            The response message
        """
        if message.id is not None and message.id in self._pending_requests:
            self._responses[message.id] = message
            try:
                event, loop = self._pending_requests[message.id]
                # Ensure the event is set on the loop where it was created
                loop.call_soon_threadsafe(event.set)
            except Exception:
                # Fallback in case loop is already closed
                with contextlib.suppress(Exception):
                    self._pending_requests[message.id][0].set()

    async def reset_state(self):
        """Reset protocol state for new sessions.

        Clears:
        - Pending requests
        - Response dictionary
        - Resets request ID counter
        """
        self._pending_requests.clear()
        self._responses.clear()
        self._next_id = 1
