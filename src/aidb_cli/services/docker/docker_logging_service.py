"""Service for Docker container logging."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.core.constants import Icons
from aidb_cli.core.paths import DockerConstants
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger
from aidb_logging.utils import get_log_file_path

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerLoggingService(BaseService):
    """Service for managing Docker container logs.

    This service handles:
    - Fetching container logs
    - Streaming logs in real-time
    - Log output formatting
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        project_name: str = DockerConstants.DEFAULT_PROJECT,
    ) -> None:
        """Initialize the Docker logging service.

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
        self._log_processes: dict[str, Any] = {}  # subprocess.Popen instances

    def get_service_logs(
        self,
        service_name: str,
        lines: int = 50,
        follow: bool = False,
    ) -> str:
        """Get logs for a specific service.

        Parameters
        ----------
        service_name : str
            Service name
        lines : int, optional
            Number of lines to fetch
        follow : bool, optional
            Follow log output

        Returns
        -------
        str
            Service logs
        """
        from aidb_cli.core.paths import ProjectPaths
        from aidb_cli.services.docker.service_dependency_service import (
            ServiceDependencyService,
        )

        dep_service = ServiceDependencyService(
            self.repo_root,
            self.command_executor,
        )
        compose_file = self.repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
        dep_service.load_services(compose_file)

        container_name = dep_service.get_container_name(service_name)
        if not container_name:
            container_name = f"{self.project_name}-{service_name}-1"

        cmd = ["docker", "logs"]

        if lines:
            cmd.extend(["--tail", str(lines)])

        if follow:
            cmd.append("--follow")

        cmd.append(container_name)

        try:
            # Use CommandExecutor for non-streaming log fetching
            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                timeout=5 if not follow else None,
                check=False,
            )

            if result.returncode == 0:
                # Combine stdout and stderr like before
                return result.stdout + (result.stderr or "")
            self.log_warning(
                "Failed to get logs for %s: %s",
                service_name,
                result.stderr,
            )
            return f"Failed to get logs for {service_name}"

        except TimeoutError:
            return "Log fetch timed out"
        except (OSError, subprocess.SubprocessError) as e:
            self.log_error("Error getting logs for %s: %s", service_name, str(e))
            return f"Error getting logs: {str(e)}"

    def stream_compose_logs(
        self,
        compose_file: Path,
        profile: str | None = None,
        verbose: bool = False,
    ) -> Any:  # Returns subprocess.Popen
        """Stream docker-compose logs for a profile.

        Parameters
        ----------
        compose_file : Path
            Path to docker-compose file
        profile : str | None, optional
            Profile to stream logs for
        verbose : bool, optional
            Show verbose output

        Returns
        -------
        subprocess.Popen | None
            Log streaming process or None on error
        """
        cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "-p",
            self.project_name,
        ]

        if profile:
            cmd.extend(["--profile", profile])

        cmd.extend(["logs", "--follow", "--tail", "50"])

        try:
            if verbose:
                CliOutput.info(
                    f"Streaming logs for profile: {profile or 'all'}",
                )

            # Use CommandExecutor's create_process for streaming
            process = self.command_executor.create_process(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Store process for later cleanup
            log_key = profile or "all"
            self._log_processes[log_key] = process

            # Spawn a background reader to consume and print logs
            try:
                import threading

                def _consume_stream(p: Any) -> None:
                    try:
                        if p and p.stdout:
                            for line in p.stdout:
                                # Print as-is; docker compose prefixes container names
                                if line:
                                    CliOutput.plain(line.rstrip("\n"))
                    except Exception as e:  # Best-effort streaming
                        self.log_debug("Log consumer ended: %s", e)

                t = threading.Thread(
                    target=_consume_stream,
                    args=(process,),
                    name=f"ComposeLog-{log_key}",
                    daemon=True,
                )
                t.start()
            except Exception as e:
                self.log_debug("Failed to start log consumer thread: %s", e)

            return process

        except (OSError, subprocess.SubprocessError) as e:
            self.log_error("Failed to start log streaming: %s", str(e))
            return None

    def stream_multiple_profiles(
        self,
        compose_file: Path,
        profiles: list[str],
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Stream docker-compose logs for multiple profiles simultaneously.

        This method starts separate log streams for each profile/container,
        enabling parallel container log monitoring with clear attribution.

        Parameters
        ----------
        compose_file : Path
            Path to docker-compose file
        profiles : list[str]
            List of profiles to stream logs for
        verbose : bool, optional
            Show verbose output

        Returns
        -------
        dict[str, subprocess.Popen | None]
            Dictionary mapping profile names to log streaming processes
            (or None if streaming failed for that profile)

        Examples
        --------
        >>> logging_service = DockerLoggingService(repo_root)
        >>> compose_file = repo_root / "docker-compose.yaml"
        >>> processes = logging_service.stream_multiple_profiles(
        ...     compose_file,
        ...     profiles=["python", "javascript", "java"],
        ...     verbose=True,
        ... )
        >>> # processes = {"python": <Popen>, "javascript": <Popen>, "java": <Popen>}
        """
        processes = {}

        if verbose:
            profile_list = ", ".join(profiles)
            CliOutput.info(
                f"Starting log streams for {len(profiles)} profiles: {profile_list}",
            )

        for profile in profiles:
            process = self.stream_compose_logs(
                compose_file=compose_file,
                profile=profile,
                verbose=False,  # Avoid duplicate verbose messages
            )
            processes[profile] = process

            if process and verbose:
                CliOutput.info(f"Started log stream for {profile}")
            elif not process:
                self.log_warning("Failed to start log stream for %s", profile)

        return processes

    def stop_all_profile_streams(self, profiles: list[str]) -> None:
        """Stop log streaming for multiple profiles.

        Parameters
        ----------
        profiles : list[str]
            List of profile names to stop streaming for
        """
        for profile in profiles:
            self.stop_log_streaming(profile=profile)

    def print_logs_from_stream(
        self,
        process: Any,  # subprocess.Popen instance
        max_lines: int = 100,
    ) -> None:
        """Print logs from a streaming process.

        Parameters
        ----------
        process : subprocess.Popen
            Log streaming process
        max_lines : int, optional
            Maximum lines to print
        """
        if not process or not process.stdout:
            return

        lines_printed = 0

        try:
            for line in process.stdout:
                if lines_printed >= max_lines:
                    CliOutput.info("... (log output truncated)")
                    break

                # Clean and format the line
                line = line.strip()
                if line:
                    CliOutput.plain(line)
                    lines_printed += 1

        except OSError as e:
            self.log_error("Error reading log stream: %s", str(e))

    def stop_log_streaming(self, profile: str | None = None) -> None:
        """Stop log streaming for a profile.

        Parameters
        ----------
        profile : str | None, optional
            Profile to stop streaming for, or None for all
        """
        if profile:
            log_key = profile or "all"
            if log_key in self._log_processes:
                process = self._log_processes[log_key]
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:  # Catch all to ensure kill() runs
                    process.kill()
                del self._log_processes[log_key]
                self.log_debug("Stopped log streaming for %s", log_key)
        else:
            # Stop all log streams
            for key, process in list(self._log_processes.items()):
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:  # Catch all to ensure kill() runs
                    process.kill()
                self.log_debug("Stopped log streaming for %s", key)
            self._log_processes.clear()

    def get_recent_logs(
        self,
        services: list[str],
        lines: int = 20,
    ) -> dict[str, str]:
        """Get recent logs for multiple services.

        Parameters
        ----------
        services : list[str]
            List of service names
        lines : int, optional
            Number of lines per service

        Returns
        -------
        dict[str, str]
            Dictionary mapping service names to logs
        """
        logs = {}

        for service in services:
            logs[service] = self.get_service_logs(service, lines=lines)

        return logs

    def show_service_logs(
        self,
        service_name: str,
        lines: int = 50,
        verbose: bool = True,
    ) -> None:
        """Display logs for a service.

        Parameters
        ----------
        service_name : str
            Service name
        lines : int, optional
            Number of lines to show
        verbose : bool, optional
            Show header and formatting
        """
        if verbose:
            from aidb_cli.core.formatting import HeadingFormatter

            HeadingFormatter.section(f"Logs for {service_name}", Icons.INFO)

        logs = self.get_service_logs(service_name, lines=lines)

        if logs:
            CliOutput.plain(logs)
        else:
            CliOutput.warning(f"No logs available for {service_name}")

        if verbose:
            CliOutput.plain("")

    def cleanup(self) -> None:
        """Cleanup service resources."""
        # Stop all log streaming processes
        self.stop_log_streaming()

    def collect_test_container_logs(
        self,
        output_file: Path | None = None,
        container_filter: dict[str, list[str]] | None = None,
        max_log_size: int = 10 * 1024 * 1024,  # 10MB per container
    ) -> dict[str, bool]:
        """Collect logs from test containers and append to file.

        Parameters
        ----------
        output_file : Path | None
            Target log file (defaults to ~/.aidb/log/test-container-output.log)
        container_filter : dict[str, list[str]] | None
            Docker label filters (defaults to test containers only)
        max_log_size : int
            Maximum log size per container in bytes (default: 10MB)

        Returns
        -------
        dict[str, bool]
            Container name -> success status mapping
        """
        # Default to test-container-output.log
        if output_file is None:
            output_file = Path(get_log_file_path("test-container-output"))

        # Default filter: test runner containers only
        # This will match containers with component labels: test, mcp, or adapter
        if container_filter is None:
            container_filter = {
                "label": [
                    "com.aidb.managed=true",
                    # Match any of: test, mcp, adapter components
                ],
            }

        results: dict[str, bool] = {}

        # Get list of containers matching the filter
        containers = self._get_test_containers(container_filter)

        if not containers:
            self.log_debug("No test containers found for log collection")
            return results

        self.log_info(f"Collecting logs from {len(containers)} test containers")

        for container_name in containers:
            try:
                # Get container logs
                logs = self._fetch_container_logs(container_name, max_log_size)

                if logs:
                    # Write logs to file
                    self._write_container_logs_to_file(
                        container_name,
                        logs,
                        output_file,
                    )
                    results[container_name] = True
                    self.log_debug(f"Collected logs from {container_name}")
                else:
                    results[container_name] = False
                    self.log_debug(f"No logs found for {container_name}")

            except Exception as e:
                # Resilience: continue collecting from other containers
                self.log_warning(f"Failed to collect logs from {container_name}: {e}")
                results[container_name] = False

        return results

    def _get_test_containers(
        self,
        container_filter: dict[str, list[str]],
    ) -> list[str]:
        """Get list of test containers matching the filter.

        Parameters
        ----------
        container_filter : dict[str, list[str]]
            Docker label filters

        Returns
        -------
        list[str]
            List of container names
        """
        containers = []

        try:
            # Build docker ps command with filters
            cmd = ["docker", "ps", "-a", "--format", "{{.Names}}"]

            # Add label filters
            for label in container_filter.get("label", []):
                cmd.extend(["--filter", f"label={label}"])

            # Additional filter to exclude service containers
            # We want containers with component=test, mcp, or adapter
            test_component_cmd = cmd + ["--filter", "label=com.aidb.component=test"]
            mcp_component_cmd = cmd + ["--filter", "label=com.aidb.component=mcp"]
            adapter_component_cmd = cmd + [
                "--filter",
                "label=com.aidb.component=adapter",
            ]

            # Run commands to get containers for each component type
            all_containers = set()

            for component_cmd in [
                test_component_cmd,
                mcp_component_cmd,
                adapter_component_cmd,
            ]:
                result = self.command_executor.execute(
                    component_cmd,
                    capture_output=True,
                    check=False,
                )

                if result.returncode == 0 and result.stdout.strip():
                    container_names = result.stdout.strip().split("\n")
                    all_containers.update(container_names)

            containers = list(all_containers)

        except (OSError, subprocess.SubprocessError) as e:
            self.log_error(f"Failed to list test containers: {e}")

        return containers

    def _fetch_container_logs(
        self,
        container_name: str,
        max_size: int,
    ) -> str:
        """Fetch logs from a container with size limit.

        Parameters
        ----------
        container_name : str
            Container name
        max_size : int
            Maximum log size in bytes

        Returns
        -------
        str
            Container logs (may be truncated)
        """
        try:
            # Get logs from container
            cmd = ["docker", "logs", container_name]

            result = self.command_executor.execute(
                cmd,
                capture_output=True,
                check=False,
                timeout=30,  # 30 second timeout for log fetch
            )

            if result.returncode != 0:
                return ""

            # Combine stdout and stderr
            logs = result.stdout + (result.stderr or "")

            # Truncate if too large
            if len(logs.encode("utf-8")) > max_size:
                # Take the last max_size bytes
                logs_bytes = logs.encode("utf-8")[-max_size:]
                # Decode, handling potential partial UTF-8 sequences
                logs = logs_bytes.decode("utf-8", errors="ignore")
                logs = f"[TRUNCATED - showing last {max_size} bytes]\n{logs}"

            return logs

        except (OSError, subprocess.SubprocessError, TimeoutError) as e:
            self.log_warning(f"Failed to fetch logs from {container_name}: {e}")
            return ""

    def _write_container_logs_to_file(
        self,
        container_name: str,
        logs: str,
        output_file: Path,
    ) -> None:
        """Append container logs to file with clear formatting.

        Parameters
        ----------
        container_name : str
            Container name
        logs : str
            Log content to write
        output_file : Path
            Target log file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        separator = "=" * 60
        header = f"\n{separator}\n"
        header += f"CONTAINER LOGS: {container_name}\n"
        header += f"Collected at: {timestamp}\n"
        header += f"{separator}\n"

        footer = f"\n{separator}\n"
        footer += f"END CONTAINER LOGS: {container_name}\n"
        footer += f"{separator}\n\n"

        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Append to file
            with output_file.open("a", encoding="utf-8") as f:
                f.write(header)
                f.write(logs)
                f.write(footer)
        except OSError as e:
            self.log_error(f"Failed to write logs to {output_file}: {e}")
