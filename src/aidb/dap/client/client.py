"""DAP client request/response handler."""

import asyncio
from typing import TYPE_CHECKING, Any, Literal, Optional

from aidb.common.constants import (
    CONNECTION_TIMEOUT_S,
    DEFAULT_ADAPTER_HOST,
    DEFAULT_PYTHON_DEBUG_PORT,
    DEFAULT_WAIT_TIMEOUT_S,
    DISCONNECT_TIMEOUT_S,
    EVENT_POLL_TIMEOUT_S,
    RECEIVER_STOP_TIMEOUT_S,
)
from aidb.dap.protocol.base import Event, Request, Response
from aidb.dap.protocol.requests import (
    ContinueRequest,
    NextRequest,
    RestartRequest,
    StepBackRequest,
    StepInRequest,
    StepOutRequest,
)
from aidb.dap.response import ResponseRegistry
from aidb.patterns import Obj

from .capabilities import CLIENT_CAPABILITIES
from .connection_manager import ConnectionManager
from .constants import EventType
from .events import EventProcessor
from .logger import PrefixedLogger
from .message_router import MessageRouter
from .public_events import PublicEventAPI
from .receiver import start_receiver
from .request_handler import RequestHandler
from .retry import DAPRetryManager, RetryConfig
from .reverse_requests import ReverseRequestHandler
from .state import SessionState
from .transport import DAPTransport

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

    from .receiver import MessageReceiver


