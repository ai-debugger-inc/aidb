"""DAP connection management for sessions."""

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.errors import DebugConnectionError, DebugSessionLostError
from aidb.dap.client import DAPClient
from aidb.dap.client.public_events import StubPublicEventAPI
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class SessionConnector(Obj):
    """Manages DAP client connections for sessions.

    This component handles:
    - DAP client creation and setup
    - Child session DAP connections
    - Stub events API before connection
    - Parent/child DAP client resolution
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None):
        """Initialize the connector.

        Parameters
        ----------
        session : Session
            The session this connector belongs to
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self.session = session
        self._dap: DAPClient | None = None
        self._stub_events: StubPublicEventAPI | None = None
        self._pending_subscriptions: list[dict[str, Any]] = []

    def setup_dap_client(self, adapter_host: str, adapter_port: int) -> DAPClient:
        """Set up the DAP client for this session.

        Parameters
        ----------
        adapter_host : str
            Host where the debug adapter is running
        adapter_port : int
            Port where the debug adapter is listening

        Returns
        -------
        DAPClient
            The configured DAP client
        """
        self.ctx.debug(f"Setting up DAP client for session {self.session.id}")

        # Create the DAP client with the adapter's host and port
        try:
            self._dap = DAPClient(
                adapter_host=adapter_host,
                adapter_port=adapter_port,
                ctx=self.ctx,
                log_prefix=f"[Session {self.session.id[:8]}]",
                session_id=self.session.id,
            )
            self.ctx.debug(f"Created DAP client for {adapter_host}:{adapter_port}")

            # Register callback for handling child session creation via
            # startDebugging reverse requests (e.g., JavaScript)
            self._dap.set_session_creation_callback(
                self.session._handle_child_session_request,
            )
            self.ctx.debug("Registered child session creation callback")

            return self._dap
        except Exception as e:
            msg = f"Failed to create DAP client for {adapter_host}:{adapter_port}"
            raise DebugConnectionError(
                msg,
                details={
                    "session_id": self.session.id,
                    "adapter_host": adapter_host,
                    "adapter_port": adapter_port,
                    "error": str(e),
                },
                recoverable=True,
            ) from e

    async def setup_child_dap_client(
        self,
        adapter_host: str,
        adapter_port: int,
    ) -> DAPClient:
        """Set up DAP client for a child session with separate connection.

        Parameters
        ----------
        adapter_host : str
            Host where the child's debug adapter is running
        adapter_port : int
            Port where the child's debug adapter is listening

        Returns
        -------
        DAPClient
            The configured and connected DAP client
        """
        self.ctx.debug(
            f"Setting up child DAP client for session {self.session.id} "
            f"at {adapter_host}:{adapter_port}",
        )

        # Create a new DAP client for the child session
        try:
            self._dap = DAPClient(
                adapter_host=adapter_host,
                adapter_port=adapter_port,
                ctx=self.ctx,
                log_prefix=f"[Child {self.session.id}]",
                session_id=self.session.id,
            )

            # Connect the child's DAP client
            await self._dap.connect()
        except Exception as e:
            msg = f"Failed to setup child DAP client at {adapter_host}:{adapter_port}"
            raise DebugConnectionError(
                msg,
                details={
                    "session_id": self.session.id,
                    "adapter_host": adapter_host,
                    "adapter_port": adapter_port,
                    "is_child": True,
                    "error": str(e),
                },
                recoverable=True,
            ) from e

        self.ctx.debug(f"Child session {self.session.id} connected to DAP")
        return self._dap

    def get_dap_client(self) -> DAPClient:
        """Get the appropriate DAP client for debug operations.

        Returns the session's own DAP client if available, otherwise
        uses the parent session's DAP client (for child sessions).

        Returns
        -------
        DAPClient
            The DAP client to use

        Raises
        ------
        RuntimeError
            If no DAP client is available
        """
        # If this session has its own DAP client, use it
        if self._dap:
            return self._dap

        # Otherwise, if this is a child session, use parent's DAP client
        if self.session.is_child and self.session.parent_session_id:
            parent = self.session.registry.get_session(self.session.parent_session_id)
            if parent and hasattr(parent, "connector") and parent.connector._dap:
                self.ctx.debug(
                    f"Child session {self.session.id} using "
                    f"parent {self.session.parent_session_id}'s DAP client",
                )
                return parent.connector._dap
            msg = f"Child session {self.session.id} cannot access parent's DAP client"
            raise DebugSessionLostError(
                msg,
                details={
                    "session_id": self.session.id,
                    "parent_session_id": self.session.parent_session_id,
                    "parent_has_dap": parent.connector._dap is not None,
                },
                recoverable=False,
            )

        # Parent sessions without _dap set
        msg = f"Session {self.session.id} has no DAP client available"
        raise DebugSessionLostError(
            msg,
            details={
                "session_id": self.session.id,
                "is_child": self.session.is_child,
                "has_dap": self._dap is not None,
            },
            recoverable=False,
        )

    def set_dap_client(self, dap: DAPClient | None) -> None:
        """Set the DAP client directly.

        Parameters
        ----------
        dap : Optional[DAPClient]
            The DAP client to set, or None to clear
        """
        self._dap = dap

    def has_dap_client(self) -> bool:
        """Check if a DAP client is available.

        Returns
        -------
        bool
            True if a DAP client is available
        """
        try:
            self.get_dap_client()
            return True
        except DebugSessionLostError:
            return False

    def create_stub_events_api(self) -> StubPublicEventAPI:
        """Create a stub events API for deferred sessions.

        This creates a stub API that captures subscriptions for later
        replay when the real DAP connection is established.

        Returns
        -------
        StubPublicEventAPI
            The stub events API
        """
        # Create the base stub
        base_stub = StubPublicEventAPI()
        self._pending_subscriptions = []

        # Create a wrapper that captures subscriptions
        class CapturingStubAPI(StubPublicEventAPI):
            """Wrapper that captures subscriptions for later replay."""

            def __init__(self, base_stub, pending_list):
                """Initialize with base stub and pending list."""
                super().__init__()
                self._base_stub = base_stub
                self._pending_list = pending_list

            def subscribe_to_event(self, event_type, handler, event_filter=None):
                """Capture and forward subscription."""
                self._pending_list.append(
                    {
                        "event_type": event_type,
                        "handler": handler,
                        "filter": event_filter,
                    },
                )
                return self._base_stub.subscribe_to_event(
                    event_type,
                    handler,
                    event_filter,
                )

        self._stub_events = CapturingStubAPI(base_stub, self._pending_subscriptions)
        return self._stub_events

    def get_events_api(self):
        """Get the public event subscription API.

        Returns the real events API if DAP is connected, otherwise
        returns the stub events API.

        Returns
        -------
        Union[PublicEventAPI, StubPublicEventAPI]
            The events API

        Raises
        ------
        RuntimeError
            If no event API is available
        """
        if self._dap:
            return self._dap.events
        if self._stub_events:
            return self._stub_events
        msg = "No event API available"
        raise RuntimeError(msg)

    def get_pending_subscriptions(self) -> list[dict[str, Any]]:
        """Get pending event subscriptions.

        Returns
        -------
        List[Dict[str, Any]]
            List of pending subscriptions to replay
        """
        return self._pending_subscriptions

    async def reconnect(self, max_attempts: int = 3, delay: float = 1.0) -> bool:
        """Attempt to reconnect to the debug adapter.

        This method tries to re-establish the connection to the debug adapter
        after a connection loss. It preserves the session state and re-subscribes
        to events after reconnection.

        Parameters
        ----------
        max_attempts : int
            Maximum number of reconnection attempts
        delay : float
            Delay between reconnection attempts in seconds

        Returns
        -------
        bool
            True if reconnection succeeded, False otherwise
        """
        if not self._dap:
            self.ctx.error(f"Session {self.session.id} has no DAP client to reconnect")
            return False

        # Store the current adapter info
        # The DAPClient stores host/port in its _transport object
        if not hasattr(self._dap, "_transport"):
            self.ctx.error("DAP client missing transport layer")
            return False

        adapter_host = self._dap._transport._host  # type: ignore
        adapter_port = self._dap._transport._port  # type: ignore
        old_dap = self._dap

        self.ctx.info(
            f"Attempting to reconnect session {self.session.id} to "
            f"{adapter_host}:{adapter_port}",
        )

        for attempt in range(max_attempts):
            try:
                # Create a new DAP client
                new_dap = DAPClient(
                    adapter_host=adapter_host,
                    adapter_port=adapter_port,
                    ctx=self.ctx,
                    log_prefix=f"[Reconnect {self.session.id[:8]}]",
                    session_id=self.session.id,
                )

                # Try to connect
                await new_dap.connect()

                # If successful, replace the old DAP client
                self._dap = new_dap

                # Clean up old DAP client
                try:
                    await old_dap.disconnect()
                except Exception as e:
                    msg = (
                        f"Failed to disconnect old DAP client "
                        f"during session reconnection: {e}"
                    )
                    self.ctx.debug(msg)

                # Re-subscribe to events if we had pending subscriptions
                if self._pending_subscriptions:
                    self.ctx.debug(
                        f"Re-subscribing to {len(self._pending_subscriptions)} events",
                    )
                    for subscription in self._pending_subscriptions:
                        try:
                            await self._dap.events.subscribe_to_event(
                                subscription["event_type"],
                                subscription["handler"],
                                subscription.get("filter"),
                            )
                        except Exception as e:
                            self.ctx.warning(
                                f"Failed to re-subscribe to "
                                f"{subscription['event_type']}: {e}",
                            )

                self.ctx.info(f"Successfully reconnected session {self.session.id}")
                return True

            except Exception as e:
                self.ctx.warning(
                    f"Reconnection attempt {attempt + 1}/{max_attempts} failed: {e}",
                )

                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
                    delay *= 1.5  # Exponential backoff

        self.ctx.error(
            f"Failed to reconnect session {self.session.id} after "
            f"{max_attempts} attempts",
        )
        return False

    async def verify_connection(self) -> bool:
        """Verify that the DAP connection is still alive.

        Returns
        -------
        bool
            True if connection is active, False otherwise
        """
        if not self._dap:
            return False

        try:
            # Try to check if the connection is active
            # This is a lightweight check that doesn't send any requests
            if hasattr(self._dap, "is_connected"):
                # Check if it's a callable or a property
                is_connected_attr = self._dap.is_connected
                if callable(is_connected_attr):
                    return is_connected_attr()
                return bool(is_connected_attr)
            # If no is_connected method/property, assume connected if DAP exists
            return True
        except Exception:
            return False

    def get_output(self, clear: bool = True) -> list[dict[str, Any]]:
        """Get collected program output (logpoints, stdout, stderr).

        This method provides proper encapsulation of the DAP client's output
        buffer, avoiding direct access to private attributes.

        Parameters
        ----------
        clear : bool
            If True (default), clears the buffer after retrieval to avoid
            returning duplicate output on subsequent calls.

        Returns
        -------
        list[dict[str, Any]]
            List of output entries, each with:
            - category: "console" (logpoints), "stdout", "stderr", etc.
            - output: The output text
            - timestamp: Unix timestamp when output was received
        """
        if not self._dap:
            return []

        state = self._dap._state
        output = list(state.output_buffer)
        if clear:
            state.output_buffer.clear()
        return output
