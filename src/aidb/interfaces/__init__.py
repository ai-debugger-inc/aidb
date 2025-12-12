"""Protocol interfaces for AIDB components.

This package defines Protocol interfaces that enable clean architectural boundaries
between packages, eliminating circular dependencies while maintaining type safety.
"""

from .adapter import ILaunchOrchestrator, IPortManager, IProcessManager
from .context import IContext
from .dap import IDAPClient
from .error_reporting import LogLevel
from .resources import ResourceType
from .session import ISession, ISessionResource

__all__ = [
    "IContext",
    "IDAPClient",
    "ILaunchOrchestrator",
    "IPortManager",
    "IProcessManager",
    "ISession",
    "ISessionResource",
    "LogLevel",
    "ResourceType",
]
