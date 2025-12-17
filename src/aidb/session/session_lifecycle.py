"""Session lifecycle management mixin.

This module contains all session lifecycle operations including starting, stopping,
destroying, and attaching to processes.
"""

from typing import TYPE_CHECKING, Any, Optional, cast

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.models import (
    AidbBreakpoint,
    AidbStopResponse,
    StartRequestType,
    StartResponse,
)
from aidb.service.execution import ExecutionControl

if TYPE_CHECKING:
    from aidb.dap.client import DAPClient
    from aidb.interfaces import IContext
    from aidb.session import Session
    from aidb.session.connector import SessionConnector
    from aidb.session.state import SessionState


class SessionLifecycleMixin:
    """Mixin providing session lifecycle management operations."""

    # Type hints for attributes from main Session class
    ctx: "IContext"
    target: str
    language: str
    child_session_ids: list[str]
    adapter_port: int | None
    start_request_type: StartRequestType
    breakpoints: list[AidbBreakpoint]
    args: list[str]
    adapter: Any
    adapter_kwargs: dict[str, Any]
    dap: Optional["DAPClient"]
    debug: Any
    resource: Any
    registry: Any
    started: bool
    state: "SessionState"
    connector: "SessionConnector"

    _id: str
    _initialized: bool
    _pending_subscriptions: list[Any]
    _dap: Optional["DAPClient"]
    _attach_params: dict[str, Any] | None

    @audit_operation(component="session.lifecycle", operation="start")
    async def start(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Complete initialization and start the debug session.

        This method handles the full initialization sequence:
            1. Sets up the DAP client if needed
            2. Launches the adapter process
            3. Connects to the DAP server
            4. Executes the initialization sequence
            5. Handles any post-initialization tasks
            6. Optionally waits for first breakpoint (if breakpoints are set)

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event after starting.
            If None (default), will auto-wait only if breakpoints are set.
        wait_timeout : float, optional
            Timeout in seconds for auto-wait, default 5.0

        Returns
        -------
        StartResponse
            Response containing session initialization status

        Raises
        ------
        AidbError
            If the session has already been started
        """
        if self.state.is_initialized():
            msg = "Session has already been started"
            raise AidbError(msg)

        try:
            # Acquire port if it was deferred
            if self.adapter_port is None:
                from aidb.resources.ports import PortRegistry

                registry = PortRegistry(session_id=self._id)

                # Get adapter config for port settings
                from aidb.session.adapter_registry import AdapterRegistry

                adapter_registry = AdapterRegistry(ctx=self.ctx)
                adapter_config = adapter_registry[self.language]

                self.adapter_port = await registry.acquire_port(
                    self.language,
                    session_id=self._id,
                    default_port=adapter_config.default_dap_port,
                    fallback_ranges=adapter_config.fallback_port_ranges,
                )
                self.ctx.debug(f"Acquired deferred port {self.adapter_port}")

            # Complete DAP setup if not done
            if self.connector._dap is None:
                self._setup_dap_client()

            self.state.set_initialized(True)

            # Handle attach mode if attach params were stored
            if hasattr(self, "_attach_params") and self._attach_params:
                return await self._handle_attach_mode(auto_wait, wait_timeout)
            # Normal launch mode - handle full initialization here
            return await self._handle_launch_mode(auto_wait, wait_timeout)

        except Exception as e:
            self.ctx.error(f"Failed to start session: {e}")
            return StartResponse(
                success=False,
                message=f"Failed to start: {e}",
            )

    def _setup_dap_client(self) -> None:
        """Set up the DAP client for this session.

        Implemented in main Session class.
        """

    async def _handle_launch_mode(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Handle launch mode initialization.

        This performs the full initialization sequence for launch mode:
        1. Launch the adapter process
        2. Connect to DAP
        3. Execute initialization sequence
        4. Set initial breakpoints
        5. Optionally wait for first breakpoint

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event
        wait_timeout : float, optional
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing session startup status
        """
        from aidb.session.utils.launch_initializer import LaunchInitializer

        session = cast("Session", self)
        initializer = LaunchInitializer(session=session, ctx=self.ctx)
        return await initializer.handle_launch_mode(auto_wait, wait_timeout)

    async def _setup_breakpoint_event_subscription(self) -> None:
        """Subscribe to breakpoint events for state synchronization.

        This sets up the critical bridge that syncs asynchronous breakpoint verification
        events from the DAP adapter back to session state.
        """
        from aidb.session.utils.event_subscription_manager import (
            EventSubscriptionManager,
        )

        session = cast("Session", self)
        manager = EventSubscriptionManager(session=session, ctx=self.ctx)
        await manager.setup_breakpoint_event_subscription()

    async def _handle_attach_mode(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Handle attach mode initialization.

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event
        wait_timeout : float, optional
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing attach status
        """
        from aidb.session.utils.attach_initializer import AttachInitializer

        session = cast("Session", self)
        initializer = AttachInitializer(session=session, ctx=self.ctx)
        return await initializer.handle_attach_mode(auto_wait, wait_timeout)

    @audit_operation(component="session.lifecycle", operation="destroy")
    async def destroy(self) -> None:
        """Clean up and destroy the session.

        This method orchestrates the complete session shutdown:
        1. Destroy child sessions
        2. Stop debug session
        3. Disconnect DAP client
        4. Stop adapter
        5. Clean up resources

        Raises
        ------
        AidbError
            If the destroy operation fails
        """
        from aidb.session.utils.shutdown_orchestrator import SessionShutdownOrchestrator

        session = cast("Session", self)
        self.ctx.debug(f"Destroying session {session.id}")

        try:
            # Delegate shutdown orchestration
            shutdown = SessionShutdownOrchestrator(session=session, ctx=self.ctx)
            await shutdown.execute_full_shutdown()

            # Unregister from session registry
            self.registry.unregister_session(session.id)

            self.ctx.debug(f"Session {session.id} destroyed successfully")

        except Exception as e:
            self.ctx.error(f"Error during session destroy: {e}")
            msg = f"Failed to destroy session: {e}"
            raise AidbError(msg) from e

    @audit_operation(component="session.lifecycle", operation="stop")
    async def stop(self) -> AidbStopResponse:
        """Stop the debug session.

        This is a facade method for the debug operations stop method,
        providing direct access from the Session object.

        Returns
        -------
        AidbStopResponse
            Response indicating the stop operation result

        Raises
        ------
        AidbError
            If the stop operation fails
        """
        # Use ExecutionControl directly instead of session.debug
        execution = ExecutionControl(cast("Session", self), self.ctx)
        return await execution.stop()

    @audit_operation(component="session.lifecycle", operation="wait_for_stop")
    async def wait_for_stop(self, timeout: float = 5.0) -> None:
        """Wait for the session to reach a stopped state.

        This method blocks until the session receives a stopped event or
        the timeout is reached.

        Parameters
        ----------
        timeout : float, optional
            Maximum time to wait in seconds, by default 5.0

        Raises
        ------
        TimeoutError
            If the session doesn't stop within the timeout period
        RuntimeError
            If DAP client is not available
        """
        session = cast("Session", self)
        if not hasattr(self, "connector") or not self.connector._dap:
            msg = f"Session {session.id} has no DAP client available"
            raise RuntimeError(msg)

        # Use the DAP client's wait_for_stopped method which properly handles events
        if not await self.connector._dap.wait_for_stopped(timeout):
            msg = (
                f"Session {session.id} did not reach stopped state within "
                f"{timeout} seconds"
            )
            raise TimeoutError(
                msg,
            )
