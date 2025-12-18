"""Session shutdown orchestration utilities."""

import asyncio
from typing import TYPE_CHECKING, Optional, cast

from aidb.models import SessionStatus
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class SessionShutdownOrchestrator(Obj):
    """Orchestrate session shutdown and resource cleanup.

    This class handles the orderly shutdown of debug sessions including:
    - Child session destruction
    - Debug session termination
    - DAP client disconnection
    - Adapter shutdown
    - Resource cleanup (ports, processes)

    Parameters
    ----------
    session : Session
        The session to manage shutdown for
    ctx : IContext, optional
        Application context for logging
    """

    def __init__(
        self,
        session: "Session",
        ctx: Optional["IContext"] = None,
    ) -> None:
        super().__init__(ctx=ctx)
        self.session = session

    async def execute_full_shutdown(self) -> None:
        """Execute complete session shutdown in proper order.

        Performs shutdown steps in order:
        1. Destroy child sessions
        2. Stop debug session if running
        3. Disconnect DAP client
        4. Stop adapter
        5. Clean up resources (ports, processes)

        Raises
        ------
        Exception
            Any error during shutdown is re-raised after logging
        """
        await self.destroy_child_sessions()
        await self.stop_debug_session()
        await self.disconnect_dap_client()
        await self.stop_adapter()
        await self.cleanup_resources()

    async def destroy_child_sessions(self) -> None:
        """Clean up child sessions recursively.

        Iterates through child session IDs and destroys each child session. Uses a copy
        of the list to avoid modification during iteration.
        """
        # Copy list to avoid modification during iteration
        for child_id in self.session.child_session_ids[:]:
            child = self.session.registry.get_session(child_id)
            if child:
                await child.destroy()

    async def stop_debug_session(self) -> None:
        """Stop the debug session if currently running.

        Checks the session status and calls ExecutionControl.stop() if running. Errors
        are logged but not propagated.
        """
        if self.session.status == SessionStatus.RUNNING:
            try:
                from aidb.service.execution import ExecutionControl

                exec_control = ExecutionControl(self.session, self.ctx)
                await exec_control.stop()
            except Exception as e:
                self.ctx.debug(f"Error stopping session during destroy: {e}")

    async def disconnect_dap_client(self) -> None:
        """Disconnect DAP client if connected.

        Checks for connector and DAP client presence before disconnecting. Errors are
        logged but not propagated.
        """
        if hasattr(self.session, "connector") and self.session.connector._dap:
            try:
                await self.session.connector._dap.disconnect()
            except Exception as e:
                self.ctx.debug(f"Error disconnecting DAP client: {e}")

    async def stop_adapter(self) -> None:
        """Stop adapter process and release resources.

        Calls adapter.stop() if the adapter exists and has a stop method. Errors are
        logged but not propagated.
        """
        if hasattr(self.session, "adapter") and self.session.adapter:
            try:
                if hasattr(self.session.adapter, "stop"):
                    await self.session.adapter.stop()
            except Exception as e:
                self.ctx.debug(f"Error stopping adapter: {e}")

    async def cleanup_resources(self) -> None:
        """Clean up all resources (ports and processes) for this session.

        Performs cleanup in order:
        1. Await pending breakpoint update tasks
        2. Unsubscribe from DAP events
        3. Clean up via resource_manager or port_registry fallback

        Errors during individual cleanup steps are logged but don't
        prevent subsequent cleanup from proceeding.
        """
        session = cast("Session", self.session)

        # Await any pending breakpoint update tasks before cleanup
        await self._await_pending_tasks(session)

        # Unsubscribe from events before cleanup
        await self._unsubscribe_from_events(session)

        # Clean up resources via manager or fallback
        await self._cleanup_via_manager_or_fallback(session)

    async def _await_pending_tasks(self, session: "Session") -> None:
        """Await pending breakpoint update tasks.

        Parameters
        ----------
        session : Session
            Session with potential pending tasks
        """
        if (
            hasattr(session, "_breakpoint_update_tasks")
            and session._breakpoint_update_tasks
        ):
            await asyncio.gather(
                *session._breakpoint_update_tasks,
                return_exceptions=True,
            )
            session._breakpoint_update_tasks.clear()

    async def _unsubscribe_from_events(self, session: "Session") -> None:
        """Unsubscribe from DAP events.

        Parameters
        ----------
        session : Session
            Session with potential event subscriptions
        """
        if (
            hasattr(session, "_event_subscriptions")
            and session._event_subscriptions
            and hasattr(session, "connector")
            and session.connector._dap
        ):
            for event_type, sub_id in session._event_subscriptions.items():
                try:
                    await asyncio.wait_for(
                        session.connector._dap.events.unsubscribe_from_event(sub_id),
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

    async def _cleanup_via_manager_or_fallback(self, session: "Session") -> None:
        """Clean up resources via manager or port registry fallback.

        Parameters
        ----------
        session : Session
            Session whose resources should be cleaned up
        """
        try:
            if hasattr(session, "resource_manager") and session.resource_manager:
                cleanup_result = await session.resource_manager.cleanup_all_resources()
                procs = cleanup_result.get("terminated_processes", 0)
                ports = cleanup_result.get("released_ports", 0)
                self.ctx.debug(
                    f"Resource cleanup complete: terminated {procs} procs, "
                    f"released {ports} ports",
                )
            else:
                # Fallback: Release ALL ports for this session using port registry
                from aidb.resources.ports import PortRegistry

                port_registry = PortRegistry(session_id=session._id, ctx=self.ctx)
                released_ports = port_registry.release_session_ports(session._id)
                if released_ports:
                    self.ctx.debug(
                        f"Released {len(released_ports)} ports: {released_ports}",
                    )
                else:
                    self.ctx.debug(f"No ports to release for session {session._id}")
        except Exception as e:
            self.ctx.error(f"Error during resource cleanup: {e}")
