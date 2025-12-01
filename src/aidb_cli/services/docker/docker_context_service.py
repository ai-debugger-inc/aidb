"""Service for managing Docker build contexts."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import Icons
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.config import VersionManager
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerContextService(BaseService):
    """Service for preparing Docker build contexts.

    This service handles:
    - Preparing Docker build context directories
    - Generating environment files
    - Managing build arguments
    - Cleaning up temporary contexts
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the Docker context service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)
        self._temp_context: Path | None = None
        self._version_manager: VersionManager | None = None

    @property
    def version_manager(self) -> VersionManager:
        """Get the version manager instance.

        Returns
        -------
        VersionManager
            Version manager instance
        """
        if self._version_manager is None:
            self._version_manager = VersionManager()
        return self._version_manager

    def get_build_args(self) -> dict[str, str]:
        """Get Docker build arguments.

        Pulls versions from versions.yaml when available and falls back to sensible
        defaults. Avoids relying on non-existent attributes of VersionManager.
        """
        # Base image/version defaults
        defaults = {
            "PYTHON_VERSION": "3.12",
            "BASE_IMAGE": "python:3.12-slim",
        }
        # Try to use shared version info
        try:
            args = self.version_manager.get_docker_build_args()
            py = args.get("PYTHON_VERSION") or defaults["PYTHON_VERSION"]
        except Exception:  # Fallback to defaults if version lookup fails
            py = defaults["PYTHON_VERSION"]
        return {
            "PACKAGE_VERSION": (self.version_manager.versions.get("version", "0.0.0")),
            "PYTHON_VERSION": py,
            "BASE_IMAGE": defaults["BASE_IMAGE"],
        }

    def _copy_required_files(
        self,
        files_to_copy: list[str],
        verbose: bool = False,
    ) -> None:
        """Copy required files to Docker context.

        Parameters
        ----------
        files_to_copy : list[str]
            List of file names to copy
        verbose : bool, optional
            Whether to show verbose output
        """
        for file_name in files_to_copy:
            src_file = self.repo_root / file_name
            if src_file.exists() and self._temp_context is not None:
                shutil.copy2(src_file, self._temp_context / file_name)
                if verbose:
                    CliOutput.info(f"  Copied {file_name}")

    def _copy_directories(
        self,
        dirs_to_copy: list[str],
        verbose: bool = False,
    ) -> None:
        """Copy required directories to Docker context.

        Parameters
        ----------
        dirs_to_copy : list[str]
            List of directory names to copy
        verbose : bool, optional
            Whether to show verbose output
        """
        for dir_name in dirs_to_copy:
            src_dir = self.repo_root / dir_name
            if src_dir.exists() and self._temp_context is not None:
                shutil.copytree(src_dir, self._temp_context / dir_name)
                if verbose:
                    CliOutput.info(f"  Copied {dir_name}/")

    def prepare_docker_context(
        self,
        include_src: bool = True,
        include_scripts: bool = True,
        verbose: bool = False,
    ) -> Path | None:
        """Prepare a Docker build context directory.

        Parameters
        ----------
        include_src : bool, optional
            Whether to include src directory
        include_scripts : bool, optional
            Whether to include scripts directory
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        Path | None
            Path to prepared context directory or None on failure
        """
        try:
            # Create temporary directory
            self._temp_context = Path(tempfile.mkdtemp(prefix="aidb_docker_"))

            if verbose:
                CliOutput.info(
                    f"{Icons.INFO} Preparing Docker context at {self._temp_context}",
                )

            # Prepare file and directory lists
            files_to_copy = ["pyproject.toml", "README.md"]
            dirs_to_copy = []

            if include_src:
                dirs_to_copy.append("src")
            if include_scripts:
                dirs_to_copy.append("scripts")

            # Copy files and directories
            self._copy_required_files(files_to_copy, verbose)
            self._copy_directories(dirs_to_copy, verbose)

            # Generate environment file
            env_file = self.generate_env_file(output_path=self._temp_context / ".env")
            if verbose and env_file:
                CliOutput.info("  Generated .env file")

            CliOutput.success("Docker context prepared")
            return self._temp_context

        except (OSError, shutil.Error) as e:
            self.log_error("Failed to prepare Docker context: %s", str(e))
            self.cleanup_context()
            return None

    def generate_env_file(self, output_path: Path | None = None) -> Path:
        """Generate environment file for Docker builds.

        Parameters
        ----------
        output_path : Path | None, optional
            Output path for env file, defaults to temp location

        Returns
        -------
        Path
            Path to generated env file
        """
        if output_path is None:
            fd, temp_name = tempfile.mkstemp(suffix=".env", prefix="aidb_")
            os.close(fd)
            output_path = Path(temp_name)

        from datetime import datetime, timezone

        build_args = self.get_build_args()
        build_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        env_content = (
            "# AIDB Docker Environment\n"
            f"PACKAGE_VERSION={build_args.get('PACKAGE_VERSION', '0.0.0')}\n"
            f"PYTHON_VERSION={build_args.get('PYTHON_VERSION', '3.12')}\n"
            f"BUILD_DATE={build_date}\n"
        )

        output_path.write_text(env_content)
        self.log_debug("Generated env file at %s", output_path)

        return output_path

    def cleanup_context(self) -> None:
        """Clean up temporary Docker context directory."""
        if self._temp_context and self._temp_context.exists():
            try:
                shutil.rmtree(self._temp_context)
                self.log_debug("Cleaned up Docker context at %s", self._temp_context)
            except (OSError, shutil.Error) as e:
                self.log_error("Failed to clean up context: %s", str(e))
            finally:
                self._temp_context = None

    def cleanup(self) -> None:
        """Cleanup service resources."""
        self.cleanup_context()
