"""Main debug service providing stateless debugging operations on a Session."""

from typing import TYPE_CHECKING

from aidb.patterns import Obj

from .breakpoints import BreakpointService
from .execution import ExecutionControl, SteppingService
from .stack import StackService
from .variables import VariableService

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session


class DebugService(Obj):
    """Stateless debugging operations on a Session.

    This class aggregates all debugging sub-services and provides a unified
    interface for debugging operations. It is designed to be stateless - all
    state is maintained in the Session object.

    Parameters
    ----------
    session : Session
        Debug session instance
    ctx : IContext, optional
        Application context

    Attributes
    ----------
    execution : ExecutionControl
        Execution control operations (continue, pause, restart, stop, start)
    stepping : SteppingService
        Step operations (step_into, step_over, step_out)
    breakpoints : BreakpointService
        Breakpoint management (set, remove, clear, list)
    variables : VariableService
        Variable inspection and modification
    stack : StackService
        Stack and thread navigation
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize the debug service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context. If not provided, uses session's context.
        """
        super().__init__(ctx=ctx or session.ctx)
        self._session = session

        # Initialize sub-services
        self.execution = ExecutionControl(session, self.ctx)
        self.stepping = SteppingService(session, self.ctx)
        self.breakpoints = BreakpointService(session, self.ctx)
        self.variables = VariableService(session, self.ctx)
        self.stack = StackService(session, self.ctx)

    @property
    def session(self) -> "Session":
        """Get the active debug session, resolving to child if applicable.

        For languages with child sessions (e.g., JavaScript), the child session
        becomes the active session once it exists. All operations are routed to
        the child unconditionally.

        Returns
        -------
        Session
            The active session (child if exists, otherwise parent)
        """
        from aidb.common.dap_utilities import resolve_active_session

        return resolve_active_session(self._session, self.ctx)
