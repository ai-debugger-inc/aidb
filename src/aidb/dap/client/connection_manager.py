"""Connection management for DAP client.

This module handles connection lifecycle, recovery, and status monitoring.
"""

import asyncio
import time
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.constants import (
    CONNECTION_TIMEOUT_S,
    DISCONNECT_TIMEOUT_S,
    EVENT_POLL_TIMEOUT_S,
    INITIAL_RETRY_DELAY_S,
    MEDIUM_SLEEP_S,
    RECEIVER_STOP_TIMEOUT_S,
)
from aidb.common.errors import DebugConnectionError, DebugTimeoutError
from aidb.dap.client.constants import CommandType
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

    from .events import EventProcessor
    from .receiver import MessageReceiver
    from .request_handler import RequestHandler
    from .state import SessionState
    from .transport import DAPTransport


class ConnectionManager(Obj):
    """Manages DAP connection lifecycle and recovery.

    This class handles:
    - Connection establishment
    - Disconnection and cleanup
    - Connection recovery on failure
    - Connection status monitoring
    """

    def __init__(
        self,
        transport: "DAPTransport",
        state: "SessionState",
        ctx: Optional["IContext"] = None,
    ):
        """Initialize the connection manager.

        Parameters
        ----------
        transport : DAPTransport
            Transport layer for connection
        state : SessionState
            Session state tracker
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self.transport = transport
        self.state = state
        self._receiver: MessageReceiver | None = None
        self._request_handler: RequestHandler | None = None
        self._event_processor: EventProcessor | None = None

    def set_components(
        self,
        receiver: Optional["MessageReceiver"] = None,
        request_handler: Optional["RequestHandler"] = None,
        event_processor: Optional["EventProcessor"] = None,
    ) -> None:
        """Set component references after initialization.

        Parameters
        ----------
        receiver : MessageReceiver, optional
            Message receiver instance
        request_handler : RequestHandler, optional
            Request handler instance
        event_processor : EventProcessor, optional
            Event processor instance
        """
        if receiver:
            self._receiver = receiver
        if request_handler:
            self._request_handler = request_handler
        if event_processor:
            self._event_processor = event_processor

    async def connect(self, timeout: float = CONNECTION_TIMEOUT_S) -> None:
        """Connect to DAP adapter.

        Parameters
        ----------
        timeout : float
            Connection timeout in seconds

        Raises
        ------
        DebugConnectionError
            If connection fails
        DebugTimeoutError
            If connection times out
        """
        self.ctx.info("Connecting to DAP adapter...")

        # Connect transport
        start_time = time.time()
        while not self.transport.is_connected():
            try:
                await self.transport.connect()
                break
            except DebugConnectionError as e:
                if time.time() - start_time > timeout:
                    msg = f"Connection timeout after {timeout}s: {e}"
                    raise DebugTimeoutError(msg, summary="Connection timeout") from e
                self.ctx.debug(f"Connection attempt failed: {e}, retrying...")
                await asyncio.sleep(EVENT_POLL_TIMEOUT_S)

        self.state.connected = True
        self.state.last_response_time = time.time()
        self.state.connection_start_time = time.time()

        # Initialize sequence numbering
        if self._request_handler:
            self._request_handler.initialize_sequence()

        # Start receiver thread if not already running
        if self._receiver and not self._receiver.is_running:
            # Need to pass the client instance, which we don't have here
            # This will need to be handled by the client
            self.ctx.debug("Receiver should be started by client")

        self.ctx.info("Connected to DAP adapter")

    async def disconnect(
        self,
        terminate_debuggee: bool = True,
        restart: bool = False,
        suspend_debuggee: bool = False,
        skip_request: bool = False,
        receiver_stop_timeout: float | None = None,
    ) -> None:
        """Disconnect from DAP adapter and clean up resources.

        Sends a proper DAP DisconnectRequest before closing the transport to ensure the
        debug adapter (e.g., java-debug plugin in JDT LS) properly cleans up its
        internal state. This is critical for pooled debug adapters that will be reused
        for subsequent debug sessions.

        Parameters
        ----------
        terminate_debuggee : bool
            Whether to terminate the debuggee process
        restart : bool
            Whether this is a restart operation
        suspend_debuggee : bool
            Whether to suspend debuggee instead of terminating
        skip_request : bool
            If True, skip sending DisconnectRequest and just close transport,
            stop receiver, clear state. Used for pooled servers that stay alive
            across sessions.
        """
        self.ctx.info("Disconnecting from DAP adapter...")

        disconnect_acknowledged = False

        # Skip DisconnectRequest for pooled servers (prevents freeze/deadlock)
        if skip_request:
            self.ctx.debug(
                "[DISCONNECT] Skipping DisconnectRequest - closing transport only",
            )
            # Jump straight to cleanup
        # Send DAP disconnect request if connected
        # This notifies the debug adapter to clean up internal state before we
        # close the connection. Without this, pooled adapters (like JDT LS)
        # may think the previous session is still active, causing timeouts
        # when starting the next debug session.
        elif self.state.connected and self._request_handler:
            try:
                from aidb.dap.protocol.bodies import DisconnectArguments
                from aidb.dap.protocol.requests import DisconnectRequest

                # Build disconnect request
                # Note: seq=0 will be overwritten by request handler
                request = DisconnectRequest(
                    seq=0,
                    arguments=DisconnectArguments(
                        terminateDebuggee=terminate_debuggee,
                        restart=restart,
                        suspendDebuggee=suspend_debuggee,
                    ),
                )

                # Send with short timeout - adapter might already be terminated
                self.ctx.debug(
                    f"[DISCONNECT] Sending DisconnectRequest "
                    f"(terminateDebuggee={request.arguments.terminateDebuggee}, "
                    f"seq={request.seq})",
                )
                try:
                    response = await self._request_handler.send_request(
                        request,
                        timeout=DISCONNECT_TIMEOUT_S,
                    )
                    # Check if response indicates success
                    if response and hasattr(response, "success") and response.success:
                        disconnect_acknowledged = True
                        self.ctx.debug(
                            f"[DISCONNECT] Response received: "
                            f"success={response.success}",
                        )
                    else:
                        self.ctx.debug(f"[DISCONNECT] Response: {response}")
                except asyncio.TimeoutError:
                    # Non-fatal - adapter may have already terminated
                    self.ctx.debug(
                        "[DISCONNECT] Timeout waiting for response "
                        "(adapter may be terminated)",
                    )
                except Exception as e:
                    # Non-fatal - continue with cleanup even if disconnect fails
                    self.ctx.debug(f"[DISCONNECT] Exception or timeout: {e}")

            except Exception as e:
                # Import or request creation failed - log but continue cleanup
                self.ctx.warning(f"Failed to send disconnect request: {e}")

        # STEP 1: Stop receiver BEFORE disconnecting transport
        # This allows the receiver to exit its read loop gracefully rather than
        # getting interrupted mid-read, which causes ResourceWarnings about
        # unclosed sockets when the event loop closes during parallel tests
        if self._receiver:
            timeout = (
                receiver_stop_timeout
                if receiver_stop_timeout is not None
                else RECEIVER_STOP_TIMEOUT_S
            )
            self.ctx.debug("[DISCONNECT] Stopping receiver before transport disconnect")
            await self._receiver.stop(timeout=timeout)
            self.ctx.debug("[DISCONNECT] Receiver stopped")

        # STEP 2: NOW disconnect transport (reader is no longer being used)
        await self.transport.disconnect()

        # STEP 3: Clear pending requests
        if self._request_handler:
            await self._request_handler.clear_pending_requests(
                error=DebugConnectionError("Connection closed"),
            )

        # Reset state
        self.state.reset()

        # Log final status for diagnostics
        if disconnect_acknowledged:
            self.ctx.info("Disconnected from DAP adapter (acknowledged)")
        else:
            self.ctx.info("Disconnected from DAP adapter (no acknowledgment)")

    async def reconnect(self, timeout: float = CONNECTION_TIMEOUT_S) -> bool:
        """Attempt to reconnect to DAP adapter.

        This method is used for recovering from stale DAP connections in pooled
        adapters. It performs a clean disconnect followed by a fresh connection.

        Parameters
        ----------
        timeout : float
            Connection timeout in seconds

        Returns
        -------
        bool
            True if reconnection successful, False otherwise
        """
        self.ctx.info("Attempting DAP reconnection...")

        try:
            # Step 1: Stop receiver FIRST (before transport disconnect)
            # This allows the receiver to exit gracefully
            if self._receiver:
                await self._receiver.stop(timeout=RECEIVER_STOP_TIMEOUT_S)

            # Step 2: Clean disconnect from stale connection
            # Don't send disconnect request since the connection is likely wedged
            await self.transport.disconnect()

            # Clear pending requests
            if self._request_handler:
                await self._request_handler.clear_pending_requests(
                    error=DebugConnectionError("Reconnection in progress"),
                )

            # Reset state
            self.state.reset()

            # Step 2: Small delay to allow adapter cleanup
            await asyncio.sleep(MEDIUM_SLEEP_S)

            # Step 3: Reconnect
            await self.connect(timeout=timeout)

            # Step 4: Restart receiver if needed
            # The client will need to restart the receiver after reconnection
            self.ctx.debug(
                "Reconnection successful - receiver needs to be restarted by client",
            )

            self.ctx.info("DAP reconnection successful")
            return True

        except Exception as e:
            self.ctx.warning(f"DAP reconnection failed: {e}")
            return False

    async def handle_connection_lost(self, command: str, error: Exception) -> None:
        """Handle connection loss during request.

        Parameters
        ----------
        command : str
            The command that was being executed
        error : Exception
            The error that occurred
        """
        # Connection loss during disconnect/terminate is expected
        if command in [CommandType.DISCONNECT.value, CommandType.TERMINATE.value]:
            self.ctx.debug(f"Connection closed during {command}: {error}")
        else:
            self.ctx.warning(f"Connection lost during {command}: {error}")

        # Mark connection as lost
        self.state.connected = False

        # Clear all pending requests with connection error
        if self._request_handler:
            await self._request_handler.clear_pending_requests(
                error=DebugConnectionError("Connection lost"),
            )

        # Attempt recovery if it's a recoverable command
        if command in ["initialize", "launch", "attach"]:
            self.ctx.info(f"Attempting to recover connection for {command}")
            # Note: Recovery needs to be async, caller must handle
            # await self.attempt_recovery()

    async def attempt_recovery(self) -> None:
        """Attempt to recover lost connection."""
        self.ctx.info("Attempting connection recovery...")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Disconnect cleanly first
                await self.transport.disconnect()

                # Wait a bit before reconnecting
                await asyncio.sleep(INITIAL_RETRY_DELAY_S * (attempt + 1))

                # Try to reconnect
                await self.transport.connect()

                # If successful, update state
                self.state.connected = True
                self.state.last_response_time = time.time()

                self.ctx.info(f"Connection recovered on attempt {attempt + 1}")
                return

            except Exception as e:
                self.ctx.warning(f"Recovery attempt {attempt + 1} failed: {e}")

        self.ctx.error("Failed to recover connection after all attempts")

    async def get_connection_status(self) -> dict[str, Any]:
        """Get detailed connection status and diagnostics.

        Returns
        -------
        Dict[str, Any]
            Connection status information including:
            - connected: Whether currently connected
            - uptime: Connection uptime in seconds
            - transport_connected: Transport layer status
            - pending_requests: Number of pending requests
            - receiver_running: Whether receiver thread is running
            - session state metrics
        """
        # Get basic diagnostics from state
        diagnostics = self.state.get_diagnostics()

        # Add connection-specific info
        diagnostics.update(
            {
                "transport_connected": (
                    self.transport.is_connected() if self.transport else False
                ),
                "pending_requests": (
                    await self._request_handler.get_pending_request_count()
                    if self._request_handler
                    else 0
                ),
                "sequence_number": (
                    await self._request_handler.get_current_sequence()
                    if self._request_handler
                    else 0
                ),
                "receiver_running": (
                    self._receiver.is_running if self._receiver else False
                ),
            },
        )

        # Calculate error rate
        if self.state.total_requests_sent > 0:
            success_rate = (
                self.state.total_responses_received / self.state.total_requests_sent
            )
            diagnostics["success_rate"] = success_rate
            diagnostics["error_rate"] = 1.0 - success_rate
        else:
            diagnostics["success_rate"] = 0.0
            diagnostics["error_rate"] = 0.0

        return diagnostics

    @property
    def is_connected(self) -> bool:
        """Check if connected to DAP adapter.

        Returns
        -------
        bool
            True if connected, False otherwise
        """
        return self.transport.is_connected() and self.state.connected
