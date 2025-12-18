"""Base operations class with shared state and utilities."""

from typing import TYPE_CHECKING, Literal, Optional

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
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
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
        return resolve_active_session(self._session, self.ctx)

    async def _execute_initialization_sequence(self, sequence) -> None:
        """Execute the DAP initialization sequence.

        This stub exists to satisfy type checking for OrchestrationMixin. The actual
        implementation is in InitializationMixin.
        """
        msg = "This method is implemented in InitializationMixin"
        raise NotImplementedError(msg)

    async def get_current_thread_id(self) -> int:
        """Get the current active thread ID.

        This method delegates to the shared utility and caches the result.

        Returns
        -------
        int
            The active thread ID
        """
        # Delegate to shared utility
        thread_id = await _get_current_thread_id(self.session, self.ctx)

        # Cache the result for BaseOperations (stateful layer)
        self._current_thread_id = thread_id
        return thread_id

    async def get_current_frame_id(self, thread_id: int | None = None) -> int:
        """Get the current active frame ID for a thread.

        This method delegates to the shared utility and caches the result.

        Parameters
        ----------
        thread_id : int, optional
            Thread ID to get frame for. If None, uses current thread.

        Returns
        -------
        int
            The active frame ID (top of stack)
        """
        # Delegate to shared utility
        frame_id = await _get_current_frame_id(self.session, self.ctx, thread_id)

        # Cache the result for BaseOperations (stateful layer)
        self._current_frame_id = frame_id
        return frame_id

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
        return await _wait_for_stop_or_terminate(self.session, self.ctx, operation_name)


# Alias for compatibility with orchestration submodules
SessionOperationsMixin = BaseOperations
