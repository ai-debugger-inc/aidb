"""Context management for aidb_logging using contextvars.

This module provides thread-safe context variables for tracking session IDs, request
IDs, and other contextual information across async and sync code.
"""

import contextvars
import threading
import time
import weakref
from typing import Any

from aidb_common.patterns import Singleton

# Context variables for different types of context
_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "session_id",
    default=None,
)

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)

_request_start_time: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "request_start_time",
    default=None,
)

_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "log_context",
    default=None,
)


# Session context management
def set_session_id(session_id: str | None) -> None:
    """Set the current session ID for logging context.

    Parameters
    ----------
    session_id : str or None
        The session ID to set
    """
    _session_id.set(session_id)


def get_session_id() -> str | None:
    """Get the current session ID.

    Returns
    -------
    str or None
        The current session ID
    """
    return _session_id.get()


def clear_session_id() -> None:
    """Clear the session ID from context."""
    _session_id.set(None)


# Request context management
def set_request_id(request_id: str | None) -> None:
    """Set the current request ID for logging context.

    Parameters
    ----------
    request_id : str or None
        The request ID to set
    """
    _request_id.set(request_id)


def get_request_id() -> str | None:
    """Get the current request ID.

    Returns
    -------
    str or None
        The current request ID
    """
    return _request_id.get()


def clear_request_id() -> None:
    """Clear the request ID from context."""
    _request_id.set(None)


# Request timing
def start_request_timing() -> None:
    """Start timing for the current request."""
    _request_start_time.set(time.time())


def get_request_duration() -> int | None:
    """Get current request duration in milliseconds.

    Returns
    -------
    int or None
        Duration in milliseconds, or None if not started
    """
    start_time = _request_start_time.get()
    if start_time:
        return int((time.time() - start_time) * 1000)
    return None


def clear_request_timing() -> None:
    """Clear request timing from context."""
    _request_start_time.set(None)


# General log context
def set_log_context(**kwargs: Any) -> None:
    """Set additional logging context key-value pairs.

    Parameters
    ----------
    ``**kwargs``
        Context key-value pairs to add to logs
    """
    current_context = _log_context.get() or {}
    updated_context = {**current_context, **kwargs}
    _log_context.set(updated_context)


def get_log_context() -> dict[str, Any]:
    """Get the current logging context.

    Returns
    -------
    dict
        Current logging context (empty dict if none set)
    """
    return _log_context.get() or {}


def clear_log_context() -> None:
    """Clear all logging context."""
    _log_context.set(None)


def clear_all_context() -> None:
    """Clear all context variables."""
    clear_session_id()
    clear_request_id()
    clear_request_timing()
    clear_log_context()


# Context managers for scoped context
class SessionContext:
    """Context manager for session-scoped logging."""

    def __init__(self, session_id: str) -> None:
        """Initialize with session ID.

        Parameters
        ----------
        session_id : str
            The session ID to use in this context
        """
        self.session_id = session_id
        self.token: contextvars.Token[str | None] | None = None

    def __enter__(self) -> "SessionContext":
        """Enter the context and set session ID."""
        self.token = _session_id.set(self.session_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and restore previous session ID."""
        if self.token:
            _session_id.reset(self.token)


class RequestContext:
    """Context manager for request-scoped logging."""

    def __init__(self, request_id: str, start_timing: bool = True) -> None:
        """Initialize with request ID.

        Parameters
        ----------
        request_id : str
            The request ID to use in this context
        start_timing : bool
            Whether to start timing the request (default: True)
        """
        self.request_id = request_id
        self.start_timing = start_timing
        self.id_token: contextvars.Token[str | None] | None = None
        self.time_token: contextvars.Token[float | None] | None = None

    def __enter__(self) -> "RequestContext":
        """Enter the context, set request ID and optionally start timing."""
        self.id_token = _request_id.set(self.request_id)
        if self.start_timing:
            self.time_token = _request_start_time.set(time.time())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and restore previous values."""
        if self.id_token:
            _request_id.reset(self.id_token)
        if self.time_token:
            _request_start_time.reset(self.time_token)


class LogContext:
    """Context manager for additional logging context."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize with context key-value pairs.

        Parameters
        ----------
        ``**kwargs``
            Context key-value pairs to add
        """
        self.context_updates = kwargs
        self.token: contextvars.Token[dict[str, Any] | None] | None = None
        self.previous_context: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        """Enter the context and update log context."""
        self.previous_context = get_log_context()
        updated = {**self.previous_context, **self.context_updates}
        self.token = _log_context.set(updated)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and restore previous context."""
        if self.token:
            _log_context.reset(self.token)


class ContextManager(Singleton["ContextManager"]):
    """Manages context variables with TTL and automatic cleanup.

    This singleton manages all context variables and provides automatic cleanup for
    orphaned contexts to prevent memory leaks.
    """

    def __init__(self):
        """Initialize the context manager."""
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._contexts: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._ttl_map: dict[str, float] = {}
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """Start background thread for context cleanup."""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True,
                name="aidb-context-cleanup",
            )
            self._cleanup_thread.start()

    def _cleanup_loop(self):
        """Background loop for cleaning up expired contexts."""
        while not self._stop_cleanup.is_set():
            try:
                current_time = time.time()
                expired = []

                # Find expired contexts
                for context_id, expiry_time in list(self._ttl_map.items()):
                    if current_time >= expiry_time:
                        expired.append(context_id)

                # Clean up expired contexts
                for context_id in expired:
                    self._ttl_map.pop(context_id, None)
                    # Context will be garbage collected via weakref

            except Exception as e:
                # Log cleanup errors at debug level - context cleanup failures
                # should not impact application functionality but may indicate issues
                import logging

                logging.getLogger(__name__).debug(
                    "Context cleanup error: %s",
                    e,
                    exc_info=True,
                )
                continue

            # Check every 60 seconds
            self._stop_cleanup.wait(60)

    def register_context(self, context_id: str, ttl_seconds: int = 3600) -> None:
        """Register a context with TTL.

        Parameters
        ----------
        context_id : str
            Context identifier
        ttl_seconds : int
            Time-to-live in seconds (default: 1 hour)
        """
        self._ttl_map[context_id] = time.time() + ttl_seconds

    def unregister_context(self, context_id: str) -> None:
        """Unregister a context.

        Parameters
        ----------
        context_id : str
            Context identifier to remove
        """
        self._ttl_map.pop(context_id, None)

    def shutdown(self):
        """Shutdown the context manager and cleanup thread."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=1)


# Global context manager instance
_context_manager = ContextManager()


def set_session_id_with_ttl(session_id: str | None, ttl_seconds: int = 3600) -> None:
    """Set session ID with automatic TTL-based cleanup.

    Parameters
    ----------
    session_id : str or None
        The session ID to set
    ttl_seconds : int
        Time-to-live in seconds (default: 1 hour)
    """
    set_session_id(session_id)
    if session_id:
        _context_manager.register_context(f"session_{session_id}", ttl_seconds)


def set_request_id_with_ttl(request_id: str | None, ttl_seconds: int = 300) -> None:
    """Set request ID with automatic TTL-based cleanup.

    Parameters
    ----------
    request_id : str or None
        The request ID to set
    ttl_seconds : int
        Time-to-live in seconds (default: 5 minutes)
    """
    set_request_id(request_id)
    if request_id:
        _context_manager.register_context(f"request_{request_id}", ttl_seconds)
