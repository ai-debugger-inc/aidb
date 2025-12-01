"""Docker cleanup manager for orchestrating cleanup operations."""

from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.managers.base.orchestrator import BaseOrchestrator
from aidb_cli.services.docker.docker_cleanup_service import DockerCleanupService
from aidb_cli.services.docker.docker_resource_service import DockerResourceService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from pathlib import Path

    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerCleanupManager(BaseOrchestrator):
    """Manager for orchestrating Docker resource cleanup operations.

    This manager coordinates between resource discovery and cleanup services to provide
    safe, label-based cleanup of Docker resources.
    """

    def __init__(
        self,
        repo_root: Optional["Path"] = None,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the Docker cleanup manager."""
        super().__init__(repo_root, command_executor)
        self._resource_service: DockerResourceService | None = None
        self._cleanup_service: DockerCleanupService | None = None

    @property
    def resource_service(self) -> DockerResourceService:
        """Get resource service instance."""
        if self._resource_service is None:
            self._resource_service = DockerResourceService(self.command_executor)
        return self._resource_service

    @property
    def cleanup_service(self) -> DockerCleanupService:
        """Get cleanup service instance."""
        if self._cleanup_service is None:
            self._cleanup_service = DockerCleanupService(self.command_executor)
        return self._cleanup_service

    def find_aidb_resources(
        self,
        all_resources: bool = False,
        volumes_only: bool = False,
        orphaned_only: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        """Find AIDB-labeled Docker resources.

        Args
        ----
            all_resources: Find all AIDB resources
            volumes_only: Only find volumes
            orphaned_only: Only find orphaned resources

        Returns
        -------
            Dictionary of resource types and their details
        """
        return self.resource_service.find_aidb_resources(
            all_resources=all_resources,
            volumes_only=volumes_only,
            orphaned_only=orphaned_only,
        )

    def cleanup_resources(
        self,
        resources: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, list[str]]]:
        """Remove the specified resources.

        Args
        ----
            resources: Dictionary of resource types to remove

        Returns
        -------
            Results with success and failed lists for each type
        """
        return self.cleanup_service.cleanup_resources(resources)

    def display_resources(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        """Display resources that will be removed.

        Args
        ----
            resources: Dictionary of resource types and their details
        """
        self.cleanup_service.display_resources(resources)

    def display_cleanup_results(
        self,
        results: dict[str, dict[str, list[str]]],
    ) -> None:
        """Display cleanup results.

        Args
        ----
            results: Cleanup results with success and failed lists
        """
        self.cleanup_service.display_cleanup_results(results)

    def count_resources(self, resources: dict[str, list[dict[str, Any]]]) -> int:
        """Count total number of resources.

        Args
        ----
            resources: Dictionary of resource types

        Returns
        -------
            Total count of all resources
        """
        return self.resource_service.count_resources(resources)
