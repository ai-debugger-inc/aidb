"""Debug service layer for AIDB.

The service layer provides stateless orchestration operations that operate
on Session infrastructure. This is the primary interface for MCP handlers.

Architecture:
    MCP Handlers → DebugService → Session → Adapters → DAP

The service layer is organized into focused sub-services:
    - ExecutionService: Program execution control (continue, pause, step)
    - BreakpointService: Breakpoint management (set, remove, list)
    - VariableService: Variable inspection and modification
    - StackService: Call stack and thread operations
"""

from .base import BaseServiceComponent
from .breakpoints import BreakpointService
from .debug_service import DebugService
from .execution import ExecutionControl, SteppingService
from .stack import StackService
from .variables import VariableService

__all__ = [
    "BaseServiceComponent",
    "BreakpointService",
    "DebugService",
    "ExecutionControl",
    "StackService",
    "SteppingService",
    "VariableService",
]
