"""Execution control operations for debugging."""

from typing import TYPE_CHECKING, Any, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.models import AidbStopResponse, ExecutionStateResponse
from aidb.session import Session

from ..base import APIOperationBase
from ..dap_utils import (
    create_continue_request,
    create_goto_request,
    create_pause_request,
)

if TYPE_CHECKING:
    from aidb.common import AidbContext


class ExecutionOperations(APIOperationBase):
    """Execution control operations for debugging."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the ExecutionOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    @audit_operation(component="api.orchestration", operation="continue")
    async def continue_(
        self,
        thread_id: int | None = None,
        single_thread: bool = False,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Continue execution of the debugged program.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to continue, by default None (queries current thread)
        single_thread : bool
            Continue only the specified thread, by default False
        wait_for_stop : bool, optional
            If True, wait for a stopped event after continuing, by default False

        Returns
        -------
        ExecutionStateResponse
            Execution state after continuing
        """
        # If no thread specified, get current thread from active session
        # This ensures we use the correct thread ID for child sessions
        if thread_id is None:
            thread_id = await self.session.debug.get_current_thread_id()

        request = create_continue_request(thread_id, single_thread)
        return await self.session.debug.continue_(request, wait_for_stop)

    @audit_operation(component="api.orchestration", operation="goto")
    async def goto(
        self,
        target: int,
        thread_id: int | None = None,
    ) -> ExecutionStateResponse:
        """Jump to a specific location in the code.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        target : int
            Target location ID (from gotoTargets request)
        thread_id : int, optional
            AidbThread to perform goto on, by default None

        Returns
        -------
        ExecutionStateResponse
            Execution state after goto

        Raises
        ------
        AidbError
            If goto operation is not supported
        """
        # First check if goto is supported
        if not self.session.has_capability("supportsGotoTargetsRequest"):
            msg = "Goto operation is not supported by this debug adapter"
            raise AidbError(msg)

        request = create_goto_request(target, thread_id)
        # Use the session's debug operations
        return await self.session.debug.goto(request)

    @audit_operation(component="api.orchestration", operation="pause")
    async def pause(self, thread_id: int | None = None) -> ExecutionStateResponse:
        """Pause execution of the debugged program.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to pause, by default None (queries current thread)

        Returns
        -------
        ExecutionStateResponse
            Execution state after pausing
        """
        # If no thread specified, get current thread from active session
        # This ensures we use the correct thread ID for child sessions
        if thread_id is None:
            thread_id = await self.session.debug.get_current_thread_id()

        request = create_pause_request(thread_id)
        return await self.session.debug.pause(request)

    @audit_operation(component="api.orchestration", operation="restart")
    async def restart(
        self,
        arguments: dict[str, Any] | None = None,
    ) -> ExecutionStateResponse:
        """Restart the debug session.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        arguments : Dict[str, Any], optional
            Additional restart arguments

        Returns
        -------
        ExecutionStateResponse
            Execution state after restart
        """
        # Check if restart is supported
        if not self.session.has_capability("supportsRestartRequest"):
            msg = "Restart operation is not supported by this debug adapter"
            raise AidbError(msg)

        from aidb.dap.protocol.bodies import RestartArguments

        restart_args = RestartArguments(arguments=arguments) if arguments else None
        await self.session.debug.restart(restart_args)

        return ExecutionStateResponse(success=True, message="Debug session restarted")

    @audit_operation(component="api.orchestration", operation="stop")
    async def stop(self) -> AidbStopResponse:
        """Stop the debug session.

        This terminates the debugged program and ends the debug session.
        This operation is automatically audited when audit logging is enabled.

        Returns
        -------
        AidbStopResponse
            Information about the stopped session
        """
        # Stop the session (which handles disconnect internally)
        await self.session.stop()

        return AidbStopResponse(
            success=True,
            message="Debug session stopped",
            stopped_session=[self.session.id],
        )
