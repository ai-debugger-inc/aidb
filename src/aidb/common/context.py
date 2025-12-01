"""Core context and controls for aidb."""

import logging
from pathlib import Path
from typing import Any

from aidb.common.errors import AidbError
from aidb_common.path import get_aidb_home
from aidb_common.patterns import Singleton


class AidbContext(Singleton["AidbContext"]):
    """Singleton application context.

    Attributes
    ----------
    logger : logging.Logger
        Application logger
    adapter_registry : AdapterRegistry
        Debug adapter registry
    """

    logger: logging.Logger
    adapter_registry: Any  # Will be AdapterRegistry, imported lazily

    def __init__(self):
        """Initialize the context."""
        if getattr(self, "_initialized", False):
            return
        self.logger = self._setup_logger()
        self._initialized = True

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a trace message."""
        from aidb_logging import TRACE

        kwargs["stacklevel"] = 2
        self.logger.log(TRACE, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        kwargs["stacklevel"] = 2
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        kwargs["stacklevel"] = 2
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        kwargs["stacklevel"] = 2
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        kwargs["stacklevel"] = 2
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        kwargs["stacklevel"] = 2
        self.logger.critical(msg, *args, **kwargs)

    def is_debug_enabled(self) -> bool:
        """Check if debug logging is enabled.

        Returns
        -------
        bool
            True if debug logging is enabled, False otherwise
        """
        return self.logger.level <= logging.DEBUG

    @staticmethod
    def state_dir() -> str:
        """Get or create the state directory for aidb."""
        state_dir_path = get_aidb_home()
        if not state_dir_path.is_dir():
            try:
                state_dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                msg = "Failed to create state directory"
                raise AidbError(msg) from e
        return str(state_dir_path)

    @staticmethod
    def get_storage_path(component_name: str, file_name: str | None = None) -> str:
        """Get a path for component storage.

        Parameters
        ----------
        component_name : str
            Name of the component requesting storage (e.g., 'session', 'logger')
        file_name : str, optional
            Specific file name to use

        Returns
        -------
        str
            Absolute path to the storage location
        """
        component_dir_path = Path(AidbContext.state_dir()) / component_name
        component_dir_path.mkdir(parents=True, exist_ok=True)
        component_dir = str(component_dir_path)

        if file_name:
            return str(Path(component_dir) / file_name)
        return component_dir

    def create_child(self, _name: str, **_kwargs: Any) -> "AidbContext":
        """Create a child context.

        For AidbContext (singleton), this just returns self since we don't need
        hierarchical contexts for this implementation.
        """
        return self

    def _setup_logger(self) -> logging.Logger:
        """Set up a simplified logger that logs everything to a file."""
        from aidb_logging import get_aidb_logger

        # Use aidb profile which already logs to the correct location
        return get_aidb_logger("aidb")
