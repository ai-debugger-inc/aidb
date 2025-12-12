"""Docker build service for test images.

Provides cohesive build operations used by both the docker and test commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aidb_cli.core.paths import DockerConstants, ProjectPaths
from aidb_cli.core.utils import CliOutput
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from pathlib import Path

    from aidb_cli.services import CommandExecutor
    from aidb_cli.services.docker.docker_image_checksum_service import (
        DockerImageChecksumService,
    )
    from aidb_cli.services.docker.service_dependency_service import (
        ServiceDependencyService,
    )

logger = get_cli_logger(__name__)


class DockerBuildService:
    """Build orchestration for Docker test images."""

    def __init__(
        self,
        repo_root: Path,
        command_executor: CommandExecutor,
        resolved_env: dict[str, str] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.command_executor = command_executor
        self.compose_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
        self.compose_dir = self.compose_file.parent
        self.resolved_env = resolved_env

    # ----------------------------
    # Base image
    # ----------------------------
    def build_base_image(
        self,
        *,
        no_cache: bool = False,
        tag: str = "latest",
        verbose: bool = False,
    ) -> int:
        """Build the base test image used by language-specific images."""
        cmd = [
            "docker",
            "build",
            "-f",
            str(self.compose_dir / "dockerfiles" / "Dockerfile.test.base"),
            "-t",
            f"aidb-test-base:{tag}",
        ]
        if no_cache:
            cmd.append("--no-cache")
        cmd.append(str(self.repo_root))

        if verbose:
            CliOutput.plain(" ".join(cmd))
        result = self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            check=False,
            passthrough_no_stream=verbose,
        )
        return result.returncode

    def _image_exists(self, image_name: str) -> bool:
        """Check if a Docker image exists locally."""
        result = self.command_executor.execute(
            ["docker", "image", "inspect", image_name],
            check=False,
            capture_output=True,
        )
        return result.returncode == 0

    def _get_unique_buildable_services(
        self,
        dep_service: ServiceDependencyService,
        services: list[str],
    ) -> list[str]:
        """Deduplicate services that build to the same image tag.

        When multiple services build to the same Docker image (e.g., test-runner and
        test-runner-python both building aidb-test-python:latest), only keep the
        first occurrence to avoid "image already exists" conflicts.

        Parameters
        ----------
        dep_service : ServiceDependencyService
            Service dependency service instance
        services : list[str]
            List of service names to deduplicate

        Returns
        -------
        list[str]
            Deduplicated list of service names
        """
        seen_images: dict[str, str] = {}  # image_tag -> first service
        unique_services: list[str] = []

        for service in services:
            image_tag = dep_service.get_service_image_tag(service)
            if image_tag:
                if image_tag not in seen_images:
                    seen_images[image_tag] = service
                    unique_services.append(service)
                else:
                    logger.debug(
                        "Skipping service '%s' (image '%s' already built by '%s')",
                        service,
                        image_tag,
                        seen_images[image_tag],
                    )
            else:
                # No image tag found, include it anyway
                unique_services.append(service)

        return unique_services

    # ----------------------------
    # Test images
    # ----------------------------
    def build_images(
        self,
        *,
        profile: str | None = None,
        no_cache: bool = False,
        verbose: bool = False,
        auto_rebuild: bool = True,
        check_only: bool = False,
    ) -> int:
        """Build docker compose images for a given profile.

        When profile is None, builds all services from all profiles with automatic
        deduplication to avoid conflicts from services sharing the same image.

        Parameters
        ----------
        profile : str or None, optional
            Docker profile to build, or None to build all profiles (default: None)
        no_cache : bool, optional
            Build without cache (default: False)
        verbose : bool, optional
            Verbose output (default: False)
        auto_rebuild : bool, optional
            Enable intelligent rebuild detection (default: True)
        check_only : bool, optional
            Only check what needs rebuilding without building (default: False)

        Returns
        -------
        int
            Return code (0 for success, non-zero for failure)
        """
        from aidb_cli.services.docker.docker_image_checksum_service import (
            DockerImageChecksumService,
        )
        from aidb_cli.services.docker.service_dependency_service import (
            ServiceDependencyService,
        )

        # Initialize checksum service for rebuild detection
        checksum_service = DockerImageChecksumService(
            self.repo_root,
            self.command_executor,
        )

        # Check rebuild status if auto_rebuild is enabled
        if auto_rebuild and not no_cache and not check_only:
            base_needs_rebuild, base_reason = checksum_service.needs_rebuild("base")
            if base_needs_rebuild:
                CliOutput.info(f"Base image needs rebuild: {base_reason}")
                rc = self.build_base_image(no_cache=no_cache, verbose=verbose)
                if rc != 0:
                    CliOutput.error("Failed to build base image", err=True)
                    return rc
                checksum_service.mark_built("base")
                CliOutput.plain("")
            else:
                logger.debug("Base image is up-to-date")
        elif check_only:
            # Just report status for all images
            self._report_rebuild_status(checksum_service)
            return 0
        else:
            # Traditional behavior: check if base image exists and build if needed
            base_image = "aidb-test-base:latest"
            base_image_missing = not self._image_exists(base_image)

            if base_image_missing:
                CliOutput.plain(
                    f"Base image '{base_image}' not found - building it first...",
                )
                rc = self.build_base_image(no_cache=no_cache, verbose=verbose)
                if rc != 0:
                    CliOutput.error("Failed to build base image", err=True)
                    return rc
                CliOutput.plain("")

        # Load service definitions from docker-compose.yaml
        dep_service = ServiceDependencyService(self.repo_root, self.command_executor)
        dep_service.load_services()

        # Get buildable services for this profile
        # Note: Services with 'extends' are automatically excluded
        if profile is None:
            # Build all profiles - get all buildable services and deduplicate
            services = dep_service.get_all_buildable_services()
            services = self._get_unique_buildable_services(dep_service, services)
            logger.debug("Building all profiles with %d unique services", len(services))
        else:
            # Build specific profile
            services = dep_service.get_buildable_services_by_profile(profile)

        if not services:
            logger.warning(
                "No buildable services found for profile '%s'",
                profile or "all",
            )
            return 0

        cmd = [
            "docker",
            "compose",
            "--project-directory",
            str(self.repo_root),
            "-f",
            str(self.compose_file),
            "--project-name",
            DockerConstants.DEFAULT_PROJECT,
            "build",
        ]
        if no_cache:
            cmd.append("--no-cache")

        # Add specific service names to build
        cmd.extend(services)

        # Use centralized environment with build args if available
        if self.resolved_env:
            env = self.resolved_env.copy()
            logger.debug(
                "Using centralized environment with %d variables for Docker build",
                len(env),
            )
        else:
            env = {}
            logger.debug("No centralized environment available, using minimal env")

        # Ensure REPO_ROOT is always set (required for docker-compose build context)
        env["REPO_ROOT"] = str(self.repo_root)

        if verbose:
            CliOutput.plain(" ".join(cmd))
        result = self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            env=env,
            check=False,
            passthrough_no_stream=verbose,
        )

        # Mark images as built if successful and auto_rebuild is enabled
        if result.returncode == 0 and auto_rebuild and not no_cache:
            self._mark_images_built(checksum_service, services, dep_service)

        return result.returncode

    def _mark_images_built(
        self,
        checksum_service: DockerImageChecksumService,
        services: list[str],
        dep_service: ServiceDependencyService,
    ) -> None:
        """Mark built images in the checksum cache.

        Parameters
        ----------
        checksum_service : DockerImageChecksumService
            Checksum service instance
        services : list[str]
            List of services that were built
        dep_service : ServiceDependencyService
            Service dependency service
        """
        from aidb_cli.services.docker.docker_image_checksum_service import (
            DockerImageType,
        )

        # Map service names to image types
        for service in services:
            image_tag = dep_service.get_service_image_tag(service)
            if not image_tag:
                continue

            # Extract image type from tag (e.g., "aidb-test-python:latest" -> "python")
            if "aidb-test-" in image_tag:
                image_type = image_tag.split("aidb-test-")[1].split(":")[0]
                if image_type in DockerImageType.all_images():
                    checksum_service.mark_built(image_type)
                    logger.debug("Marked %s image as built", image_type)

    def _report_rebuild_status(
        self,
        checksum_service: DockerImageChecksumService,
    ) -> None:
        """Report rebuild status for all images.

        Parameters
        ----------
        checksum_service : DockerImageChecksumService
            Checksum service instance
        """
        from aidb_cli.core.constants import Icons
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Docker Image Rebuild Status", Icons.INFO)

        status_map = checksum_service.check_all_images()

        for image_type, (needs_rebuild, reason) in status_map.items():
            image_name = f"aidb-test-{image_type}:latest"
            if needs_rebuild:
                CliOutput.warning(f"  {image_name:<35} - needs rebuild")
                CliOutput.plain(f"    Reason: {reason}")
            else:
                CliOutput.success(f"  {image_name:<35} - {reason}")
