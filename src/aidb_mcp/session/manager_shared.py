"""Shared state for session management.

This module contains the global state variables used by the session manager and its
split modules.
"""

from __future__ import annotations

import threading
import time
import traceback
from typing import TYPE_CHECKING

from aidb_logging import get_mcp_logger

if TYPE_CHECKING:
    from aidb import DebugService

    from .context import MCPSessionContext

logger = get_mcp_logger(__name__)


class TrackedRLock:
    """RLock wrapper with timeout detection for debugging deadlocks.

    Uses a 10-second timeout to detect potential deadlocks. Normal lock operations are
    logged at DEBUG level; failures are logged at ERROR level with stack traces.
    """

    def __init__(self, name: str = "state_lock"):
        self._lock = threading.RLock()
        self._name = name
        self._holder_thread: str | None = None
        self._holder_stack: str | None = None
        self._acquire_time: float | None = None
        self._acquire_count = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquire the lock with deadlock detection.

        Parameters
        ----------
        blocking : bool, optional
            If True, block until lock is acquired. Default is True.
        timeout : float, optional
            Maximum time to wait for lock. If -1, uses default timeout
            of 10 seconds for deadlock detection.

        Returns
        -------
        bool
            True if lock was acquired, False otherwise.
        """
        thread_name = threading.current_thread().name

        logger.debug(
            "[LOCK] %s: Thread '%s' acquiring (holder=%s)",
            self._name,
            thread_name,
            self._holder_thread,
        )

        start = time.monotonic()
        # Use timeout to detect potential deadlocks
        actual_timeout = timeout if timeout >= 0 else 10.0
        result = self._lock.acquire(blocking=blocking, timeout=actual_timeout)
        elapsed = time.monotonic() - start

        if result:
            self._holder_thread = thread_name
            self._holder_stack = "".join(traceback.format_stack()[-5:-1])
            self._acquire_time = time.monotonic()
            self._acquire_count += 1
            logger.debug(
                "[LOCK] %s: Thread '%s' acquired (%.3fs, count=%d)",
                self._name,
                thread_name,
                elapsed,
                self._acquire_count,
            )
        else:
            # Failure to acquire is always an error - log with full details
            stack = "".join(traceback.format_stack()[-5:-1])
            logger.error(
                "[LOCK] %s: Thread '%s' FAILED to acquire after %.3fs! "
                "Holder: %s\nHolder stack:\n%s\nCaller stack:\n%s",
                self._name,
                thread_name,
                elapsed,
                self._holder_thread,
                self._holder_stack,
                stack,
            )

        return result

    def release(self) -> None:
        """Release the lock and clear holder tracking state."""
        thread_name = threading.current_thread().name
        held_duration = (
            time.monotonic() - self._acquire_time if self._acquire_time else 0
        )
        logger.debug(
            "[LOCK] %s: Thread '%s' releasing (held %.3fs)",
            self._name,
            thread_name,
            held_duration,
        )
        self._holder_thread = None
        self._holder_stack = None
        self._acquire_time = None
        self._lock.release()

    def __enter__(self):
        result = self.acquire()
        if not result:
            msg = (
                f"Failed to acquire {self._name} after timeout - "
                f"possible deadlock (holder was: {self._holder_thread})"
            )
            raise RuntimeError(msg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# Thread safety for global state - use tracked lock for debugging
_state_lock = TrackedRLock("MCP_STATE_LOCK")  # Reentrant lock for nested calls

# Multi-session support
# _DEBUG_SESSIONS and _DEBUG_SERVICES now point to the same DebugService instances
# _DEBUG_SESSIONS kept for backward compatibility with health checks, resources, etc.
_DEBUG_SESSIONS: dict[str, DebugService] = {}
_DEBUG_SERVICES: dict[str, DebugService] = {}  # DebugService instances wrapping Session
_SESSION_CONTEXTS: dict[str, MCPSessionContext] = {}
_DEFAULT_SESSION_ID: str | None = None  # Track the default session

# Init context for tracking init tool state (thread-safe with _state_lock)
_INIT_CONTEXT: dict[str, bool | str | None] = {
    "initialized": False,
    "language": None,
    "framework": None,
    "mode": None,
}
