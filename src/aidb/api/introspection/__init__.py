"""Introspection operations for debugging state inspection.

This package provides introspection operations organized into logical groups:
- AidbVariable operations (locals, globals, evaluate, set_variable, watch)
- Memory operations (read_memory, write_memory, disassemble)
- Stack operations (callstack, threads, frames, scopes, exception, modules)
- Output operations (get_output for logpoints, stdout, stderr)
"""

from typing import TYPE_CHECKING, Any, Optional

from aidb.session import Session

from .memory import MemoryOperations
from .stack import StackOperations
from .variables import VariableOperations

if TYPE_CHECKING:
    from aidb.common import AidbContext


class APIIntrospectionOperations(VariableOperations, MemoryOperations, StackOperations):
    """Combined introspection operations for the API.

    This class combines all introspection operations through multiple inheritance,
    providing a single interface for all debugging state inspection operations.
    """

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the APIIntrospectionOperations instance.

        Parameters
        ----------
        session : Session
            Session to use
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def get_output(self, clear: bool = True) -> list[dict[str, Any]]:
        """Get collected program output (logpoints, stdout, stderr).

        Output is collected from DAP output events during program execution.
        Logpoint messages appear with category "console".

        Parameters
        ----------
        clear : bool
            If True (default), clears the buffer after retrieval to avoid
            returning duplicate output on subsequent calls.

        Returns
        -------
        list[dict[str, Any]]
            List of output entries, each with:
            - category: "console" (logpoints), "stdout", "stderr", etc.
            - output: The output text
            - timestamp: Unix timestamp when output was received
        """
        return self.session.get_output(clear=clear)


__all__ = [
    "APIIntrospectionOperations",
    "VariableOperations",
    "MemoryOperations",
    "StackOperations",
]
