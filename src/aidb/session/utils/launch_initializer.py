"""Launch initialization utilities for debug sessions."""

from typing import TYPE_CHECKING, cast

from aidb.models import StartResponse
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class LaunchInitializer(Obj):
    """Handle launch mode initialization for debug sessions.

    This class manages the launch workflow including:
    - Launch adapter process
    - Connect DAP client
    - Execute initialization sequence
    - Start debug session

    Parameters
    ----------
    session : Session
        The session to initialize in launch mode
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

    async def handle_launch_mode(
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
        session = cast("Session", self.session)

        try:
            # Launch the adapter process
            await self.launch_adapter_process()

            # Connect the DAP client
            if session.dap:
                await session.dap.connect()
                # Note: Pending subscriptions (from deferred sessions) will be
                # transferred to the DAP client as events are subscribed

                # Subscribe to breakpoint events for state synchronization
                await session._setup_breakpoint_event_subscription()

            # Execute the adapter-specific initialization sequence
            sequence = session.adapter.config.get_initialization_sequence()
            await self.execute_initialization_sequence(sequence)

            # Call post-initialization operations (e.g., set initial breakpoints)
            from aidb.service.execution import ExecutionControl

            exec_control = ExecutionControl(session, self.ctx)
            result = await exec_control.start(
                auto_wait=auto_wait,
                wait_timeout=wait_timeout,
            )

            # Mark session as started if successful
            if result.success:
                session.started = True

            return result

        except Exception as e:
            import traceback

            self.ctx.error(f"Failed to launch: {e}")
            self.ctx.error(f"Traceback: {traceback.format_exc()}")
            return StartResponse(
                success=False,
                message=f"Launch failed: {e}",
            )

    async def launch_adapter_process(self) -> None:
        """Launch the debug adapter process.

        This method handles the actual launching of the debug adapter, which varies by
        language and configuration.
        """
        session = cast("Session", self.session)

        try:
            # Use the adapter's launch method based on start request type
            if session.start_request_type.value == "launch":
                process_info = await session.adapter.launch(
                    session.target,
                    port=session.adapter_port,
                    args=session.args,
                    env=session.adapter_kwargs.get("env"),
                    cwd=session.adapter_kwargs.get("cwd"),
                )
            elif session.start_request_type.value == "attach":
                process_info = await session.adapter.attach(session.target)
            else:
                msg = f"Unknown start request type: {session.start_request_type}"
                raise ValueError(msg)

            self.ctx.debug(f"Adapter process launched: {process_info}")

            # Update the session's adapter port if it changed
            if isinstance(process_info, tuple) and len(process_info) >= 2:
                _, actual_port = process_info
                if actual_port != session.adapter_port:
                    self.ctx.debug(
                        f"Adapter used different port {actual_port} "
                        f"than allocated {session.adapter_port}",
                    )
                    session.adapter_port = actual_port
                    # Need to recreate DAP client with correct port
                    if session.connector._dap:
                        session.connector._dap = None
                        session._setup_dap_client()

        except Exception as e:
            self.ctx.error(f"Failed to launch adapter process: {e}")
            raise

    async def execute_initialization_sequence(self, sequence: list) -> None:
        """Execute the DAP initialization sequence.

        This delegates to the InitializationOps class which handles
        the actual DAP protocol initialization.

        Parameters
        ----------
        sequence : list
            List of initialization steps to execute
        """
        from aidb.session.ops.initialization import InitializationMixin

        session = cast("Session", self.session)
        init_ops = InitializationMixin(session=session, ctx=self.ctx)
        await init_ops._execute_initialization_sequence(sequence)
