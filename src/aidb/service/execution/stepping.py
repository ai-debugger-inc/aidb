"""Stepping service operations."""

from typing import TYPE_CHECKING

from aidb.common.capabilities import DAPCapability, OperationName
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
from aidb.dap.protocol.responses import (
    NextResponse,
    StepBackResponse,
    StepInResponse,
    StepOutResponse,
)
from aidb.dap.protocol.types import SteppingGranularity
from aidb.models import ExecutionStateResponse
from aidb.service.decorators import requires_capability

from ..base import BaseServiceComponent

if TYPE_CHECKING:
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
        return SteppingGranularity.STATEMENT


class SteppingService(BaseServiceComponent):
    """Stepping service operations.

    Provides methods for stepping through code: step_into, step_out,
    step_over, and step_back.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize stepping service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def step_into(
        self,
        thread_id: int,
        target_id: int | None = None,
        granularity: str | None = None,
    ) -> ExecutionStateResponse:
        """Step into the next function call.

        Parameters
        ----------
        thread_id : int
            Thread to perform step operation on
        target_id : int, optional
            Target to step into (for selective stepping)
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')

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

        await self._send_and_ensure(request, StepInResponse)

        if getattr(self.session.dap, "is_terminated", False):
            return self._build_terminated_state()

        return await self._build_stopped_execution_state()

    async def step_out(
        self,
        thread_id: int,
        granularity: str | None = None,
    ) -> ExecutionStateResponse:
        """Step out of the current function.

        Parameters
        ----------
        thread_id : int
            Thread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')

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

        await self._send_and_ensure(request, StepOutResponse)

        if getattr(self.session.dap, "is_terminated", False):
            return self._build_terminated_state()

        return await self._build_stopped_execution_state()

    async def step_over(
        self,
        thread_id: int,
        granularity: str | None = None,
    ) -> ExecutionStateResponse:
        """Step over the next statement.

        Parameters
        ----------
        thread_id : int
            Thread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')

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

        await self._send_and_ensure(request, NextResponse)

        if getattr(self.session.dap, "is_terminated", False):
            return self._build_terminated_state()

        return await self._build_stopped_execution_state()

    @requires_capability(DAPCapability.STEP_BACK, OperationName.STEP_BACK)
    async def step_back(
        self,
        thread_id: int,
        granularity: str | None = None,
    ) -> ExecutionStateResponse:
        """Step backwards to the previous statement.

        Parameters
        ----------
        thread_id : int
            Thread to perform step operation on
        granularity : str, optional
            Stepping granularity ('statement', 'line', 'instruction')

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

        await self._send_and_ensure(request, StepBackResponse)

        if getattr(self.session.dap, "is_terminated", False):
            return self._build_terminated_state()

        return await self._build_stopped_execution_state()
