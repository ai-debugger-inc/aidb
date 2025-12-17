"""Attach initialization utilities for debug sessions."""

from typing import TYPE_CHECKING, cast

from aidb.common.errors import AidbError
from aidb.models import StartResponse
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class AttachInitializer(Obj):
    """Handle attach mode initialization for debug sessions.

    This class manages the attach workflow including:
    - Attach to host:port (remote attach)
    - Attach to PID (local attach)
    - Shared finalization logic for DAP connection and initialization

    Parameters
    ----------
    session : Session
        The session to initialize in attach mode
    ctx : IContext, optional
        Application context for logging
    """

    def __init__(
        self,
        session: "Session",
        ctx: "IContext | None" = None,
    ) -> None:
        super().__init__(ctx=ctx)
        self.session = session

    async def handle_attach_mode(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Handle attach mode initialization.

        Routes to the appropriate attach method based on parameters.

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
        session = cast("Session", self.session)
        params = session._attach_params
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
                return await self.attach_to_host_port(
                    host,
                    port,
                    timeout,
                    project_name,
                    auto_wait,
                    wait_timeout,
                )
            if pid:
                return await self.attach_to_pid(
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

    async def attach_to_host_port(
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
        project_name : str, optional
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
        session = cast("Session", self.session)

        if hasattr(session.adapter, "attach_remote"):
            _, dap_port = await session.adapter.attach_remote(
                host=host,
                port=port,
                timeout=timeout,
                project_name=project_name,
            )
            await self._update_adapter_port_if_changed(dap_port)
        else:
            # Fallback - use launch mode flow
            return await session._handle_launch_mode(auto_wait, wait_timeout)

        return await self._finalize_attach(auto_wait, wait_timeout)

    async def attach_to_pid(
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
        project_name : str, optional
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
        session = cast("Session", self.session)

        if hasattr(session.adapter, "attach_pid"):
            _, dap_port = session.adapter.attach_pid(
                pid=pid,
                timeout=timeout,
                project_name=project_name,
            )
            await self._update_adapter_port_if_changed(dap_port)
        else:
            # Fallback - use launch mode flow
            return await session._handle_launch_mode(auto_wait, wait_timeout)

        return await self._finalize_attach(auto_wait, wait_timeout)

    async def _update_adapter_port_if_changed(self, dap_port: int | None) -> None:
        """Update the adapter port if it changed during attach.

        Parameters
        ----------
        dap_port : int, optional
            The new DAP port from the adapter
        """
        session = cast("Session", self.session)

        if dap_port and dap_port != session.adapter_port:
            self.ctx.debug(
                f"Adapter port changed from {session.adapter_port} to {dap_port}",
            )
            session.adapter_port = dap_port
            # Update the DAP client's port before connecting
            if hasattr(session, "dap") and session.dap:
                await session.dap.update_adapter_port(dap_port)

    async def _finalize_attach(
        self,
        auto_wait: bool | None,
        wait_timeout: float,
    ) -> StartResponse:
        """Finalize attachment by connecting DAP and running initialization.

        This shared method handles the common post-attach workflow:
        1. Connect to DAP
        2. Subscribe to breakpoint events
        3. Execute initialization sequence
        4. Start debug session

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event
        wait_timeout : float
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing attach status
        """
        session = cast("Session", self.session)

        # Connect to DAP and perform initialization
        if session.dap:
            await session.dap.connect()
            # Subscribe to breakpoint events for state synchronization
            await session._setup_breakpoint_event_subscription()

        # Execute the adapter-specific initialization sequence
        from aidb.session.ops.initialization import InitializationMixin

        sequence = session.adapter.config.get_initialization_sequence()
        init_ops = InitializationMixin(session=session, ctx=self.ctx)
        await init_ops._execute_initialization_sequence(sequence)

        # Call post-initialization operations (e.g., set initial breakpoints)
        from aidb.service.execution import ExecutionControl

        exec_control = ExecutionControl(session, self.ctx)
        result = await exec_control.start(
            auto_wait=auto_wait,
            wait_timeout=wait_timeout,
        )

        if result.success:
            session.started = True

        return result
