"""DAP reverse request handling.

This module handles reverse requests from debug adapters to the client. Reverse
requests are when the adapter initiates a request to the client, as opposed to
the normal flow where the client initiates requests.

Currently supports:
    - startDebugging: Used for child debugging sessions
"""

from typing import TYPE_CHECKING, Any

from aidb.dap.protocol.responses import StartDebuggingResponse
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class ReverseRequestHandler(Obj):
    """Handles reverse requests from debug adapters.

    This class processes requests that originate from the debug adapter and sends
    appropriate responses back.
    """

    def __init__(self, transport, ctx: "IContext", session_creation_callback=None):
        """Initialize the reverse request handler.

        Parameters
        ----------
        transport : DAPTransport
            The transport to send responses through
        ctx : IContext
            Context for logging
        session_creation_callback : callable, optional
            Callback function to create child sessions when startDebugging is received.
            Should accept a config dict and return a session ID string.
        """
        super().__init__(ctx)
        self._transport = transport
        self._seq = 0  # Sequence counter for responses
        self._session_creation_callback = session_creation_callback

    def handle_request(self, message: dict[str, Any]) -> None:
        """Handle a reverse request from the adapter.

        Parameters
        ----------
        message : dict
            The request message from the adapter
        """
        command = message.get("command")
        seq = message.get("seq")

        if not command:
            self.ctx.error("Reverse request missing command")
            return

        if seq is None:
            self.ctx.error(f"Reverse request '{command}' missing seq")
            return

        # Route to appropriate handler
        if command == "startDebugging":
            # Create task to handle async startDebugging request
            import asyncio

            asyncio.create_task(self._handle_start_debugging(message))
        else:
            # Unknown reverse request - send error response
            import asyncio

            self.ctx.warning(f"Unsupported reverse request: {command}")
            asyncio.create_task(
                self._send_error_response(seq, command, "Unsupported reverse request"),
            )

    async def _handle_start_debugging(self, message: dict[str, Any]) -> None:
        """Handle a startDebugging reverse request.

        If a session creation callback is configured, it will be invoked to create
        a child session. Otherwise, sends a basic acknowledgment.

        Parameters
        ----------
        message : dict
            The startDebugging request message
        """
        seq = message.get("seq") or 0
        command = message.get("command") or "startDebugging"
        args = message.get("arguments", {})

        self.ctx.debug(f"Received startDebugging request (seq={seq})")

        # Extract configuration for child session
        config = args.get("configuration", {})

        # Generate a sequence number for the response
        response_seq = self._get_next_seq()

        # Try to create a child session if callback is configured
        if self._session_creation_callback:
            try:
                # Invoke callback to create child session
                child_session_id = await self._session_creation_callback(config)
                self.ctx.info(
                    f"Created child session {child_session_id} "
                    f"from startDebugging request",
                )

                # Send success response with child session ID
                response_body = {"sessionId": child_session_id}

                # Pass through any adapter-specific fields (e.g.,
                # __pendingTargetId for vscode-js-debug). Fields starting with
                # "__" are typically adapter-specific extensions.
                adapter_fields = {k: v for k, v in config.items() if k.startswith("__")}
                response_body.update(adapter_fields)

                response = StartDebuggingResponse(
                    seq=response_seq,
                    request_seq=seq,
                    success=True,
                    command=command,
                    extra=response_body,
                )
            except Exception as e:
                # Send error response if child creation fails
                self.ctx.error(f"Failed to create child session: {e}")
                response = StartDebuggingResponse(
                    seq=response_seq,
                    request_seq=seq,
                    success=False,
                    command=command,
                    message=f"Failed to create child session: {str(e)}",
                )
        else:
            # Fallback to basic acknowledgment if no callback configured
            self.ctx.warning(
                "No session creation callback configured - sending basic "
                "acknowledgment",
            )
            response = StartDebuggingResponse(
                seq=response_seq,
                request_seq=seq,
                success=True,
                command=command,
            )

        await self._transport.send_message(response)
        self.ctx.debug(f"Sent startDebugging response (seq={response_seq})")

    def _get_next_seq(self) -> int:
        """Get the next sequence number for a response.

        Returns
        -------
        int
            The next sequence number
        """
        self._seq += 1
        return self._seq

    async def _send_error_response(self, seq: int, command: str, message: str) -> None:
        """Send an error response for a reverse request.

        Parameters
        ----------
        seq : int
            The sequence number of the request
        command : str
            The command that was requested
        message : str
            The error message
        """
        # Create a generic error response Note: We use dict here since we don't
        # have specific error response classes for all possible reverse requests
        response_seq = self._get_next_seq()
        response = {
            "type": "response",
            "seq": response_seq,
            "request_seq": seq,
            "success": False,
            "command": command,
            "message": message,
        }

        await self._transport.send_message(response)
        self.ctx.debug(f"Sent error response for '{command}' (seq={seq}): {message}")
