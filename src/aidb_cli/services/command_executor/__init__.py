"""Command executor service.

Provides unified command execution with automatic TTY detection, streaming, and
environment management.
"""

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.common.errors import AidbError
from aidb_cli.core.constants import STREAM_WINDOW_SIZE, ExitCode
from aidb_common.env import read_bool
from aidb_logging import get_cli_logger

from .stream_handler import StreamHandler

if TYPE_CHECKING:
    import click

logger = get_cli_logger(__name__)

# CI environment variable names
_CI_ENV_VARS = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_HOME",
    "CIRCLECI",
    "TRAVIS",
    "BUILDKITE",
    "DRONE",
    "TEAMCITY_VERSION",
    "TF_BUILD",
    "GITHUB_WORKFLOW",
)


class CommandExecutor:
    """Centralized command executor with automatic streaming detection.

    Handles all subprocess execution for the CLI with smart defaults:
    - Streams output in TTY environments (rolling window display)
    - Buffers output in CI/CD environments
    - Provides consistent error handling and logging

    This is the ONLY class in the CLI that should execute subprocesses.
    All commands and managers must use this service for consistency.

    Examples
    --------
    >>> executor = CommandExecutor()
    >>> result = executor.execute(['ls', '-la'])
    >>> result = executor.execute(['git', 'log'], capture_output=True)
    """

    def __init__(self, ctx: "click.Context | None" = None) -> None:
        """Initialize command executor.

        Parameters
        ----------
        ctx : click.Context, optional
            CLI context for accessing verbosity flags and environment
        """
        self._ctx = ctx

        # Cache TTY/CI detection results
        self._is_ci: bool | None = None
        self._is_tty: bool | None = None
        self._supports_ansi: bool | None = None

        # Get base environment from context or system
        if ctx and hasattr(ctx, "obj") and hasattr(ctx.obj, "resolved_env"):
            self._base_env: dict[str, str] = ctx.obj.resolved_env.copy()
        else:
            self._base_env = dict(os.environ)

    # -------------------------------------------------------------------------
    # TTY / CI Detection
    # -------------------------------------------------------------------------

    @property
    def is_ci(self) -> bool:
        """Check if running in CI/CD environment."""
        if self._is_ci is None:
            self._is_ci = any(self._base_env.get(var) for var in _CI_ENV_VARS)
            if self._is_ci:
                logger.debug("CI environment detected")
        return self._is_ci

    @property
    def is_tty(self) -> bool:
        """Check if stdout is a TTY."""
        if self._is_tty is None:
            self._is_tty = sys.stdout.isatty()
        return self._is_tty

    @property
    def supports_ansi(self) -> bool:
        """Check if environment supports ANSI escape codes."""
        if self._supports_ansi is None:
            from aidb_cli.core.constants import EnvVars

            force_ansi = read_bool(EnvVars.CLI_FORCE_ANSI, False)
            self._supports_ansi = self.is_tty or force_ansi
        return self._supports_ansi

    def get_terminal_width(self, fallback: int = 80) -> int:
        """Get terminal width for formatting."""
        try:
            return shutil.get_terminal_size(fallback=(fallback, 24)).columns
        except Exception:
            return fallback

    def should_stream(self) -> bool:
        """Determine if output should be streamed based on environment."""
        from aidb_cli.core.constants import EnvVars

        if read_bool(EnvVars.CLI_FORCE_STREAMING, False):
            return True
        if self.is_ci:
            return False
        return self.is_tty

    def should_stream_for_verbosity(
        self,
        verbose: bool = False,
        verbose_debug: bool = False,
    ) -> bool:
        """Determine if output should be streamed based on verbosity level."""
        if self.is_ci:
            return False
        if not verbose and not verbose_debug:
            return False
        return self.is_tty

    # -------------------------------------------------------------------------
    # Environment Management
    # -------------------------------------------------------------------------

    def build_environment(
        self,
        env_overrides: dict[str, str] | None = None,
    ) -> dict[str, str] | None:
        """Build command environment with overrides.

        Returns None if no overrides (subprocess uses default environment).
        """
        if not env_overrides:
            return None
        command_env = self._base_env.copy()
        command_env.update(env_overrides)
        return command_env

    def find_executable(self, name: str) -> Path | None:
        """Find an executable in PATH."""
        path = shutil.which(name)
        return Path(path) if path else None

    def add_to_path(
        self,
        directory: Path,
        env: dict[str, str] | None = None,
        prepend: bool = True,
    ) -> dict[str, str]:
        """Add a directory to PATH."""
        env = self._base_env.copy() if env is None else env.copy()
        path_components = [p for p in env.get("PATH", "").split(os.pathsep) if p]
        dir_str = str(directory)

        if dir_str not in path_components:
            if prepend:
                path_components.insert(0, dir_str)
            else:
                path_components.append(dir_str)
            env["PATH"] = os.pathsep.join(path_components)

        return env

    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------

    def _determine_streaming_mode(
        self,
        capture_output: bool | None,
        verbose: bool | None,
        verbose_debug: bool | None,
    ) -> bool:
        """Determine if streaming should be used based on parameters."""
        if capture_output is True:
            return False
        if capture_output is False:
            return self.should_stream()

        # Use OutputStrategy if available
        if self._ctx and hasattr(self._ctx, "obj") and hasattr(self._ctx.obj, "output"):
            return self._ctx.obj.output.should_stream()

        # Fallback to verbosity parameters
        if verbose is not None or verbose_debug is not None:
            v = verbose if verbose is not None else False
            vvv = verbose_debug if verbose_debug is not None else False
            return self.should_stream_for_verbosity(v, vvv)

        return self.should_stream()

    def execute(
        self,
        cmd: list[str] | str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: float | None = None,
        capture_output: bool | None = None,
        verbose: bool | None = None,
        verbose_debug: bool | None = None,
        passthrough_no_stream: bool = False,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a command with automatic streaming detection.

        Parameters
        ----------
        cmd : list[str] or str
            Command to execute
        cwd : Path, optional
            Working directory
        env : dict[str, str], optional
            Environment variables to add/override
        check : bool
            Whether to raise exception on failure
        timeout : float, optional
            Timeout in seconds
        capture_output : bool, optional
            If True, capture output. If False, show output. If None, auto-detect.
        verbose : bool, optional
            Whether verbose mode is enabled
        verbose_debug : bool, optional
            Whether verbose debug mode is enabled
        passthrough_no_stream : bool
            If True, output passes directly to stdout without buffering
        **kwargs : Any
            Additional arguments passed to subprocess

        Returns
        -------
        subprocess.CompletedProcess[str]
            Result of command execution

        Raises
        ------
        AidbError
            If command fails and check=True
        """
        if isinstance(cmd, str):
            cmd = cmd.split()

        stream = self._determine_streaming_mode(capture_output, verbose, verbose_debug)

        if capture_output is None:
            capture_output = not stream

        logger.debug("Executing: %s (stream=%s)", " ".join(cmd), stream)

        command_env = self.build_environment(env)

        # Passthrough mode: direct execution without streaming
        if passthrough_no_stream:
            return self._run_subprocess(
                cmd,
                cwd=cwd,
                env=command_env,
                capture_output=False,
                timeout=timeout,
                check=check,
                **kwargs,
            )

        # Streaming mode: use rolling window display
        if stream:
            stream_handler = StreamHandler(
                max_lines=STREAM_WINDOW_SIZE,
                clear_on_exit=False,
                supports_ansi=self.supports_ansi,
                terminal_width=self.get_terminal_width(),
            )
            return stream_handler.run_with_streaming(
                cmd,
                cwd=cwd,
                env=command_env,
                timeout=timeout,
                check=check,
            )

        # Buffered mode: standard subprocess execution
        return self._run_subprocess(
            cmd,
            cwd=cwd,
            env=command_env,
            capture_output=capture_output,
            timeout=timeout,
            check=check,
            **kwargs,
        )

    def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = False,
        timeout: float | None = None,
        check: bool = True,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess[str]:
        """Run subprocess with error handling."""
        try:
            result = subprocess.run(  # noqa: S603
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
                cmd_str = " ".join(cmd)
                error_msg = f"Command failed (exit {result.returncode}): {cmd_str}"
                if result.stderr:
                    error_msg += f"\n{result.stderr}"
                raise AidbError(error_msg)

            return result

        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
            if check:
                raise AidbError(error_msg) from e
            return subprocess.CompletedProcess(cmd, ExitCode.TIMEOUT, "", str(e))

        except FileNotFoundError as e:
            error_msg = f"Command not found: {cmd[0]}"
            if check:
                raise AidbError(error_msg) from e
            return subprocess.CompletedProcess(cmd, ExitCode.NOT_FOUND, "", str(e))

    def create_process(
        self,
        cmd: list[str] | str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdout: Any = subprocess.PIPE,
        stderr: Any = subprocess.PIPE,
        **kwargs: Any,
    ) -> subprocess.Popen:
        """Create a subprocess.Popen for advanced streaming scenarios.

        Use this for cases requiring real-time streaming with direct process control
        (e.g., log tailing). For most commands, use execute() instead.
        """
        if isinstance(cmd, str):
            cmd = cmd.split()

        command_env = self.build_environment(env)

        try:
            return subprocess.Popen(  # noqa: S603
                cmd,
                cwd=cwd,
                env=command_env,
                stdout=stdout,
                stderr=stderr,
                **kwargs,
            )
        except FileNotFoundError as e:
            msg = f"Command not found: {cmd[0]}"
            raise AidbError(msg) from e

    def _normalize_terminal_state(self) -> None:
        """Reset terminal ANSI state."""
        if self.supports_ansi:
            with contextlib.suppress(Exception):
                print("\033[0m", end="", flush=True)


# Backward compatibility: expose StreamHandler as StreamHandlerService
StreamHandlerService = StreamHandler

__all__ = [
    "CommandExecutor",
    "StreamHandler",
    "StreamHandlerService",  # Backward compat
]
