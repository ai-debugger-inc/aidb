"""Base checker class with common utilities."""

from typing import Any


class BaseChecker:
    """Base class for all version checkers."""

    def __init__(self, config: dict[str, Any]):
        """Initialize checker with configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Loaded versions.json configuration
        """
        self.config = config
