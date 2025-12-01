"""Service for managing adapter downloads."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

from aidb.adapters.management import AdapterDownloader
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.constants import Language
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DownloadService(BaseService):
    """Service for downloading and managing adapter packages.

    This service handles:
    - Downloading adapters from GitHub releases
    - Managing download progress and errors
    - Validating downloaded packages
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the download service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)
        self._downloader: AdapterDownloader | None = None

    @property
    def downloader(self) -> AdapterDownloader | None:
        """Get the adapter downloader instance.

        Returns
        -------
        AdapterDownloader | None
            Downloader instance if initialized
        """
        if self._downloader is None:
            try:
                self._downloader = AdapterDownloader()
            except Exception as e:
                self.log_error("Failed to initialize adapter downloader: %s", str(e))
        return self._downloader

    def download_all_adapters(
        self,
        languages: list[str] | None = None,
        force: bool = False,
        verbose: bool = False,
    ) -> bool:
        """Download all specified language adapters.

        Parameters
        ----------
        languages : list[str] | None, optional
            Specific languages to download, or None for all
        force : bool, optional
            Force re-download even if already present
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        bool
            True if all downloads succeeded
        """
        if not self.downloader:
            CliOutput.error("Downloader not available")
            return False

        try:
            # Determine languages to download
            if languages is None:
                languages = [lang.value for lang in Language]

            CliOutput.info(f"Downloading adapters for: {', '.join(languages)}")

            success_count = 0
            failed = []

            for lang in languages:
                if verbose:
                    CliOutput.info(f"\nDownloading {lang} adapter...")

                if self._download_single_adapter(lang, force=force, verbose=verbose):
                    success_count += 1
                    CliOutput.success(f"{lang} adapter downloaded")
                else:
                    failed.append(lang)
                    CliOutput.error(f"Failed to download {lang} adapter")

            # Summary
            if success_count == len(languages):
                click.echo()  # Add blank line before summary
                CliOutput.success("All adapters downloaded successfully")
                return True
            if failed:
                click.echo()  # Add blank line before error
                CliOutput.error(f"Failed to download: {', '.join(failed)}")
            return False

        except Exception as e:
            self.log_error("Download failed: %s", str(e))
            CliOutput.error(f"Download failed: {str(e)}")
            return False

    def download_single_adapter(
        self,
        language: str,
        version: str | None = None,
        force: bool = False,
        verbose: bool = False,
    ) -> bool:
        """Download a single language adapter.

        Parameters
        ----------
        language : str
            Language to download adapter for
        version : str | None, optional
            Specific version to download
        force : bool, optional
            Force re-download even if already present
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        bool
            True if download succeeded
        """
        if not self.downloader:
            self.log_error("Downloader not available")
            return False

        try:
            # Check if already downloaded
            target_dir = Path.home() / ".cache" / "aidb" / "adapters" / language
            if target_dir.exists() and not force:
                if verbose:
                    CliOutput.info(f"{language} adapter already exists at {target_dir}")
                return True

            # Download adapter
            result = self.downloader.download_adapter(
                language=language,
                version=version,
                force=force,
            )

            if result:
                if verbose:
                    CliOutput.success(f"Downloaded {language} adapter")
                return True
            self.log_error("Download failed for %s adapter", language)
            return False

        except Exception as e:
            self.log_error("Failed to download %s adapter: %s", language, str(e))
            return False

    def _download_single_adapter(
        self,
        language: str,
        force: bool = False,
        verbose: bool = False,
    ) -> bool:
        """Download a single adapter.

        Parameters
        ----------
        language : str
            Language to download adapter for
        force : bool, optional
            Force re-download even if already present
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        bool
            True if download succeeded
        """
        return self.download_single_adapter(
            language=language,
            version=None,
            force=force,
            verbose=verbose,
        )

    def cleanup(self) -> None:
        """Cleanup service resources."""
        # No specific cleanup needed for this service
