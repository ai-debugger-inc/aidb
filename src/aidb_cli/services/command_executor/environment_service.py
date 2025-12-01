"""Service for managing command execution environments."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import click

from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class EnvironmentService:
    """Service for managing environment variables for command execution.

    This service handles environment variable management, including building
    environments with overrides and managing Python-specific environment settings.
    """

    def __init__(self, ctx: Optional["click.Context"] = None) -> None:
        """Initialize the environment service.

        Parameters
        ----------
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        """
        self.ctx = ctx
        # Use centralized environment if available, otherwise use os.environ
        if ctx and hasattr(ctx.obj, "resolved_env"):
            self._base_env = ctx.obj.resolved_env.copy()
        else:
            self._base_env = dict(os.environ)

    def build_environment(
        self,
        env_overrides: dict[str, str] | None = None,
        inherit: bool = True,
    ) -> dict[str, str] | None:
        """Build command environment with overrides.

        Parameters
        ----------
        env_overrides : dict[str, str] | None, optional
            Environment variables to add/override
        inherit : bool, optional
            Whether to inherit current environment

        Returns
        -------
        dict[str, str] | None
            Complete environment or None for default
        """
        # Only return None if no overrides and we want subprocess default behavior
        if not env_overrides:
            return None  # Use subprocess default environment

        # If we have overrides, always build and return a complete environment
        if not inherit:
            # Start with empty environment
            command_env = {}
        else:
            # Start with copy of current environment
            command_env = self._base_env.copy()

        # Apply overrides
        command_env.update(env_overrides)
        logger.debug("Environment overrides: %s", list(env_overrides.keys()))

        return command_env

    def setup_python_environment(
        self,
        env: dict[str, str] | None = None,
        unbuffered: bool = True,
    ) -> dict[str, str]:
        """Set up Python-specific environment variables.

        Parameters
        ----------
        env : dict[str, str] | None, optional
            Base environment to modify
        unbuffered : bool, optional
            Whether to set PYTHONUNBUFFERED

        Returns
        -------
        dict[str, str]
            Environment with Python settings
        """
        env = self._base_env.copy() if env is None else env.copy()

        if unbuffered:
            env["PYTHONUNBUFFERED"] = "1"
            logger.debug("Set PYTHONUNBUFFERED=1 for unbuffered output")

        return env

    def get_path_components(self) -> list[str]:
        """Get components of the PATH environment variable.

        Returns
        -------
        list[str]
            List of directories in PATH
        """
        path_var = self._base_env.get("PATH", "")
        return path_var.split(os.pathsep) if path_var else []

    def find_executable(self, name: str) -> Path | None:
        """Find an executable in PATH.

        Parameters
        ----------
        name : str
            Name of the executable to find

        Returns
        -------
        Path | None
            Path to executable if found
        """
        import shutil

        path = shutil.which(name)
        return Path(path) if path else None

    def add_to_path(
        self,
        directory: Path,
        env: dict[str, str] | None = None,
        prepend: bool = True,
    ) -> dict[str, str]:
        """Add a directory to PATH.

        Parameters
        ----------
        directory : Path
            Directory to add to PATH
        env : dict[str, str] | None, optional
            Environment to modify
        prepend : bool, optional
            Whether to prepend (True) or append (False)

        Returns
        -------
        dict[str, str]
            Environment with updated PATH
        """
        env = self._base_env.copy() if env is None else env.copy()

        path_components = env.get("PATH", "").split(os.pathsep)
        path_components = [p for p in path_components if p]  # Remove empty

        dir_str = str(directory)
        if dir_str not in path_components:
            if prepend:
                path_components.insert(0, dir_str)
            else:
                path_components.append(dir_str)

            env["PATH"] = os.pathsep.join(path_components)
            logger.debug("Added %s to PATH", directory)

        return env

    def get_env_info(self) -> dict[str, Any]:
        """Get information about the current environment.

        Returns
        -------
        dict[str, Any]
            Environment information
        """
        return {
            "platform": os.name,
            "path_count": len(self.get_path_components()),
            "python": self.find_executable("python"),
            "env_vars": len(self._base_env),
            "home": Path.home(),
            "cwd": Path.cwd(),
        }
