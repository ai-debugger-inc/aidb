"""Session-aware logging wrapper for DAP client components."""

from typing import TYPE_CHECKING

from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class PrefixedLogger(Obj):
    """Context wrapper that adds prefix to all log messages.

    This wrapper transparently adds a session prefix to all logging methods
    while delegating all other attribute access to the underlying IContext.
    This allows DAP client components to use session-aware logging without any
    modifications to their existing log calls.

    Parameters
    ----------
    ctx : IContext
        The underlying context to wrap
    prefix : str
        The prefix to prepend to all log messages
    """

    def __init__(self, ctx: "IContext", prefix: str):
        """Initialize the prefixed logger.

        Parameters
        ----------
        ctx : IContext
            The underlying context to wrap
        prefix : str
            The prefix to prepend to all log messages
        """
        super().__init__(ctx)
        self._prefix = prefix

    def debug(self, msg: str) -> None:
        """Log a debug message with prefix.

        Parameters
        ----------
        msg : str
            The message to log
        """
        self.ctx.debug(f"{self._prefix} {msg}")

    def info(self, msg: str) -> None:
        """Log an info message with prefix.

        Parameters
        ----------
        msg : str
            The message to log
        """
        self.ctx.info(f"{self._prefix} {msg}")

    def warning(self, msg: str) -> None:
        """Log a warning message with prefix.

        Parameters
        ----------
        msg : str
            The message to log
        """
        self.ctx.warning(f"{self._prefix} {msg}")

    def error(self, msg: str) -> None:
        """Log an error message with prefix.

        Parameters
        ----------
        msg : str
            The message to log
        """
        self.ctx.error(f"{self._prefix} {msg}")

    def __getattr__(self, name):
        """Delegate all other attributes to the underlying context.

        This allows the PrefixedLogger to be used as a drop-in replacement for
        AidbContext in all contexts, not just logging.

        Parameters
        ----------
        name : str
            The attribute name to access

        Returns
        -------
        Any
            The attribute value from the underlying context
        """
        return getattr(self.ctx, name)
