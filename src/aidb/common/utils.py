"""Utility functions for aidb."""

import functools
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import threading

    from aidb.common.context import AidbContext


def ensure_ctx(ctx: Any | None = None) -> "AidbContext":
    """Return the singleton AidbContext instance."""
    from unittest.mock import MagicMock, Mock

    from aidb.common.context import AidbContext

    # If it's a mock, return it as is for testing
    if isinstance(ctx, Mock | MagicMock):
        return ctx

    # Check if it's a PrefixedLogger (which wraps AidbContext)
    # We check for the duck-typed interface rather than importing to avoid circular deps
    if hasattr(ctx, "_prefix") and hasattr(ctx, "ctx"):
        # It's a PrefixedLogger, return it as-is (cast to expected return type)
        return cast("AidbContext", ctx)

    if not isinstance(ctx, AidbContext):
        ctx = AidbContext()
    return ctx


def acquire_lock(func):
    """Acquire a lock before executing a method.

    Expects classes to inherit from `Obj` base class with `self.ctx` and
    `self.lock`.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        lock: threading.RLock = self.lock
        with lock:
            return func(self, *args, **kwargs)

    return wrapper
