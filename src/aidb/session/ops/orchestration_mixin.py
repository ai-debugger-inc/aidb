"""Orchestration operations mixin for execution control.

This module delegates to the orchestration subpackage modules for better organization.
"""

import asyncio
from typing import TYPE_CHECKING, Literal, Optional, cast

from aidb.api.constants import SHORT_SLEEP_S
from aidb.common.errors import DebugTimeoutError
from aidb.dap.protocol.bodies import (
    RestartArguments,
    SetBreakpointsArguments,
    SetDataBreakpointsArguments,
    SetExceptionBreakpointsArguments,
    SetFunctionBreakpointsArguments,
)
from aidb.dap.protocol.requests import (
    ContinueRequest,
    GotoRequest,
    PauseRequest,
    SetBreakpointsRequest,
    SetDataBreakpointsRequest,
    SetExceptionBreakpointsRequest,
    SetFunctionBreakpointsRequest,
)
from aidb.dap.protocol.types import (
    DataBreakpoint,
    ExceptionFilterOptions,
    ExceptionOptions,
    FunctionBreakpoint,
    Source,
    SourceBreakpoint,
)
from aidb.models import (
    AidbBreakpointsResponse,
    AidbDataBreakpointInfoResponse,
    AidbDataBreakpointsResponse,
    AidbExceptionBreakpointsResponse,
    AidbFunctionBreakpointsResponse,
    AidbStopResponse,
    ExecutionStateResponse,
    StartResponse,
)

