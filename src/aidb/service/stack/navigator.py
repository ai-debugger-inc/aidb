"""Stack and thread navigation service operations."""

from typing import TYPE_CHECKING

from aidb.common.capabilities import DAPCapability, OperationName
from aidb.common.constants import STACK_TRACE_TIMEOUT_S
from aidb.dap.protocol.bodies import (
    ExceptionInfoArguments,
    ModulesArguments,
    ScopesArguments,
    StackTraceArguments,
)
from aidb.dap.protocol.requests import (
    ExceptionInfoRequest,
    ModulesRequest,
    ScopesRequest,
    StackTraceRequest,
    ThreadsRequest,
)
from aidb.dap.protocol.responses import (
    ExceptionInfoResponse,
    ModulesResponse,
    ScopesResponse,
    StackTraceResponse,
    ThreadsResponse,
)
from aidb.dap.protocol.types import Scope
from aidb.models import (
    AidbCallStackResponse,
    AidbExceptionResponse,
    AidbModulesResponse,
    AidbStackFrame,
    AidbThreadsResponse,
    ExecutionStateResponse,
    Module,
)
from aidb.models.entities.session import ExecutionState, SessionStatus, StopReason
from aidb.service.decorators import requires_capability

from ..base import BaseServiceComponent

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class StackService(BaseServiceComponent):
    """Stack and thread navigation service.

    Provides methods for inspecting call stacks, threads, frames, scopes, exception
    information, and execution state.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize stack service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def callstack(self, thread_id: int) -> AidbCallStackResponse:
        """Get call stack for a specific thread.

        Parameters
        ----------
        thread_id : int
            ID of the thread to get call stack for

        Returns
        -------
        AidbCallStackResponse
            Call stack frames for the specified thread
        """
        request = StackTraceRequest(
            seq=0,
            arguments=StackTraceArguments(threadId=thread_id),
        )

        stack_response = await self._send_and_ensure(request, StackTraceResponse)
        if stack_response.body and stack_response.body.stackFrames:
            return AidbCallStackResponse.from_dap(stack_response)
        return AidbCallStackResponse(frames=[])

    async def threads(self) -> AidbThreadsResponse:
        """Get all threads and their current states.

        Returns
        -------
        AidbThreadsResponse
            Response containing all threads and their current states
        """
        request = ThreadsRequest(seq=0)

        threads_response = await self._send_and_ensure(
            request,
            ThreadsResponse,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        return AidbThreadsResponse.from_dap(threads_response)

    async def frame(self, frame_id: int | None = None) -> AidbStackFrame:
        """Get information about a stack frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get info for. If None, uses current active frame.

        Returns
        -------
        AidbStackFrame
            Information about the specified stack frame

        Raises
        ------
        ValueError
            If frame with specified ID is not found
        """
        thread_id = await self.get_current_thread_id()
        frame_id = await self._resolve_frame_id(frame_id)

        request = StackTraceRequest(
            seq=0,
            arguments=StackTraceArguments(threadId=thread_id),
        )

        stack_response = await self._send_and_ensure(request, StackTraceResponse)
        frame = AidbCallStackResponse.get_frame_from_dap(stack_response, frame_id)

        if frame is None:
            msg = f"Frame with ID {frame_id} not found in thread {thread_id}"
            raise ValueError(msg)

        return frame

    async def get_scopes(self, frame_id: int | None = None) -> list[Scope]:
        """Get variable scopes for a stack frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get scopes for. If None, uses current frame.

        Returns
        -------
        list[Scope]
            List of available scopes in the frame
        """
        frame_id = await self._resolve_frame_id(frame_id)

        request = ScopesRequest(
            seq=0,
            arguments=ScopesArguments(frameId=frame_id),
        )

        scopes_response = await self._send_and_ensure(request, ScopesResponse)

        if scopes_response.body and scopes_response.body.scopes:
            return scopes_response.body.scopes
        return []

    @requires_capability(DAPCapability.EXCEPTION_INFO, OperationName.EXCEPTION_INFO)
    async def exception(self, thread_id: int) -> AidbExceptionResponse:
        """Get exception information for specific thread.

        Parameters
        ----------
        thread_id : int
            ID of the thread to get exception information for

        Returns
        -------
        AidbExceptionResponse
            Exception information including details and break mode
        """
        request = ExceptionInfoRequest(
            seq=0,
            arguments=ExceptionInfoArguments(threadId=thread_id),
        )

        exception_response = await self._send_and_ensure(request, ExceptionInfoResponse)
        return AidbExceptionResponse.from_dap(exception_response)

    @requires_capability(DAPCapability.MODULES, OperationName.MODULES)
    async def get_modules(
        self,
        start_module: int = 0,
        module_count: int = 100,
    ) -> AidbModulesResponse:
        """Get list of loaded modules.

        Parameters
        ----------
        start_module : int
            Index of first module to return
        module_count : int
            Maximum number of modules to return

        Returns
        -------
        AidbModulesResponse
            Response containing list of loaded modules
        """
        request = ModulesRequest(
            seq=0,
            arguments=ModulesArguments(
                startModule=start_module,
                moduleCount=module_count,
            ),
        )

        mod_response = await self._send_and_ensure(
            request,
            ModulesResponse,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        body = mod_response.body if mod_response.body else None

        if body and hasattr(body, "modules"):
            modules = [
                Module(
                    id=int(mod.id) if isinstance(mod.id, int | str) else 0,
                    name=mod.name,
                    path=mod.path if hasattr(mod, "path") else None,
                    isOptimized=(
                        mod.isOptimized if hasattr(mod, "isOptimized") else None
                    ),
                    isUserCode=mod.isUserCode if hasattr(mod, "isUserCode") else None,
                    version=mod.version if hasattr(mod, "version") else None,
                    symbolStatus=(
                        mod.symbolStatus if hasattr(mod, "symbolStatus") else None
                    ),
                    symbolFilePath=(
                        mod.symbolFilePath if hasattr(mod, "symbolFilePath") else None
                    ),
                    dateTimeStamp=(
                        mod.dateTimeStamp if hasattr(mod, "dateTimeStamp") else None
                    ),
                    addressRange=(
                        mod.addressRange if hasattr(mod, "addressRange") else None
                    ),
                )
                for mod in body.modules
            ]
            return AidbModulesResponse(
                success=True,
                modules=modules,
                totalModules=(
                    body.totalModules if hasattr(body, "totalModules") else None
                ),
            )
        return AidbModulesResponse(
            success=False,
            modules=[],
            message="No modules in response",
        )

    async def get_execution_state(self) -> ExecutionStateResponse:
        """Get current execution state of the debug session.

        Returns
        -------
        ExecutionStateResponse
            Current execution state with status, location, and stop reason
        """
        session_status = self.session.status
        self.ctx.debug(f"[get_execution_state] session_status={session_status}")

        terminated = session_status in (SessionStatus.TERMINATED, SessionStatus.ERROR)
        paused = session_status == SessionStatus.PAUSED
        running = session_status == SessionStatus.RUNNING
        self.ctx.debug(
            f"[get_execution_state] terminated={terminated}, paused={paused}, "
            f"running={running}",
        )

        stop_reason = None
        thread_id = None
        frame_id = None
        current_file = None
        current_line = None
        exception_info = None

        if terminated:
            stop_reason = StopReason.EXIT

        elif paused:
            try:
                if hasattr(self.session.dap, "_event_processor") and hasattr(
                    self.session.dap._event_processor,
                    "_state",
                ):
                    processor_state = self.session.dap._event_processor._state
                    if processor_state.stop_reason:
                        stop_reason = processor_state.stop_reason
                        self.ctx.debug(
                            f"[get_execution_state] Got stop_reason from processor: "
                            f"{stop_reason}",
                        )
                    else:
                        stop_reason = StopReason.UNKNOWN
                        self.ctx.debug(
                            "[get_execution_state] No stop_reason in processor, "
                            "using UNKNOWN",
                        )

                thread_id = await self.get_current_thread_id()
                self.ctx.debug(f"[get_execution_state] thread_id={thread_id}")

                callstack_response = await self.callstack(thread_id)
                frames = callstack_response.frames
                frames_count = len(frames) if frames else 0
                self.ctx.debug(
                    f"[get_execution_state] callstack success="
                    f"{callstack_response.success}, frames_count={frames_count}",
                )
                if callstack_response.success and callstack_response.frames:
                    top_frame = callstack_response.frames[0]
                    frame_id = top_frame.id
                    current_file = top_frame.source.path if top_frame.source else None
                    current_line = top_frame.line
                    self.ctx.debug(
                        f"[get_execution_state] Got location: file={current_file}, "
                        f"line={current_line}",
                    )

                if stop_reason == StopReason.EXCEPTION:
                    try:
                        exc_response = await self.exception(thread_id)
                        if exc_response.success:
                            exception_info = {
                                "description": exc_response.exception_id,
                                "details": exc_response.description,
                                "break_mode": exc_response.break_mode,
                            }
                    except Exception as exc:
                        self.ctx.debug(f"Could not get exception info: {exc}")

            except Exception as e:
                self.ctx.debug(f"Could not get full execution context: {e}")
                if stop_reason is None:
                    stop_reason = StopReason.UNKNOWN

        exec_state = ExecutionState(
            status=session_status,
            running=running,
            paused=paused,
            terminated=terminated,
            stop_reason=stop_reason,
            thread_id=thread_id,
            frame_id=frame_id,
            current_file=current_file,
            current_line=current_line,
            exception_info=exception_info,
        )

        self.ctx.debug(f"[get_execution_state] Built exec_state: {exec_state}")

        return ExecutionStateResponse(
            success=True,
            execution_state=exec_state,
        )
