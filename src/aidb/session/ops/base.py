"""Base operations class with shared state and utilities."""

import asyncio
from typing import TYPE_CHECKING, Literal, Optional, cast

from aidb.api.constants import SHORT_SLEEP_S, STACK_TRACE_TIMEOUT_S
from aidb.common.errors import DebugTimeoutError
from aidb.dap.protocol.bodies import StackTraceArguments
from aidb.dap.protocol.requests import StackTraceRequest, ThreadsRequest
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import StackTraceResponse, ThreadsResponse
    from aidb.interfaces import IContext
    from aidb.session import Session


class BaseOperations(Obj):
    """Base class for session debugger operations.

    Provides shared state management and utilities used across all operation mixins.
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize base operations.

        Parameters
        ----------
        session : Session
            The session that owns this debugger operations
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(ctx=ctx)
        self._session = session

        # Shared execution state tracking
        self._current_thread_id: int | None = None
        self._current_frame_id: int | None = None

        # Initialization sequence state
        self._operation_responses: dict[str, Response] = {}

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
        # If this is already a child, return as-is
        if self._session.is_child:
            return self._session

        # For adapters requiring child sessions, always use child when it exists
        # The child is THE active session - no conditional logic
        if (
            hasattr(self._session, "adapter")
            and self._session.adapter
            and hasattr(self._session.adapter, "requires_child_session_wait")
            and self._session.adapter.requires_child_session_wait
            and self._session.child_session_ids
        ):
            # Resolve to first child (JavaScript only has one)
            child_id = self._session.child_session_ids[0]
            child = self._session.registry.get_session(child_id)

            if child:
                self.ctx.debug(
                    f"Resolved operation session {self._session.id} → child {child.id}",
                )
                return child

            # Child ID registered but session not found - shouldn't happen
            self.ctx.warning(
                f"Child session {child_id} registered but not found in registry",
            )

        return self._session

    async def _execute_initialization_sequence(self, sequence) -> None:
        """Execute the DAP initialization sequence.

        This stub exists to satisfy type checking for OrchestrationMixin. The actual
        implementation is in InitializationMixin.
        """
        msg = "This method is implemented in InitializationMixin"
        raise NotImplementedError(msg)

    async def get_current_thread_id(self) -> int:
        """Get the current active thread ID.

        Returns
        -------
        int
            The active thread ID

        Raises
        ------
        ValueError
            If no active thread can be found
        """
        # First, check if the DAP client has a current thread ID from a stopped event
        if hasattr(self.session.dap, "_event_processor") and hasattr(
            self.session.dap._event_processor,
            "_state",
        ):
            dap_thread_id = self.session.dap._event_processor._state.current_thread_id
            if dap_thread_id is not None:
                self.ctx.debug(
                    f"Using thread ID {dap_thread_id} from "
                    f"DAP client state (stopped event)",
                )
                self._current_thread_id = dap_thread_id
                return dap_thread_id

        # Try to get threads to find an active one
        try:
            self.ctx.debug("Attempting to get current threads...")
            request = ThreadsRequest(seq=0)
            response: Response = await self.session.dap.send_request(request)
            threads_response = cast("ThreadsResponse", response)
            threads_response.ensure_success()

            if threads_response.body and threads_response.body.threads:
                thread_count = len(threads_response.body.threads)
                self.ctx.debug(f"Found {thread_count} threads")
                # Return the first available thread (most likely the main
                # thread)
                first_thread = threads_response.body.threads[0]
                self.ctx.debug(
                    f"Using thread ID {first_thread.id} (name: {first_thread.name})",
                )
                self._current_thread_id = first_thread.id
                return first_thread.id
            self.ctx.warning("Threads response had no body or no threads")

        except Exception as e:
            self.ctx.warning(f"Failed to get threads: {type(e).__name__}: {e}")

        # Fallback to cached value or default
        if self._current_thread_id is not None:
            self.ctx.debug(f"Using cached thread ID {self._current_thread_id}")
            return self._current_thread_id

        # Last resort: return 1 (common default for main thread)
        self.ctx.warning(
            "Using fallback thread ID 1 - thread tracking may be unreliable",
        )
        return 1

    async def get_current_frame_id(self, thread_id: int | None = None) -> int:
        """Get the current active frame ID for a thread.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread ID to get frame for. If None, uses current thread.

        Returns
        -------
        int
            The active frame ID (top of stack)

        Raises
        ------
        ValueError
            If no active frame can be found
        """
        if thread_id is None:
            thread_id = await self.get_current_thread_id()

        try:
            self.ctx.debug(f"Attempting to get stack trace for thread {thread_id}...")
            request = StackTraceRequest(
                seq=0,
                arguments=StackTraceArguments(threadId=thread_id),
            )

            # Add explicit timeout to prevent infinite waits (especially Java pooled)
            response: Response = await self.session.dap.send_request(
                request,
                timeout=STACK_TRACE_TIMEOUT_S,
            )
            stack_response = cast("StackTraceResponse", response)
            stack_response.ensure_success()

            if stack_response.body and stack_response.body.stackFrames:
                frame_count = len(stack_response.body.stackFrames)
                self.ctx.debug(
                    f"Found {frame_count} stack frames for thread {thread_id}",
                )
                # Return the top frame (index 0)
                top_frame = stack_response.body.stackFrames[0]
                self.ctx.debug(
                    f"Using frame ID {top_frame.id} "
                    f"(name: {top_frame.name}, line: {top_frame.line})",
                )
                self._current_frame_id = top_frame.id
                return top_frame.id
            self.ctx.warning(
                f"Stack trace response for thread {thread_id} had no body or no frames",
            )

        except Exception as e:
            self.ctx.warning(
                f"Failed to get stack trace for thread "
                f"{thread_id}: {type(e).__name__}: {e}",
            )

        # Fallback to cached value or default
        if self._current_frame_id is not None:
            self.ctx.debug(f"Using cached frame ID {self._current_frame_id}")
            return self._current_frame_id

        # Last resort: return 0 (common default for top frame)
        self.ctx.warning("Using fallback frame ID 0 - frame tracking may be unreliable")
        return 0

    async def _wait_for_stop_or_terminate(
        self,
        operation_name: str,
    ) -> Literal["stopped", "terminated", "timeout"]:
        """Wait for stopped or terminated using event subscription.

        This is a helper method that bridges the async subscription API with
        the synchronous orchestration methods.

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

        # Await the result directly
        result = await self.session.events.wait_for_stopped_or_terminated_async(
            timeout=self.session.dap.DEFAULT_WAIT_TIMEOUT,
        )

        if result == "timeout":
            msg = f"Timeout waiting for stop after {operation_name}"
            raise DebugTimeoutError(msg)

        return cast("Literal['stopped', 'terminated', 'timeout']", result)


# Alias for compatibility with orchestration submodules
SessionOperationsMixin = BaseOperations
