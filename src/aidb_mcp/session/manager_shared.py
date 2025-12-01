"""Shared state for session management.

This module contains the global state variables used by the session manager and its
split modules.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aidb import DebugAPI

    from .context import MCPSessionContext

# Thread safety for global state
_state_lock = threading.RLock()  # Reentrant lock for nested calls

# Multi-session support
_DEBUG_SESSIONS: dict[str, DebugAPI] = {}
_SESSION_CONTEXTS: dict[str, MCPSessionContext] = {}
_DEFAULT_SESSION_ID: str | None = None  # Track the default session
