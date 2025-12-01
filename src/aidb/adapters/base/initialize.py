"""DAP initialization sequence definitions for debug adapters."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any


class InitializationOpType(Enum):
    """Types of DAP operations in initialization sequence."""

    INITIALIZE = "initialize"
    WAIT_FOR_INITIALIZED = "wait_for_initialized"
    WAIT_FOR_PLUGIN_READY = "wait_for_plugin_ready"
    ATTACH = "attach"
    LAUNCH = "launch"
    SET_BREAKPOINTS = "set_breakpoints"
    WAIT_FOR_BREAKPOINT_VERIFICATION = "wait_for_breakpoint_verification"
    CONFIGURATION_DONE = "configuration_done"
    WAIT_FOR_ATTACH_RESPONSE = "wait_for_attach_response"
    WAIT_FOR_LAUNCH_RESPONSE = "wait_for_launch_response"
    CUSTOM = "custom"
    WAIT = "wait"


@dataclass
class InitializationOp:
    """A single DAP operation with optional parameters.

    Attributes
    ----------
    type : InitializationOpType
        The type of operation to perform
    wait_for_response : bool
        Whether to wait for a response from this operation
    timeout : float
        Timeout in seconds for waiting for responses or events
    optional : bool
        If True, failures in this operation won't stop the sequence
    """

    type: InitializationOpType
    wait_for_response: bool = True
    timeout: float = 15.0
    optional: bool = False
    name: str | None = None
    handler: Callable[[dict[str, Any]], None] | None = None
