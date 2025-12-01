"""Orchestration operations for debugging control flow.

This package provides orchestration operations organized into logical groups:
- AidbBreakpoint operations (set, clear, exception, function, data breakpoints)
- Execution control (continue, pause, goto, restart, stop)
- Step operations (step_into, step_over, step_out)
"""

from typing import TYPE_CHECKING, Optional

from aidb.session import Session

from .breakpoints import BreakpointOperations
from .execution import ExecutionOperations
from .stepping import SteppingOperations

if TYPE_CHECKING:
    from aidb.common import AidbContext


class APIOrchestrationOperations(
    BreakpointOperations,
    ExecutionOperations,
    SteppingOperations,
):
    """Combined orchestration operations for the API.

    This class combines all orchestration operations through multiple inheritance,
    providing a single interface for all debugging control flow operations.
    """

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the APIOrchestrationOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)


__all__ = [
    "APIOrchestrationOperations",
    "BreakpointOperations",
    "ExecutionOperations",
    "SteppingOperations",
]
