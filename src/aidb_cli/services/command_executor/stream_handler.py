"""Rolling window output streaming for subprocess commands."""

import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from aidb.common.errors import AidbError
from aidb_cli.core.constants import THREAD_JOIN_TIMEOUT_S, CliTimeouts, ExitCode
from aidb_cli.core.utils import CliOutput
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class StreamHandler:
    """Rolling window display for subprocess output.

    Provides a terminal-friendly rolling window that shows the most recent N lines of
    output, updating in place using ANSI escape codes.
    """

    def __init__(
        self,
        max_lines: int = 8,
        clear_on_exit: bool = True,
        supports_ansi: bool = True,
        terminal_width: int = 80,
    ) -> None:
        """Initialize stream handler.

        Parameters
        ----------
        max_lines : int
            Maximum lines in rolling window
        clear_on_exit : bool
            Whether to clear output on exit
        supports_ansi : bool
            Whether ANSI escape codes are supported
        terminal_width : int
            Terminal width for line truncation
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
        self._min_render_interval = 0.08  # 80ms throttle
        self._last_render_time = 0.0
        self._has_output = False
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
        cwd : Path, optional
            Working directory
        env : dict[str, str], optional
            Environment variables
        timeout : float, optional
            Timeout in seconds
        check : bool
            Whether to raise on non-zero exit

        Returns
        -------
        subprocess.CompletedProcess[str]
            Result of command execution
        """
        self._reset_state()

        try:
            self.process = self._start_subprocess(cmd, cwd, env)

            stdout_thread = threading.Thread(
                target=self._read_stream,
                args=(self.process.stdout,),
            )
            stdout_thread.start()

            render_thread = threading.Thread(target=self._render_loop)
            render_thread.start()

            returncode = self._wait_for_completion(
                stdout_thread,
                render_thread,
                timeout,
            )

            if self.clear_on_exit and self._has_output:
                self._clear_display()

            if self._has_output:
                CliOutput.plain("")

            output = "\n".join(self.full_output)

            if check and returncode != 0:
                error_msg = f"Command failed (exit {returncode}): {' '.join(cmd)}"
                raise AidbError(error_msg)

            return subprocess.CompletedProcess(cmd, returncode, output, "")

        except FileNotFoundError as e:
            error_msg = f"Command not found: {cmd[0]}"
            if check:
                raise AidbError(error_msg) from e
            return subprocess.CompletedProcess(cmd, ExitCode.NOT_FOUND, "", str(e))
        finally:
            self._cleanup_process()

    def _reset_state(self) -> None:
        """Reset internal state for new run."""
        self.display_lines.clear()
        self.full_output.clear()
        self._stop_event.clear()
        self._frame_initialized = False
        self._current_window_size = 0
        self._last_render_time = 0.0
        self._has_output = False
        self._last_plain_printed = 0

    def _read_stream(self, stream) -> None:
        """Read from stream and update output buffers."""
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
        """Continuously render rolling window with throttling."""
        try:
            while not self._stop_event.is_set():
                current_time = time.time()
                if current_time - self._last_render_time >= self._min_render_interval:
                    self._update_display()
                    self._last_render_time = current_time
                time.sleep(CliTimeouts.STREAM_MIN_POLL_INTERVAL_S)
            self._update_display()  # Final update
        except (OSError, ValueError) as e:
            logger.debug("Error in render loop: %s", e)

    def _update_display(self) -> None:
        """Update rolling display with recent output."""
        with self._display_lock:
            current_lines = list(self.display_lines)

        if not current_lines:
            return

        if not self._has_output:
            self._has_output = True

        if self.supports_ansi:
            self._update_ansi_display(current_lines)
        else:
            self._update_plain_display()

    def _update_ansi_display(self, current_lines: list[str]) -> None:
        """Update display using ANSI escape codes."""
        lines_to_display = min(len(current_lines), self.max_lines)

        if not self._frame_initialized:
            CliOutput.plain("")
            self._frame_initialized = True
            self._current_window_size = 0

        if lines_to_display > self._current_window_size:
            for _ in range(lines_to_display - self._current_window_size):
                print("")
            self._current_window_size = lines_to_display

        if self._current_window_size > 0:
            print(f"\033[{self._current_window_size}A", end="")

        window = current_lines[-self._current_window_size :]
        for line in window:
            print("\033[K", end="")  # Clear line
            print(self._sanitize_and_truncate(line))

        sys.stdout.flush()

    def _update_plain_display(self) -> None:
        """Update display without ANSI codes (fallback)."""
        start = self._last_plain_printed
        end = len(self.full_output)
        if start < end:
            for line in self.full_output[start:end]:
                print(self._sanitize_and_truncate(line))
            sys.stdout.flush()
            self._last_plain_printed = end

    def _clear_display(self) -> None:
        """Clear the streaming display area."""
        should_clear = (
            self.supports_ansi and self._has_output and self._current_window_size > 0
        )
        if not should_clear:
            return

        try:
            print(f"\033[{self._current_window_size}A", end="")
            for i in range(self._current_window_size):
                print("\033[2K", end="")
                if i < self._current_window_size - 1:
                    print("\033[1B", end="")
            print("\033[0m\033[2K\r", end="")
            sys.stdout.flush()
            self._current_window_size = 0
            self._frame_initialized = False
        except OSError:
            self._current_window_size = 0
            self._frame_initialized = False

    def _sanitize_and_truncate(self, s: str) -> str:
        """Sanitize and truncate string for display."""
        if "\r" in s:
            s = s.split("\r")[-1]
        # Remove ANSI for width calculation
        clean_s = re.sub(r"\x1b\[[0-9;]*m", "", s)
        if len(clean_s) > self.terminal_width:
            return s[: self.terminal_width - 3] + "..."
        return s

    def _start_subprocess(
        self,
        cmd: list[str],
        cwd: Path | None,
        env: dict[str, str] | None,
    ) -> subprocess.Popen:
        """Start subprocess with proper configuration."""
        cmd_copy = cmd.copy()
        if cmd_copy[0] in ("python", "python3"):
            cmd_copy = cmd_copy[:1] + ["-u"] + cmd_copy[1:]

        return subprocess.Popen(  # noqa: S603
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
        """Wait for process completion with optional timeout."""
        start_time = time.time()
        while self.process and self.process.poll() is None:
            if timeout and (time.time() - start_time) > timeout:
                if self.process:
                    self.process.terminate()
                    time.sleep(CliTimeouts.STREAM_POLL_INTERVAL_S)
                    if self.process and self.process.poll() is None:
                        self.process.kill()
                msg = f"Command timed out after {timeout} seconds"
                raise TimeoutError(msg)
            time.sleep(CliTimeouts.STREAM_POLL_INTERVAL_S)

        self._stop_event.set()
        stdout_thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
        render_thread.join(timeout=THREAD_JOIN_TIMEOUT_S)

        return self.process.poll() or 0 if self.process else 0

    def _cleanup_process(self) -> None:
        """Clean up process and threads."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(CliTimeouts.STREAM_POLL_INTERVAL_S)
            if self.process.poll() is None:
                self.process.kill()
        self._stop_event.set()


# Backward compatibility alias
StreamHandlerService = StreamHandler
