"""Introspection operations for debugging state inspection.

This package provides introspection operations organized into logical groups:
- AidbVariable operations (locals, globals, evaluate, set_variable, watch)
- Memory operations (read_memory, write_memory, disassemble)
- Stack operations (callstack, threads, frames, scopes, exception, modules)
"""

from typing import TYPE_CHECKING, Optional

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


__all__ = [
    "APIIntrospectionOperations",
    "VariableOperations",
    "MemoryOperations",
    "StackOperations",
]
