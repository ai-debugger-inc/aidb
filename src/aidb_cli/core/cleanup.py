"""Resource cleanup utilities for test environments.

Ensures proper cleanup of Docker resources, temporary files, and test artifacts.
"""

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import click

    from aidb_cli.services import CommandExecutor

from aidb_cli.core.constants import ProjectNames
from aidb_cli.core.paths import ProjectPaths
from aidb_cli.core.utils import CliOutput
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class ResourceCleaner:
    """Manages cleanup of test resources."""

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: Optional["click.Context"] = None,
    ) -> None:
        """Initialize resource cleaner.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor, optional
            Command executor for subprocess calls
        ctx : click.Context, optional
            CLI context for accessing centralized environment
        """
        self.repo_root = repo_root
        self.docker_compose_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
        self.cleanup_actions: list[str] = []
        self._command_executor = command_executor
        self.ctx = ctx

    @property
    def command_executor(self) -> "CommandExecutor":
        """Get command executor instance, creating if necessary.

        Returns
        -------
        CommandExecutor
            Command executor instance
        """
        if self._command_executor is None:
            from aidb_cli.services import CommandExecutor

            # Use Click context if available to ensure consistent streaming behavior
            click_ctx = None
            try:
                import click

                click_ctx = click.get_current_context(silent=True)
            except Exception:
                click_ctx = None
            ctx_to_use = self.ctx if self.ctx is not None else click_ctx
            self._command_executor = CommandExecutor(ctx=ctx_to_use)
        return self._command_executor

    def cleanup_docker_resources(
        self,
        profile: str | None = None,
        remove_volumes: bool = True,
        remove_networks: bool = True,
        remove_images: bool = False,
    ) -> bool:
        """Clean up Docker resources created during testing.

        Parameters
        ----------
        profile : str, optional
            Docker compose profile to clean up
        remove_volumes : bool
            Whether to remove volumes
        remove_networks : bool
            Whether to remove networks
        remove_images : bool
            Whether to remove images

        Returns
        -------
        bool
            True if cleanup successful
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.process("Cleaning up Docker resources...")

        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.docker_compose_file),
        ]

        if profile:
            cmd.extend(["--profile", profile])

        cmd.extend(["down", "--remove-orphans"])

        if remove_volumes:
            cmd.append("-v")

        result = self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
        )

        if result.returncode != 0:
            CliOutput.error(f"Failed to clean up containers: {result.stderr}")
            return False

        self.cleanup_actions.append("Stopped and removed containers")

        if remove_volumes:
            self._cleanup_dangling_volumes()

        if remove_networks:
            # Force stop any remaining containers before network cleanup
            self._stop_aidb_containers()
            self._cleanup_test_networks()

        if remove_images:
            self._cleanup_test_images()

        CliOutput.success("Docker cleanup complete")
        return True

    def _cleanup_dangling_volumes(self) -> None:
        """Remove dangling Docker volumes."""
        cmd = ["docker", "volume", "ls", "-q", "--filter", "dangling=true"]
        result = self.command_executor.execute(cmd, capture_output=True)

        if result.returncode == 0 and result.stdout.strip():
            volumes = result.stdout.strip().split("\n")
            for volume in volumes:
                if "aidb" in volume:  # Only clean AIDB-related volumes
                    self.command_executor.execute(
                        ["docker", "volume", "rm", volume],
                        capture_output=True,
                    )
                    logger.debug("Removed volume: %s", volume)

            self.cleanup_actions.append(f"Removed {len(volumes)} dangling volumes")

    def _cleanup_test_networks(self) -> None:
        """Remove test-specific Docker networks."""
        cmd = ["docker", "network", "ls", "--format", "{{.Name}}"]
        result = self.command_executor.execute(cmd, capture_output=True)

        if result.returncode == 0:
            networks = result.stdout.strip().split("\n")
            for network in networks:
                if ProjectNames.TEST_PROJECT in network:
                    # Try to remove network, ignore errors if it has active endpoints
                    remove_result = self.command_executor.execute(
                        ["docker", "network", "rm", network],
                        capture_output=True,
                        check=False,  # Don't raise on error
                    )
                    if remove_result.returncode == 0:
                        logger.debug("Removed network: %s", network)
                        self.cleanup_actions.append(f"Removed network: {network}")
                    else:
                        logger.debug(
                            "Could not remove network %s: %s",
                            network,
                            remove_result.stderr,
                        )

    def _stop_aidb_containers(self) -> None:
        """Force stop and remove all AIDB-managed containers (running or exited)."""
        cmd = ["docker", "ps", "-aq", "--filter", "label=com.aidb.managed=true"]
        result = self.command_executor.execute(cmd, capture_output=True)

        if result.returncode == 0 and result.stdout.strip():
            container_ids = result.stdout.strip().split("\n")
            for container_id in container_ids:
                # Force stop the container
                self.command_executor.execute(
                    ["docker", "stop", "--time=1", container_id],
                    capture_output=True,
                    check=False,
                )
                # Force remove the container
                self.command_executor.execute(
                    ["docker", "rm", "--force", container_id],
                    capture_output=True,
                    check=False,
                )
            logger.debug("Force stopped %d AIDB containers", len(container_ids))

    def _cleanup_test_images(self) -> None:
        """Remove test-specific Docker images."""
        cmd = [
            "docker",
            "images",
            "--format",
            "{{.Repository}}:{{.Tag}}",
            "--filter",
            "label=com.aidb.managed=true",
        ]
        result = self.command_executor.execute(cmd, capture_output=True)

        if result.returncode == 0 and result.stdout.strip():
            images = result.stdout.strip().split("\n")
            for image in images:
                self.command_executor.execute(
                    ["docker", "rmi", image],
                    capture_output=True,
                )
                logger.debug("Removed image: %s", image)

            self.cleanup_actions.append(f"Removed {len(images)} test images")

    def cleanup_test_artifacts(
        self,
        clean_cache: bool = False,
        clean_coverage: bool = False,
        clean_logs: bool = False,
    ) -> bool:
        """Clean up test artifacts from the filesystem.

        Parameters
        ----------
        clean_cache : bool
            Whether to clean pytest cache
        clean_coverage : bool
            Whether to clean coverage data
        clean_logs : bool
            Whether to clean log files

        Returns
        -------
        bool
            True if cleanup successful
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.process("Cleaning up test artifacts...")

        if clean_cache:
            pytest_cache = self.repo_root / ".pytest_cache"
            if pytest_cache.exists():
                shutil.rmtree(pytest_cache)
                self.cleanup_actions.append("Removed pytest cache")
                logger.debug("Removed pytest cache")

        if clean_coverage:
            coverage_file = self.repo_root / ".coverage"
            if coverage_file.exists():
                coverage_file.unlink()
                self.cleanup_actions.append("Removed coverage data")

            htmlcov = self.repo_root / "htmlcov"
            if htmlcov.exists():
                shutil.rmtree(htmlcov)
                self.cleanup_actions.append("Removed HTML coverage report")

        if clean_logs:
            log_patterns = [
                "*.log",
                "test-*.txt",
                f"{ProjectNames.TEST_PROJECT}-*.log",
            ]

            for pattern in log_patterns:
                for log_file in self.repo_root.glob(pattern):
                    log_file.unlink()
                    logger.debug("Removed log file: %s", log_file)

            self.cleanup_actions.append("Removed log files")

        CliOutput.success("Artifact cleanup complete")
        return True

    def cleanup_temp_files(self) -> bool:
        """Clean up temporary files created during testing.

        Returns
        -------
        bool
            True if cleanup successful
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.process("Cleaning up temporary files...")

        temp_dirs = [
            self.repo_root / "tmp",
            self.repo_root / ".tmp",
            Path(tempfile.gettempdir()) / ProjectNames.TEST_PROJECT,
        ]

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    self.cleanup_actions.append(f"Removed {temp_dir}")
                    logger.debug("Removed temp directory: %s", temp_dir)
                except (OSError, shutil.Error) as e:
                    logger.warning("Failed to remove %s: %s", temp_dir, e)

        return True

    def full_cleanup(self, force: bool = False) -> bool:
        """Perform full cleanup of all test resources.

        Parameters
        ----------
        force : bool
            Whether to force cleanup even if tests are running

        Returns
        -------
        bool
            True if cleanup successful
        """
        if not force:
            result = self.command_executor.execute(
                ["docker", "ps", "--filter", "label=com.aidb.managed=true", "-q"],
                capture_output=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                CliOutput.warning(
                    "Tests appear to be running. Use --force to clean anyway.",
                )
                return False

        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.process("Starting full cleanup...")

        self.cleanup_docker_resources(
            remove_volumes=True,
            remove_networks=True,
            remove_images=force,
        )

        self.cleanup_test_artifacts(
            clean_cache=True,
            clean_coverage=True,
            clean_logs=True,
        )

        self.cleanup_temp_files()

        if self.cleanup_actions:
            HeadingFormatter.section("Cleanup Summary")
            for action in self.cleanup_actions:
                CliOutput.info(f"  • {action}")

        CliOutput.success("\nFull cleanup complete!")
        return True

    def register_cleanup_handler(self) -> None:
        """Register cleanup handler for graceful shutdown."""
        import atexit
        import signal

        def cleanup_handler(signum=None, frame=None):  # noqa: ARG001
            """Handle cleanup on exit or signal."""
            logger.info("Running cleanup handler...")
            self.cleanup_docker_resources()

        atexit.register(cleanup_handler)

        signal.signal(signal.SIGTERM, cleanup_handler)
        signal.signal(signal.SIGINT, cleanup_handler)
