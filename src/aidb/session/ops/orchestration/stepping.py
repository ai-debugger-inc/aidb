"""Stepping orchestration operations."""

from typing import TYPE_CHECKING, Optional

from aidb.dap.protocol.bodies import (
    NextArguments,
    StepBackArguments,
    StepInArguments,
    StepOutArguments,
)
from aidb.dap.protocol.requests import (
    NextRequest,
    StepBackRequest,
    StepInRequest,
    StepOutRequest,
)
from aidb.dap.protocol.types import SteppingGranularity
from aidb.models import ExecutionStateResponse

from ..base import SessionOperationsMixin
from ..decorators import requires_capability
from ..instrumentation import instrument_step
from .decorators import clears_frame_cache

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.interfaces import IContext
    from aidb.session import Session


def _convert_granularity(granularity: str | None) -> SteppingGranularity | None:
    """Convert string granularity to SteppingGranularity enum.

    Parameters
    ----------
    granularity : str, optional
        String granularity value

    Returns
    -------
    SteppingGranularity, optional
        Enum value or None
    """
    if granularity is None:
        return None
    try:
        return SteppingGranularity(granularity)
    except ValueError:
        # Default to statement if invalid value
        return SteppingGranularity.STATEMENT


class SteppingOperations(SessionOperationsMixin):
    """Stepping orchestration operations."""

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize stepping operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

    @instrument_step("step_into")
    @clears_frame_cache
    async def step_into(
        self,
        thread_id: int,
        target_id: int | None = None,
        granularity: str | None = None,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Step into the next function call.

        Parameters
        ----------
        thread_id : int
            AidbThread to perform step operation on
        target_id : int, optional
            Target to step into (for selective stepping)
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')
        wait_for_stop : bool
            If True, wait for a stopped event after stepping (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after stepping
        """
        args = StepInArguments(
            threadId=thread_id,
            targetId=target_id,
            granularity=_convert_granularity(granularity),
        )
        request = StepInRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )

        # DAP client now waits for stopped/terminated for step operations.
        # When this returns, we can immediately map the resulting state
        # without adding a second wait (avoids double-wait races).
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # If session terminated during the step, return terminated state
        if getattr(self.session.dap, "is_terminated", False):
            from aidb.models import ExecutionState, SessionStatus, StopReason

            exec_state = ExecutionState(
                status=SessionStatus.TERMINATED,
                running=False,
                paused=False,
                stop_reason=StopReason.EXIT,
                terminated=True,
            )
            return ExecutionStateResponse(success=True, execution_state=exec_state)

        # Otherwise, we are stopped; build a proper stopped execution state
        from .execution import _build_stopped_execution_state

        return await _build_stopped_execution_state(self)

    @instrument_step("step_out")
    @clears_frame_cache
    async def step_out(
        self,
        thread_id: int,
        granularity: str | None = None,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Step out of the current function.

        Parameters
        ----------
        thread_id : int
            AidbThread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')
        wait_for_stop : bool
            If True, wait for a stopped event after stepping (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after stepping
        """
        args = StepOutArguments(
            threadId=thread_id,
            granularity=_convert_granularity(granularity),
        )
        request = StepOutRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )

        # Let DAP client handle waiting for stop/terminate and map immediately
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        if getattr(self.session.dap, "is_terminated", False):
            from aidb.models import ExecutionState, SessionStatus, StopReason

            exec_state = ExecutionState(
                status=SessionStatus.TERMINATED,
                running=False,
                paused=False,
                stop_reason=StopReason.EXIT,
                terminated=True,
            )
            return ExecutionStateResponse(success=True, execution_state=exec_state)

        from .execution import _build_stopped_execution_state

        return await _build_stopped_execution_state(self)

    @instrument_step("step_over")
    @clears_frame_cache
    async def step_over(
        self,
        thread_id: int,
        granularity: str | None = None,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Step over the next statement.

        Parameters
        ----------
        thread_id : int
            AidbThread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')
        wait_for_stop : bool
            If True, wait for a stopped event after stepping (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after stepping
        """
        args = NextArguments(
            threadId=thread_id,
            granularity=_convert_granularity(granularity),
        )
        request = NextRequest(seq=await self.session.dap.get_next_seq(), arguments=args)

        # Let DAP client handle waiting for stop/terminate and map immediately
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        if getattr(self.session.dap, "is_terminated", False):
            from aidb.models import ExecutionState, SessionStatus, StopReason

            exec_state = ExecutionState(
                status=SessionStatus.TERMINATED,
                running=False,
                paused=False,
                stop_reason=StopReason.EXIT,
                terminated=True,
            )
            return ExecutionStateResponse(success=True, execution_state=exec_state)

        from .execution import _build_stopped_execution_state

        return await _build_stopped_execution_state(self)

    @requires_capability("supportsStepBack", "step back")
    @instrument_step("step_back")
    @clears_frame_cache
    async def step_back(
        self,
        thread_id: int,
        granularity: str | None = None,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Step backwards to the previous statement.

        Parameters
        ----------
        thread_id : int
            AidbThread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')
        wait_for_stop : bool
            If True, wait for a stopped event after stepping (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after stepping backwards

        Raises
        ------
        NotImplementedError
            If the debug adapter doesn't support stepping backwards
        """
        args = StepBackArguments(
            threadId=thread_id,
            granularity=_convert_granularity(granularity),
        )
        request = StepBackRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=args,
        )

        # Let DAP client handle waiting for stop/terminate and map immediately
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        if getattr(self.session.dap, "is_terminated", False):
            from aidb.models import ExecutionState, SessionStatus, StopReason

            exec_state = ExecutionState(
                status=SessionStatus.TERMINATED,
                running=False,
                paused=False,
                stop_reason=StopReason.EXIT,
                terminated=True,
            )
            return ExecutionStateResponse(success=True, execution_state=exec_state)

        from .execution import _build_stopped_execution_state

        return await _build_stopped_execution_state(self)
