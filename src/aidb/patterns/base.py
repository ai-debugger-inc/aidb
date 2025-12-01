"""Aidb base classes."""

import asyncio
from typing import Any


class Obj:
    """The base class for most aidb classes."""

    ctx: Any  # Context object - typically AidbContext

    def __init__(self, ctx: Any | None = None):
        """Initialize the base class.

        Parameters
        ----------
        ctx : Any, optional
            Context object for logging and configuration. If not provided,
            uses the singleton AidbContext instance.
        """
        # If no context provided, get the singleton instance
        if ctx is None:
            from aidb.common import ensure_ctx

            ctx = ensure_ctx()
        self.ctx = ctx
        # Async lock for async methods - lazily initialized
        self._async_lock: asyncio.Lock | None = None

    @property
    def async_lock(self) -> asyncio.Lock:
        """Get the async lock, creating it if needed.

        Lazy initialization avoids issues when objects are created outside of an async
        context.
        """
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
