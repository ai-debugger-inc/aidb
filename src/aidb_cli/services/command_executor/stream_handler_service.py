"""Service for handling command output streaming."""

import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from aidb.common.errors import AidbError
from aidb_cli.core.constants import ExitCode
from aidb_cli.core.utils import CliOutput
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class StreamHandlerService:
    """Service for handling subprocess output streaming with rolling window display.

    This service manages streaming output specifically for subprocess/command output,
    providing a rolling window display that is separate from user-facing CLI output. It
    should only be used for debug/subprocess output, not for user-facing messages.
    """

    def __init__(
        self,
        max_lines: int = 8,
        clear_on_exit: bool = True,
        supports_ansi: bool = True,
        terminal_width: int = 80,
    ) -> None:
        """Initialize the stream handler service.

        Parameters
        ----------
        max_lines : int, optional
            Maximum lines in rolling window (default: 8)
        clear_on_exit : bool, optional
            Whether to clear output on exit (default: True)
        supports_ansi : bool, optional
            Whether ANSI codes are supported
        terminal_width : int, optional
            Terminal width for formatting
        """
        self.max_lines = max_lines
        self.clear_on_exit = clear_on_exit
        self.supports_ansi = supports_ansi
        self.terminal_width = terminal_width

        # Internal state
        self.display_lines: deque[str] = deque(maxlen=max_lines)
        self.full_output: list[str] = []
        self.process: subprocess.Popen | None = None
        self._stop_event = threading.Event()
        self._display_lock = threading.Lock()
        self._frame_initialized = False
        self._current_window_size = 0
        # Slightly slower throttle to reduce flicker on very chatty output
        self._min_render_interval = 0.08  # 80ms throttle
        self._last_render_time = 0.0
        self._has_output = False  # Track if we've shown any output
        # Track last printed index for non-ANSI fallback streaming
        self._last_plain_printed = 0

    def run_with_streaming(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command with streaming output.

        Parameters
        ----------
        cmd : list[str]
            Command to execute
        cwd : Path | None, optional
            Working directory
        env : dict[str, str] | None, optional
            Environment variables
        timeout : float | None, optional
            Timeout in seconds
        check : bool, optional
            Whether to raise on failure

        Returns
        -------
        subprocess.CompletedProcess[str]
            Result of command execution

        Raises
        ------
        AidbError
            If command fails and check=True
        """
        # Reset state
        self.display_lines.clear()
        self.full_output.clear()
        self._stop_event.clear()
        self._frame_initialized = False
        self._current_window_size = 0
        self._last_render_time = 0.0
        self._has_output = False
        self._last_plain_printed = 0

        try:
            # Start process
            self.process = self._start_subprocess(cmd, cwd, env)

            # Start reading thread
            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(self.process.stdout,),
            )
            stdout_thread.start()

            # Start render thread
            render_thread = threading.Thread(target=self._render_loop)
            render_thread.start()

            # Wait for completion
            returncode = self._wait_for_completion(
                stdout_thread,
                render_thread,
                timeout,
            )

            # Clear the streaming display if requested and we have output
            if self.clear_on_exit and self._has_output:
                self._clear_display()

            # Add blank line after streaming window
            if self._has_output:
                CliOutput.plain("")

            # Build result
            output = "\n".join(self.full_output)

            if check and returncode != 0:
                error_msg = (
                    f"Command failed with exit code {returncode}: {' '.join(cmd)}"
                )
                logger.error(error_msg)
                raise AidbError(error_msg)

            return subprocess.CompletedProcess(
                cmd,
                returncode,
                output,
                "",  # stderr is merged into stdout
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
        finally:
            self._cleanup_process()

    def _read_stream(self, stream) -> None:
        """Read from a stream and update output buffers."""
        if not stream:
            return

        try:
            while not self._stop_event.is_set():
                line = stream.readline()
                if not line:
                    break

                line = line.rstrip("\n\r")
                if line:
                    self.full_output.append(line)
                    with self._display_lock:
                        self.display_lines.append(line)

        except OSError as e:
            logger.debug("Error reading stream: %s", e)

    def _render_loop(self) -> None:
        """Continuously render the rolling window with throttling."""
        try:
            while not self._stop_event.is_set():
                current_time = time.time()
                # Only render if enough time has passed since last render
                if current_time - self._last_render_time >= self._min_render_interval:
                    self._update_display()
                    self._last_render_time = current_time
                time.sleep(0.01)  # Small sleep to prevent busy waiting

            # Final update to ensure all output is displayed
            self._update_display()
        except (OSError, ValueError) as e:
            logger.debug("Error in render loop: %s", e)

    def _update_display(self) -> None:
        """Update the rolling display with recent output."""
        with self._display_lock:
            current_lines = list(self.display_lines)

        if not current_lines:
            return

        # Track that we have output to display
        if not self._has_output:
            self._has_output = True

        if self.supports_ansi:
            # Rolling window mode with ANSI support
            # Calculate how many lines we should display
            lines_to_display = min(len(current_lines), self.max_lines)

            # Initialize frame on first output
            if not self._frame_initialized:
                CliOutput.plain("")  # Add blank line before streaming starts
                self._frame_initialized = True
                self._current_window_size = 0

            # If window is growing, add new lines
            if lines_to_display > self._current_window_size:
                lines_to_add = lines_to_display - self._current_window_size
                for _ in range(lines_to_add):
                    print("")  # Add new line to grow window
                self._current_window_size = lines_to_display

            # Move cursor up to top of current window
            if self._current_window_size > 0:
                self._ansi_cursor_up(self._current_window_size)

            # Get the lines to display (most recent ones)
            window = current_lines[-self._current_window_size :]

            # Clear and print each line in the window
            for line in window:
                render_line = self._sanitize_and_truncate(line)
                self._ansi_clear_line()
                print(render_line)

            sys.stdout.flush()
        else:
            # Non-ANSI fallback - print only newly captured lines since last update
            start = self._last_plain_printed
            end = len(self.full_output)
            if start < end:
                for line in self.full_output[start:end]:
                    print(self._sanitize_and_truncate(line))
                sys.stdout.flush()
                self._last_plain_printed = end

    def _clear_display(self) -> None:
        """Clear the streaming display area if output was shown."""
        # Only clear if we actually displayed output and have ANSI support
        if not (
            self.supports_ansi and self._has_output and self._current_window_size > 0
        ):
            return

        try:
            # Move up to start of window
            self._ansi_cursor_up(self._current_window_size)

            # Clear all lines in the window (we're already at the top)
            for i in range(self._current_window_size):
                print("\033[2K", end="")  # Clear entire line
                if i < self._current_window_size - 1:
                    print("\033[1B", end="")  # Move down to next line

            # Minimal terminal cleanup - just reset attributes and clear line
            print("\033[0m", end="")  # Reset ANSI attributes only
            print("\033[2K", end="")  # Clear current line
            print("\r", end="")  # Move cursor to beginning of line
            sys.stdout.flush()

            # Reset window state after clearing
            self._current_window_size = 0
            self._frame_initialized = False

        except OSError as e:
            # If ANSI cleanup fails, just reset state without clearing
            logger.debug("Failed to clear display: %s", e)
            self._current_window_size = 0
            self._frame_initialized = False
            # Even if clearing fails, try minimal terminal reset
            try:
                print("\033[0m\r", end="")
                sys.stdout.flush()
            except Exception:  # Last-resort cleanup - catch all
                pass

    def _ansi_cursor_up(self, n: int) -> None:
        """Move cursor up n lines using ANSI escape codes."""
        if n > 0:
            print(f"\033[{n}A", end="")

    def _ansi_clear_line(self) -> None:
        """Clear the current line using ANSI escape codes."""
        print("\033[K", end="")

    def _sanitize_and_truncate(self, s: str) -> str:
        """Sanitize and truncate a string for display."""
        # Normalize carriage-return based progress updates to final segment
        if "\r" in s:
            s = s.split("\r")[-1]
        # Remove ANSI escape sequences for width calculation
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
        clean_s = ansi_escape.sub("", s)

        # Truncate if needed
        if len(clean_s) > self.terminal_width:
            return s[: self.terminal_width - 3] + "..."
        return s

    def _start_subprocess(
        self,
        cmd: list[str],
        cwd: Path | None,
        env: dict[str, str] | None,
    ) -> subprocess.Popen:
        """Start subprocess with proper configuration.

        Parameters
        ----------
        cmd : list[str]
            Command to execute
        cwd : Path | None
            Working directory
        env : dict[str, str] | None
            Environment variables

        Returns
        -------
        subprocess.Popen
            Started process

        Raises
        ------
        FileNotFoundError
            If command executable is not found
        """
        # Handle Python commands with unbuffered output
        cmd_copy = cmd.copy()
        if cmd_copy[0] in ["python", "python3"]:
            cmd_copy = cmd_copy[:1] + ["-u"] + cmd_copy[1:]

        return subprocess.Popen(
            cmd_copy,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            text=True,
        )

    def _wait_for_completion(
        self,
        stdout_thread: threading.Thread,
        render_thread: threading.Thread,
        timeout: float | None,
    ) -> int:
        """Wait for process completion with optional timeout.

        Parameters
        ----------
        stdout_thread : threading.Thread
            Output reading thread
        render_thread : threading.Thread
            Render thread
        timeout : float | None
            Timeout in seconds

        Returns
        -------
        int
            Process return code

        Raises
        ------
        TimeoutError
            If process exceeds timeout
        """
        start_time = time.time()
        while self.process and self.process.poll() is None:
            if timeout and (time.time() - start_time) > timeout:
                if self.process:
                    self.process.terminate()
                    time.sleep(0.1)
                    if self.process and self.process.poll() is None:
                        self.process.kill()
                msg = f"Command timed out after {timeout} seconds"
                raise TimeoutError(msg)
            time.sleep(0.1)

        # Wait for threads to finish
        self._stop_event.set()
        stdout_thread.join(timeout=2)
        render_thread.join(timeout=2)

        return self.process.poll() or 0 if self.process else 0

    def _cleanup_process(self) -> None:
        """Clean up process and threads."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(0.1)
            if self.process.poll() is None:
                self.process.kill()
        self._stop_event.set()
