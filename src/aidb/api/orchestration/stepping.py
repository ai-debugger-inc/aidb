"""Step operations for debugging control flow."""

from typing import TYPE_CHECKING, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.models import ExecutionStateResponse
from aidb.session import Session

from ..base import APIOperationBase
from ..constants import DEFAULT_STEP_GRANULARITY
from ..dap_utils import (
    resolve_thread_id,
)

if TYPE_CHECKING:
    from aidb.common import AidbContext


class SteppingOperations(APIOperationBase):
    """Step operations for debugging control flow."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the SteppingOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def _execute_step_operation(
        self,
        operation: str,
        thread_id: int | None = None,
        granularity: str = DEFAULT_STEP_GRANULARITY,
    ) -> ExecutionStateResponse:
        """Execute a step operation.

        Parameters
        ----------
        operation : str
            The step operation type ("stepIn", "stepOut", "next")
        thread_id : int, optional
            AidbThread to step, by default None (queries current thread)
        granularity : str
            Step granularity ("statement", "line", "instruction")

        Returns
        -------
        ExecutionStateResponse
            Execution state after stepping

        Raises
        ------
        AidbError
            If session is not paused
        """
        # Check DAP stopped state, not just session status
        # This handles child sessions that stop at breakpoints during initialization
        # where DAP is stopped but session status is still INITIALIZED
        if not self.session.is_dap_stopped():
            current_status = self.session.status.name
            msg = (
                f"Cannot {operation} - session is not paused "
                f"(current status: {current_status})"
            )
            raise AidbError(msg)

        # If no thread specified, get current thread from active session
        # This ensures we use the correct thread ID for child sessions
        if thread_id is None:
            resolved_thread_id = await self.session.debug.get_current_thread_id()
        else:
            resolved_thread_id = resolve_thread_id(thread_id)

        # Call the appropriate session.debug method with wait_for_stop=True
        if operation == "stepIn":
            response = await self.session.debug.step_into(
                thread_id=resolved_thread_id,
                granularity=granularity,
                wait_for_stop=True,
            )
        elif operation == "stepOut":
            response = await self.session.debug.step_out(
                thread_id=resolved_thread_id,
                granularity=granularity,
                wait_for_stop=True,
            )
        elif operation == "next":
            response = await self.session.debug.step_over(
                thread_id=resolved_thread_id,
                granularity=granularity,
                wait_for_stop=True,
            )
        else:
            msg = f"Unknown step operation: {operation}"
            raise AidbError(msg)

        return response

    @audit_operation(component="api.orchestration", operation="step_into")
    async def step_into(
        self,
        thread_id: int | None = None,
        granularity: str = DEFAULT_STEP_GRANULARITY,
    ) -> ExecutionStateResponse:
        """Step into the next function call.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to step, by default None (current thread)
        granularity : str
            Step granularity: "statement", "line", or "instruction"

        Returns
        -------
        ExecutionStateResponse
            Execution state after stepping

        Raises
        ------
        AidbError
            If session is not paused
        """
        return await self._execute_step_operation(
            "stepIn",
            thread_id,
            granularity,
        )

    @audit_operation(component="api.orchestration", operation="step_out")
    async def step_out(
        self,
        thread_id: int | None = None,
        granularity: str = DEFAULT_STEP_GRANULARITY,
    ) -> ExecutionStateResponse:
        """Step out of the current function.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to step, by default None (current thread)
        granularity : str
            Step granularity: "statement", "line", or "instruction"

        Returns
        -------
        ExecutionStateResponse
            Execution state after stepping

        Raises
        ------
        AidbError
            If session is not paused
        """
        return await self._execute_step_operation(
            "stepOut",
            thread_id,
            granularity,
        )

    @audit_operation(component="api.orchestration", operation="step_over")
    async def step_over(
        self,
        thread_id: int | None = None,
        granularity: str = DEFAULT_STEP_GRANULARITY,
    ) -> ExecutionStateResponse:
        """Step over the current line.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to step, by default None (current thread)
        granularity : str
            Step granularity: "statement", "line", or "instruction"

        Returns
        -------
        ExecutionStateResponse
            Execution state after stepping

        Raises
        ------
        AidbError
            If session is not paused
        """
        return await self._execute_step_operation(
            "next",
            thread_id,
            granularity,
        )
