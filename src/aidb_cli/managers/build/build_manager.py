"""Refactored build manager using orchestrator pattern."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.paths import CachePaths
from aidb_cli.managers.base.orchestrator import BaseOrchestrator
from aidb_cli.services.adapter import AdapterService
from aidb_cli.services.build import DownloadService
from aidb_cli.services.docker import DockerContextService
from aidb_common.config import VersionManager
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class BuildManager(BaseOrchestrator):
    """Centralized orchestrator for all build operations.

    This refactored version uses the orchestrator pattern to coordinate multiple
    services for build operations.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the build manager orchestrator.

        Parameters
        ----------
        repo_root : Path | None, optional
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        """
        super().__init__(repo_root, command_executor)

        # Initialize version manager
        self.versions_file = self.repo_root / "versions.yaml"
        self.version_manager = VersionManager(self.versions_file)

        # Cache directories
        self.user_cache_dir = CachePaths.adapters_dir()
        self.repo_cache_dir = CachePaths.repo_cache(self.repo_root)

        # Create cache directories
        self.user_cache_dir.mkdir(parents=True, exist_ok=True)
        self.repo_cache_dir.mkdir(parents=True, exist_ok=True)

        # Ensure services are registered up front so get_service works immediately
        try:
            self._register_services()
        except Exception:
            # Non-fatal: services will be lazily created when requested
            pass

    def _register_services(self) -> None:
        """Register services for build operations."""
        self.register_service(AdapterService)
        self.register_service(DownloadService)
        self.register_service(DockerContextService)

    # Delegate methods to maintain backward compatibility

    def get_supported_languages(self) -> list[str]:
        """Get list of supported adapter languages."""
        service = self.get_service(AdapterService)
        langs = service.get_supported_languages()
        if not langs:
            # Fallback to default list if registry unavailable
            from aidb_cli.core.constants import SUPPORTED_LANGUAGES

            return SUPPORTED_LANGUAGES
        return langs

    def get_build_args(self) -> dict[str, str]:
        """Get Docker build arguments."""
        service = self.get_service(DockerContextService)
        return service.get_build_args()

    def check_adapters_built(
        self,
        languages: list[str] | None = None,
        verbose: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Check which adapters are built and which need building."""
        service = self.get_service(AdapterService)
        return service.check_adapters_built(languages, verbose)

    def find_adapter_source(
        self,
        language: str,
        check_built: bool = False,
        verbose: bool = False,
    ) -> Path | None:
        """Find the source directory for a specific adapter."""
        service = self.get_service(AdapterService)
        return service.find_adapter_source(language, check_built, verbose)

    def find_all_adapters(self, verbose: bool = False) -> dict[str, Path | None]:
        """Find all available adapters and their locations."""
        service = self.get_service(AdapterService)
        return service.find_all_adapters(verbose)

    def download_all_adapters(
        self,
        languages: list[str] | None = None,
        force: bool = False,
        verbose: bool = False,
    ) -> bool:
        """Download all specified language adapters."""
        service = self.get_service(DownloadService)
        return service.download_all_adapters(languages, force, verbose)

    def prepare_docker_context(
        self,
        include_src: bool = True,
        include_scripts: bool = True,
        verbose: bool = False,
    ) -> Path | None:
        """Prepare a Docker build context directory."""
        service = self.get_service(DockerContextService)
        return service.prepare_docker_context(include_src, include_scripts, verbose)

    def generate_env_file(self, output_path: Path | None = None) -> Path:
        """Generate environment file for Docker builds."""
        service = self.get_service(DockerContextService)
        return service.generate_env_file(output_path)

    def build_adapters(
        self,
        languages: list[str] | None = None,
        method: str = "download",
        verbose: bool = False,
        force: bool = False,
    ) -> bool:
        """Build adapters using specified method.

        Parameters
        ----------
        languages : list[str] | None, optional
            Languages to build, defaults to all
        method : str, optional
            Build method: 'download' or 'local'
        verbose : bool, optional
            Whether to show verbose output
        force : bool, optional
            Force rebuild even if already built

        Returns
        -------
        bool
            True if all builds succeeded
        """
        if languages is None:
            languages = self.get_supported_languages()

        if method == "download":
            return self._build_with_download(languages, verbose)
        if method == "local":
            return self._build_locally(languages, verbose)
        logger.error("Unknown build method: %s", method)
        return False

    def _build_locally(self, languages: list[str], verbose: bool = False) -> bool:
        """Build adapters locally."""
        service = self.get_service(AdapterService)
        return service.build_locally(languages, verbose)

    def _build_with_download(self, languages: list[str], verbose: bool = False) -> bool:
        """Build adapters by downloading."""
        download_service = self.get_service(DownloadService)
        adapter_service = self.get_service(AdapterService)

        # Download adapters
        if not download_service.download_all_adapters(languages, verbose=verbose):
            return False

        # Copy to user cache
        for lang in languages:
            source_path = CachePaths.user_cache() / lang
            if source_path.exists():
                adapter_service.copy_to_user_cache(lang, source_path, verbose)

        return True

    def clean_adapter_cache(self, user_only: bool = False) -> bool:
        """Clean adapter cache directories."""
        service = self.get_service(AdapterService)
        return service.clean_adapter_cache(user_only)

    def get_adapter_info(self, language: str) -> dict[str, str]:
        """Get information about a specific adapter."""
        service = self.get_service(AdapterService)
        return service.get_adapter_info(language)

    @property
    def registry(self):
        """Get the adapter registry."""
        service = self.get_service(AdapterService)
        return service.registry

    @property
    def adapter_downloader(self):
        """Get the adapter downloader."""
        service = self.get_service(DownloadService)
        return service.downloader