from .base import BaseOperations
from .orchestration import (
    BreakpointOperations,
    ExecutionOperations,
    SteppingOperations,
)

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class OrchestrationMixin(BaseOperations):
    """Orchestration operations mixin for execution control.

    This class delegates to the specialized operation classes in the orchestration
    subpackage.
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize orchestration operations.

        Parameters
        ----------
        session : Session
            The session that owns this debugger operations
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

        # Initialize delegated operation classes
        self._breakpoint_ops = BreakpointOperations(session, ctx)
        self._execution_ops = ExecutionOperations(session, ctx)
        self._stepping_ops = SteppingOperations(session, ctx)

    async def _wait_for_stop_or_terminate(
        self,
        operation_name: str,
    ) -> Literal["stopped", "terminated", "timeout"]:
        """Wait for stopped or terminated event using event subscription.

        This is a helper method that bridges the async subscription API with the
        synchronous orchestration methods.

        Parameters
        ----------
        operation_name : str
            Name of the operation for error messages

        Returns
        -------
        Literal["stopped", "terminated", "timeout"]
            The result of waiting

        Raises
        ------
        DebugTimeoutError
            If timeout occurs
        """
        # Use subscription-based waiting
        if not hasattr(self.session.events, "wait_for_stopped_or_terminated_async"):
            await asyncio.sleep(SHORT_SLEEP_S)
            return "stopped"

        # Await the result directly (edge-triggered to wait for NEXT event)
        result = await self.session.events.wait_for_stopped_or_terminated_async(
            timeout=self.session.dap.DEFAULT_WAIT_TIMEOUT,
            edge_triggered=True,
        )
        self.ctx.debug(
            f"_wait_for_stop_or_terminate: "
            f"wait_for_stopped_or_terminated_async returned: '{result}'",
        )

        if result == "timeout":
            msg = f"Timeout waiting for stop after {operation_name}"
            raise DebugTimeoutError(msg)

        self.ctx.debug(f"_wait_for_stop_or_terminate: returning '{result}'")
        return cast("Literal['stopped', 'terminated', 'timeout']", result)

    # Execution Control Operations (delegated to ExecutionOperations)

    async def start(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Start or launch the debug session.

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event after
            starting. If None (default), will auto-wait only if breakpoints are
            set.
        wait_timeout : float, optional
            Timeout in seconds for auto-wait, default 5.0

        Returns
        -------
        StartResponse
            Response containing session startup status and information
        """
        return await self._execution_ops.start(
            auto_wait=auto_wait,
            wait_timeout=wait_timeout,
        )

    async def stop(self) -> AidbStopResponse:
        """Stop the debug session.

        Returns
        -------
        AidbStopResponse
            Response containing session termination status
        """
        return await self._execution_ops.stop()

    async def continue_(
        self,
        request: ContinueRequest,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Continue execution until the next breakpoint.

        Parameters
        ----------
        request : ContinueRequest
            DAP request specifying thread to continue and execution options
        wait_for_stop : bool
            If True, wait for a stopped event after continue (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after continuing
        """
        return await self._execution_ops.continue_(request, wait_for_stop)

    async def pause(self, request: PauseRequest) -> ExecutionStateResponse:
        """Pause the execution.

        Parameters
        ----------
        request : PauseRequest
            DAP request specifying which thread to pause

        Returns
        -------
        ExecutionStateResponse
            Current execution state after pausing
        """
        return await self._execution_ops.pause(request)

    async def goto(self, request: GotoRequest) -> ExecutionStateResponse:
        """Jump to a specific location in the target.

        Parameters
        ----------
        request : GotoRequest
            DAP request containing target location and thread information

        Returns
        -------
        ExecutionStateResponse
            Current execution state after jumping to the target location
        """
        return await self._execution_ops.goto(request)

    async def restart(self, arguments: RestartArguments | None = None) -> None:
        """Restart the current debug session.

        Parameters
        ----------
        arguments : RestartArguments, optional
            Optional restart arguments specifying new configuration
        """
        return await self._execution_ops.restart(arguments)

    # Stepping Operations (delegated to SteppingOperations)

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
        return await self._stepping_ops.step_into(
            thread_id,
            target_id,
            granularity,
            wait_for_stop,
        )

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
        return await self._stepping_ops.step_out(thread_id, granularity, wait_for_stop)

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
        return await self._stepping_ops.step_over(thread_id, granularity, wait_for_stop)

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
        return await self._stepping_ops.step_back(thread_id, granularity, wait_for_stop)

    # AidbBreakpoint Operations (delegated to BreakpointOperations)

    async def breakpoint(
        self,
        request: "SetBreakpointsRequest",
    ) -> AidbBreakpointsResponse:
        """Set breakpoints using DAP protocol request.

        Parameters
        ----------
        request : SetBreakpointsRequest
            DAP protocol request for setting breakpoints

        Returns
        -------
        AidbBreakpointsResponse
            Response containing the status of each requested breakpoint
        """
        return await self._breakpoint_ops.breakpoint(request)

    async def set_breakpoints(
        self,
        source: Source,
        breakpoints: list[SourceBreakpoint],
    ) -> AidbBreakpointsResponse:
        """Set line breakpoints in a source file.

        Parameters
        ----------
        source : Source
            Source file to set breakpoints in
        breakpoints : List[SourceBreakpoint]
            List of breakpoint definitions with line numbers and optional
            conditions

        Returns
        -------
        AidbBreakpointsResponse
            Response containing the status of each requested breakpoint
        """
        # Create a SetBreakpointsRequest for the breakpoint operation
        args = SetBreakpointsArguments(
            source=source,
            breakpoints=breakpoints if breakpoints else [],
        )
        request = SetBreakpointsRequest(seq=0, arguments=args)
        return await self._breakpoint_ops.breakpoint(request)

    async def set_logpoints(
        self,
        source_path: str,
        logpoints: list[SourceBreakpoint],
    ) -> AidbBreakpointsResponse:
        """Set logpoints for debugging without stopping execution.

        Logpoints are like breakpoints but instead of stopping execution, they
        log a message to the debug console. This is useful for tracing execution
        without interrupting the program flow.

        Parameters
        ----------
        source_path : str
            Path to the source file where logpoints should be set
        logpoints : List[SourceBreakpoint]
            List of logpoint specifications with line numbers and log messages

        Returns
        -------
        AidbBreakpointsResponse
            Response containing successfully set logpoints with their IDs

        Raises
        ------
        NotImplementedError
            If the debug adapter doesn't support logpoints
        """
        return await self._breakpoint_ops.set_logpoints(source_path, logpoints)

    async def set_function_breakpoints(
        self,
        breakpoints: list[FunctionBreakpoint],
    ) -> AidbFunctionBreakpointsResponse:
        """Set function breakpoints.

        Parameters
        ----------
        breakpoints : List[FunctionBreakpoint]
            List of function names to set breakpoints on

        Returns
        -------
        AidbFunctionBreakpointsResponse
            Response containing the status of each requested function breakpoint
        """
        args = SetFunctionBreakpointsArguments(breakpoints=breakpoints)
        request = SetFunctionBreakpointsRequest(seq=0, arguments=args)
        return await self._breakpoint_ops.function_breakpoint(request)

    async def set_exception_breakpoints(
        self,
        filters: list[str],
        filter_options: list[ExceptionFilterOptions] | None = None,
        exception_options: list[ExceptionOptions] | None = None,
    ) -> AidbExceptionBreakpointsResponse:
        """Set exception breakpoints.

        Parameters
        ----------
        filters : List[str]
            List of exception filter IDs to enable
        filter_options : List[ExceptionFilterOptions], optional
            Options for exception filters
        exception_options : List[ExceptionOptions], optional
            Specific exception types to break on

        Returns
        -------
        AidbExceptionBreakpointsResponse
            Response confirming exception breakpoint configuration
        """
        args = SetExceptionBreakpointsArguments(filters=filters)
        if filter_options:
            args.filterOptions = filter_options
        if exception_options:
            args.exceptionOptions = exception_options
        request = SetExceptionBreakpointsRequest(seq=0, arguments=args)
        return await self._breakpoint_ops.exception_breakpoint(request)

    async def set_data_breakpoints(
        self,
        breakpoints: list[DataBreakpoint],
    ) -> AidbDataBreakpointsResponse:
        """Set data breakpoints (watchpoints).

        Parameters
        ----------
        breakpoints : List[DataBreakpoint]
            List of data breakpoints with addresses and access types

        Returns
        -------
        AidbDataBreakpointsResponse
            Response containing the status of each requested data breakpoint
        """
        args = SetDataBreakpointsArguments(breakpoints=breakpoints)
        request = SetDataBreakpointsRequest(seq=0, arguments=args)
        return await self._breakpoint_ops.data_breakpoint(request)

    async def get_data_breakpoint_info(
        self,
        variable_reference: int | None = None,
        name: str | None = None,
        _frame_id: int | None = None,
    ) -> AidbDataBreakpointInfoResponse:
        """Get information needed to set a data breakpoint.

        Parameters
        ----------
        variable_reference : int, optional
            Reference to the variable container
        name : str, optional
            Name of the variable
        frame_id : int, optional
            Frame context for evaluation

        Returns
        -------
        AidbDataBreakpointInfoResponse
            Information required to set a data breakpoint for the variable
        """
        # Note: frame_id is not used by the current implementation
        if variable_reference is None:
            msg = "variable_reference is required"
            raise ValueError(msg)
        if name is None:
            msg = "name is required"
            raise ValueError(msg)
        return await self._breakpoint_ops.get_data_breakpoint_info(
            variable_reference,
            name,
        )

    async def clear_breakpoints(
        self,
        source: Source | None = None,
        clear_all: bool = False,
    ) -> AidbBreakpointsResponse:
        """Clear breakpoints in a source file or all breakpoints.

        Parameters
        ----------
        source : Source, optional
            If provided, clear only breakpoints in this source.
        clear_all : bool, optional
            If True, clear all breakpoints from all files.

        Returns
        -------
        AidbBreakpointsResponse
            Empty response confirming breakpoints were cleared
        """
        # Convert Source to string path if provided
        source_path = source.path if source and hasattr(source, "path") else None
        return await self._breakpoint_ops.clear_breakpoints(
            source_path,
            _clear_all=clear_all,
        )

    async def remove_breakpoint(
        self,
        source_path: str,
        line: int,
    ) -> AidbBreakpointsResponse:
        """Remove a single breakpoint from a source file.

        Parameters
        ----------
        source_path : str
            Path to the source file
        line : int
            Line number of the breakpoint to remove

        Returns
        -------
        AidbBreakpointsResponse
            Updated breakpoints for the file
        """
        return await self._breakpoint_ops.remove_breakpoint(source_path, line)

    async def clear_function_breakpoints(
        self,
        names: list[str] | None = None,
    ) -> AidbFunctionBreakpointsResponse:
        """Clear function breakpoints.

        Parameters
        ----------
        names : Optional[List[str]]
            Specific function names to clear breakpoints from.
            If None, clears all function breakpoints.

        Returns
        -------
        AidbFunctionBreakpointsResponse
            Response confirming function breakpoints were cleared
        """
        return await self._breakpoint_ops.clear_function_breakpoints(names)

    async def clear_data_breakpoints(self) -> AidbDataBreakpointsResponse:
        """Clear all data breakpoints.

        Returns
        -------
        AidbDataBreakpointsResponse
            Empty response confirming data breakpoints were cleared
        """
        return await self._breakpoint_ops.clear_data_breakpoints()
