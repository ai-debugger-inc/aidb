"""Interface definitions for resource management components."""

from enum import Enum


class ResourceType(Enum):
    """Types of resources that can be managed."""

    PORT = "port"
    PROCESS = "process"
    FILE = "file"
    SESSION = "session"
