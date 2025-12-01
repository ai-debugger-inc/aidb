"""Context protocol interfaces."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from logging import Logger


class IContext(Protocol):
    """Protocol interface for AIDB context.

    This interface allows components to use context functionality without importing the
    concrete implementation.
    """

    # Logging methods
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log debug message."""
        ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log info message."""
        ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log warning message."""
        ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log error message."""
        ...

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log critical message."""
        ...

    @property
    def logger(self) -> "Logger":
        """Get the underlying logger."""
        ...

    # Storage and paths
    def get_storage_path(
        self,
        component_name: str,
        file_name: str | None = None,
    ) -> str:
        """Get a storage path for the given component."""
        ...

    # Debug status
    def is_debug_enabled(self) -> bool:
        """Check if debug logging is enabled."""
        ...

    # Context management
    def create_child(self, name: str, **kwargs: Any) -> "IContext":
        """Create a child context."""
        ...
