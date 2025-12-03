"""Service for building adapters and managing ACT containers."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.core.paths import CachePaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_cli.services.docker.docker_cleanup_service import DockerCleanupService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class AdapterBuildService(BaseService):
    """Service for building adapters and managing ACT containers.

    This service handles:
    - Building adapters locally via ACT
    - Finding ACT containers
    - Cleaning up ACT containers
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the adapter build service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)

    def build_locally(  # noqa: C901
        self,
        languages: list[str],
        verbose: bool = False,
        resolved_env: dict[str, str] | None = None,
    ) -> bool:
        """Build adapters locally using act to run GitHub Actions workflow.

        All adapters are built in parallel via a single act invocation that
        triggers the workflow's matrix strategy.

        Parameters
        ----------
        languages : list[str]
            Languages to build adapters for
        verbose : bool, optional
            Whether to show verbose output
        resolved_env : dict[str, str] | None, optional
            Resolved environment variables from centralized manager

        Returns
        -------
        bool
            True if all builds succeeded
        """
        workflow_file = (
            self.repo_root / ".github" / "workflows" / "adapter-build-act.yaml"
        )

        if not workflow_file.exists():
            self.log_error("Build workflow not found: %s", workflow_file)
            CliOutput.error(f"Build workflow not found: {workflow_file}")
            return False

        if not self._check_act_installed():
            return False

        # Build all adapters in parallel via a single act invocation
        adapters_input = ",".join(languages)

        if verbose:
            lang_list = ", ".join(languages)
            CliOutput.info(f"Building adapters in parallel: {lang_list}")

        cmd = [
            "act",
            "--actrc",
            str(self.repo_root / ".github" / "actrc"),
            "workflow_dispatch",
            "-W",
            str(workflow_file),
            "--input",
            f"adapters={adapters_input}",
        ]

        if verbose:
            CliOutput.info(f"Running: {' '.join(cmd)}")

        try:
            # Use resolved environment if provided (contains AIDB_* vars)
            # This allows centralized environment management
            env = resolved_env if resolved_env else None

            # For verbose mode, pass through act's rich output directly without
            # rolling-window streaming to avoid overlapping UI artifacts
            result = self.command_executor.execute(
                cmd,
                cwd=self.repo_root,
                capture_output=not verbose,
                check=False,
                env=env,
                passthrough_no_stream=verbose,
            )

            build_succeeded = result.returncode == 0

            if not build_succeeded:
                if not verbose:
                    # Show only the tail of the output to keep console readable
                    err = (result.stderr or "").splitlines()
                    tail = "\n".join(err[-40:]) if err else ""
                    if tail:
                        CliOutput.error(f"Build failed (last 40 lines):\n{tail}")
                    else:
                        CliOutput.error("Build failed")
                    logger.debug("Full build stderr length: %s lines", len(err))
                else:
                    CliOutput.error("Build failed")

        except (OSError, subprocess.SubprocessError) as e:
            self.log_error("Build failed: %s", str(e))
            CliOutput.error(f"Build failed: {e}")
            return False

        if verbose:
            CliOutput.info("Extracting artifacts from ACT containers...")
        extracted = self.extract_artifacts_from_containers(verbose=verbose)
        if verbose:
            if extracted > 0:
                CliOutput.success(f"Extracted artifacts from {extracted} container(s)")
            else:
                CliOutput.warning("No artifacts extracted from containers")

        if verbose:
            CliOutput.info("Cleaning up ACT containers...")
        cleaned = self.cleanup_act_containers(verbose=verbose)
        if verbose and cleaned > 0:
            CliOutput.success(f"Cleaned up {cleaned} ACT container(s)")

        if build_succeeded:
            CliOutput.success(
                f"Successfully built all {len(languages)} adapter(s)",
            )
            return True

        CliOutput.error("Failed to build adapters")
        return False

    def find_act_containers(self) -> list[dict[str, Any]]:
        """Find ACT containers by name pattern.

        Returns
        -------
        list[dict[str, Any]]
            List of ACT container information dictionaries
        """
        try:
            result = self.command_executor.execute(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    "name=act-Build-Debug-Adapters",
                    "--format",
                    "{{json .}}",
                ],
                capture_output=True,
                check=True,
            )

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    container = json.loads(line)
                    containers.append(container)

            return containers

        except Exception as e:
            logger.debug("Failed to find ACT containers: %s", str(e))
            return []

    def extract_artifacts_from_containers(self, verbose: bool = False) -> int:  # noqa: C901
        """Extract build artifacts from ACT containers to host.

        ACT containers don't automatically sync files to the host filesystem,
        so we need to manually copy artifacts using docker cp.

        Parameters
        ----------
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        int
            Number of containers artifacts were extracted from
        """
        containers = self.find_act_containers()

        if not containers:
            if verbose:
                CliOutput.info("No ACT containers found to extract artifacts from")
            return 0

        cache_dir = CachePaths.repo_cache(self.repo_root)
        cache_dir.mkdir(parents=True, exist_ok=True)

        extracted_count = 0

        for container in containers:
            container_id = container.get("ID", "")
            container_name = container.get("Names", container_id)

            # Parse language from container name (e.g., "act-...Build-python-...")
            # Container names: act-Build-Debug-Adapters-...-Build-{language}-...
            language = self._parse_language_from_container_name(container_name)
            if language:
                language_cache_dir = cache_dir / language
                if language_cache_dir.exists():
                    if verbose:
                        CliOutput.info(
                            f"Cleaning existing {language} cache before extraction...",
                        )
                    try:
                        shutil.rmtree(language_cache_dir)
                    except Exception as e:
                        logger.debug(
                            "Failed to clean %s cache: %s",
                            language,
                            str(e),
                        )

            if verbose:
                CliOutput.info(f"Extracting from {container_name[:50]}...")

            try:
                cache_path_str = str(CachePaths.repo_cache(self.repo_root))
                result = self.command_executor.execute(
                    [
                        "docker",
                        "cp",
                        f"{container_id}:{cache_path_str}/.",
                        str(cache_dir),
                    ],
                    capture_output=True,
                    check=False,
                )

                if result.returncode == 0:
                    extracted_count += 1
                    if verbose:
                        short_name = container_name[:50]
                        CliOutput.success(f"Extracted artifacts from {short_name}")
                else:
                    no_file = "no such file" not in result.stderr.lower()
                    if verbose and result.stderr and no_file:
                        short_name = container_name[:50]
                        CliOutput.warning(f"No artifacts found in {short_name}")

            except Exception as e:
                logger.debug(
                    "Failed to extract from container %s: %s",
                    container_id,
                    str(e),
                )
                if verbose:
                    short_name = container_name[:50]
                    CliOutput.warning(f"Could not extract from {short_name}: {e}")

        return extracted_count

    def cleanup_act_containers(self, verbose: bool = False) -> int:
        """Cleanup ACT containers from adapter builds.

        Parameters
        ----------
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        int
            Number of containers cleaned up
        """
        containers = self.find_act_containers()

        if not containers:
            if verbose:
                CliOutput.info("No ACT containers found to cleanup")
            return 0

        if verbose:
            CliOutput.info(f"Found {len(containers)} ACT container(s) to cleanup")

        cleanup_service = DockerCleanupService(self.command_executor)
        results = cleanup_service.cleanup_resources({"containers": containers})

        success_count = len(results["containers"]["success"])
        failed_count = len(results["containers"]["failed"])

        if verbose:
            if success_count > 0:
                CliOutput.success(f"Cleaned up {success_count} ACT container(s)")
            if failed_count > 0:
                CliOutput.warning(f"Failed to cleanup {failed_count} ACT container(s)")

        return success_count

    def _check_act_installed(self) -> bool:
        """Check if act is installed.

        Returns
        -------
        bool
            True if act is installed
        """
        try:
            result = self.command_executor.execute(
                ["which", "act"],
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                CliOutput.error(
                    "'act' not found. Install from: https://github.com/nektos/act",
                )
                return False
            return True
        except (OSError, subprocess.SubprocessError):
            CliOutput.error(
                "'act' not found. Install from: https://github.com/nektos/act",
            )
            return False

    def _parse_language_from_container_name(self, container_name: str) -> str | None:
        """Parse language from ACT container name.

        Container names follow pattern:
        act-Build-Debug-Adapters-build-adapters-Build-{language}-...

        Parameters
        ----------
        container_name : str
            Container name from docker ps

        Returns
        -------
        str | None
            Language name (python, javascript, java) or None if not found
        """
        supported_languages = ["python", "javascript", "java"]

        # Look for pattern "Build-{language}" in container name
        for lang in supported_languages:
            if f"Build-{lang}" in container_name or f"build-{lang}" in container_name:
                return lang

        # Fallback: check if language name appears anywhere in the name
        for lang in supported_languages:
            if lang in container_name.lower():
                return lang

        return None

    def cleanup(self) -> None:
        """Cleanup service resources."""
