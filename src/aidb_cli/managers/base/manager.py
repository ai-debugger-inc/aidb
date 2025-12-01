"""Base manager class with singleton pattern."""

from pathlib import Path

from aidb_common.patterns.singleton import Singleton
from aidb_common.repo import detect_repo_root
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class BaseManager(Singleton["BaseManager"]):
    """Base manager with singleton pattern and common functionality.

    This base class provides:
    - Thread-safe singleton pattern (via aidb_common.patterns.singleton)
    - Repository root detection
    - Common initialization logic
    - Logging setup

    Notes
    -----
    Inherits from Singleton which provides:
    - Thread-safe instance creation with RLock
    - Automatic singleton management per subclass
    - reset() class method for testing
    - stub=True parameter to bypass singleton in tests
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        """Initialize the base manager.

        Parameters
        ----------
        repo_root : Path | None, optional
            Repository root directory. If not provided, will be auto-detected.
        """
        if repo_root is None:
            repo_root = detect_repo_root()

        self.repo_root = repo_root
        self._setup_logging()
        self._initialize()

        logger.debug(
            "%s initialized with repo_root: %s",
            self.__class__.__name__,
            self.repo_root,
        )

    def _setup_logging(self) -> None:
        """Set up logging for the manager.

        Subclasses can override to customize logging setup.
        """

    def _initialize(self) -> None:
        """Initialize manager-specific resources.

        Subclasses should override to perform their initialization.
        """
