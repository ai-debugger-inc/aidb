"""Facade service for coordinating adapter operations."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.managers.base.service import BaseService
from aidb_cli.services.adapter.adapter_build_service import AdapterBuildService
from aidb_cli.services.adapter.adapter_discovery_service import AdapterDiscoveryService
from aidb_cli.services.adapter.adapter_install_service import AdapterInstallService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class AdapterService(BaseService):
    """Facade service for coordinating adapter operations.

    This service delegates to specialized services:
    - AdapterDiscoveryService: Finding and checking adapters
    - AdapterBuildService: Building adapters via ACT
    - AdapterInstallService: Installing and caching adapters
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the adapter service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)
        self._discovery_service: AdapterDiscoveryService | None = None
        self._build_service: AdapterBuildService | None = None
        self._install_service: AdapterInstallService | None = None

    @property
    def discovery(self) -> AdapterDiscoveryService:
        """Get discovery service instance."""
        if self._discovery_service is None:
            self._discovery_service = AdapterDiscoveryService(
                self.repo_root,
                self.command_executor,
            )
        return self._discovery_service

    @property
    def build(self) -> AdapterBuildService:
        """Get build service instance."""
        if self._build_service is None:
            self._build_service = AdapterBuildService(
                self.repo_root,
                self.command_executor,
            )
        return self._build_service

    @property
    def install(self) -> AdapterInstallService:
        """Get install service instance."""
        if self._install_service is None:
            self._install_service = AdapterInstallService(
                self.repo_root,
                self.command_executor,
            )
        return self._install_service

    def get_supported_languages(self) -> list[str]:
        """Get list of supported adapter languages."""
        return self.discovery.get_supported_languages()

    def find_adapter_source(
        self,
        language: str,
        check_built: bool = False,
        verbose: bool = False,
    ) -> Path | None:
        """Find the source directory for a specific adapter."""
        return self.discovery.find_adapter_source(language, check_built, verbose)

    def find_all_adapters(self, verbose: bool = False) -> dict[str, Path | None]:
        """Find all available adapters and their locations."""
        return self.discovery.find_all_adapters(verbose)

    def check_adapters_built(
        self,
        languages: list[str] | None = None,
        verbose: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Check which adapters are built and which need building."""
        return self.discovery.check_adapters_built(languages, verbose)

    def get_adapter_info(self, language: str) -> dict[str, str]:
        """Get information about a specific adapter."""
        return self.discovery.get_adapter_info(language)

    def build_locally(
        self,
        languages: list[str],
        verbose: bool = False,
        resolved_env: dict[str, str] | None = None,
    ) -> bool:
        """Build adapters locally using act to run GitHub Actions workflow."""
        return self.build.build_locally(languages, verbose, resolved_env)

    def find_act_containers(self) -> list[dict]:
        """Find ACT containers by name pattern."""
        return self.build.find_act_containers()

    def extract_artifacts_from_containers(self, verbose: bool = False) -> int:
        """Extract build artifacts from ACT containers to host."""
        return self.build.extract_artifacts_from_containers(verbose)

    def cleanup_act_containers(self, verbose: bool = False) -> int:
        """Cleanup ACT containers from adapter builds."""
        return self.build.cleanup_act_containers(verbose)

    def install_adapters(
        self,
        languages: list[str],
        verbose: bool = False,
    ) -> bool:
        """Install adapters from repo cache to user's AIDB directory."""
        return self.install.install_adapters(languages, verbose)

    def copy_to_user_cache(
        self,
        language: str,
        source_path: Path,
        verbose: bool = False,
    ) -> bool:
        """Copy adapter to user cache directory."""
        return self.install.copy_to_user_cache(language, source_path, verbose)

    def clean_adapter_cache(self, user_only: bool = False) -> bool:
        """Clean adapter cache directories."""
        return self.install.clean_adapter_cache(user_only)

    def cleanup(self) -> None:
        """Cleanup service resources."""
        if self._discovery_service:
            self._discovery_service.cleanup()
        if self._build_service:
            self._build_service.cleanup()
        if self._install_service:
            self._install_service.cleanup()
