"""Protocol interfaces for AIDB components.

This package defines Protocol interfaces that enable clean architectural boundaries
between packages, eliminating circular dependencies while maintaining type safety.
"""

from .adapter import IAdapter, IAdapterRegistry
from .api import IDebugAPI, IResourceManager, ISessionBuilder, ISessionManager
from .context import IContext
from .dap import IDAPClient
from .error_reporting import LogLevel
from .resources import ResourceType
from .session import ISession, ISessionResource

__all__ = [
    "IAdapter",
    "IAdapterRegistry",
    "IContext",
    "IDAPClient",
    "IDebugAPI",
    "IResourceManager",
    "ISession",
    "ISessionBuilder",
    "ISessionManager",
    "ISessionResource",
    "LogLevel",
    "ResourceType",
]
