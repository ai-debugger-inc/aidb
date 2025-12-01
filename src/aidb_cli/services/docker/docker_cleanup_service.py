"""Service for Docker resource cleanup operations."""

from typing import TYPE_CHECKING, Any, Optional

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerCleanupService(BaseService):
    """Service for cleaning up Docker resources.

    This service handles:
    - Removing containers, volumes, networks, and images
    - Displaying resources to be removed
    - Tracking cleanup results
    """

    def __init__(
        self,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the Docker cleanup service."""
        super().__init__(None, command_executor)

    def cleanup_resources(
        self,
        resources: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, list[str]]]:
        """Remove the specified resources.

        Args
        ----
            resources: Dictionary of resource types and their details

        Returns
        -------
            Results with 'success' and 'failed' lists for each resource type
        """
        results: dict[str, dict[str, list[str]]] = {
            "containers": {"success": [], "failed": []},
            "volumes": {"success": [], "failed": []},
            "networks": {"success": [], "failed": []},
            "images": {"success": [], "failed": []},
        }

        # Remove containers first (stops and removes)
        for container in resources.get("containers", []):
            container_id = container.get("ID", "")
            container_name = container.get("Names", container_id)

            if self.remove_container(container_id):
                results["containers"]["success"].append(container_name)
            else:
                results["containers"]["failed"].append(container_name)

        # Remove volumes
        for volume in resources.get("volumes", []):
            volume_name = volume.get("Name", "")

            if self.remove_volume(volume_name):
                results["volumes"]["success"].append(volume_name)
            else:
                results["volumes"]["failed"].append(volume_name)

        # Remove networks
        for network in resources.get("networks", []):
            network_name = network.get("Name", "")

            if self.remove_network(network_name):
                results["networks"]["success"].append(network_name)
            else:
                results["networks"]["failed"].append(network_name)

        # Remove images last
        for image in resources.get("images", []):
            image_id = image.get("ID", "")
            image_name = (
                f"{image.get('Repository', 'unknown')}:{image.get('Tag', 'unknown')}"
            )

            if self.remove_image(image_id):
                results["images"]["success"].append(image_name)
            else:
                results["images"]["failed"].append(image_name)

        return results

    def remove_container(self, container_id: str) -> bool:
        """Remove a container (stop and remove).

        Args
        ----
            container_id: Container ID or name

        Returns
        -------
            True if successful, False otherwise
        """
        try:
            # Stop the container first
            self.command_executor.execute(
                ["docker", "stop", container_id],
                capture_output=True,
                check=False,  # Don't fail if already stopped
            )

            # Remove the container
            self.command_executor.execute(
                ["docker", "rm", container_id],
                capture_output=True,
                check=True,
            )
            return True
        except AidbError as e:
            logger.error("Failed to remove container %s: %s", container_id, e)
            return False

    def remove_volume(self, volume_name: str) -> bool:
        """Remove a volume.

        Args
        ----
            volume_name: Volume name

        Returns
        -------
            True if successful, False otherwise
        """
        try:
            self.command_executor.execute(
                ["docker", "volume", "rm", volume_name],
                capture_output=True,
                check=True,
            )
            return True
        except AidbError as e:
            logger.error("Failed to remove volume %s: %s", volume_name, e)
            return False

    def remove_network(self, network_name: str) -> bool:
        """Remove a network.

        Args
        ----
            network_name: Network name

        Returns
        -------
            True if successful, False otherwise
        """
        try:
            self.command_executor.execute(
                ["docker", "network", "rm", network_name],
                capture_output=True,
                check=True,
            )
            return True
        except AidbError as e:
            logger.error("Failed to remove network %s: %s", network_name, e)
            return False

    def remove_image(self, image_id: str) -> bool:
        """Remove an image.

        Args
        ----
            image_id: Image ID or name

        Returns
        -------
            True if successful, False otherwise
        """
        try:
            self.command_executor.execute(
                ["docker", "rmi", image_id],
                capture_output=True,
                check=True,
            )
            return True
        except AidbError as e:
            logger.error("Failed to remove image %s: %s", image_id, e)
            return False

    def display_resources(self, resources: dict[str, list[dict[str, Any]]]) -> None:
        """Display resources that will be removed.

        Args
        ----
            resources: Dictionary of resource types and their details
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Found AIDB Resources", Icons.MAGNIFYING)

        for resource_type, items in resources.items():
            if not items:
                continue

            CliOutput.plain(f"{Icons.DOCKER} {resource_type.capitalize()}:")
            for item in items:
                if resource_type == "containers":
                    name = item.get("Names", item.get("ID", "unknown"))
                    status = item.get("Status", "unknown")
                    CliOutput.plain(f"  • {name} ({status})")
                elif resource_type == "volumes":
                    name = item.get("Name", "unknown")
                    CliOutput.plain(f"  • {name}")
                elif resource_type == "networks":
                    name = item.get("Name", "unknown")
                    driver = item.get("Driver", "unknown")
                    CliOutput.plain(f"  • {name} ({driver})")
                elif resource_type == "images":
                    repo = item.get("Repository", "unknown")
                    tag = item.get("Tag", "unknown")
                    size = item.get("Size", "unknown")
                    CliOutput.plain(f"  • {repo}:{tag} ({size})")

    def display_cleanup_results(
        self,
        results: dict[str, dict[str, list[str]]],
    ) -> None:
        """Display cleanup results.

        Args
        ----
            results: Cleanup results with success and failed lists
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Cleanup Results")

        for resource_type, result in results.items():
            success_count = len(result["success"])
            failed_count = len(result["failed"])

            if success_count > 0:
                CliOutput.success(
                    f"  {resource_type.capitalize()}: {success_count} removed",
                )

            if failed_count > 0:
                CliOutput.error(
                    f"  {resource_type.capitalize()}: {failed_count} failed",
                )
                for name in result["failed"]:
                    CliOutput.error(f"    - {name}")