class DAPClient(Obj):
    """Main DAP client providing single entry point for all requests.

    This class is the heart of the new architecture, providing: - Single request
    path that all components use - Proper request/response tracking with futures
    - AidbThread-safe request serialization - Clean separation from event processing
    - Connection recovery for setup commands only

    Key improvements over old design: - No circular dependencies - Event
    handlers never send requests - Single code path for all requests - Proper
    request/response lifecycle management
    """

    # Default timeout for wait operations
    DEFAULT_WAIT_TIMEOUT = CONNECTION_TIMEOUT_S

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        adapter_host: str = DEFAULT_ADAPTER_HOST,
        adapter_port: int = DEFAULT_PYTHON_DEBUG_PORT,
        log_prefix: str | None = None,
        event_bridge: Any | None = None,
        parent_session: Any | None = None,
        session_id: str | None = None,
    ):
        """Initialize DAP client.

        Parameters
        ----------
        ctx : IContext, optional
            Application context for logging
        adapter_host : str
            DAP adapter host
        adapter_port : int
            DAP adapter port
        log_prefix : str, optional
            Prefix for logging messages
        event_bridge : EventBridge, optional
            EventBridge for forwarding events to child sessions
        parent_session : Session, optional
            Parent session reference for event forwarding
        session_id : str, optional
            Session ID for event processor logging and debugging
        """
        # Initialize Obj with provided context
        super().__init__(ctx)

        # Store session_id for audit logging and event processor
        self._session_id = session_id

        # Store the prefixed logger if needed and override our ctx
        if log_prefix and ctx:
            self.ctx = PrefixedLogger(ctx, log_prefix)  # type: ignore[assignment, misc]  # noqa: E501

        self._client_capabilities = CLIENT_CAPABILITIES.copy()

        # Pass context to components (ensure non-None for components that require it)
        effective_ctx = ctx or self.ctx
        self._transport = DAPTransport(adapter_host, adapter_port, ctx)
        self._state = SessionState()
        self._event_processor = EventProcessor(self._state, ctx, session_id=session_id)
        self._public_events = PublicEventAPI(self._event_processor, ctx)
        self._reverse_request_handler = ReverseRequestHandler(
            self._transport,
            effective_ctx,
        )

        # Store EventBridge and parent session for event forwarding
        self._event_bridge = event_bridge
        self._parent_session = parent_session

        # Initialize request handler with retry manager
        self._retry_manager: DAPRetryManager | None = None
        self._request_handler = RequestHandler(
            transport=self._transport,
            ctx=ctx,
            retry_manager=self._retry_manager,
        )

        # Initialize connection manager
        self._connection_manager = ConnectionManager(
            transport=self._transport,
            state=self._state,
            ctx=ctx,
        )
        self._connection_manager.set_components(
            request_handler=self._request_handler,
            event_processor=self._event_processor,
        )

        # Wire event processor to request handler for terminated event handling
        self._request_handler.set_event_processor(self._event_processor)

        # Initialize message router
        self._message_router = MessageRouter(ctx=ctx)
        self._message_router.set_handlers(
            request_handler=self._request_handler,
            event_processor=self._event_processor,
            reverse_request_handler=self._reverse_request_handler,
        )

        # Background receiver (will be set by receiver.py)
        self._receiver: MessageReceiver | None = (
            None  # Store receiver instance for cleanup
        )
        self._response_registry = ResponseRegistry()

        # DAP audit state (initialized on first use)
        self._should_audit_dap: bool | None = None

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
        """
        # Use ConnectionManager for main connection logic
        await self._connection_manager.connect(timeout)

        # Start receiver thread (client-specific, needs 'self')
        if not self._receiver or not self._receiver.is_running:
            self._receiver = await start_receiver(self)
            self._connection_manager.set_components(receiver=self._receiver)
            self.ctx.debug("Started receiver thread")
            # Give receiver thread a moment to start processing
            await asyncio.sleep(EVENT_POLL_TIMEOUT_S)

    async def get_next_seq(self) -> int:
        """Get the next sequence number for DAP messages.

        Returns
        -------
        int
            Next sequence number
        """
        return await self._request_handler.get_next_seq()

    async def disconnect(
        self,
        terminate_debuggee: bool = True,
        restart: bool = False,
        suspend_debuggee: bool = False,
        skip_request: bool = False,
        receiver_stop_timeout: float | None = None,
    ) -> None:
        """Disconnect from DAP adapter.

        Parameters
        ----------
        terminate_debuggee : bool
            Whether to terminate the debuggee process
        restart : bool
            Whether this is a restart operation
        suspend_debuggee : bool
            Whether to suspend debuggee instead of terminating
        skip_request : bool
            If True, close transport without sending DisconnectRequest.
            Used for pooled servers that stay alive across sessions.
        """
        # Let ConnectionManager handle most of the disconnection
        await self._connection_manager.disconnect(
            terminate_debuggee=terminate_debuggee,
            restart=restart,
            suspend_debuggee=suspend_debuggee,
            skip_request=skip_request,
            receiver_stop_timeout=receiver_stop_timeout,
        )

        # Clean up event subscriptions (client-specific)
        await self._public_events.cleanup()

        # Clear our receiver reference
        self._receiver = None

    async def reconnect(self, timeout: float = CONNECTION_TIMEOUT_S) -> bool:
        """Reconnect to DAP adapter with receiver restart.

        This method is used for recovering from stale DAP connections in pooled
        adapters. It performs a clean reconnection and restarts the receiver.

        Parameters
        ----------
        timeout : float
            Connection timeout in seconds

        Returns
        -------
        bool
            True if reconnection successful, False otherwise
        """
        self.ctx.info("Attempting DAP reconnection with receiver restart...")

        try:
            # Step 1: Use connection manager to reconnect
            if not await self._connection_manager.reconnect(timeout):
                self.ctx.error("Connection manager reconnection failed")
                return False

            # Step 2: Restart receiver
            # Stop existing receiver if running
            if self._receiver:
                try:
                    await self._receiver.stop(timeout=RECEIVER_STOP_TIMEOUT_S)
                except Exception as e:
                    self.ctx.debug(f"Error stopping receiver during reconnect: {e}")

            # Start new receiver
            self._receiver = await start_receiver(self)
            self._connection_manager.set_components(receiver=self._receiver)
            self.ctx.debug("Restarted receiver thread after reconnection")

            # Give receiver thread a moment to start processing
            await asyncio.sleep(EVENT_POLL_TIMEOUT_S)

            self.ctx.info("DAP reconnection with receiver restart successful")
            return True

        except Exception as e:
            self.ctx.error(f"DAP reconnection failed: {e}")
            return False

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for audit logging.

        Parameters
        ----------
        session_id : str
            The session ID to use for audit logging
        """
        self._session_id = session_id

    async def send_request(
        self,
        request: Request,
        timeout: float | None = None,
        retry_config: RetryConfig | None = None,
    ) -> Response:
        """Send a DAP request and wait for response.

        This is THE single entry point for all DAP requests. Ensures proper
        sequencing, serialization, and error handling.

        Parameters
        ----------
        request : Request
            The typed DAP request object to send
        timeout : float, optional
            Response timeout (defaults to 30 seconds)
        retry_config : RetryConfig, optional
            Retry configuration. If None, uses default based on command type

        Returns
        -------
        Response
            The typed DAP response

        Raises
        ------
        DebugTimeoutError
            If response not received within timeout
        DebugConnectionError
            If not connected or connection lost
        DebugSessionLostError
            If session lost and command requires active session
        """
        # Handle retry config
        if retry_config is None:
            if hasattr(request, "_retry_config"):
                retry_config = request._retry_config
            else:
                retry_config = DAPRetryManager.get_retry_config(
                    request.command,
                    context={"request": request},
                )

        # Update retry manager if we have a config
        if retry_config:
            if not self._retry_manager:
                self._retry_manager = DAPRetryManager()
            self._request_handler.retry_manager = self._retry_manager

        # Check if this is an execution command that should handle termination
        if self._is_execution_command(request):
            # Use the termination-aware handler for execution commands
            self.ctx.debug(f"Using send_execution_request for {request.command}")
            return await self._request_handler.send_execution_request(
                request,
                timeout or 30.0,
            )
        # Use standard request handling for other commands
        self.ctx.debug(f"Using standard send_request for {request.command}")
        return await self._request_handler.send_request(request, timeout)

    def _is_execution_command(self, request: Request) -> bool:
        """Check if request is an execution command that may terminate.

        Parameters
        ----------
        request : Request
            The request to check

        Returns
        -------
        bool
            True if this is an execution command
        """
        return isinstance(
            request,
            ContinueRequest
            | StepInRequest
            | StepOutRequest
            | StepBackRequest
            | NextRequest
            | RestartRequest,
        )

    async def send_request_no_wait(self, request: Request) -> int:
        """Send a request without waiting for response.

        Used for requests where the response is deferred (e.g., debugpy attach).

        Parameters
        ----------
        request : Request
            The request to send

        Returns
        -------
        int
            The sequence number assigned to the request
        """
        return await self._request_handler.send_request_no_wait(request)

    def set_session_creation_callback(self, callback):
        """Set the callback for creating child sessions.

        Parameters
        ----------
        callback : callable
            Function that accepts a config dict and returns a session ID string
        """
        if self._reverse_request_handler:
            self._reverse_request_handler._session_creation_callback = callback
            self.ctx.debug("Set session creation callback for reverse request handler")

    async def wait_for_response(self, seq: int, timeout: float = 15.0) -> Response:
        """Wait for a specific response by sequence number.

        Used to retrieve deferred responses.

        Parameters
        ----------
        seq : int
            The sequence number to wait for
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        Response
            The response with matching sequence number

        Raises
        ------
        DebugTimeoutError
            If response not received within timeout
        """
        return await self._request_handler.wait_for_response(seq, timeout)

    async def process_message(self, message: dict[str, Any]) -> None:
        """Process a message received from the adapter.

        This method is called by the receiver thread for each message.

        Parameters
        ----------
        message : dict
            The received message
        """
        await self._message_router.process_message(message)

    @property
    def client_capabilities(self) -> dict[str, Any]:
        """Get the client capabilities.

        Returns
        -------
        Dict[str, Any]
            The client capabilities that will be sent to the adapter
        """
        return self._client_capabilities.copy()

    @property
    def state(self) -> SessionState:
        """Get the current session state."""
        return self._state

    @property
    def event_processor(self) -> EventProcessor:
        """Get the event processor."""
        return self._event_processor

    @property
    def transport(self) -> DAPTransport:
        """Get the transport layer."""
        return self._transport

    @property
    def adapter_port(self) -> int:
        """Get the current adapter port."""
        return self._transport._port

    async def update_adapter_port(self, port: int) -> None:
        """Update the adapter port and reconnect if necessary.

        This is used when the adapter process selects a different port than the
        one originally requested (e.g., if the requested port was unavailable).

        Parameters
        ----------
        port : int
            The new port number
        """
        old_port = self._transport._port
        if old_port == port:
            return  # No change needed

        self.ctx.debug(f"Updating DAP client port from {old_port} to {port}")

        # If we're already connected, we need to reconnect to the new port
        was_connected = self.is_connected
        if was_connected:
            self.ctx.debug("Disconnecting from old port to reconnect to new port")
            await self.disconnect()

        # Update the port
        self._transport._port = port

        # Reconnect if we were connected before
        if was_connected:
            self.ctx.debug(f"Reconnecting to new port {port}")
            try:
                await self.connect(timeout=CONNECTION_TIMEOUT_S)
                self.ctx.debug("Successfully reconnected to new port")
            except Exception as e:
                self.ctx.error(f"Failed to reconnect to new port {port}: {e}")
                raise

    @property
    def is_connected(self) -> bool:
        """Check if connected to adapter."""
        return self._connection_manager.is_connected

    @property
    def is_stopped(self) -> bool:
        """Check if the debug session is currently stopped/paused.

        Returns
        -------
        bool
            True if stopped at a breakpoint or pause, False otherwise
        """
        return self._event_processor._state.stopped

    @property
    def is_terminated(self) -> bool:
        """Check if the debug session has terminated.

        Returns
        -------
        bool
            True if the session has terminated, False otherwise
        """
        return self._event_processor._state.terminated

    async def send_request_and_wait_for_event(
        self,
        request: Request,
        event_type: str,
        timeout: float | None = None,
        event_timeout: float = 5.0,
    ) -> Response:
        """Send a DAP request and wait for a specific event.

        This method is useful for operations like continue/step that need to
        wait for a "stopped" event to know the operation is complete.

        Parameters
        ----------
        request : Request
            The typed DAP request object to send
        event_type : str
            Event type to wait for (e.g., "stopped", "terminated")
        timeout : float, optional
            Response timeout for the request (defaults to 30 seconds)
        event_timeout : float
            Timeout for waiting for the event (defaults to 5 seconds)

        Returns
        -------
        Response
            The typed DAP response

        Raises
        ------
        DebugTimeoutError
            If response or event not received within timeout
        DebugConnectionError
            If not connected or connection lost
        """
        return await self._request_handler.send_request_and_wait_for_event(
            request,
            event_type,
            self._event_processor,
            timeout,
            event_timeout,
        )

    async def wait_for_stopped(self, timeout: float = 5.0) -> bool:
        """Wait for the debugger to stop at a breakpoint or pause.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if stopped event received, False if timeout
        """
        future = await self._public_events.wait_for_stopped_async(timeout)
        return await future

    async def wait_for_stopped_or_terminated(
        self,
        timeout: float | None = None,
    ) -> str:
        """Wait for the debugger to stop at a breakpoint or terminate.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds. If not provided, uses default timeout.

        Returns
        -------
        str
            "stopped", "terminated", or "timeout"
        """
        if timeout is None:
            timeout = DEFAULT_WAIT_TIMEOUT_S
        return await self._public_events.wait_for_stopped_or_terminated_async(timeout)

    async def wait_for_event(self, event_type: str, timeout: float = 5.0) -> bool:
        """Wait for a specific DAP event.

        Parameters
        ----------
        event_type : str
            Event type to wait for
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if event received, False if timeout
        """
        event = await self._public_events.wait_for_event_async(event_type, timeout)
        return event is not None

    def clear_event(self, event_type: str) -> None:
        """Clear a specific event flag.

        Use to reset level-triggered events like 'stopped' before sending
        operations (step/continue) that expect a new event.

        Parameters
        ----------
        event_type : str
            The event type to clear (e.g., "stopped", "terminated")
        """
        # Clear event in event processor
        try:
            if event_type in self._event_processor._event_received:
                self._event_processor._event_received[event_type].clear()
                self.ctx.debug(f"Cleared event flag: {event_type}")
            else:
                self.ctx.warning(f"Event type {event_type} not found in event registry")
        except KeyError as e:
            self.ctx.warning(f"Event type {event_type} not found: {e}")
        except Exception as e:
            self.ctx.warning(f"Unexpected error clearing event {event_type}: {e}")

    def get_stop_reason(self) -> str | None:
        """Get the reason for the last stop event.

        Returns
        -------
        str or None
            Stop reason (e.g., "breakpoint", "step", "exception") or None
        """
        return self._state.stop_reason if hasattr(self._state, "stop_reason") else None

    async def get_connection_status(self) -> dict[str, Any]:
        """Get detailed connection status and diagnostics.

        Returns
        -------
        dict
            Detailed connection status
        """
        return await self._connection_manager.get_connection_status()

    @property
    def events(self) -> PublicEventAPI:
        """Get the public event subscription API.

        Returns
        -------
        PublicEventAPI
            The public event API for managing subscriptions
        """
        return self._public_events

    async def __aenter__(self) -> "DAPClient":
        """Enter context manager - connect and start receiver.

        Returns
        -------
        DAPClient
            Self for use in with statement

        """
        await self.connect()
        # Receiver is already started in connect(), no need to start again
        return self

    def enable_event_forwarding(
        self,
        event_bridge: Any | None,
        parent_session: Any | None,
    ) -> None:
        """Enable event forwarding to child sessions.

        This method provides a clean API for setting up event forwarding without
        reaching into private attributes.

        Parameters
        ----------
        event_bridge : EventBridge, optional
            The EventBridge instance for forwarding events
        parent_session : Session, optional
            The parent session that owns this DAP client
        """
        self._event_bridge = event_bridge
        self._parent_session = parent_session
        if event_bridge and parent_session:
            self.ctx.debug(f"Event forwarding enabled for session {parent_session.id}")

    def ingest_synthetic_event(self, event: Event) -> None:
        """Ingest a synthetic event from the EventBridge.

        This method provides a clean API for the EventBridge to inject events
        into the DAP client's event processor without directly manipulating
        internal state.

        Parameters
        ----------
        event : Event
            The DAP event to process
        """
        if not self._event_processor:
            self.ctx.warning("Cannot ingest event: no event processor")
            return

        try:
            # Process the event through the normal event processor
            self._event_processor.process_event(event)

            # Update thread state if this is a stopped event
            if (
                event.event == EventType.STOPPED.value
                and event.body
                and hasattr(event.body, "threadId")
            ):
                self._event_processor._state.current_thread_id = event.body.threadId
                # Set stopped immediately - location will be fetched on-demand
                self._event_processor._state.stopped = True
                # Schedule background location update (non-blocking)
                try:
                    asyncio.create_task(
                        self._update_current_location(event.body.threadId),
                    )
                except RuntimeError:
                    # No event loop, skip background update
                    self.ctx.debug(
                        "No event loop available for background location update",
                    )
            elif event.event == EventType.CONTINUED.value:
                # Don't override stopped state set by event processor
                # The event processor handles continued events properly
                pass
            elif event.event == EventType.TERMINATED.value:
                self._event_processor._state.terminated = True
                self._event_processor._state.stopped = False
                # Clear location when terminated
                self._event_processor._state.current_file = None
                self._event_processor._state.current_line = None
                self._event_processor._state.current_column = None

        except Exception as e:
            self.ctx.error(f"Error ingesting synthetic event: {e}")

    async def _update_current_location(self, thread_id: int | None) -> None:
        """Update current location in state from stack trace.

        This method fetches the stack trace for the current thread and updates
        the state with location information before marking the session as stopped.
        This ensures is_stopped() only returns True when complete state is available.

        Parameters
        ----------
        thread_id : int | None
            Thread ID to get stack trace for
        """
        try:
            if not thread_id:
                self.ctx.debug("No thread ID available for location update")
                return

            # Import here to avoid circular imports
            from aidb.dap.protocol.bodies import StackTraceArguments
            from aidb.dap.protocol.requests import StackTraceRequest

            # Create stack trace request
            request = StackTraceRequest(
                arguments=StackTraceArguments(
                    threadId=thread_id,
                    startFrame=0,
                    levels=1,  # We only need the top frame for location
                ),
            )

            # Send request and get response
            response = await self.send_request(request, timeout=DISCONNECT_TIMEOUT_S)

            if response.success and response.body and response.body.stackFrames:
                top_frame = response.body.stackFrames[0]
                if top_frame.source and top_frame.source.path:
                    # Update state with location information
                    self._event_processor._state.current_file = top_frame.source.path
                    self._event_processor._state.current_line = top_frame.line
                    self._event_processor._state.current_column = top_frame.column

                    self.ctx.debug(
                        f"Updated location: {top_frame.source.path}:{top_frame.line}",
                    )
                else:
                    self.ctx.debug("Stack frame has no source information")
            else:
                self.ctx.debug("Failed to get stack trace or no frames available")

        except Exception as e:
            self.ctx.debug(f"Could not update current location: {e}")
            # Don't let location update failure prevent stopped state

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:
        """Exit context manager - ensure cleanup.

        Parameters
        ----------
        exc_type : type
            Exception type if any
        exc_val : Exception
            Exception value if any
        exc_tb : traceback
            Exception traceback if any

        """
        try:
            await self.disconnect()
        except Exception as e:
            self.ctx.error(f"Error during context manager cleanup: {e}")
        return False  # Don't suppress exceptions
