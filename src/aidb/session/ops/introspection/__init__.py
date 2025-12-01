"""Introspection operations subpackage.

This subpackage contains introspection operations split into focused modules:
- variables.py: AidbVariable inspection and modification operations
- memory.py: Memory read/write and disassembly operations
- stack.py: Stack frames, threads, and module operations
"""

from .memory import MemoryOperations
from .stack import StackOperations
from .variables import VariableOperations

__all__ = [
    "VariableOperations",
    "MemoryOperations",
    "StackOperations",
]
