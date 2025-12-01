"""Service for managing Docker service dependencies."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.core.paths import ProjectPaths
from aidb_cli.managers.base.service import BaseService
from aidb_common.io import safe_read_yaml
from aidb_common.io.files import FileOperationError
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class ServiceDependency:
    """Represents a service and its dependencies."""

    def __init__(
        self,
        name: str,
        profiles: list[str] | None = None,
        depends_on: list[str] | None = None,
        health_check: dict[str, Any] | None = None,
        container_name: str | None = None,
        has_build: bool = False,
        extends: str | None = None,
    ) -> None:
        """Initialize service dependency.

        Parameters
        ----------
        name : str
            Service name
        profiles : list[str], optional
            Docker compose profiles this service belongs to
        depends_on : list[str], optional
            List of service dependencies
        health_check : dict, optional
            Health check configuration
        container_name : str, optional
            Explicit container name
        has_build : bool, optional
            Whether service has a build configuration
        extends : str, optional
            Name of service this extends from
        """
        self.name = name
        self.profiles = profiles or []
        self.depends_on = depends_on or []
        self.health_check = health_check
        self.started = False
        self.healthy = False
        self.container_name = container_name
        self.has_build = has_build
        self.extends = extends


class ServiceDependencyService(BaseService):
    """Service for managing Docker service dependencies and resolution.

    This service handles:
    - Loading service definitions from docker-compose files
    - Resolving service dependency graphs
    - Tracking service states
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the service dependency service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)
        self.services: dict[str, ServiceDependency] = {}
        self.compose_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE

    def load_services(self, compose_file: Path | None = None) -> None:  # noqa: C901
        """Load service definitions from docker-compose.yaml.

        Parameters
        ----------
        compose_file : Path | None, optional
            Path to compose file, defaults to test compose file
        """
        if compose_file:
            self.compose_file = compose_file

        if not self.compose_file.exists():
            self.log_warning("Docker compose file not found: %s", self.compose_file)
            return

        try:
            compose_data = safe_read_yaml(self.compose_file)

            services_data = compose_data.get("services", {})

            for service_name, service_config in services_data.items():
                # Extract dependency information
                depends_on = []
                depends_on_raw = service_config.get("depends_on", [])

                if isinstance(depends_on_raw, list):
                    depends_on = depends_on_raw
                elif isinstance(depends_on_raw, dict):
                    # Handle condition-based dependencies
                    depends_on = list(depends_on_raw.keys())

                # Extract profiles (support multiple)
                profiles = service_config.get("profiles", [])

                # Extract health check
                health_check = service_config.get("healthcheck")
                # Extract explicit container name if set
                container_name = service_config.get("container_name")
                # Check if service has build configuration
                has_build = "build" in service_config

                # Extract extends information
                extends = None
                extends_config = service_config.get("extends")
                if extends_config:
                    if isinstance(extends_config, str):
                        extends = extends_config
                    elif isinstance(extends_config, dict):
                        extends = extends_config.get("service")

                # Create service dependency
                self.services[service_name] = ServiceDependency(
                    name=service_name,
                    profiles=profiles,
                    depends_on=depends_on,
                    health_check=health_check,
                    container_name=container_name,
                    has_build=has_build,
                    extends=extends,
                )

                self.log_debug(
                    "Loaded service %s (profiles: %s, deps: %s, buildable: %s)",
                    service_name,
                    profiles,
                    depends_on,
                    has_build,
                )

        except FileOperationError as e:
            self.log_error("Failed to load services from compose file: %s", str(e))
        except (KeyError, TypeError, AttributeError) as e:
            self.log_error("Invalid compose file structure: %s", str(e))

    def resolve_dependencies(self, service_name: str) -> list[str]:
        """Resolve service dependencies in correct start order.

        Parameters
        ----------
        service_name : str
            Service to resolve dependencies for

        Returns
        -------
        list[str]
            Ordered list of services to start (dependencies first)
        """
        if service_name not in self.services:
            self.log_warning("Service %s not found", service_name)
            return [service_name]

        resolved = []
        visited = set()

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)

            if name in self.services:
                for dep in self.services[name].depends_on:
                    visit(dep)

            if name not in resolved:
                resolved.append(name)

        visit(service_name)
        self.log_debug("Resolved dependencies for %s: %s", service_name, resolved)
        return resolved

    def get_services_by_profile(self, profile: str) -> list[str]:
        """Get all services belonging to a specific profile.

        Parameters
        ----------
        profile : str
            Profile name

        Returns
        -------
        list[str]
            List of service names in the profile
        """
        services = [
            name
            for name, service in self.services.items()
            if profile in service.profiles
        ]
        self.log_debug("Services in profile %s: %s", profile, services)
        return services

    def get_buildable_services_by_profile(
        self,
        profile: str,
        pattern: str | None = None,
    ) -> list[str]:
        """Get services with build configurations in a specific profile.

        Services that extend other services are excluded since they should
        use the parent's image rather than rebuild it.

        Parameters
        ----------
        profile : str
            Profile name
        pattern : str, optional
            Service name pattern to filter (supports * wildcard)

        Returns
        -------
        list[str]
            List of buildable service names in the profile
        """
        services = [
            name
            for name, service in self.services.items()
            if profile in service.profiles and service.has_build and not service.extends
        ]

        # Apply pattern filter if provided
        if pattern:
            import fnmatch

            services = [s for s in services if fnmatch.fnmatch(s, pattern)]

        self.log_debug(
            "Buildable services in profile %s (pattern: %s): %s",
            profile,
            pattern or "none",
            services,
        )
        return services

    def get_all_buildable_services(
        self,
        pattern: str | None = None,
    ) -> list[str]:
        """Get all services with build configurations, regardless of profile.

        Services that extend other services are excluded since they should
        use the parent's image rather than rebuild it.

        Parameters
        ----------
        pattern : str, optional
            Service name pattern to filter (supports * wildcard)

        Returns
        -------
        list[str]
            List of all buildable service names
        """
        services = [
            name
            for name, service in self.services.items()
            if service.has_build and not service.extends
        ]

        # Apply pattern filter if provided
        if pattern:
            import fnmatch

            services = [s for s in services if fnmatch.fnmatch(s, pattern)]

        self.log_debug(
            "All buildable services (pattern: %s): %s",
            pattern or "none",
            services,
        )
        return services

    def get_service_image_tag(self, service_name: str) -> str | None:
        """Get the image tag for a service from docker-compose configuration.

        Parameters
        ----------
        service_name : str
            Service name

        Returns
        -------
        str or None
            Image tag if found, None otherwise
        """
        from aidb_common.io.files import safe_read_yaml

        try:
            compose_data = safe_read_yaml(self.compose_file)
            services_data = compose_data.get("services", {})
            service_config = services_data.get(service_name, {})
            return service_config.get("image")
        except Exception as e:
            self.log_warning(
                "Failed to get image tag for service %s: %s",
                service_name,
                str(e),
            )
            return None

    def mark_service_started(self, service_name: str) -> None:
        """Mark a service as started.

        Parameters
        ----------
        service_name : str
            Service name to mark as started
        """
        if service_name in self.services:
            self.services[service_name].started = True
            self.log_debug("Marked service %s as started", service_name)

    def mark_service_healthy(self, service_name: str) -> None:
        """Mark a service as healthy.

        Parameters
        ----------
        service_name : str
            Service name to mark as healthy
        """
        if service_name in self.services:
            self.services[service_name].healthy = True
            self.log_debug("Marked service %s as healthy", service_name)

    def get_container_name(self, service_name: str) -> str | None:
        """Get container name for a service from compose config.

        Parameters
        ----------
        service_name : str
            Service name

        Returns
        -------
        str | None
            Container name if defined, None otherwise
        """
        if service_name in self.services:
            return self.services[service_name].container_name
        return None

    def get_service(self, service_name: str) -> ServiceDependency | None:
        """Get a service dependency object.

        Parameters
        ----------
        service_name : str
            Service name

        Returns
        -------
        ServiceDependency | None
            Service dependency object or None if not found
        """
        return self.services.get(service_name)

    def get_all_services(self) -> dict[str, ServiceDependency]:
        """Get all loaded services.

        Returns
        -------
        dict[str, ServiceDependency]
            Dictionary of all services
        """
        return self.services

    def cleanup(self) -> None:
        """Cleanup service resources."""
        # Reset all service states
        for service in self.services.values():
            service.started = False
            service.healthy = False
