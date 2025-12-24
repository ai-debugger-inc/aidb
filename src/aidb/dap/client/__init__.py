"""New DAP client with clean architecture.

This package provides a redesigned DAP client that fixes the architectural
issues in the original implementation:

- No circular dependencies
- Event handlers never send requests
- Single request path through client.send_request()
- Proper thread safety and request serialization
- Clean separation of concerns

The main entry points are:
- DAPClient: Low-level client for direct DAP protocol access
- SessionState: Shared state tracking
- EventProcessor: Event handling without request sending
"""

from .capabilities import CLIENT_CAPABILITIES
from .client import DAPClient
from .constants import CONNECTION_SETUP_COMMANDS
from .events import EventProcessor
from .receiver import MessageReceiver, start_receiver
from .state import SessionState
from .transport import DAPTransport

__all__ = [
    "CLIENT_CAPABILITIES",
    # Main classes
    "DAPClient",
    "SessionState",
    "EventProcessor",
    "DAPTransport",
    "MessageReceiver",
    # Utilities
    "start_receiver",
    "CONNECTION_SETUP_COMMANDS",
]

# Version info
__version__ = "0.1.0"
