"""Service for Docker container health checking."""

# subprocess import removed - using CommandExecutor instead
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import CliTimeouts
from aidb_cli.core.paths import DockerConstants
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerHealthService(BaseService):
    """Service for checking Docker container health.

    This service handles:
    - Waiting for container health status
    - Checking service readiness
    - Health check retries and timeouts
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        project_name: str = DockerConstants.DEFAULT_PROJECT,
    ) -> None:
        """Initialize the Docker health service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        project_name : str, optional
            Docker project name
        """
        super().__init__(repo_root, command_executor)
        self.project_name = project_name

    def wait_for_health(
        self,
        service_name: str,
        timeout: int = DockerConstants.DEFAULT_HEALTH_TIMEOUT,
        verbose: bool = False,
        container_name: str | None = None,
    ) -> bool:
        """Wait for a service to become healthy.

        Parameters
        ----------
        service_name : str
            Service name to check
        timeout : int, optional
            Timeout in seconds
        verbose : bool, optional
            Show verbose output

        Returns
        -------
        bool
            True if service became healthy, False otherwise
        """
        start_time = time.time()
        container = container_name or f"{self.project_name}-{service_name}-1"

        if verbose:
            CliOutput.info(f"Waiting for {service_name} to be healthy...")

        while time.time() - start_time < timeout:
            # Check container health status
            result = self.command_executor.execute(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container,
                ],
                capture_output=True,
                check=False,
            )

            if result.returncode == 0:
                health_status = result.stdout.strip()

                if health_status == "healthy":
                    if verbose:
                        CliOutput.success(f"{service_name} is healthy")
                    self.log_info("Service %s is healthy", service_name)
                    return True

                if health_status in ["unhealthy", "none"]:
                    # Check if container is at least running
                    running_result = self.command_executor.execute(
                        [
                            "docker",
                            "inspect",
                            "--format",
                            "{{.State.Running}}",
                            container,
                        ],
                        capture_output=True,
                        check=False,
                    )

                    if (
                        running_result.returncode == 0
                        and running_result.stdout.strip() == "true"
                    ):
                        if verbose:
                            CliOutput.warning(
                                f"{service_name} is running but not healthy",
                            )
                    else:
                        self.log_warning("Service %s is not running", service_name)
                        return False

            time.sleep(CliTimeouts.DOCKER_HEALTH_CHECK_INTERVAL_S)

        self.log_warning(
            "Service %s did not become healthy within %d seconds",
            service_name,
            timeout,
        )
        return False

    def check_service_health(
        self,
        service_name: str,
        container_name: str | None = None,
    ) -> str:
        """Check the current health status of a service.

        Parameters
        ----------
        service_name : str
            Service name to check

        Returns
        -------
        str
            Health status: 'healthy', 'unhealthy', 'starting', 'none', or 'not_found'
        """
        container = container_name or f"{self.project_name}-{service_name}-1"

        result = self.command_executor.execute(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Health.Status}}",
                container,
            ],
            capture_output=True,
            check=False,
        )

        if result.returncode == 0:
            status = result.stdout.strip()
            return status if status else "none"

        return "not_found"

    def is_container_running(
        self,
        service_name: str,
        container_name: str | None = None,
    ) -> bool:
        """Check if a container is running.

        Parameters
        ----------
        service_name : str
            Service name to check

        Returns
        -------
        bool
            True if container is running
        """
        container = container_name or f"{self.project_name}-{service_name}-1"

        result = self.command_executor.execute(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Running}}",
                container,
            ],
            capture_output=True,
            check=False,
        )

        return result.returncode == 0 and result.stdout.strip() == "true"

    def run_health_checks(self, services: list[str]) -> dict[str, bool]:
        """Run health checks for multiple services.

        Parameters
        ----------
        services : list[str]
            List of service names to check

        Returns
        -------
        dict[str, bool]
            Dictionary mapping service names to health status
        """
        results = {}

        for service in services:
            health_status = self.check_service_health(service)
            results[service] = health_status == "healthy"
            self.log_debug("Service %s health: %s", service, health_status)

        return results

    def wait_for_services(
        self,
        services: list[str],
        timeout: int = DockerConstants.DEFAULT_HEALTH_TIMEOUT,
        verbose: bool = False,
    ) -> dict[str, bool]:
        """Wait for multiple services to become healthy.

        Parameters
        ----------
        services : list[str]
            List of service names to wait for
        timeout : int, optional
            Timeout in seconds
        verbose : bool, optional
            Show verbose output

        Returns
        -------
        dict[str, bool]
            Dictionary mapping service names to success status
        """
        results = {}
        start_time = time.time()
        remaining_timeout = timeout

        for service in services:
            # Calculate remaining timeout for this service
            elapsed = time.time() - start_time
            remaining_timeout = max(1, timeout - int(elapsed))

            # Wait for this service
            success = self.wait_for_health(
                service,
                timeout=remaining_timeout,
                verbose=verbose,
            )
            results[service] = success

            if not success and verbose:
                CliOutput.error(f"{service} failed health check")

        return results

    def cleanup(self) -> None:
        """Cleanup service resources."""
        # No specific cleanup needed for this service
