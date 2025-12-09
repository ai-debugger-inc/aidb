"""Refactored Docker orchestrator using orchestrator pattern."""

import contextlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import SERVICE_DISCOVERY_TIMEOUT_S
from aidb_cli.core.paths import DockerConstants, ProjectPaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.orchestrator import BaseOrchestrator
from aidb_cli.managers.docker.docker_executor import DockerComposeExecutor
from aidb_cli.managers.environment_manager import EnvironmentManager
from aidb_cli.services.docker import (
    ComposeGeneratorService,
    DockerHealthService,
    DockerLoggingService,
    ServiceDependencyService,
)
from aidb_common.config import VersionManager
from aidb_common.constants import SUPPORTED_LANGUAGES
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    import click

    from aidb_cli.services.command_executor import CommandExecutor

logger = get_cli_logger(__name__)


class DockerOrchestrator(BaseOrchestrator):
    """Orchestrates Docker services for testing.

    This refactored version uses the orchestrator pattern to coordinate multiple
    services for Docker operations.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: Optional["click.Context"] = None,
    ) -> None:
        """Initialize the Docker orchestrator.

        Parameters
        ----------
        repo_root : Path | None, optional
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        """
        # Initialize repo_root first so we can set compose_file before super() call
        if repo_root is None:
            from aidb_common.repo import detect_repo_root

            repo_root = detect_repo_root()

        # Auto-generate compose file if needed (hash-based caching)
        compose_generator = ComposeGeneratorService(repo_root)
        if compose_generator.needs_regeneration():
            logger.info("Regenerating docker-compose.yaml from templates...")
            compose_generator.generate()
            logger.debug("Compose file regeneration complete")

        self.compose_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE

        super().__init__(repo_root, command_executor)
        self.ctx = ctx
        self.version_manager = VersionManager(
            self.repo_root / ProjectPaths.VERSIONS_YAML,
        )

        # Use centralized environment if context available,
        # otherwise create new EnvironmentManager
        if ctx and hasattr(ctx.obj, "resolved_env"):
            environment = ctx.obj.resolved_env
        else:
            # Fallback: create a fresh EnvironmentManager when no context
            env_manager = EnvironmentManager(self.repo_root)
            environment = env_manager.get_environment()

        self.executor = DockerComposeExecutor(
            self.compose_file,
            environment=environment,
            project_name=DockerConstants.DEFAULT_PROJECT,
        )

    def _register_services(self) -> None:
        """Register services for Docker operations."""
        self.register_service(ServiceDependencyService)
        self.register_service(DockerHealthService)
        self.register_service(DockerLoggingService)
        self._load_services()

    def _load_services(self) -> None:
        """Load service definitions from docker-compose.yaml."""
        dependency_service = self.get_service(ServiceDependencyService)
        dependency_service.load_services(self.compose_file)
        self.services = dependency_service.services

    def resolve_dependencies(self, service_name: str) -> list[str]:
        """Resolve all dependencies for a service."""
        service = self.get_service(ServiceDependencyService)
        return service.resolve_dependencies(service_name)

    def start_service(
        self,
        service_name: str,
        wait_healthy: bool = True,
        timeout: int = 60,
        extra_env: dict[str, str] | None = None,
    ) -> bool:
        """Start a service and optionally wait for it to be healthy.

        Parameters
        ----------
        service_name : str
            Name of the service to start
        wait_healthy : bool, optional
            Wait for service to be healthy
        timeout : int, optional
            Health check timeout
        extra_env : dict[str, str] | None, optional
            Additional environment variables to pass to container

        Returns
        -------
        bool
            True if service started successfully
        """
        dep_service = self.get_service(ServiceDependencyService)
        health_service = self.get_service(DockerHealthService)

        if service_name not in self.services:
            logger.error("Unknown service: %s", service_name)
            return False

        service = self.services[service_name]

        if service.started:
            logger.debug("Service %s already started", service_name)
            return True

        dependencies = dep_service.resolve_dependencies(service_name)
        logger.debug("Starting services in order: %s", dependencies)

        for dep_name in dependencies:
            if dep_name == service_name:
                continue

            if not self.start_service(dep_name, wait_healthy=True, extra_env=extra_env):
                logger.error("Failed to start dependency: %s", dep_name)
                return False

        CliOutput.info(f"Starting {service_name}...")

        profiles = service.profiles if service.profiles else []

        result = self.executor.execute(
            ["up", "-d", service_name],
            profile=profiles if profiles else None,
            capture_output=True,  # Force capture for Docker ops
            extra_env=extra_env,
        )

        if result.returncode != 0:
            CliOutput.error(f"Failed to start {service_name}: {result.stderr}")
            return False

        service.started = True
        CliOutput.success(f"Started {service_name}")

        if wait_healthy and service.health_check:
            return health_service.wait_for_health(
                service_name,
                timeout=timeout,
                container_name=getattr(service, "container_name", None),
            )

        return True

    def wait_for_health(self, service_name: str, timeout: int = 60) -> bool:
        """Wait for a service to be healthy."""
        health_service = self.get_service(DockerHealthService)

        if service_name not in self.services:
            return False

        service = self.services[service_name]
        healthy = health_service.wait_for_health(
            service_name,
            timeout=timeout,
            container_name=getattr(service, "container_name", None),
        )

        if healthy:
            service.healthy = True

        return healthy

    def stop_service(self, service_name: str) -> bool:
        """Stop a service."""
        if service_name not in self.services:
            return False

        service = self.services[service_name]

        result = self.executor.execute(
            ["stop", service_name],
            profile=service.profiles,
            capture_output=True,  # Force capture for Docker ops
        )

        if result.returncode == 0:
            service.started = False
            service.healthy = False
            CliOutput.success(f"Stopped {service_name}")
            return True

        CliOutput.error(f"Failed to stop {service_name}: {result.stderr}")
        return False

    def cleanup_services(
        self,
        profile: str | None = None,
        remove_volumes: bool = True,
        quiet: bool = False,
    ) -> bool:
        """Clean up Docker services and resources.

        Parameters
        ----------
        profile : str | None
            Docker profile to clean up
        remove_volumes : bool
            Whether to remove volumes
        quiet : bool
            Suppress output messages
        """
        if not quiet:
            CliOutput.info("Cleaning up Docker services...")

        args = ["down"]
        if remove_volumes:
            args.append("-v")
        args.append("--remove-orphans")

        result = self.executor.execute(args, profile=profile, capture_output=True)

        if result.returncode == 0:
            if not quiet:
                CliOutput.success("Cleanup complete")

            # Reset service states
            for service in self.services.values():
                if not profile or profile in service.profiles:
                    service.started = False
                    service.healthy = False

            return True

        if not quiet:
            CliOutput.error(f"Cleanup failed: {result.stderr}")
        return False

    def get_service_logs(
        self,
        service_name: str,
        lines: int = 100,
    ) -> str | None:
        """Get logs from a service."""
        logging_service = self.get_service(DockerLoggingService)
        return logging_service.get_service_logs(
            service_name,
            lines=lines,
        )

    def start_test_environment(  # noqa: C901
        self,
        test_suite: str,
        language: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> bool:
        """Start a complete test environment.

        Parameters
        ----------
        test_suite : str
            Test suite name (used as profile)
        language : str | None, optional
            Language filter (for compatibility)
        extra_env : dict[str, str] | None, optional
            Additional environment variables to pass to containers

        Returns
        -------
        bool
            True if environment started successfully
        """
        CliOutput.info(f"Starting test environment for {test_suite}...")
        logger.debug("Received test_suite='%s', language='%s'", test_suite, language)

        services_to_start = []

        # Get dependency service for dynamic discovery
        dep_service = self.get_service(ServiceDependencyService)

        # Handle language-specific framework tests dynamically
        if test_suite in SUPPORTED_LANGUAGES:
            # Get services in this profile and filter for test-runner pattern
            profile_services = dep_service.get_services_by_profile(test_suite)
            services_to_start.extend(
                [s for s in profile_services if s.startswith("test-runner-")],
            )
        elif test_suite == "frameworks":
            # Get all services in frameworks profile and filter for test-runner pattern
            framework_services = dep_service.get_services_by_profile("frameworks")
            services_to_start.extend(
                [s for s in framework_services if s.startswith("test-runner-")],
            )
        else:
            # Handle all other suites dynamically using profile discovery
            profile_services = dep_service.get_services_by_profile(test_suite)
            if profile_services:
                services_to_start.extend(profile_services)
            else:
                # Fallback to test-runner if no services found for profile
                services_to_start.append("test-runner")

        logger.debug("Services to start: %s", services_to_start)

        success = True
        for service in services_to_start:
            # Test runner services are one-shot containers
            # Don't wait for health checks on them
            is_test_runner = "test-runner" in service
            if not self.start_service(
                service,
                wait_healthy=not is_test_runner,
                extra_env=extra_env,
            ):
                success = False
                break

        if success:
            CliOutput.success("Test environment ready!")
        else:
            CliOutput.error("Failed to start test environment")
            self.cleanup_services()

        return success

    def debug_environment(self) -> None:
        """Print current Docker environment for debugging."""
        print(self.env_provider.debug_environment())

    def run_health_checks(self) -> dict[str, bool]:
        """Run health checks on all started services."""
        health_service = self.get_service(DockerHealthService)
        results = {}

        for name, service in self.services.items():
            if not service.started:
                continue

            if service.health_check:
                healthy = health_service.wait_for_health(
                    name,
                    timeout=SERVICE_DISCOVERY_TIMEOUT_S,
                )
                results[name] = healthy
            else:
                results[name] = True  # No health check means assumed healthy

        return results

    def stream_compose_logs(
        self,
        follow: bool = True,
        profile: str | None = None,
    ) -> subprocess.Popen | None:
        """Stream logs from all compose services."""
        logging_service = self.get_service(DockerLoggingService)
        return logging_service.stream_compose_logs(
            compose_file=self.compose_file,
            profile=profile,
            follow=follow,
        )

    def wait_for_compose_completion(
        self,
        profile: str,
        stream_logs: bool = False,
        timeout: int = 600,
    ) -> int:
        """Wait for compose services to complete and return the exit code."""
        args = ["wait"]
        if timeout:
            args.extend(["--timeout", str(timeout)])

        log_process: subprocess.Popen | None = None
        if stream_logs:
            log_process = self.stream_compose_logs(profile=profile)

        result = self.executor.execute(args, profile=profile, capture_output=True)

        if log_process is not None:
            with contextlib.suppress(Exception):
                log_process.terminate()

        return result.returncode
