"""Docker Compose command execution.

Provides centralized execution of docker-compose commands with proper environment
variable management and consistent logging.
"""

import subprocess  # Required for type hints
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.common.errors import AidbError
from aidb_cli.core.paths import DockerConstants
from aidb_logging import DEBUG, get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerComposeExecutor:
    """Centralized executor for all docker-compose commands.

    Uses pre-resolved environment from centralized EnvironmentManager and focuses solely
    on command execution.
    """

    def __init__(
        self,
        compose_file: Path,
        environment: dict[str, str],
        project_name: str = DockerConstants.DEFAULT_PROJECT,
        command_executor: Optional["CommandExecutor"] = None,
        env_file: Path | None = None,
    ):
        """Initialize the executor.

        Parameters
        ----------
        compose_file : Path
            Path to docker-compose.yaml file
        environment : dict[str, str]
            Pre-resolved environment variables from centralized EnvironmentManager
        project_name : str
            Docker compose project name
        command_executor : CommandExecutor, optional
            Command executor instance
        env_file : Path, optional
            Path to .env file for docker compose build args (e.g., PYTHON_TAG)
        """
        self.compose_file = compose_file
        self.project_name = project_name
        self.repo_root = compose_file.parent.parent.parent
        self.base_environment = environment.copy()
        self._command_executor = command_executor
        self.env_file = env_file

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

            # Pass Click context if present so streaming honors -v/-vvv
            click_ctx = None
            try:
                import click

                click_ctx = click.get_current_context(silent=True)
            except Exception:
                click_ctx = None
            self._command_executor = CommandExecutor(ctx=click_ctx)
        return self._command_executor

    def execute(
        self,
        args: list[str],
        profile: str | list[str] | None = None,
        capture_output: bool = True,
        extra_env: dict[str, str] | None = None,
        **kwargs,
    ) -> "subprocess.CompletedProcess":
        """Execute a docker-compose command.

        Parameters
        ----------
        args : list[str]
            Docker compose arguments (e.g., ["up", "-d", "service"])
        profile : str, optional
            Docker compose profile to use
        capture_output : bool
            Whether to capture output
        extra_env : dict, optional
            Additional environment variables for this command only
        **kwargs
            Additional arguments for self.command_executor.execute

        Returns
        -------
        CompletedProcess
            Result of the command execution
        """
        cmd = self._build_command(args, profile)

        # Start with base environment and merge extra vars
        env = self.base_environment.copy()
        if extra_env:
            env.update(extra_env)
            logger.debug(
                "Applied extra environment variables: %s",
                list(extra_env.keys()),
            )

        logger.debug("Executing: %s", " ".join(cmd))
        if logger.isEnabledFor(DEBUG):
            self._debug_environment(env)

        return self.command_executor.execute(
            cmd,
            env=env,
            capture_output=capture_output,
            cwd=self.repo_root,
            **kwargs,
        )

    def execute_streaming(
        self,
        args: list[str],
        profile: str | list[str] | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Execute with streaming output.

        Parameters
        ----------
        args : list[str]
            Docker compose arguments
        profile : str, optional
            Docker compose profile to use
        extra_env : dict, optional
            Additional environment variables
        **kwargs
            Additional arguments for subprocess.Popen

        Returns
        -------
        subprocess.Popen
            Process handle for streaming
        """
        cmd = self._build_command(args, profile)

        # Start with base environment and merge extra vars
        env = self.base_environment.copy()
        if extra_env:
            env.update(extra_env)
            logger.debug(
                "Applied extra environment variables: %s",
                list(extra_env.keys()),
            )

        logger.debug("Streaming: %s", " ".join(cmd))
        if logger.isEnabledFor(DEBUG):
            self._debug_environment(env)

        return self.command_executor.create_process(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.repo_root,
            text=True,
            bufsize=1,
            **kwargs,
        )

    def _build_command(
        self,
        args: list[str],
        profile: str | list[str] | None,
    ) -> list[str]:
        """Build the complete docker-compose command."""
        import os

        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
        ]

        # Add env file if specified (for build args like PYTHON_TAG)
        if self.env_file and self.env_file.exists():
            cmd.extend(["--env-file", str(self.env_file)])

        cmd.extend(["--project-name", self.project_name])

        if profile:
            if isinstance(profile, list):
                for p in profile:
                    cmd.extend(["--profile", p])
            else:
                cmd.extend(["--profile", profile])

        cmd.extend(args)

        # In CI (GITHUB_ACTIONS=true), add --no-build to 'up' commands
        # to use pre-pulled images instead of rebuilding
        if os.environ.get("GITHUB_ACTIONS") == "true" and "up" in args:
            up_idx = cmd.index("up")
            cmd.insert(up_idx + 1, "--no-build")
            logger.debug("CI detected: added --no-build to use pre-pulled images")

        return cmd

    def get_running_services(self) -> list[str]:
        """Get list of currently running Docker Compose services.

        Returns
        -------
        list[str]
            Names of running services
        """
        try:
            result = self.execute(
                ["ps", "--services", "--filter", "status=running"],
                capture_output=True,
                check=True,
            )
            return [
                line.strip()
                for line in result.stdout.strip().split("\n")
                if line.strip()
            ]
        except AidbError:
            logger.debug("No running services found or docker-compose ps failed")
            return []

    def get_service_port(self, service: str, internal_port: str = "8000") -> str | None:
        """Get the mapped external port for a service's internal port.

        Parameters
        ----------
        service : str
            Service name
        internal_port : str
            Internal port to query

        Returns
        -------
        str | None
            External port if found, None otherwise
        """
        try:
            result = self.execute(
                ["port", service, internal_port],
                capture_output=True,
                check=True,
            )
            port_line = result.stdout.strip()
            if port_line and ":" in port_line:
                return port_line.split(":")[-1]
            return None
        except AidbError:
            logger.debug("Failed to get port mapping for %s:%s", service, internal_port)
            return None

    def build(
        self,
        extra_env: dict[str, str] | None = None,
    ) -> "subprocess.CompletedProcess":
        """Build Docker Compose services.

        Parameters
        ----------
        extra_env : dict, optional
            Additional environment variables

        Returns
        -------
        CompletedProcess
            Result of the build command
        """
        return self.execute(["build"], extra_env=extra_env)

    def up(
        self,
        services: list[str] | None = None,
        detach: bool = True,
        extra_env: dict[str, str] | None = None,
        capture_output: bool = True,
        **kwargs,
    ) -> "subprocess.CompletedProcess":
        """Start Docker Compose services.

        Parameters
        ----------
        services : list[str], optional
            Specific services to start (all if None)
        detach : bool
            Run in detached mode
        extra_env : dict, optional
            Additional environment variables
        capture_output : bool
            Whether to capture output
        **kwargs
            Additional arguments for self.command_executor.execute

        Returns
        -------
        CompletedProcess
            Result of the up command
        """
        args = ["up"]
        if detach:
            args.append("-d")
        if services:
            args.extend(services)
        return self.execute(
            args,
            extra_env=extra_env,
            capture_output=capture_output,
            **kwargs,
        )

    def down(
        self,
        remove_volumes: bool = False,
        timeout: int | None = None,
    ) -> "subprocess.CompletedProcess":
        """Stop and remove Docker Compose services.

        Parameters
        ----------
        remove_volumes : bool
            Whether to remove volumes
        timeout : int, optional
            Timeout in seconds for stopping containers

        Returns
        -------
        CompletedProcess
            Result of the down command
        """
        args = ["down", "--remove-orphans"]
        if remove_volumes:
            args.append("-v")
        if timeout is not None:
            args.extend(["--timeout", str(timeout)])
        return self.execute(args)

    def run_service(
        self,
        service: str,
        remove: bool = True,
        extra_env: dict[str, str] | None = None,
        command: list[str] | None = None,
        capture_output: bool = True,
        **kwargs,
    ) -> "subprocess.CompletedProcess":
        """Run a one-off command in a service.

        Parameters
        ----------
        service : str
            Service to run
        remove : bool
            Remove container after run
        extra_env : dict, optional
            Additional environment variables
        command : list[str], optional
            Command to run in service
        capture_output : bool
            Whether to capture output
        **kwargs
            Additional arguments for self.command_executor.execute

        Returns
        -------
        CompletedProcess
            Result of the run command
        """
        args = ["run"]
        if remove:
            args.append("--rm")
        args.append(service)
        if command:
            args.extend(command)
        return self.execute(
            args,
            extra_env=extra_env,
            capture_output=capture_output,
            **kwargs,
        )

    def _debug_environment(self, env: dict[str, str]) -> None:
        """Debug log environment variables for Docker execution."""
        lines = ["Docker Compose Environment:"]
        lines.append(f"  Total variables: {len(env)}")

        # Show relevant environment variable groups
        prefixes = ["AIDB_", "TEST_", "PYTEST_", "COMPOSE_", "DOCKER_"]
        for prefix in prefixes:
            prefix_vars = {k: v for k, v in env.items() if k.startswith(prefix)}
            if prefix_vars:
                lines.append(f"  {prefix}* variables: {len(prefix_vars)}")
                for key in sorted(prefix_vars.keys()):
                    value = prefix_vars[key]
                    # Mask sensitive values
                    if any(s in key for s in ["SECRET", "KEY", "TOKEN", "WEBHOOK"]):
                        masked = f"{value[:10]}..." if len(value) > 10 else "***"
                    else:
                        masked = value
                    lines.append(f"    {key}={masked}")

        # Always show REPO_ROOT
        if "REPO_ROOT" in env:
            lines.append(f"  REPO_ROOT={env['REPO_ROOT']}")

        debug_output = "\n".join(lines)
        logger.debug(debug_output)
