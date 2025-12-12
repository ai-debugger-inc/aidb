"""Session lifecycle management mixin.

This module contains all session lifecycle operations including starting, stopping,
destroying, and attaching to processes.
"""

from typing import TYPE_CHECKING, Any, Optional, cast

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.dap.client.constants import EventType
from aidb.models import (
    AidbBreakpoint,
    AidbStopResponse,
    SessionStatus,
    StartRequestType,
    StartResponse,
)

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
        try:
            # Launch the adapter process
            await self._launch_adapter_process()

            # Connect the DAP client
            if self.dap:
                await self.dap.connect()
                # Note: Pending subscriptions (from deferred sessions) will be
                # transferred to the DAP client as events are subscribed

                # Subscribe to breakpoint events for state synchronization
                await self._setup_breakpoint_event_subscription()

            # Execute the adapter-specific initialization sequence
            sequence = self.adapter.config.get_initialization_sequence()
            await self._execute_initialization_sequence(sequence)

            # Call post-initialization operations (e.g., set initial breakpoints)
            result = await self.debug.start(
                auto_wait=auto_wait,
                wait_timeout=wait_timeout,
            )

            # Mark session as started if successful
            if result.success:
                self.started = True

            return result

        except Exception as e:
            import traceback

            self.ctx.error(f"Failed to launch: {e}")
            self.ctx.error(f"Traceback: {traceback.format_exc()}")
            return StartResponse(
                success=False,
                message=f"Launch failed: {e}",
            )

    async def _launch_adapter_process(self) -> None:
        """Launch the debug adapter process.

        This method handles the actual launching of the debug adapter, which varies by
        language and configuration.
        """
        try:
            # Use the adapter's launch method based on start request type
            if self.start_request_type.value == "launch":
                process_info = await self.adapter.launch(
                    self.target,
                    port=self.adapter_port,
                    args=self.args,
                    env=self.adapter_kwargs.get("env"),
                    cwd=self.adapter_kwargs.get("cwd"),
                )
            elif self.start_request_type.value == "attach":
                process_info = await self.adapter.attach(self.target)
            else:
                msg = f"Unknown start request type: {self.start_request_type}"
                raise ValueError(
                    msg,
                )

            self.ctx.debug(f"Adapter process launched: {process_info}")

            # Update the session's adapter port if it changed (shouldn't happen now)
            if isinstance(process_info, tuple) and len(process_info) >= 2:
                _, actual_port = process_info
                if actual_port != self.adapter_port:
                    self.ctx.debug(
                        f"Adapter used different port {actual_port} "
                        f"than allocated {self.adapter_port}",
                    )
                    self.adapter_port = actual_port
                    # Need to recreate DAP client with correct port
                    if self.connector._dap:
                        self.connector._dap = None
                        self._setup_dap_client()

        except Exception as e:
            self.ctx.error(f"Failed to launch adapter process: {e}")
            raise

    async def _execute_initialization_sequence(self, sequence: list) -> None:
        """Execute the DAP initialization sequence.

        This delegates to the InitializationOps class which handles
        the actual DAP protocol initialization.

        Parameters
        ----------
        sequence : list
            List of initialization steps to execute
        """
        # Delegate to the initialization operations module
        from aidb.session.ops.initialization import InitializationMixin

        init_ops = InitializationMixin(session=cast("Session", self), ctx=self.ctx)
        await init_ops._execute_initialization_sequence(sequence)

    async def _setup_breakpoint_event_subscription(self) -> None:
        """Subscribe to breakpoint events for state synchronization.

        This sets up the critical bridge that syncs asynchronous breakpoint verification
        events from the DAP adapter back to session state. Without this, breakpoints
        remain unverified in session state even after the adapter confirms verification.
        """
        # Idempotence check: skip if already subscribed
        session = cast("Session", self)
        if hasattr(session, "_event_subscriptions") and session._event_subscriptions:
            self.ctx.debug(
                "Breakpoint event subscriptions already set up, skipping",
            )
            return

        if not self.dap or not hasattr(self.dap, "events"):
            self.ctx.debug(
                "Cannot subscribe to breakpoint events: "
                "DAP or events API not available",
            )
            return

        # Initialize tracking dict if not present
        if not hasattr(session, "_event_subscriptions"):
            session._event_subscriptions = {}

        try:
            # Subscribe to breakpoint events using the session's handler
            # The handler (_on_breakpoint_event) is defined in SessionBreakpointsMixin
            subscription_id = await self.dap.events.subscribe_to_event(
                EventType.BREAKPOINT.value,
                session._on_breakpoint_event,
            )
            session._event_subscriptions[EventType.BREAKPOINT.value] = subscription_id
            self.ctx.debug(
                f"Subscribed to breakpoint events for state sync "
                f"(subscription_id={subscription_id})",
            )

            # Subscribe to loadedSource events for proactive rebinding
            # This accelerates breakpoint verification by re-sending setBreakpoints
            # when sources load, rather than waiting for async verification
            loaded_source_key = EventType.LOADED_SOURCE.value
            loadedsource_sub_id = await self.dap.events.subscribe_to_event(
                loaded_source_key,
                session._on_loaded_source_event,
            )
            session._event_subscriptions[loaded_source_key] = loadedsource_sub_id
            self.ctx.debug(
                f"Subscribed to loadedSource events for proactive rebinding "
                f"(subscription_id={loadedsource_sub_id})",
            )

            # Subscribe to terminated event to clear breakpoint cache
            # This prevents returning stale breakpoint data after session ends
            terminated_sub_id = await self.dap.events.subscribe_to_event(
                EventType.TERMINATED.value,
                session._on_terminated_event,
            )
            session._event_subscriptions[EventType.TERMINATED.value] = terminated_sub_id
            self.ctx.debug(
                f"Subscribed to terminated event for cache cleanup "
                f"(subscription_id={terminated_sub_id})",
            )
        except Exception as e:
            # Non-fatal: breakpoint sync is important but not critical
            # for basic operation
            self.ctx.warning(
                f"Failed to subscribe to breakpoint events: {e}. "
                "Breakpoint verification state may not update correctly.",
            )

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
        params = self._attach_params
        if params is None:
            msg = "No attach parameters set"
            raise AidbError(msg)
        host = params.get("host")
        port = params.get("port")
        pid = params.get("pid")
        timeout = params.get("timeout", 10000)
        project_name = params.get("project_name")

        try:
            if host and port:
                # Remote or local attach via host:port
                return await self._attach_to_host_port(
                    host,
                    port,
                    timeout,
                    project_name,
                    auto_wait,
                    wait_timeout,
                )
            if pid:
                # Local attach via PID
                return await self._attach_to_pid(
                    pid,
                    timeout,
                    project_name,
                    auto_wait,
                    wait_timeout,
                )
            msg = "Attach mode requires either host:port or pid"
            raise AidbError(msg)

        except Exception as e:
            self.ctx.error(f"Failed to attach: {e}")
            return StartResponse(
                success=False,
                message=f"Attach failed: {e}",
            )

    async def _attach_to_host_port(
        self,
        host: str,
        port: int,
        timeout: int,
        project_name: str | None,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Attach to a process via host and port.

        Parameters
        ----------
        host : str
            Host to attach to
        port : int
            Port to attach to
        timeout : int
            Timeout in milliseconds
        project_name : Optional[str]
            Project name for context
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event
        wait_timeout : float, optional
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing attach status
        """
        if hasattr(self.adapter, "attach_remote"):
            _, dap_port = await self.adapter.attach_remote(
                host=host,
                port=port,
                timeout=timeout,
                project_name=project_name,
            )
            # Update the session's adapter port if it changed
            if dap_port and dap_port != self.adapter_port:
                self.ctx.debug(
                    f"Adapter port changed from {self.adapter_port} to {dap_port}",
                )
                self.adapter_port = dap_port
                # Update the DAP client's port before connecting
                if hasattr(self, "dap") and self.dap:
                    await self.dap.update_adapter_port(dap_port)
        else:
            # Fallback - use launch mode flow
            return await self._handle_launch_mode(auto_wait, wait_timeout)

        # Connect to DAP and perform initialization
        if self.dap:
            await self.dap.connect()
            # Subscribe to breakpoint events for state synchronization
            await self._setup_breakpoint_event_subscription()

        # Execute the adapter-specific initialization sequence
        sequence = self.adapter.config.get_initialization_sequence()
        await self._execute_initialization_sequence(sequence)

        # Call post-initialization operations (e.g., set initial breakpoints)
        result = await self.debug.start(auto_wait=auto_wait, wait_timeout=wait_timeout)

        if result.success:
            self.started = True

        return result

    async def _attach_to_pid(
        self,
        pid: int,
        timeout: int,
        project_name: str | None,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Attach to a process via PID.

        Parameters
        ----------
        pid : int
            Process ID to attach to
        timeout : int
            Timeout in milliseconds
        project_name : Optional[str]
            Project name for context
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event
        wait_timeout : float, optional
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing attach status
        """
        if hasattr(self.adapter, "attach_pid"):
            _, dap_port = self.adapter.attach_pid(
                pid=pid,
                timeout=timeout,
                project_name=project_name,
            )
            # Update the session's adapter port if it changed
            if dap_port and dap_port != self.adapter_port:
                self.ctx.debug(
                    f"Adapter port changed from {self.adapter_port} to {dap_port}",
                )
                self.adapter_port = dap_port
                # Update the DAP client's port before connecting
                if hasattr(self, "dap") and self.dap:
                    await self.dap.update_adapter_port(dap_port)
        else:
            # Fallback - use launch mode flow
            return await self._handle_launch_mode(auto_wait, wait_timeout)

        # Connect to DAP and perform initialization
        if self.dap:
            await self.dap.connect()
            # Subscribe to breakpoint events for state synchronization
            await self._setup_breakpoint_event_subscription()

        # Execute the adapter-specific initialization sequence
        sequence = self.adapter.config.get_initialization_sequence()
        await self._execute_initialization_sequence(sequence)

        # Call post-initialization operations (e.g., set initial breakpoints)
        result = await self.debug.start(auto_wait=auto_wait, wait_timeout=wait_timeout)

        if result.success:
            self.started = True

        return result

    async def _destroy_child_sessions(self) -> None:
        """Clean up child sessions."""
        for child_id in self.child_session_ids[
            :
        ]:  # Copy list to avoid modification during iteration
            child = self.registry.get_session(child_id)
            if child:
                await child.destroy()

    async def _stop_debug_session(self, session: Any) -> None:
        """Stop the debug session if running.

        Parameters
        ----------
        session : Any
            Session object with status attribute
        """
        if session.status == SessionStatus.RUNNING:
            try:
                await self.debug.stop()
            except Exception as e:
                self.ctx.debug(f"Error stopping session during destroy: {e}")

    async def _disconnect_dap_client(self) -> None:
        """Disconnect DAP client if connected."""
        if hasattr(self, "connector") and self.connector._dap:
            try:
                await self.connector._dap.disconnect()
            except Exception as e:
                self.ctx.debug(f"Error disconnecting DAP client: {e}")

    async def _stop_adapter(self) -> None:
        """Stop adapter (terminates process and releases resources)."""
        if hasattr(self, "adapter") and self.adapter:
            try:
                if hasattr(self.adapter, "stop"):
                    await self.adapter.stop()
            except Exception as e:
                self.ctx.debug(f"Error stopping adapter: {e}")

    async def _cleanup_resources(self) -> None:
        """Clean up all resources (ports and processes) for this session."""
        # Await any pending breakpoint update tasks before cleanup
        session = cast("Session", self)
        if (
            hasattr(session, "_breakpoint_update_tasks")
            and session._breakpoint_update_tasks
        ):
            import asyncio

            await asyncio.gather(
                *session._breakpoint_update_tasks,
                return_exceptions=True,
            )
            session._breakpoint_update_tasks.clear()

        try:
            # Unsubscribe from events before cleanup
            # Use timeout to prevent hanging if receiver is blocked
            if (
                hasattr(session, "_event_subscriptions")
                and session._event_subscriptions
                and hasattr(self, "connector")
                and self.connector._dap
            ):
                import asyncio

                for event_type, sub_id in session._event_subscriptions.items():
                    try:
                        await asyncio.wait_for(
                            self.connector._dap.events.unsubscribe_from_event(sub_id),
                            timeout=2.0,  # Don't block cleanup indefinitely
                        )
                        self.ctx.debug(
                            f"Unsubscribed from {event_type} events (id={sub_id})",
                        )
                    except asyncio.TimeoutError:
                        self.ctx.warning(
                            f"Timeout unsubscribing from {event_type} (id={sub_id})",
                        )
                    except Exception as e:
                        self.ctx.debug(
                            f"Failed to unsubscribe from {event_type}: {e}",
                        )
                session._event_subscriptions.clear()

            if hasattr(self, "resource_manager") and self.resource_manager:
                cleanup_result = await self.resource_manager.cleanup_all_resources()
                self.ctx.debug(
                    f"Resource cleanup complete: "
                    f"terminated {cleanup_result.get('terminated_processes', 0)} "
                    f"procs, "
                    f"released {cleanup_result.get('released_ports', 0)} ports",
                )
            else:
                # Fallback: Release ALL ports for this session using port registry
                from aidb.resources.ports import PortRegistry

                port_registry = PortRegistry(session_id=self._id, ctx=self.ctx)
                released_ports = port_registry.release_session_ports(self._id)
                if released_ports:
                    self.ctx.debug(
                        f"Released {len(released_ports)} ports: {released_ports}",
                    )
                else:
                    self.ctx.debug(f"No ports to release for session {self._id}")
        except Exception as e:
            self.ctx.error(f"Error during resource cleanup: {e}")

    @audit_operation(component="session.lifecycle", operation="destroy")
    async def destroy(self) -> None:
        """Clean up and destroy the session."""
        session = cast("Session", self)
        self.ctx.debug(f"Destroying session {session.id}")

        try:
            # Clean up child sessions first
            await self._destroy_child_sessions()

            # Stop the debug session if running
            await self._stop_debug_session(session)

            # Disconnect DAP client
            await self._disconnect_dap_client()

            # Stop adapter
            await self._stop_adapter()

            # Clean up all resources
            await self._cleanup_resources()

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
        return await self.debug.stop()

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
