"""Session handlers package.

Aggregates session-related handlers for initialization, lifecycle, management, and
configuration.
"""

from __future__ import annotations

from ...session.manager_state import (
    get_init_context,
    get_init_language,
    is_initialized,
    reset_init_context,
    set_init_context,
)
from .configuration import HANDLERS as CONFIG_HANDLERS
from .initialization import HANDLERS as INIT_HANDLERS
from .lifecycle import HANDLERS as LIFECYCLE_HANDLERS
from .management import HANDLERS as MGMT_HANDLERS

# Aggregate all handler dictionaries
HANDLERS = {
    **INIT_HANDLERS,
    **LIFECYCLE_HANDLERS,
    **MGMT_HANDLERS,
    **CONFIG_HANDLERS,
}

__all__ = [
    "HANDLERS",
    "get_init_context",
    "get_init_language",
    "is_initialized",
    "reset_init_context",
    "set_init_context",
]
