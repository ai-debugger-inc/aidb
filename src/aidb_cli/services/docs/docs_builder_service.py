"""Service for building documentation."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.env import reader
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.managers.docker import DockerComposeExecutor
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


@dataclass(frozen=True)
class DocsTarget:
    """Compose target configuration for docs operations."""

    build_service: str
    serve_service: str
    port_env_var: str
    default_port: int


class DocsBuilderService(BaseService):
    """Service for building documentation.

    This service handles:
    - Docker-based documentation building
    - Internal documentation building
    - Build artifact management
    - Compose file validation
    """

    # Predefined documentation targets
    PUBLIC = DocsTarget(
        build_service="aidb-docs-build",
        serve_service="aidb-docs",
        port_env_var="AIDB_DOCS_PORT",
        default_port=8000,
    )

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the docs builder service."""
        super().__init__(repo_root, command_executor)
        self.compose_file = self._get_compose_file()

    def _get_compose_file(self) -> Path:
        """Get the Docker compose file path for docs."""
        from aidb_cli.core.paths import ProjectPaths

        return self.repo_root / ProjectPaths.DOCS_DOCKER_COMPOSE

    def ensure_compose_file(self) -> Path:
        """Ensure the Docker compose file exists.

        Auto-syncs versions.json to .env file before checking.

        Returns
        -------
            Path to the compose file

        Raises
        ------
            FileNotFoundError: If compose file doesn't exist
        """
        # Auto-sync versions before any docker operation
        from aidb_cli.services.docs.docs_env_sync_service import DocsEnvSyncService

        syncer = DocsEnvSyncService(self.repo_root)
        syncer.sync_if_needed()

        if not self.compose_file.exists():
            CliOutput.error(f"Docs compose file not found: {self.compose_file}")
            msg = f"Docs compose file not found: {self.compose_file}"
            raise FileNotFoundError(msg)
        return self.compose_file

    def get_docs_executor(self) -> "DockerComposeExecutor":
        """Get a configured DockerComposeExecutor for docs operations.

        Returns
        -------
            Configured DockerComposeExecutor
        """
        from aidb_cli.core.paths import DockerConstants
        from aidb_cli.managers.docker import DockerComposeExecutor
        from aidb_cli.managers.environment_manager import EnvironmentManager

        self.ensure_compose_file()

        # Use centralized environment if available, otherwise create new one
        environment = self.resolved_env
        if environment is None:
            # Fallback: create a fresh EnvironmentManager when no context
            env_manager = EnvironmentManager(self.repo_root)
            environment = env_manager.get_environment()
            self.log_debug("Using fresh EnvironmentManager for docs service")
        else:
            self.log_debug("Using centralized environment for docs service")

        # Path to .env file containing PYTHON_TAG and other build vars
        env_file = self.compose_file.parent / ".env"

        return DockerComposeExecutor(
            self.compose_file,
            environment=environment,
            project_name=DockerConstants.DOCS_PROJECT,
            env_file=env_file if env_file.exists() else None,
        )

    def build_docs(self, target: DocsTarget, rebuild: bool = False) -> None:
        """Build documentation using Docker compose.

        Parameters
        ----------
        target : DocsTarget
            Documentation target configuration
        rebuild : bool
            If True, rebuild the Docker image before building docs.
            Use this when dependencies (requirements.txt) have changed.
        """
        executor = self.get_docs_executor()

        if rebuild:
            self.log_info("Rebuilding Docker image for docs...")
            executor.execute(
                ["build", "--no-cache", target.build_service],
                capture_output=False,
            )

        executor.run_service(
            target.build_service,
            remove=True,
            capture_output=False,
            check=True,
        )

    def get_running_services(self) -> list[str]:
        """Get list of running documentation services.

        Returns
        -------
            List of running service names
        """
        executor = self.get_docs_executor()
        return executor.get_running_services()

    def get_service_port(
        self,
        service: str,
        internal_port: str = "8000",
    ) -> str | None:
        """Get the exposed port for a running service.

        Args
        ----
            service: Service name
            internal_port: Internal port number

        Returns
        -------
            Exposed port or None if not running
        """
        executor = self.get_docs_executor()
        return executor.get_service_port(service, internal_port)

    def get_service_status(
        self,
        target: DocsTarget,
    ) -> tuple[bool, str | None]:
        """Get status of a documentation service.

        Args
        ----
            target: Documentation target

        Returns
        -------
            Tuple of (is_running, port)
        """
        running_services = self.get_running_services()

        if target.serve_service in running_services:
            port = self.get_service_port(target.serve_service, "8000")
            if port is None:
                port = reader.read_str(
                    target.port_env_var,
                    default=str(target.default_port),
                )
            return True, port
        return False, None
