"""Stack and thread inspection operations."""

from typing import TYPE_CHECKING, Optional

from aidb.audit.middleware import audit_operation
from aidb.common.errors import AidbError
from aidb.dap.protocol.types import Scope
from aidb.models import (
    AidbCallStackResponse,
    AidbExceptionResponse,
    AidbModulesResponse,
    AidbStackFrame,
    AidbThreadsResponse,
)
from aidb.session import Session

from ..base import APIOperationBase
from ..dap_utils import resolve_frame_id, resolve_thread_id

if TYPE_CHECKING:
    from aidb.common import AidbContext


class StackOperations(APIOperationBase):
    """Stack and thread inspection operations."""

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the StackOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    @audit_operation(component="api.introspection", operation="get_callstack")
    async def callstack(self, thread_id: int | None = None) -> AidbCallStackResponse:
        """Get the call stack for a thread.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to get stack for, by default None (current thread)

        Returns
        -------
        AidbCallStackResponse
            Call stack frames

        Raises
        ------
        AidbError
            If session is not paused
        """
        if not self.session.is_paused():
            current_status = self.session.status.name
            msg = (
                f"Cannot get call stack - session is not paused "
                f"(current status: {current_status})"
            )
            raise AidbError(msg)

        # Use session's current thread ID from stopped event if not explicitly provided
        # This is critical for remote attach where thread IDs may not start at 1
        if thread_id is None:
            resolved_thread_id = await self.session.debug.get_current_thread_id()
        else:
            resolved_thread_id = resolve_thread_id(thread_id)

        # Delegate to session.debug.callstack() which handles all the DAP logic
        return await self.session.debug.callstack(thread_id=resolved_thread_id)

    @audit_operation(component="api.introspection", operation="get_frame")
    async def frame(self, frame_id: int | None = None) -> AidbStackFrame:
        """Get information about a specific stack frame.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID, by default None (top frame)

        Returns
        -------
        AidbStackFrame
            Information about the frame

        Raises
        ------
        AidbError
            If session is not paused or frame not found
        """
        if not self.session.is_paused():
            current_status = self.session.status.name
            msg = (
                f"Cannot get frame - session is not paused "
                f"(current status: {current_status})"
            )
            raise AidbError(msg)

        resolved_frame_id = resolve_frame_id(frame_id)

        # Delegate to session.debug.frame() which handles all the DAP logic
        return await self.session.debug.frame(frame_id=resolved_frame_id)

    @audit_operation(component="api.introspection", operation="get_threads")
    async def threads(self) -> AidbThreadsResponse:
        """Get all threads in the debugged process.

        This operation is automatically audited when audit logging is enabled.

        Returns
        -------
        AidbThreadsResponse
            All threads in the process
        """
        # Delegate to session.debug.threads() which handles all the DAP logic
        return await self.session.debug.threads()

    @audit_operation(component="api.introspection", operation="get_scopes")
    async def scopes(self, frame_id: int | None = None) -> list[Scope]:
        """Get variable scopes for a stack frame.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        frame_id : int, optional
            Frame to get scopes for, by default None (top frame)

        Returns
        -------
        list[Scope]
            List of available scopes in the frame

        Raises
        ------
        AidbError
            If session is not paused or frame not found
        """
        if not self.session.is_paused():
            current_status = self.session.status.name
            msg = (
                f"Cannot get scopes - session is not paused "
                f"(current status: {current_status})"
            )
            raise AidbError(msg)

        resolved_frame_id = resolve_frame_id(frame_id)

        # Delegate to session.debug.get_scopes() which handles all the DAP logic
        return await self.session.debug.get_scopes(frame_id=resolved_frame_id)

    @audit_operation(component="api.introspection", operation="get_exception")
    async def exception(self, thread_id: int | None = None) -> AidbExceptionResponse:
        """Get exception information for a thread.

        This operation is automatically audited when audit logging is enabled.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread to get exception for, by default None

        Returns
        -------
        AidbExceptionResponse
            Exception details if available

        Raises
        ------
        AidbError
            If no exception information available
        """
        resolved_thread_id = resolve_thread_id(thread_id)

        # Delegate to session.debug.exception() which handles all the DAP logic
        return await self.session.debug.exception(thread_id=resolved_thread_id)

    @audit_operation(component="api.introspection", operation="get_modules")
    async def get_modules(self) -> AidbModulesResponse:
        """Get loaded modules information.

        This operation is automatically audited when audit logging is enabled.

        Returns
        -------
        AidbModulesResponse
            Information about loaded modules

        Raises
        ------
        AidbError
            If modules request is not supported
        """
        # Check if modules are supported
        if not self.session.supports_modules():
            msg = "Modules request is not supported by this debug adapter"
            raise AidbError(msg)

        # Delegate to session.debug.get_modules() which handles all the DAP logic
        return await self.session.debug.get_modules()
