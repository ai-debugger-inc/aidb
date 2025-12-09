"""Service for test execution and process management."""

import contextlib
import shlex
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

from aidb_cli.core.constants import (
    PROCESS_WAIT_TIMEOUT_S,
    STREAM_WINDOW_SIZE,
    Icons,
)
from aidb_cli.core.paths import DockerConstants, ProjectPaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_cli.services.command_executor import StreamHandler
from aidb_cli.services.docker.docker_build_service import DockerBuildService
from aidb_cli.services.test.pytest_logging_service import PytestLoggingService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestExecutionService(BaseService):
    """Service for executing tests and managing test processes.

    This service handles:
    - Building Docker commands for test execution
    - Running test processes
    - Managing test environment variables
    - Handling test execution modes (local vs Docker)
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: Optional["click.Context"] = None,
        skip_session_logging: bool = False,
    ) -> None:
        """Initialize the test execution service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        skip_session_logging : bool, optional
            If True, skip session-isolated logging (useful for unit tests)
        """
        super().__init__(repo_root, command_executor, ctx)
        self.compose_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
        self.pytest_logging = PytestLoggingService(
            repo_root,
            command_executor,
            ctx,
            skip_session_logging=skip_session_logging,
        )
        self._current_session_dir: Path | None = None
        self._current_session_id: str | None = None
        self._current_session_timestamp: str | None = None

    @property
    def current_session_id(self) -> str | None:
        """Get the current test session ID.

        Returns
        -------
        str | None
            Current session ID, or None if no session has been started
        """
        return self._current_session_id

    @property
    def current_session_timestamp(self) -> str | None:
        """Get the current test session timestamp.

        Returns
        -------
        str | None
            Current session timestamp (YYYYMMDD-HHMMSS), or None if no
            session has been started
        """
        return self._current_session_timestamp

    def _log_environment_debug_info(self, full_env: dict[str, str]) -> None:
        """Log debug information about environment variables.

        Parameters
        ----------
        full_env : dict[str, str]
            Complete environment dictionary
        """
        logger.debug("Docker environment variables being passed:")
        logger.debug("  REPO_ROOT=%s", full_env.get("REPO_ROOT", "NOT_SET"))
        logger.debug("  TEST_SUITE=%s", full_env.get("TEST_SUITE", "NOT_SET"))
        logger.debug("  TEST_LANGUAGE=%s", full_env.get("TEST_LANGUAGE", "NOT_SET"))
        logger.debug("  TEST_PATTERN=%s", full_env.get("TEST_PATTERN", "NOT_SET"))
        logger.debug("  PYTEST_ADDOPTS=%s", full_env.get("PYTEST_ADDOPTS", "NOT_SET"))

        # Log all AIDB_ and TEST_ prefixed environment variables
        aidb_vars = {
            k: v for k, v in full_env.items() if k.startswith(("AIDB_", "TEST_"))
        }
        if aidb_vars:
            logger.debug("  AIDB/TEST variables: %s", list(aidb_vars.keys()))

        # Log important Docker-related variables
        docker_vars = ["COMPOSE_PROJECT_NAME", "DOCKER_HOST", "PATH"]
        for var in docker_vars:
            if var in full_env:
                logger.debug("  %s=%s", var, full_env[var])

        logger.debug("  Total environment variables: %s", len(full_env))

    def _start_log_streaming(self, container_name: str) -> subprocess.Popen | None:
        """Start streaming logs from container with real-time persistence.

        NOTE: This method is ONLY used for containerized test execution.
        Local tests don't call this, so test-container-output.log will be
        empty for local test runs. This is expected and not an error.
        For local tests, see {repo_root}/pytest-logs/test-results.log instead.

        Streams container logs to both terminal (stdout) and log file
        (~/.aidb/log/test-container-output.log) in real-time. This ensures logs are
        preserved even if the container is killed or removed before
        cleanup can collect them.

        Parameters
        ----------
        container_name : str
            Name of the container to stream logs from

        Returns
        -------
        subprocess.Popen | None
            Log streaming process or None if failed
        """
        from aidb_logging.utils import get_log_file_path

        logs_cmd = ["docker", "logs", "-f", container_name]
        try:
            # Capture output so we can tee to both terminal and file
            logs_process = subprocess.Popen(  # noqa: S603
                logs_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered for real-time output
            )

            # Thread to read and tee output to both terminal and log file
            def stream_and_persist():
                """Read container logs and write to both terminal and file."""
                try:
                    log_file = Path(get_log_file_path("test-container-output"))
                    with log_file.open("a", encoding="utf-8") as f:
                        # Write header to log file
                        f.write(f"\n{'=' * 80}\n")
                        f.write(f"Container: {container_name}\n")
                        f.write(f"{'=' * 80}\n")
                        f.flush()

                        # Stream each line to both destinations
                        if logs_process.stdout:
                            for line in logs_process.stdout:
                                # Write to terminal (respects shell redirection)
                                sys.stdout.write(line)
                                sys.stdout.flush()
                                # Write to log file (persistent)
                                f.write(line)
                                f.flush()
                except Exception as e:
                    logger.warning(
                        "Error during log streaming for %s: %s",
                        container_name,
                        e,
                    )

            # Start streaming thread
            thread = threading.Thread(
                target=stream_and_persist,
                daemon=True,
                name=f"LogStream-{container_name}",
            )
            thread.start()

            logger.debug(
                "Started log streaming with persistence for container %s",
                container_name,
            )
            return logs_process
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("Failed to start log streaming: %s", e)
            return None

    def _get_container_name(self, service: str) -> str:
        """Get the container name for a given service.

        Parameters
        ----------
        service : str
            Service name from docker-compose.yaml

        Returns
        -------
        str
            Container name as defined in docker-compose.yaml
        """
        from aidb_cli.core.paths import DockerConstants
        from aidb_cli.services.docker.service_dependency_service import (
            ServiceDependencyService,
        )

        dep_service = ServiceDependencyService(self.repo_root, self.command_executor)
        dep_service.load_services(self.compose_file)

        container_name = dep_service.get_container_name(service)
        if container_name:
            return container_name

        return f"{DockerConstants.DEFAULT_PROJECT}-{service}-1"

    def _ensure_test_images(
        self,
        profile: str,
        service: str,  # noqa: ARG002
        build: bool,
        verbose: bool,
    ) -> int:
        """Ensure test images are available.

        Uses intelligent rebuild detection to automatically rebuild images
        when source files change, even without the --build flag.

        In CI (IS_GITHUB=true), images are pre-pulled from GHCR, so we
        skip checksum-based rebuild detection and trust the pulled images.
        Note: We use IS_GITHUB (repo variable) instead of GITHUB_ACTIONS
        because we want checksum detection when running with `act` locally.

        Parameters
        ----------
        profile : str
            Docker profile to use
        service : str
            Service to run
        build : bool
            Whether to force rebuild images (overrides checksum detection)
        verbose : bool
            Enable verbose output

        Returns
        -------
        int
            Exit code (0 for success)
        """
        import os

        # In CI (IS_GITHUB=true), images are pre-pulled from GHCR.
        # Skip checksum-based rebuild detection - trust the pulled images.
        # Note: IS_GITHUB is a repo variable that's "true" in real GitHub CI
        # but "false" when using `act` locally. This ensures local `act` runs
        # still use checksum detection for rebuild decisions.
        if os.environ.get("IS_GITHUB") == "true" and not build:
            if verbose:
                CliOutput.info("CI detected: using pre-pulled images")
            return 0

        from aidb_cli.services.docker.docker_image_checksum_service import (
            DockerImageChecksumService,
        )

        build_service = DockerBuildService(
            self.repo_root,
            self.command_executor,
            self.resolved_env,
        )
        checksum_service = DockerImageChecksumService(
            self.repo_root,
            self.command_executor,
        )

        # Check if any images need rebuilding
        rebuild_status = checksum_service.check_all_images()
        needs_rebuild = any(needs for needs, _ in rebuild_status.values())

        if needs_rebuild and not build:
            # Auto-rebuild needed
            CliOutput.info("Detected changes requiring image rebuild")
            if verbose:
                for image_type, (needs, reason) in rebuild_status.items():
                    if needs:
                        CliOutput.plain(f"  {image_type}: {reason}")

        # Build images if needed or requested
        if build or needs_rebuild:
            rc = build_service.build_images(
                profile=profile,
                no_cache=False,
                verbose=verbose,
            )
            if rc != 0:
                return rc
        elif verbose:
            CliOutput.info("Images are up-to-date, skipping build")

        return 0

    def _execute_test_container(
        self,
        run_cmd: list[str],
        full_env: dict[str, str],
        verbose: bool,
        suite: str,
    ) -> None:
        """Execute test container in detached mode.

        Parameters
        ----------
        run_cmd : list[str]
            Docker command to execute
        full_env : dict[str, str]
            Environment variables
        verbose : bool
            Enable verbose output
        suite : str
            Test suite name
        """
        if verbose:
            CliOutput.plain(f"{Icons.TEST} Running tests: {' '.join(run_cmd)}")
        else:
            CliOutput.plain(f"{Icons.TEST} Running {suite} tests...")

        # Force capture_output to avoid interactive streaming window artifacts
        # for docker compose control-plane commands. Live pytest output is
        # streamed via the dedicated docker logs -f tee elsewhere.
        self.command_executor.execute(
            run_cmd,
            cwd=self.repo_root,
            check=False,
            env=full_env,
            capture_output=True,
        )

    def _wait_for_test_completion(
        self,
        service: str,
    ) -> tuple[int, subprocess.Popen | None]:
        """Wait for test container to complete and stream logs.

        Parameters
        ----------
        service : str
            Service name

        Returns
        -------
        tuple[int, subprocess.Popen | None]
            Exit code and log streaming process
        """
        container_name = self._get_container_name(service)
        logs_process = self._start_log_streaming(container_name)

        # Wait for container to finish
        wait_cmd = ["docker", "wait", container_name]
        wait_result = self.command_executor.execute(
            wait_cmd,
            cwd=self.repo_root,
            check=False,
            capture_output=True,
        )

        if wait_result.returncode != 0:
            # If we're aborting due to Ctrl+C, downgrade the noise
            aborting = False
            try:
                if self.ctx and hasattr(self.ctx, "obj"):
                    aborting = bool(getattr(self.ctx.obj, "aborting", False))
            except Exception:
                aborting = False

            if aborting:
                logger.debug(
                    "Aborted while waiting for container %s: %s",
                    container_name,
                    wait_result.stderr,
                )
                CliOutput.info("Aborted while waiting for test container")
            else:
                logger.error(
                    "Failed to wait for container %s: %s",
                    container_name,
                    wait_result.stderr,
                )
                CliOutput.error("Failed to wait for test container", err=True)
            return 1, logs_process

        # Parse exit code
        try:
            exit_code = int(wait_result.stdout.strip())
        except (ValueError, AttributeError) as e:
            logger.error(
                "Failed to parse container exit code from '%s': %s",
                wait_result.stdout,
                e,
            )
            CliOutput.error("Failed to parse test container exit code", err=True)
            return 1, logs_process

        return exit_code, logs_process

    def build_docker_command(
        self,
        profile: str,
        service: str | None = None,
        command: str | None = None,
        env_vars: dict[str, str] | None = None,  # noqa: ARG002
        build: bool = False,
        detach: bool = False,
    ) -> list[str]:
        """Build the docker compose command.

        Parameters
        ----------
        profile : str
            Docker compose profile to use
        service : str, optional
            Specific service to run
        command : str, optional
            Override command for the service
        env_vars : dict[str, str], optional
            Additional environment variables
        build : bool
            Whether to build images
        detach : bool
            Whether to run in detached mode

        Returns
        -------
        list[str]
            Command parts to execute
        """

        cmd = [
            "docker",
            "compose",
            "--project-directory",
            str(self.repo_root),
            "-f",
            str(self.compose_file),
            "--project-name",
            DockerConstants.DEFAULT_PROJECT,
        ]

        # Use the specific profile for the suite (default to base if none provided)
        profile_to_use = profile or "base"
        cmd.extend(["--profile", profile_to_use])

        if build:
            cmd.append("build")
        else:
            cmd.append("up")

            if detach:
                cmd.append("-d")

            if service:
                cmd.append(service)

            # Override command
            if command:
                cmd.extend(["--", command])

        return cmd

    def run_tests(
        self,
        suite: str,
        profile: str,
        env_vars: dict[str, str] | None = None,
        build: bool = False,
        verbose: bool = False,
        centralized_env: dict[str, str] | None = None,
        quiet: bool = False,
    ) -> int:
        """Run tests with specified configuration.

        Parameters
        ----------
        suite : str
            Test suite to run
        profile : str
            Docker profile to use
        env_vars : dict[str, str], optional
            Environment variables for test execution
        build : bool
            Whether to rebuild images
        verbose : bool
            Enable verbose output
        centralized_env : dict[str, str], optional
            Centralized environment from EnvironmentManager
        quiet : bool
            Suppress individual test result messages (for parallel execution)

        Returns
        -------
        int
            Exit code from test execution
        """
        # Determine service based on profile using dynamic discovery
        from aidb_cli.services.docker.service_dependency_service import (
            ServiceDependencyService,
        )

        dep_service = ServiceDependencyService(self.repo_root, self.command_executor)
        dep_service.load_services(self.compose_file)

        # Use profile to find services (profile determines which containers are running)
        profile_services = dep_service.get_services_by_profile(profile)
        if profile_services:
            test_runners = [s for s in profile_services if "test-runner" in s]
            service = test_runners[0] if test_runners else profile_services[0]
        else:
            service = "test-runner"

        # Cleanup old sessions before starting new test run
        self.pytest_logging.cleanup_all_locations()

        # Ensure test images are available
        rc = self._ensure_test_images(profile, service, build, verbose)
        if rc != 0:
            return rc

        # Prepare test environment with base environment for merging
        # Determine base environment (centralized > context > system fallback)
        if centralized_env is not None:
            base = centralized_env
        elif self.resolved_env is not None:
            base = self.resolved_env
        else:
            import os

            base = dict(os.environ)
            base["REPO_ROOT"] = str(self.repo_root)

        full_env = self.prepare_test_environment(
            suite=suite,
            extra_env=env_vars,
            base_env=base,
        )
        self._log_environment_debug_info(full_env)

        # Build and execute test command
        run_cmd = self.build_docker_command(
            profile=profile,
            service=service,
            env_vars=env_vars,
            detach=True,
        )

        # Only start the container if it's not already running to avoid
        # duplicate startup noise. When running in parallel orchestration,
        # containers may already be started.
        if not self._is_service_running(service):
            self._execute_test_container(run_cmd, full_env, verbose, suite)
        else:
            if verbose:
                CliOutput.info(f"Reusing running service: {service}")

        # Wait for completion and stream logs
        exit_code, logs_process = self._wait_for_test_completion(service)

        # Stop log streaming
        if logs_process:
            try:
                logs_process.terminate()
                logs_process.wait(timeout=PROCESS_WAIT_TIMEOUT_S)
                logger.debug("Stopped log streaming")
            except (
                OSError,
                subprocess.SubprocessError,
                subprocess.TimeoutExpired,
            ) as e:
                logger.debug("Error stopping log stream (non-fatal): %s", e)
                with contextlib.suppress(Exception):
                    logs_process.kill()

        # Report results (unless quiet mode for parallel execution)
        if not quiet:
            if exit_code == 0:
                CliOutput.success("Tests passed")
            else:
                CliOutput.error("Tests failed", err=True)

        return exit_code

    def _is_service_running(self, service: str) -> bool:
        """Check if a given service is currently running for this project.

        Parameters
        ----------
        service : str
            Service name to check

        Returns
        -------
        bool
            True if service is running
        """
        cmd = [
            "docker",
            "compose",
            "--project-directory",
            str(self.repo_root),
            "-f",
            str(self.compose_file),
            "--project-name",
            DockerConstants.DEFAULT_PROJECT,
            "ps",
            "--services",
            "--filter",
            "status=running",
        ]
        result = self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout:
            return False
        running = [s.strip() for s in result.stdout.splitlines() if s.strip()]
        return service in running

    def build_docker_images(self, profile: str, verbose: bool = False) -> int:
        """Build Docker images for testing.

        Parameters
        ----------
        profile : str
            Docker profile to build
        verbose : bool
            Enable verbose output

        Returns
        -------
        int
            Exit code from build process
        """
        build_cmd = self.build_docker_command(profile=profile, build=True)

        if verbose:
            CliOutput.plain(f"{Icons.BUILD} Building images: {' '.join(build_cmd)}")
        else:
            CliOutput.plain(f"{Icons.BUILD} Building Docker images...")

        with click.progressbar(length=1, label="Building images") as bar:
            result = self.command_executor.execute(
                build_cmd,
                cwd=self.repo_root,
                check=False,
            )
            bar.update(1)

        if result.returncode != 0:
            CliOutput.error("Docker build failed", err=True)

        return result.returncode

    def run_local_tests(
        self,
        suite_path: Path,
        suite: str | None = None,
        pytest_args: list[str] | None = None,
        centralized_env: dict[str, str] | None = None,
    ) -> int:
        """Run tests locally without Docker.

        Creates session-isolated pytest output directory and captures both
        pytest's native logging and full stdout/stderr to match container test pattern.

        Parameters
        ----------
        suite_path : Path
            Path to the test suite directory
        suite : str | None, optional
            Test suite name for session identification
        pytest_args : list[str], optional
            Additional pytest arguments
        centralized_env : dict[str, str], optional
            Centralized environment variables for test execution

        Returns
        -------
        int
            Exit code from pytest
        """
        # Cleanup old sessions before starting new test run
        self.pytest_logging.cleanup_all_locations()

        # Generate timestamp once for session consistency
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self._current_session_timestamp = timestamp

        # Generate session-specific directory using consistent timestamp
        session_id = self.pytest_logging.generate_session_id(suite, timestamp=timestamp)
        session_dir = self.pytest_logging.create_session_directory(session_id)
        self._current_session_dir = session_dir
        self._current_session_id = session_id

        # Get session-specific log paths
        pytest_log_file = self.pytest_logging.get_pytest_log_file_path(session_dir)
        test_results_file = self.pytest_logging.get_test_results_path(session_dir)

        # Build pytest command with tee for real-time file streaming
        # (matches container behavior)
        pytest_cmd_parts = [sys.executable, "-m", "pytest", str(suite_path)]
        if pytest_args:
            pytest_cmd_parts.extend(pytest_args)

        # Force colored output even through pipes
        # (pytest disables colors for pipes by default)
        pytest_cmd_parts.append("--color=yes")

        # Override pytest log_file configuration to use session directory
        pytest_cmd_parts.extend(["-o", f"log_file={pytest_log_file}"])

        # Escape arguments for shell safety
        pytest_cmd = " ".join(shlex.quote(str(arg)) for arg in pytest_cmd_parts)

        # Use bash with tee to stream output to both terminal and file
        # (exactly like containers). This ensures output is written in real-time,
        # surviving Ctrl+C interruptions.
        # Use pipefail to return pytest's exit code, not tee's
        bash_cmd = (
            f"set -o pipefail; {pytest_cmd} 2>&1 | "
            f"tee {shlex.quote(str(test_results_file))}"
        )

        # Log the complete command for debugging (logger only)
        logger.info("Executing pytest command: %s", pytest_cmd)
        logger.info("Session directory: %s", session_dir)

        # Show session, command, and log locations (after initial banner from test.py)
        # Simplify command for display (strip long paths, keep essential args)
        # pytest_cmd_parts[2:] = ["pytest", suite_path, args...]
        simplified_cmd = " ".join(
            arg
            for arg in pytest_cmd_parts[2:]  # Starts with 'pytest'
            if not str(arg).startswith("/")  # Skip absolute paths
        )
        CliOutput.plain("")
        CliOutput.plain(f"Session: {session_id}")
        CliOutput.plain(f"Command: {simplified_cmd}")
        CliOutput.plain("")

        # Show log locations with actual session ID
        CliOutput.plain("Logs:")
        test_log_path = session_dir
        rel_test_path = str(test_log_path.relative_to(self.repo_root))
        CliOutput.plain(f"  Test: {rel_test_path}")

        # App logs in home directory
        from aidb_cli.core.paths import CachePaths

        app_log_dir = CachePaths.log_dir()
        app_log_str = str(app_log_dir).replace(str(Path.home()), "~")
        CliOutput.plain(f"  CLI:  {app_log_str}")

        # Use centralized environment if provided, otherwise use current environment
        if centralized_env:
            command_env = centralized_env.copy()
        elif self.resolved_env:
            command_env = self.resolved_env.copy()
        else:
            # Local tests might not always have centralized env
            # (e.g., direct pytest calls)
            import os

            command_env = dict(os.environ)

        # Force color support for pytest and other tools
        # (pytest auto-disables colors when piped through | tee)
        command_env.update(
            {
                "FORCE_COLOR": "1",  # Generic color forcing (works for many tools)
                "PY_COLORS": "1",  # Python-specific color support
            },
        )

        # Execute with bash and tee for real-time file streaming
        # Use rolling window for TTY, direct passthrough for non-TTY
        exit_code = 0
        try:
            # Check if we should use rolling window streaming
            if self.command_executor.should_stream():
                # Use StreamHandler for rolling window UX
                # The tee in bash_cmd ensures file is written in real-time
                stream_handler = StreamHandler(
                    max_lines=STREAM_WINDOW_SIZE,
                    clear_on_exit=False,
                    supports_ansi=self.command_executor.supports_ansi,
                    terminal_width=self.command_executor.get_terminal_width(),
                )

                # Run bash command through stream handler
                result = stream_handler.run_with_streaming(
                    ["bash", "-c", bash_cmd],
                    cwd=self.repo_root,
                    env=command_env,
                    check=False,
                )

                exit_code = result.returncode
            else:
                # Non-TTY: Direct execution with tee (no rolling window needed)
                # Capture output for Click compatibility
                process = subprocess.Popen(  # noqa: S602, S603, S607
                    ["bash", "-c", bash_cmd],
                    cwd=self.repo_root,
                    env=command_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                # Read and echo output line by line for real-time display
                if process.stdout:
                    for line in process.stdout:
                        click.echo(line, nl=False)

                exit_code = process.wait()
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully - pytest output already saved to file via tee
            logger.info("Test execution interrupted by user")
            exit_code = 130  # Standard exit code for SIGINT
        except Exception as e:
            logger.error("Error during test execution: %s", e)
            exit_code = 1

        return exit_code

    @property
    def current_session_dir(self) -> Path | None:
        """Get the current session directory path.

        Returns
        -------
        Path | None
            Path to current session directory or None if no session active
        """
        return self._current_session_dir

    def run_shell(self, profile: str = "shell") -> int:
        """Open an interactive shell in the test container.

        Parameters
        ----------
        profile : str
            Docker profile to use

        Returns
        -------
        int
            Exit code from shell session
        """
        cmd = self.build_docker_command(
            profile=profile,
            service="shell",
            command="/bin/bash",
        )

        CliOutput.plain(f"{Icons.SHELL} Starting interactive shell...")
        result = self.command_executor.execute(cmd, cwd=self.repo_root, check=False)

        return result.returncode

    def clean_test_environment(self) -> int:
        """Clean up Docker test environment.

        Returns
        -------
        int
            Exit code from cleanup
        """
        cmd = [
            "docker",
            "compose",
            "--project-directory",
            str(self.repo_root),
            "-f",
            str(self.compose_file),
            "down",
            "--volumes",
            "--remove-orphans",
        ]

        CliOutput.plain(f"{Icons.CLEAN} Cleaning up test environment...")
        result = self.command_executor.execute(cmd, cwd=self.repo_root, check=False)

        if result.returncode == 0:
            CliOutput.success("Cleanup complete")
        else:
            CliOutput.error("Cleanup failed", err=True)

        return result.returncode

    def prepare_test_environment(
        self,
        suite: str | None = None,
        language: str = "all",
        markers: str | None = None,
        pattern: str | None = None,
        pytest_args: str | None = None,
        parallel: int | None = None,
        extra_env: dict[str, str] | None = None,
        base_env: dict[str, str] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, str]:
        """Prepare environment variables for test execution.

        Unified method that handles both framework container startup and
        direct test execution. Can return either just test-specific variables
        or a complete environment merged with a base environment.

        Parameters
        ----------
        suite : str | None, optional
            Test suite to run (uses "local" if None)
        language : str, default="all"
            Language to test
        markers : str, optional
            Pytest markers
        pattern : str, optional
            Test pattern
        pytest_args : str, optional
            Additional pytest arguments
        parallel : int, optional
            Number of parallel workers
        extra_env : dict[str, str], optional
            Additional environment variables to include in result
        base_env : dict[str, str], optional
            Base environment to merge with (centralized/system env).
            If None, returns only test-specific variables.
            If provided, merges test vars into base_env.
        timestamp : str | None, optional
            Pre-generated timestamp for session ID. If None, generates new one.
            Pass a shared timestamp when calling from multi-language loops to
            ensure all languages use the same session ID.

        Returns
        -------
        dict[str, str]
            Environment variables for test execution.
            If base_env is None: returns only test vars.
            If base_env provided: returns merged environment.
        """
        # Check if session ID already exists in extra_env (from parallel execution)
        # This ensures we reuse the same session ID throughout the execution flow
        if extra_env and "PYTEST_SESSION_ID" in extra_env:
            session_id = extra_env["PYTEST_SESSION_ID"]
            # Extract timestamp from session ID (format: suite-YYYYMMDD-HHMMSS)
            parts = session_id.split("-")
            if len(parts) >= 3:
                timestamp = "-".join(parts[-2:])
            else:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        else:
            # Generate new timestamp and session ID
            if timestamp is None:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            session_id = self.pytest_logging.generate_session_id(
                suite,
                timestamp=timestamp,
            )

        self._current_session_timestamp = timestamp
        self._current_session_id = session_id

        # Build test-specific environment variables
        test_env_vars = {
            "PYTEST_SESSION_ID": session_id,
            "PYTEST_LOG_DIR": "/workspace/pytest-logs",
            "REPO_ROOT": str(self.repo_root),
        }

        # Add test suite if provided
        if suite:
            test_env_vars["TEST_SUITE"] = suite

        # Add language
        test_env_vars["TEST_LANGUAGE"] = language

        # Add optional test parameters
        if markers:
            test_env_vars["TEST_MARKERS"] = markers
        if pattern:
            test_env_vars["TEST_PATTERN"] = pattern
        if pytest_args:
            test_env_vars["PYTEST_ADDOPTS"] = pytest_args
        if parallel:
            test_env_vars["PYTEST_PARALLEL"] = str(parallel)

        # Build TEST_COMMAND for test-runner service
        # Other services (mcp, shared, etc.) override command in compose file
        test_cmd_parts = [
            "bash -c '",
            "cd /workspace &&",
            "python -m pip install -e .[test,dev] -q &&",
            "python -m pytest ${TEST_PATH:-src/tests}",
            "${TEST_PATTERN:+-k ${TEST_PATTERN}}",
            "${TEST_MARKERS:+-m ${TEST_MARKERS}}",
            "'",
        ]
        test_env_vars["TEST_COMMAND"] = " ".join(test_cmd_parts)

        # Merge with extra environment variables if provided
        if extra_env:
            test_env_vars.update({k: str(v) for k, v in extra_env.items()})

        # If no base environment provided, return test vars only
        if base_env is None:
            return test_env_vars

        # Merge test vars with base environment
        full_env = base_env.copy()
        full_env.update(test_env_vars)

        # Show session and log locations (after initial banner from test.py)
        CliOutput.plain("")
        CliOutput.plain(f"Session: {full_env['PYTEST_SESSION_ID']}")
        CliOutput.plain("")

        # Show log locations for Docker mode
        CliOutput.plain("Logs:")
        from aidb_cli.core.paths import CachePaths

        container_data_dir = CachePaths.container_data_dir(self.repo_root)
        rel_container_path = str(container_data_dir.relative_to(self.repo_root))
        CliOutput.plain(f"  Container: {rel_container_path}")

        return full_env
