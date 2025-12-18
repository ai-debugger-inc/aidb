"""Output capture utilities for debug adapters."""

import asyncio
import collections
from typing import TYPE_CHECKING, Any, Optional

from aidb.common import acquire_lock
from aidb.common.constants import EVENT_QUEUE_POLL_TIMEOUT_S
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class AdapterOutputCapture(Obj):
    """Captures stdout and stderr from adapter processes in circular buffers.

    This class prevents pipe blocking by continuously reading output from
    subprocess pipes in background threads. Output is stored in circular
    buffers with a maximum size to prevent memory issues.

    Attributes
    ----------
    max_buffer_size : int
        Maximum size of each output buffer in bytes (default 10KB)
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        max_buffer_size: int = 10 * 1024,  # 10KB default
        log_initial_output: bool = False,
    ):
        """Initialize output capture.

        Parameters
        ----------
        ctx : IContext, optional
            Application context for logging
        max_buffer_size : int
            Maximum size of each output buffer in bytes
        log_initial_output : bool
            If True, log the first few lines of output for debugging
        """
        super().__init__(ctx)
        self.max_buffer_size = max_buffer_size
        self.log_initial_output = log_initial_output
        # Add sync lock for thread-safe buffer access
        import threading

        self.lock = threading.RLock()

        # Circular buffers for captured output
        self._stdout_buffer: collections.deque[str] = collections.deque(
            maxlen=max_buffer_size,
        )
        self._stderr_buffer: collections.deque[str] = collections.deque(
            maxlen=max_buffer_size,
        )

        # Async tasks for subprocess output capture
        self._async_tasks: list[asyncio.Task] = []

        # Track if we've logged initial output
        self._logged_initial_stdout = False
        self._logged_initial_stderr = False
        self._initial_lines_to_log = 5

        # Stop event for async tasks
        self._stop_event = asyncio.Event()

        # Process reference (set when starting capture)
        self._process: Any | None = None

    async def start_capture_async(self, proc: asyncio.subprocess.Process) -> None:
        """Start capturing output from an async subprocess.

        Parameters
        ----------
        proc : asyncio.subprocess.Process
            The async subprocess to capture output from
        """
        self._process = proc

        # Start async tasks to read from stdout and stderr
        tasks = []
        if proc.stdout:
            tasks.append(
                asyncio.create_task(
                    self._read_stream_async(proc.stdout, self._stdout_buffer, "stdout"),
                ),
            )
            self.ctx.debug("Started async stdout capture task")

        if proc.stderr:
            tasks.append(
                asyncio.create_task(
                    self._read_stream_async(proc.stderr, self._stderr_buffer, "stderr"),
                ),
            )
            self.ctx.debug("Started async stderr capture task")

        # Store tasks for cleanup
        self._async_tasks = tasks

    async def _read_stream_async(
        self,
        stream: asyncio.StreamReader,
        buffer: collections.deque,
        name: str,
    ) -> None:
        """Read from an async stream continuously.

        Parameters
        ----------
        stream : asyncio.StreamReader
            The async stream to read from
        buffer : deque
            Buffer to store output in
        name : str
            Name of the stream (stdout/stderr)
        """
        lines_logged = 0
        try:
            while not self._stop_event.is_set():
                try:
                    # Read line with timeout
                    line = await asyncio.wait_for(
                        stream.readline(),
                        timeout=EVENT_QUEUE_POLL_TIMEOUT_S,
                    )
                    if not line:
                        break  # EOF

                    # Log initial output if requested
                    if (
                        self.log_initial_output
                        and lines_logged < self._initial_lines_to_log
                    ):
                        line_str = line.decode("utf-8", errors="replace").strip()
                        if line_str:
                            self.ctx.debug(
                                f"Adapter {name} (line {lines_logged + 1}): {line_str}",
                            )
                            lines_logged += 1

                    # Store in buffer
                    with self.lock:
                        for byte in line:
                            buffer.append(byte)

                    # Log errors
                    line_str = line.decode("utf-8", errors="replace").lower()
                    if "error" in line_str:
                        self.ctx.warning(
                            f"Adapter {name} ERROR: "
                            f"{line.strip().decode('utf-8', errors='replace')}",
                        )

                except asyncio.TimeoutError:
                    continue  # Check stop event and continue
                except Exception as e:
                    self.ctx.debug(f"Error reading {name}: {e}")
                    break

        except Exception as e:
            self.ctx.error(f"Fatal error in async {name} reader: {e}")
        finally:
            self.ctx.debug(f"Stopped async {name} capture")

    async def stop_capture_async(self) -> None:
        """Stop capturing output from async subprocess.

        Cancels async tasks and waits for them to complete.
        """
        self._stop_event.set()

        # Cancel async tasks
        for task in self._async_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._async_tasks:
            await asyncio.gather(*self._async_tasks, return_exceptions=True)

        self._async_tasks.clear()

    @acquire_lock
    def get_captured_output(self) -> tuple[str, str]:
        """Get the captured stdout and stderr.

        Returns
        -------
        Tuple[str, str]
            Captured stdout and stderr as strings
        """
        # Join the deque contents into strings, converting bytes to chars if needed
        stdout = "".join(
            chr(b) if isinstance(b, int) else str(b) for b in self._stdout_buffer
        )
        stderr = "".join(
            chr(b) if isinstance(b, int) else str(b) for b in self._stderr_buffer
        )

        return stdout, stderr

    @acquire_lock
    def get_recent_output(self, num_bytes: int = 1024) -> tuple[str, str]:
        """Get the most recent output from buffers.

        Parameters
        ----------
        num_bytes : int
            Number of recent bytes to retrieve

        Returns
        -------
        Tuple[str, str]
            Recent stdout and stderr as strings
        """
        # Get last N bytes from deque
        stdout_recent = []
        for i in range(min(num_bytes, len(self._stdout_buffer))):
            b = self._stdout_buffer[-(i + 1)]
            stdout_recent.append(chr(b) if isinstance(b, int) else str(b))
        stdout_recent.reverse()
        stdout = "".join(stdout_recent)

        # Get last N bytes from deque
        stderr_recent = []
        for i in range(min(num_bytes, len(self._stderr_buffer))):
            b = self._stderr_buffer[-(i + 1)]
            stderr_recent.append(chr(b) if isinstance(b, int) else str(b))
        stderr_recent.reverse()
        stderr = "".join(stderr_recent)

        return stdout, stderr

    @acquire_lock
    def clear_buffers(self) -> None:
        """Clear both output buffers."""
        self._stdout_buffer.clear()
        self._stderr_buffer.clear()
