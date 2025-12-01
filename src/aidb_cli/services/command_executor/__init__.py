"""Command executor service subpackage.

This package provides modular services for command execution with a
unified facade interface.

The CommandExecutor facade provides the main interface, delegating to:
- ExecutionService: Core command execution
- TtyDetectionService: TTY/CI environment detection
- StreamHandlerService: Output streaming/buffering
- EnvironmentService: Environment variable management
"""

import contextlib
import subprocess
from pathlib import Path
from typing import Any

from aidb_cli.core.constants import STREAM_WINDOW_SIZE
from aidb_common.env import read_bool
from aidb_logging import get_cli_logger

from .environment_service import EnvironmentService
from .execution_service import ExecutionService
from .stream_handler_service import StreamHandlerService
from .tty_detection_service import TtyDetectionService

logger = get_cli_logger(__name__)


class CommandExecutor:
    """Centralized command executor with automatic streaming detection.

    This class acts as a facade over specialized services to provide
    a unified interface for command execution throughout the CLI.

    Handles all subprocess execution for the CLI with smart defaults:
    - Streams output in TTY environments for better UX (10-line rolling window)
    - Buffers output in CI/CD or when verbose mode is enabled
    - Provides consistent error handling and logging
    - Respects the global --verbose flag from CLI context

    This is the ONLY class in the CLI that should execute subprocesses.
    All commands and managers must use this service for consistency.

    Examples
    --------
    >>> # Create executor (usually done by Context)
    >>> executor = CommandExecutor()
    >>>
    >>> # Auto-detect streaming vs buffering
    >>> result = executor.execute(['ls', '-la'])
    >>>
    >>> # Force output capture regardless of environment
    >>> result = executor.execute(
    ...     ['git', 'log', '--oneline'],
    ...     capture_output=True
    ... )
    >>> print(result.stdout)
    """

    def __init__(self, ctx=None):
        """Initialize command executor.

        Parameters
        ----------
        ctx : click.Context, optional
            CLI context for accessing verbosity flags
        """
        # Initialize component services
        self._tty_service = TtyDetectionService(ctx)
        self._env_service = EnvironmentService()
        self._exec_service = ExecutionService()
        self._ctx = ctx

        # Configuration
        self._force_streaming = read_bool("AIDB_CLI_FORCE_STREAMING", False)

    def should_stream(self) -> bool:
        """Determine if output should be streamed based on environment.

        Returns
        -------
        bool
            True if streaming should be used, False for buffering
        """
        # Always use streaming for both NORMAL and LARGE sizes
        # The difference is handled in the max_lines parameter
        return self._tty_service.should_stream(verbose=False)

    def should_stream_for_verbosity(
        self,
        verbose: bool = False,
        verbose_debug: bool = False,
    ) -> bool:
        """Determine if output should be streamed based on verbosity level.

        Parameters
        ----------
        verbose : bool, optional
            Whether -v verbose mode is enabled
        verbose_debug : bool, optional
            Whether -vvv verbose debug mode is enabled

        Returns
        -------
        bool
            True if streaming should be enabled for the given verbosity level
        """
        return self._tty_service.should_stream_for_verbosity(verbose, verbose_debug)

    def _determine_streaming_mode(
        self,
        capture_output: bool | None,
        verbose: bool | None,
        verbose_debug: bool | None,
    ) -> bool:
        """Determine if streaming should be used based on parameters.

        Parameters
        ----------
        capture_output : bool | None
            Explicit capture_output setting
        verbose : bool | None
            Verbose mode flag
        verbose_debug : bool | None
            Verbose debug mode flag

        Returns
        -------
        bool
            True if streaming should be used
        """
        # Explicit capture_output=True always disables streaming
        if capture_output is True:
            logger.debug("Streaming disabled: capture_output=True")
            return False

        # capture_output=False means we want to see output unconditionally
        if capture_output is False:
            stream = self.should_stream()
            logger.debug("Streaming decision for capture_output=False: %s", stream)
            return stream

        # Use OutputStrategy if available (preferred path)
        if self._ctx and hasattr(self._ctx, "obj") and hasattr(self._ctx.obj, "output"):
            stream = self._ctx.obj.output.should_stream()
            logger.debug("Streaming decision from OutputStrategy: %s", stream)
            return stream

        # Fallback: use verbosity parameters if provided
        if verbose is not None or verbose_debug is not None:
            v = verbose if verbose is not None else False
            vvv = verbose_debug if verbose_debug is not None else False
            stream = self.should_stream_for_verbosity(v, vvv)
            logger.debug("Streaming decision from verbosity flags: %s", stream)
            return stream

        # Ultimate fallback: use TTY-based detection (legacy behavior)
        # This ensures TTY environments get streaming by default
        stream = self.should_stream()
        logger.debug("Streaming decision from TTY detection fallback: %s", stream)
        return stream

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
        r"""Execute a command with automatic streaming detection.

        Parameters
        ----------
        cmd : list[str] or str
            Command to execute
        cwd : Path, optional
            Working directory
        env : dict[str, str], optional
            Environment variables
        check : bool
            Whether to raise exception on failure
        timeout : float, optional
            Timeout in seconds
        capture_output : bool, optional
            Whether to capture output. If True, forces buffering regardless
            of environment. If False, output goes to stdout/stderr. If None
            (default), auto-detection determines behavior based on TTY and flags
        verbose : bool, optional
            Whether -v verbose mode is enabled (affects streaming behavior)
        verbose_debug : bool, optional
            Whether -vvv verbose debug mode is enabled (affects streaming behavior)
        passthrough_no_stream : bool
            If True, output passes directly through to stdout/stderr without
            buffering or streaming. Prevents deadlocks when subprocess generates
            large amounts of output. Default is False
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
        # Convert string command to list
        if isinstance(cmd, str):
            cmd = cmd.split()

        # Determine if we should stream
        stream = self._determine_streaming_mode(capture_output, verbose, verbose_debug)

        # Update capture_output based on streaming decision
        if capture_output is None:
            capture_output = not stream

        logger.debug("Executing command: %s (stream=%s)", " ".join(cmd), stream)
        if cwd:
            logger.debug("Working directory: %s", cwd)

        # Remove terminal normalization - it was disrupting VSCode terminal features
        # Focus on preventing streaming initialization when not needed

        # Build environment
        command_env = self._env_service.build_environment(env)

        # Debug log environment if executing docker compose
        if len(cmd) > 1 and cmd[0] == "docker" and cmd[1] == "compose":
            if command_env:
                repo_root_val = command_env.get("REPO_ROOT", "NOT_SET")
                logger.debug("Docker compose environment: REPO_ROOT=%s", repo_root_val)
                # Show all AIDB/TEST env vars being passed
                relevant_vars = {
                    k: v
                    for k, v in command_env.items()
                    if k.startswith(("REPO_", "TEST_", "AIDB_", "PYTEST_"))
                }
                logger.debug(
                    "Docker compose relevant env vars: %s",
                    list(relevant_vars.keys()),
                )
            else:
                logger.debug(
                    "Docker compose using default environment (command_env is None)",
                )

        # Defensive guard: ensure capture_output=True never triggers streaming
        if capture_output is True and stream:
            logger.warning(
                "Logic error: capture_output=True but stream=True, "
                "forcing stream=False",
            )
            stream = False

        # Allow callers to force passthrough without rolling-window streaming
        if passthrough_no_stream:
            logger.debug("Passthrough without streaming for command: %s", " ".join(cmd))
            return self._exec_service.execute(
                cmd,
                cwd=cwd,
                env=command_env,
                capture_output=False,
                timeout=timeout,
                check=check,
                **kwargs,
            )

        if stream:
            # Additional safety check: never stream when capture_output is
            # explicitly True
            if capture_output is True:
                logger.error(
                    "Critical logic error: attempting to stream with "
                    "capture_output=True",
                )
                msg = "Cannot use streaming when capture_output=True"
                raise ValueError(msg)

            # Use streaming execution with configured window size
            terminal_width = self._tty_service.get_terminal_width()
            stream_service = StreamHandlerService(
                max_lines=STREAM_WINDOW_SIZE,
                clear_on_exit=False,
                supports_ansi=self._tty_service.supports_ansi,
                terminal_width=terminal_width,
            )

            return stream_service.run_with_streaming(
                cmd,
                cwd=cwd,
                env=command_env,
                timeout=timeout,
                check=check,
            )
        # Use buffered execution - ensure no streaming artifacts
        logger.debug("Using buffered execution (capture_output=%s)", capture_output)
        return self._exec_service.execute(
            cmd,
            cwd=cwd,
            env=command_env,
            capture_output=capture_output,
            timeout=timeout,
            check=check,
            **kwargs,
        )

    def create_process(
        self,
        cmd: list[str] | str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs: Any,
    ) -> subprocess.Popen:
        r"""Create a subprocess.Popen for advanced streaming scenarios.

        This method is intended for cases where real-time streaming with
        direct process control is required (e.g., log tailing). For most
        command execution, use the execute() method instead.

        Parameters
        ----------
        cmd : list[str] or str
            Command to execute
        cwd : Path, optional
            Working directory
        env : dict[str, str], optional
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

        Examples
        --------
        >>> # Create a process for streaming logs
        >>> process = executor.create_process(
        ...     ['docker', 'logs', '--follow', 'mycontainer'],
        ...     stdout=subprocess.PIPE,
        ...     stderr=subprocess.STDOUT,
        ...     text=True
        ... )
        >>> # Read from process.stdout in real-time
        >>> for line in process.stdout:
        ...     print(line.strip())
        """
        # Convert string command to list
        if isinstance(cmd, str):
            cmd = cmd.split()

        # Build environment
        command_env = self._env_service.build_environment(env)

        # Delegate to execution service
        return self._exec_service.create_process(
            cmd,
            cwd=cwd,
            env=command_env,
            stdout=stdout,
            stderr=stderr,
            **kwargs,
        )

    # Convenience methods for environment management

    def find_executable(self, name: str) -> Path | None:
        """Find an executable in PATH.

        Parameters
        ----------
        name : str
            Name of the executable

        Returns
        -------
        Path | None
            Path to executable if found
        """
        return self._env_service.find_executable(name)

    def add_to_path(
        self,
        directory: Path,
        env: dict[str, str] | None = None,
        prepend: bool = True,
    ) -> dict[str, str]:
        """Add a directory to PATH.

        Parameters
        ----------
        directory : Path
            Directory to add
        env : dict[str, str], optional
            Environment to modify
        prepend : bool
            Whether to prepend or append

        Returns
        -------
        dict[str, str]
            Environment with updated PATH
        """
        return self._env_service.add_to_path(directory, env, prepend)

    @property
    def is_ci(self) -> bool:
        """Check if running in CI/CD environment.

        Returns
        -------
        bool
            True if in CI/CD environment
        """
        return self._tty_service.is_ci

    @property
    def is_tty(self) -> bool:
        """Check if stdout is a TTY.

        Returns
        -------
        bool
            True if stdout is a TTY
        """
        return self._tty_service.is_tty

    def _normalize_terminal_state(self) -> None:
        """Ensure terminal is in a clean state before command execution.

        This method helps prevent streaming artifacts from persisting between command
        invocations by ensuring the terminal cursor and display state are properly
        normalized.
        """
        if not self._tty_service.supports_ansi:
            return

        with contextlib.suppress(Exception):
            # Very minimal terminal normalization - only reset ANSI attributes
            # Avoid disrupting VSCode terminal features like sticky scroll
            print("\033[0m", end="", flush=True)


__all__ = [
    # Main facade
    "CommandExecutor",
    # Component services
    "ExecutionService",
    "TtyDetectionService",
    "StreamHandlerService",
    "EnvironmentService",
]
