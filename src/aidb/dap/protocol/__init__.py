"""DAP Protocol Package.

This package contains auto-generated Debug Adapter Protocol classes.
"""

# Base classes
from .base import (
    DAPDataclass,
    Event,
    ImmutableAfterInit,
    ProtocolMessage,
    Request,
    Response,
)
from .bodies import *  # noqa: F403
from .events import *  # noqa: F403

# Import all protocol classes for convenience
from .requests import *  # noqa: F403
from .responses import *  # noqa: F403
from .types import *  # noqa: F403

__all__ = [
    "DAPDataclass",
    "ImmutableAfterInit",
    "ProtocolMessage",
    "Request",
    "Response",
    "Event",
]
