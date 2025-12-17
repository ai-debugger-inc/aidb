"""Base service component with shared utilities."""

from typing import TYPE_CHECKING, Literal, TypeVar, cast

from aidb.common.dap_utilities import (
    get_current_frame_id as _get_current_frame_id,
)
from aidb.common.dap_utilities import (
    get_current_thread_id as _get_current_thread_id,
)
from aidb.common.dap_utilities import (
    resolve_active_session,
)
from aidb.common.dap_utilities import (
    wait_for_stop_or_terminate as _wait_for_stop_or_terminate,
)
from aidb.dap.client.constants import StopReason as DAPStopReason
from aidb.models import ExecutionStateResponse
from aidb.models.entities.session import ExecutionState, SessionStatus, StopReason
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Request, Response
    from aidb.interfaces import IContext
    from aidb.session import Session

# TypeVar for typed response helper
T = TypeVar("T", bound="Response")


class BaseServiceComponent(Obj):
    """Base class for service components.

    Provides session access and common utilities for all service operations.
    Unlike session ops, service components are stateless - they operate on
    the Session's state rather than maintaining their own.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize the service component.

        Parameters
        ----------
        session : Session
            The session to operate on
        ctx : IContext, optional
            Application context. If None, uses session's context.
        """
        super().__init__(ctx=ctx or session.ctx)
        self._session = session

    @property
    def session(self) -> "Session":
        """Get the active session, resolving to child if applicable.

        For languages with child sessions (e.g., JavaScript), the child session
        becomes the active session once it exists. All operations are routed to
        the child unconditionally.

        Returns
        -------
        Session
            The active session (child if exists, otherwise parent)
        """
        return resolve_active_session(self._session, self.ctx)

    @property
    def dap(self):
        """Get the DAP client for the active session.

        Returns
        -------
        DAPClient
            The DAP client instance
        """
        return self.session.dap

    async def get_current_thread_id(self) -> int:
        """Get the current active thread ID.

        Returns
        -------
        int
            The active thread ID
        """
        return await _get_current_thread_id(self.session, self.ctx)

    async def get_current_frame_id(self, thread_id: int | None = None) -> int:
        """Get the current active frame ID for a thread.

        Parameters
        ----------
        thread_id : int, optional
            Thread ID to get frame for. If None, uses current thread.

        Returns
        -------
        int
            The active frame ID (top of stack)
        """
        return await _get_current_frame_id(self.session, self.ctx, thread_id)

    async def _wait_for_stop_or_terminate(
        self,
        operation_name: str,
    ) -> Literal["stopped", "terminated", "timeout"]:
        """Wait for stopped or terminated using event subscription.

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
        return await _wait_for_stop_or_terminate(self.session, self.ctx, operation_name)

    async def _send_and_ensure(
        self,
        request: "Request",
        response_type: type[T],  # noqa: ARG002 - used for type inference
        timeout: float | None = None,
    ) -> T:
        """Send a DAP request and ensure success, returning typed response.

        This helper consolidates the common pattern of sending a request,
        ensuring success, and casting to the expected response type.

        Parameters
        ----------
        request : Request
            The DAP request to send
        response_type : type[T]
            The expected response type for casting
        timeout : float, optional
            Optional timeout override

        Returns
        -------
        T
            The typed response

        Raises
        ------
        DAPError
            If the request fails
        """
        if timeout is not None:
            response = await self.session.dap.send_request(request, timeout=timeout)
        else:
            response = await self.session.dap.send_request(request)
        response.ensure_success()
        return cast("T", response)

    async def _resolve_frame_id(self, frame_id: int | None = None) -> int:
        """Resolve frame_id, using current frame if None.

        Parameters
        ----------
        frame_id : int, optional
            The frame ID to use, or None to use current frame

        Returns
        -------
        int
            The resolved frame ID
        """
        if frame_id is not None:
            return frame_id
        thread_id = await self.get_current_thread_id()
        return await self.get_current_frame_id(thread_id)

    def _build_terminated_state(self) -> ExecutionStateResponse:
        """Build ExecutionStateResponse for terminated state.

        Returns
        -------
        ExecutionStateResponse
            Response indicating the session has terminated
        """
        exec_state = ExecutionState(
            status=SessionStatus.TERMINATED,
            running=False,
            paused=False,
            stop_reason=StopReason.EXIT,
            terminated=True,
        )
        return ExecutionStateResponse(success=True, execution_state=exec_state)

    async def _build_stopped_execution_state(self) -> ExecutionStateResponse:
        """Build ExecutionStateResponse for stopped state.

        Retrieves stop reason from DAP event processor and current position
        from the call stack.

        Returns
        -------
        ExecutionStateResponse
            Response with proper stopped state information
        """
        # Import here to avoid circular import - StackService imports from this module
        from aidb.service.stack import StackService

        resolved_session = self.session
        self.ctx.debug(
            f"_build_stopped_execution_state: parent_session={self._session.id}, "
            f"resolved_session={resolved_session.id}, "
            f"is_child={resolved_session.is_child}",
        )

        # Get stop reason from DAP event processor
        event_processor = self.session.dap._event_processor
        stop_reason_str = None

        if hasattr(event_processor, "_last_stopped_event"):
            last_stopped = event_processor._last_stopped_event
            if last_stopped and hasattr(last_stopped, "body") and last_stopped.body:
                stop_reason_str = getattr(last_stopped.body, "reason", None)

        if stop_reason_str is None:
            stop_reason_str = getattr(event_processor._state, "stop_reason", None)

        if stop_reason_str is None:
            stop_reason_str = "unknown"

        stop_reason_map = {
            DAPStopReason.BREAKPOINT.value: StopReason.BREAKPOINT,
            DAPStopReason.STEP.value: StopReason.STEP,
            DAPStopReason.PAUSE.value: StopReason.PAUSE,
            DAPStopReason.EXCEPTION.value: StopReason.EXCEPTION,
            DAPStopReason.ENTRY.value: StopReason.ENTRY,
            DAPStopReason.EXIT.value: StopReason.EXIT,
        }
        stop_reason = stop_reason_map.get(stop_reason_str, StopReason.UNKNOWN)

        thread_id = await self.get_current_thread_id()
        self.ctx.debug(
            f"_build_stopped_execution_state: thread_id={thread_id}, "
            f"stop_reason={stop_reason}",
        )

        # Try to get current file/line from stack trace
        current_file = None
        current_line = None
        try:
            stack_service = StackService(self.session, self.ctx)
            stack_response = await stack_service.callstack(thread_id=thread_id)
            frame_count = len(stack_response.frames) if stack_response.frames else 0
            self.ctx.debug(
                f"Call stack result: success={stack_response.success}, "
                f"frames_count={frame_count}",
            )
            if stack_response.success and stack_response.top_frame:
                top_frame = stack_response.top_frame
                if top_frame.source and top_frame.source.path:
                    current_file = top_frame.source.path
                    current_line = top_frame.source.line
        except Exception as e:
            self.ctx.debug(f"Could not get call stack for position: {e}")

        exec_state = ExecutionState(
            status=SessionStatus.PAUSED,
            running=False,
            paused=True,
            stop_reason=stop_reason,
            thread_id=thread_id,
            current_file=current_file,
            current_line=current_line,
            terminated=False,
        )

        return ExecutionStateResponse(success=True, execution_state=exec_state)
