"""Service for installing adapters and managing cache."""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import Icons
from aidb_cli.core.paths import CachePaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.path import get_aidb_adapters_dir
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class AdapterInstallService(BaseService):
    """Service for installing adapters and managing cache.

    This service handles:
    - Installing adapters from cache to user directory
    - Copying adapters to cache
    - Cleaning adapter cache
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the adapter install service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        self._cache_dir: Path | None = None
        super().__init__(repo_root, command_executor)

    def _initialize_service(self) -> None:
        """Initialize service-specific resources."""
        self._cache_dir = CachePaths.repo_cache(self.repo_root)

    def install_adapters(
        self,
        languages: list[str],
        verbose: bool = False,
    ) -> bool:
        """Install adapters from repo cache to user's AIDB directory.

        This copies adapters from {repo}/.cache/adapters/ to ~/.aidb/adapters/
        for use in runtime debugging sessions.

        Parameters
        ----------
        languages : list[str]
            Languages to install adapters for
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        bool
            True if all installations succeeded
        """
        if not self._cache_dir:
            self.log_error("Cache directory not configured")
            CliOutput.error("Cache directory not configured")
            return False

        install_dir = get_aidb_adapters_dir()
        success_count = 0
        missing = []

        for language in languages:
            source_path = self._cache_dir / language

            if not source_path.exists():
                self.log_error("Adapter not found in cache: %s", language)
                missing.append(language)
                continue

            target_path = install_dir / language

            try:
                install_dir.mkdir(parents=True, exist_ok=True)

                if target_path.exists():
                    shutil.rmtree(target_path)

                shutil.copytree(source_path, target_path)

                if verbose:
                    CliOutput.success(
                        f"Installed {language} adapter to {target_path}",
                    )

                success_count += 1

            except (OSError, shutil.Error) as e:
                self.log_error("Failed to install %s adapter: %s", language, str(e))
                CliOutput.error(
                    f"Failed to install {language} adapter: {e}",
                )

        if missing:
            CliOutput.warning(
                f"Adapters not found in cache: {', '.join(missing)}",
            )
            CliOutput.info(
                "Run './dev-cli adapters build' or './dev-cli adapters download' first",
            )

        if success_count == len(languages):
            CliOutput.success(
                f"Installed {success_count} adapter(s) to {install_dir}",
            )
            return True
        if success_count > 0:
            CliOutput.warning(
                f"Installed {success_count}/{len(languages)} adapter(s)",
            )
            return False
        CliOutput.error("Failed to install any adapters")
        return False

    def copy_to_user_cache(
        self,
        language: str,
        source_path: Path,
        verbose: bool = False,
    ) -> bool:
        """Copy adapter to user cache directory.

        Parameters
        ----------
        language : str
            Language name
        source_path : Path
            Source path to copy from
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        bool
            True if copy succeeded
        """
        if not self._cache_dir:
            self.log_error("Cache directory not configured")
            return False

        target_path = self._cache_dir / language

        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                shutil.rmtree(target_path)

            shutil.copytree(source_path, target_path)

            if verbose:
                msg = f"Copied {language} adapter to cache: {target_path}"
                CliOutput.success(msg)

            return True

        except (OSError, shutil.Error) as e:
            self.log_error("Failed to copy adapter to cache: %s", str(e))
            return False

    def clean_adapter_cache(self, user_only: bool = False) -> bool:
        """Clean adapter cache directories.

        Parameters
        ----------
        user_only : bool, optional
            If True, only clean user cache. If False, clean all caches.

        Returns
        -------
        bool
            True if cleanup succeeded
        """
        try:
            if self._cache_dir and self._cache_dir.exists():
                CliOutput.info(f"Cleaning user cache: {self._cache_dir}")
                shutil.rmtree(self._cache_dir)
                CliOutput.success("User cache cleaned")

            if not user_only:
                repo_adapters = self.repo_root / "src" / "aidb" / "adapters" / "lang"
                if repo_adapters.exists():
                    for lang_dir in repo_adapters.iterdir():
                        if lang_dir.is_dir():
                            for cache_dir in lang_dir.rglob("__pycache__"):
                                shutil.rmtree(cache_dir)
                            for pyc_file in lang_dir.rglob("*.pyc"):
                                pyc_file.unlink()
                    CliOutput.success("Repo cache cleaned")

            return True

        except (OSError, shutil.Error) as e:
            self.log_error("Failed to clean cache: %s", str(e))
            return False

    def cleanup(self) -> None:
        """Cleanup service resources."""
