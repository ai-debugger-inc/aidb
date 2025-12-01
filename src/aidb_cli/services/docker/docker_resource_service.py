"""Service for Docker resource discovery and management."""

import json
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.errors import AidbError
from aidb_cli.core.constants import DockerLabels, DockerLabelValues
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerResourceService(BaseService):
    """Service for discovering and managing Docker resources.

    This service handles:
    - Finding AIDB-labeled Docker resources (containers, volumes, networks, images)
    - Checking resource status and usage
    - Filtering resources by various criteria
    """

    def __init__(
        self,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the Docker resource service."""
        super().__init__(None, command_executor)
        self.project_filter = f"{DockerLabels.PROJECT}={DockerLabelValues.PROJECT_NAME}"

    def find_aidb_resources(
        self,
        all_resources: bool = False,
        volumes_only: bool = False,
        orphaned_only: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        """Find AIDB-labeled Docker resources.

        Args
        ----
            all_resources: Find all AIDB resources (containers, volumes, networks, images)
            volumes_only: Only find volumes
            orphaned_only: Only find orphaned resources

        Returns
        -------
            Dictionary of resource types and their details
        """
        resources: dict[str, list[dict[str, str]]] = {
            "containers": [],
            "volumes": [],
            "networks": [],
            "images": [],
        }

        try:
            if not volumes_only:
                # Find containers
                containers = self.find_containers(orphaned_only=orphaned_only)
                resources["containers"] = containers

                if all_resources:
                    # Find networks
                    networks = self.find_networks()
                    resources["networks"] = networks

                    # Find images
                    images = self.find_images()
                    resources["images"] = images

            # Always find volumes
            volumes = self.find_volumes(orphaned_only=orphaned_only)
            resources["volumes"] = volumes

        except AidbError as e:
            logger.error("Failed to query Docker resources: %s", e)
            msg = f"Docker query failed: {e}"
            raise RuntimeError(msg) from e

        return resources

    def find_containers(self, orphaned_only: bool = False) -> list[dict[str, Any]]:
        """Find AIDB containers.

        Args
        ----
            orphaned_only: Only find exited/stopped containers

        Returns
        -------
            List of container dictionaries
        """
        cmd = [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={self.project_filter}",
            "--format",
            "{{json .}}",
        ]

        if orphaned_only:
            cmd.extend(["--filter", "status=exited"])

        try:
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=True,
            )

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    container = json.loads(line)
                    containers.append(container)

            return containers
        except AidbError:
            logger.debug("No AIDB containers found or Docker unavailable")
            return []

    def find_volumes(self, orphaned_only: bool = False) -> list[dict[str, Any]]:
        """Find AIDB volumes.

        Args
        ----
            orphaned_only: Only find volumes not in use

        Returns
        -------
            List of volume dictionaries
        """
        cmd = [
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label={self.project_filter}",
            "--format",
            "{{json .}}",
        ]

        try:
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=True,
            )

            volumes = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    volume = json.loads(line)
                    if orphaned_only:
                        if not self.is_volume_in_use(volume["Name"]):
                            volumes.append(volume)
                    else:
                        volumes.append(volume)

            return volumes
        except AidbError:
            logger.debug("No AIDB volumes found or Docker unavailable")
            return []

    def find_networks(self) -> list[dict[str, Any]]:
        """Find AIDB networks.

        Returns
        -------
            List of network dictionaries
        """
        cmd = [
            "docker",
            "network",
            "ls",
            "--filter",
            f"label={self.project_filter}",
            "--format",
            "{{json .}}",
        ]

        try:
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=True,
            )

            networks = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    network = json.loads(line)
                    networks.append(network)

            return networks
        except AidbError:
            logger.debug("No AIDB networks found or Docker unavailable")
            return []

    def find_images(self) -> list[dict[str, Any]]:
        """Find AIDB images.

        Returns
        -------
            List of image dictionaries
        """
        cmd = [
            "docker",
            "images",
            "--filter",
            f"label={self.project_filter}",
            "--format",
            "{{json .}}",
        ]

        try:
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=True,
            )

            images = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    image = json.loads(line)
                    images.append(image)

            return images
        except AidbError:
            logger.debug("No AIDB images found or Docker unavailable")
            return []

    def is_volume_in_use(self, volume_name: str) -> bool:
        """Check if a volume is currently in use by any container.

        Args
        ----
            volume_name: Name of the volume to check

        Returns
        -------
            True if volume is in use, False otherwise
        """
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "{{.Mounts}}",
            "--filter",
            f"volume={volume_name}",
        ]

        try:
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except AidbError:
            return False

    def count_resources(self, resources: dict[str, list[dict[str, Any]]]) -> int:
        """Count total number of resources.

        Args
        ----
            resources: Dictionary of resource types and items

        Returns
        -------
            Total count of all resources
        """
        return sum(len(items) for items in resources.values())
