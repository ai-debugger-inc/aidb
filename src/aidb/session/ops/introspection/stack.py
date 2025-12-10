"""Stack and thread introspection operations."""

from typing import TYPE_CHECKING, cast

from aidb.api.constants import STACK_TRACE_TIMEOUT_S
from aidb.common import AidbContext
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
from aidb.dap.protocol.types import Scope
from aidb.models import (
    AidbCallStackResponse,
    AidbExceptionResponse,
    AidbModulesResponse,
    AidbStackFrame,
    AidbThreadsResponse,
    Module,
)

from ..base import SessionOperationsMixin
from ..decorators import requires_capability

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import (
        ExceptionInfoResponse,
        ModulesResponse,
        ScopesResponse,
        StackTraceResponse,
        ThreadsResponse,
    )
    from aidb.session import Session


class StackOperations(SessionOperationsMixin):
    """Stack and thread introspection operations."""

    def __init__(self, session: "Session", ctx: AidbContext | None = None) -> None:
        """Initialize stack operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
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
            seq=0,  # Will be overwritten by client
            arguments=StackTraceArguments(threadId=thread_id),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Cast to proper response type and create AidbCallStackResponse
        stack_response = cast("StackTraceResponse", response)
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
        request = ThreadsRequest(seq=0)  # Will be overwritten by client

        # Use resilient request method with automatic recovery
        response: Response = await self.session.dap.send_request(
            request,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        response.ensure_success()

        # Cast to proper response type and create AidbThreadsResponse
        threads_response = cast("ThreadsResponse", response)
        return AidbThreadsResponse.from_dap(threads_response)

    async def frame(self, frame_id: int | None = None) -> AidbStackFrame:
        """Get information about a stack frame.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to get info for. If None, uses current active frame, by
            default None

        Returns
        -------
        AidbStackFrame
            Information about the specified stack frame
        """
        # Get current thread ID dynamically
        thread_id = await self.get_current_thread_id()

        # If no specific frame_id requested, get the current active frame
        if frame_id is None:
            frame_id = await self.get_current_frame_id(thread_id)

        request = StackTraceRequest(
            seq=0,  # Will be overwritten by client
            arguments=StackTraceArguments(threadId=thread_id),
        )

        response: Response = await self.session.dap.send_request(request)
        stack_response = cast("StackTraceResponse", response)
        stack_response.ensure_success()

        # Use the from_dap method to extract the specific frame
        frame = AidbCallStackResponse.get_frame_from_dap(stack_response, frame_id)

        if frame is None:
            msg = f"Frame with ID {frame_id} not found in thread {thread_id}"
            raise ValueError(
                msg,
            )

        return frame

    async def get_scopes(self, frame_id: int) -> list[Scope]:
        """Get variable scopes for a stack frame.

        Parameters
        ----------
        frame_id : int
            Frame ID to get scopes for

        Returns
        -------
        list[Scope]
            List of available scopes in the frame
        """
        request = ScopesRequest(
            seq=0,  # Will be overwritten by client
            arguments=ScopesArguments(frameId=frame_id),
        )

        response: Response = await self.session.dap.send_request(request)
        scopes_response = cast("ScopesResponse", response)
        scopes_response.ensure_success()

        # Return the scopes from the response
        if scopes_response.body and scopes_response.body.scopes:
            return scopes_response.body.scopes
        return []

    @requires_capability("supportsExceptionInfoRequest", "exception information")
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
            seq=0,  # Will be overwritten by client
            arguments=ExceptionInfoArguments(threadId=thread_id),
        )

        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

        # Cast to proper response type and create AidbExceptionResponse
        exception_response = cast("ExceptionInfoResponse", response)
        return AidbExceptionResponse.from_dap(exception_response)

    @requires_capability("supportsModulesRequest", "module introspection")
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

        Raises
        ------
        AdapterCapabilityNotSupportedError
            If the adapter does not support module introspection
        """
        request = ModulesRequest(
            seq=0,
            arguments=ModulesArguments(
                startModule=start_module,
                moduleCount=module_count,
            ),
        )

        response: Response = await self.session.dap.send_request(
            request,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        response.ensure_success()

        mod_response = cast("ModulesResponse", response)
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
