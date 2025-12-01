"""Decorators for orchestration operations."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast

T = TypeVar("T")


def clears_frame_cache(func: Callable[..., T]) -> Callable[..., T]:
    """Decorate clear fram cache logic.

    This decorator should be applied to any operation that changes the execution
    state (step, continue, etc.) because frame IDs become invalid after these
    operations in the DAP protocol.

    Parameters
    ----------
    func : Callable
        The function to wrap

    Returns
    -------
    Callable
        The wrapped function that clears frame cache after execution
    """

    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        """Decorate clear frame cache after execution logic."""
        try:
            # Call the original function
            result = func(self, *args, **kwargs)
            if isinstance(result, Awaitable):
                result = await result
            return result
        finally:
            # Always clear the cached frame ID after execution state changes
            # This ensures we don't use stale frame IDs in subsequent operations
            if hasattr(self, "_current_frame_id"):
                self._current_frame_id = None
            if hasattr(self, "_current_thread_id"):
                # Optionally clear thread ID too if needed
                # Though thread IDs tend to be more stable than frame IDs
                pass

    return cast("Callable[..., T]", wrapper)


def clears_execution_cache(func: Callable[..., T]) -> Callable[..., T]:
    """Decorate clear-all execution cache functionality.

    Parameters
    ----------
    func : Callable
        The function to wrap

    Returns
    -------
    Callable
        The wrapped function that clears all execution caches
    """

    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
        """Wrap clear execution cache logic."""
        try:
            # Call the original function
            result = func(self, *args, **kwargs)
            if isinstance(result, Awaitable):
                result = await result
            return result
        finally:
            # Clear all execution-related caches
            if hasattr(self, "_current_frame_id"):
                self._current_frame_id = None
            if hasattr(self, "_current_thread_id"):
                self._current_thread_id = None

    return cast("Callable[..., T]", wrapper)
