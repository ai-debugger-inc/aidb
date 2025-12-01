"""Base service class for CLI services."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    import click

    from aidb_cli.services.command_executor import CommandExecutor

logger = get_cli_logger(__name__)


class BaseService:
    """Base service class providing common functionality for CLI services.

    This base class provides:
    - Repository context
    - Command execution support
    - Logging setup
    - Error handling patterns
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: Optional["click.Context"] = None,
    ) -> None:
        """Initialize the base service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        """
        self.repo_root = repo_root
        self._command_executor = command_executor
        self.ctx = ctx
        self._logger = get_cli_logger(self.__class__.__module__)
        self._initialize_service()

    def _initialize_service(self) -> None:
        """Initialize service-specific resources.

        Subclasses should override to perform their initialization.
        """

    @property
    def command_executor(self) -> "CommandExecutor":
        """Get command executor instance, creating if necessary.

        Returns
        -------
        CommandExecutor
            Command executor instance

        Raises
        ------
        RuntimeError
            If no command executor is available
        """
        if self._command_executor is None:
            from aidb_cli.services.command_executor import CommandExecutor

            # Prefer the Click context if available to correctly honor verbosity
            click_ctx = None
            try:
                import click

                click_ctx = click.get_current_context(silent=True)
            except Exception:
                click_ctx = None

            # If this service was constructed with a ctx, pass it through
            ctx_to_use = self.ctx if self.ctx is not None else click_ctx
            self._command_executor = CommandExecutor(ctx=ctx_to_use)
        return self._command_executor

    @property
    def resolved_env(self) -> dict[str, str] | None:
        """Get the resolved environment from CLI context if available.

        Returns
        -------
        dict[str, str] | None
            Resolved environment variables or None if no context
        """
        if self.ctx and hasattr(self.ctx.obj, "resolved_env"):
            return self.ctx.obj.resolved_env
        return None

    def log_debug(self, message: str, *args: Any) -> None:
        r"""Log a debug message with service context.

        Parameters
        ----------
        message : str
            Log message format string
        *args : Any
            Arguments for message formatting
        """
        self._logger.debug("[%s] " + message, self.__class__.__name__, *args)

    def log_info(self, message: str, *args: Any) -> None:
        r"""Log an info message with service context.

        Parameters
        ----------
        message : str
            Log message format string
        *args : Any
            Arguments for message formatting
        """
        self._logger.info("[%s] " + message, self.__class__.__name__, *args)

    def log_warning(self, message: str, *args: Any) -> None:
        r"""Log a warning message with service context.

        Parameters
        ----------
        message : str
            Log message format string
        *args : Any
            Arguments for message formatting
        """
        self._logger.warning("[%s] " + message, self.__class__.__name__, *args)

    def log_error(self, message: str, *args: Any) -> None:
        r"""Log an error message with service context.

        Parameters
        ----------
        message : str
            Log message format string
        *args : Any
            Arguments for message formatting
        """
        self._logger.error("[%s] " + message, self.__class__.__name__, *args)

    def validate_paths(self, *paths: Path) -> bool:
        """Validate that paths exist.

        Parameters
        ----------
        *paths : Path
            Paths to validate

        Returns
        -------
        bool
            True if all paths exist
        """
        for path in paths:
            if not path.exists():
                self.log_error("Path does not exist: %s", path)
                return False
        return True

    def ensure_directory(self, path: Path) -> Path:
        """Ensure a directory exists, creating if necessary.

        Parameters
        ----------
        path : Path
            Directory path

        Returns
        -------
        Path
            The directory path
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def cleanup(self) -> None:
        """Cleanup service resources.

        Subclasses should override if they need cleanup logic.
        """
