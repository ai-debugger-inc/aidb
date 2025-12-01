"""DAP client capabilities.

This module defines what capabilities the DAP client supports. These are sent TO
the debug adapter during initialization.

Note: This is different from adapter capabilities, which are received FROM the
debug adapter in the InitializeResponse.
"""

from typing import Any

# These correspond to fields in InitializeRequestArguments
CLIENT_CAPABILITIES: dict[str, Any] = {
    # Basic client info
    "clientID": "aidb",
    "clientName": "ai-debugger",
    "locale": "en-US",
    # Path and formatting
    "pathFormat": "path",
    "columnsStartAt1": True,
    "linesStartAt1": True,
    # AidbVariable support
    "supportsVariableType": True,
    "supportsVariablePaging": False,
    # Terminal and process support
    "supportsRunInTerminalRequest": False,
    "supportsArgsCanBeInterpretedByShell": False,
    # Memory support
    "supportsMemoryReferences": True,  # Enable memory read/write operations
    "supportsMemoryEvent": True,  # Enable memory event handling
    # UI and progress
    "supportsProgressReporting": False,
    "supportsANSIStyling": False,
    # Events
    "supportsInvalidatedEvent": True,
    # Multi-session debugging support
    "supportsStartDebuggingRequest": True,  # Enable for multi-session support
}
