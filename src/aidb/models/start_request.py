"""Start request type enumeration for debug sessions."""

from enum import Enum


class StartRequestType(Enum):
    """Debug session start request types as defined by DAP.

    These define how a debug session is initiated - either by launching
    a new process or attaching to an existing one.
    """

    LAUNCH = "launch"  # Start a new process to debug
    ATTACH = "attach"  # Attach to an existing process

    def __str__(self) -> str:
        """Return the string value for DAP compatibility."""
        return self.value
