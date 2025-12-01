"""Core command execution service."""

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import ExitCode
from aidb_logging import get_cli_logger

from .environment_service import EnvironmentService

logger = get_cli_logger(__name__)


class ExecutionService:
    """Core service for command execution.

    This service handles the actual subprocess execution with proper error handling and
    environment setup.
    """

    def __init__(self, ctx: Optional["click.Context"] = None) -> None:
        """Initialize the execution service.

        Parameters
        ----------
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        """
        self.ctx = ctx
        self._env_service = EnvironmentService(ctx)
        # Use centralized environment if available
        if ctx and hasattr(ctx.obj, "resolved_env"):
            self._env = ctx.obj.resolved_env
        else:
            self._env = None

    def execute(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
        timeout: float | None = None,
        check: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        r"""Execute a command with the given parameters.

        Parameters
        ----------
        cmd : list[str]
            Command to execute
        cwd : Path | None, optional
            Working directory
        env : dict[str, str] | None, optional
            Environment variables to add/override
        capture_output : bool, optional
            Whether to capture output
        timeout : float | None, optional
            Timeout in seconds
        check : bool, optional
            Whether to raise exception on failure
        **kwargs : Any
            Additional arguments passed to subprocess.run

        Returns
        -------
        subprocess.CompletedProcess[str]
            Result of command execution

        Raises
        ------
        AidbError
            If command fails and check=True
        """
        # Build environment
        logger.debug("Executing command: %s", " ".join(cmd))
        if cwd:
            logger.debug("Working directory: %s", cwd)

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                check=False,
                **kwargs,
            )

            if check and result.returncode != 0:
                error_msg = f"Command failed with exit code {result.returncode}: {' '.join(cmd)}"
                if result.stderr:
                    error_msg += f"\nError output: {result.stderr}"
                logger.error(error_msg)
                raise AidbError(error_msg)

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
            logger.error(error_msg)
            if check:
                raise AidbError(error_msg) from e
            return subprocess.CompletedProcess(
                cmd,
                ExitCode.TIMEOUT,
                "",
                str(e),
            )

        except FileNotFoundError as e:
            error_msg = f"Command not found: {cmd[0]}"
            logger.error(error_msg)
            if check:
                raise AidbError(error_msg) from e
            return subprocess.CompletedProcess(
                cmd,
                ExitCode.NOT_FOUND,
                "",
                str(e),
            )

    def create_process(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs: Any,
    ) -> subprocess.Popen:
        r"""Create a subprocess.Popen for advanced streaming scenarios.

        Parameters
        ----------
        cmd : list[str]
            Command to execute
        cwd : Path | None, optional
            Working directory
        env : dict[str, str] | None, optional
            Environment variables to add/override
        stdout : Any
            stdout handling (default: subprocess.PIPE)
        stderr : Any
            stderr handling (default: subprocess.PIPE)
        **kwargs : Any
            Additional arguments passed to subprocess.Popen

        Returns
        -------
        subprocess.Popen
            The created process object

        Raises
        ------
        AidbError
            If command cannot be found
        """
        # Build environment
        command_env = self._env_service.build_environment(env)

        logger.debug("Creating process: %s", " ".join(cmd))
        if cwd:
            logger.debug("Working directory: %s", cwd)

        try:
            return subprocess.Popen(
                cmd,
                cwd=cwd,
                env=command_env,
                stdout=stdout,
                stderr=stderr,
                **kwargs,
            )
        except FileNotFoundError as e:
            error_msg = f"Command not found: {cmd[0]}"
            logger.error(error_msg)
            raise AidbError(error_msg) from e

    def _is_ci_environment(self) -> bool:
        """Detect if running in CI/CD environment.

        Returns
        -------
        bool
            True if CI environment detected
        """
        ci_env_vars = [
            "CI",  # Generic CI indicator
            "GITHUB_ACTIONS",  # GitHub Actions
            "GITLAB_CI",  # GitLab CI
            "JENKINS_HOME",  # Jenkins
            "CIRCLECI",  # CircleCI
            "TRAVIS",  # Travis CI
            "BUILDKITE",  # Buildkite
            "DRONE",  # Drone
            "TEAMCITY_VERSION",  # TeamCity
            "TF_BUILD",  # Azure DevOps
        ]

        # Use centralized environment if available, otherwise fall back to os.environ
        env_to_check = self._env if self._env else os.environ

        for var in ci_env_vars:
            if env_to_check.get(var):
                return True

        # Additional GitHub Actions specific check
        return bool(env_to_check.get("GITHUB_WORKFLOW"))
