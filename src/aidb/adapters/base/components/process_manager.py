"""Process management component for debug adapters.

This module handles all process lifecycle operations for debug adapters, including
launching, monitoring, stopping, and cleaning up orphaned processes.
"""

import asyncio
import os
import signal
import time
from typing import TYPE_CHECKING, Optional

import psutil

from aidb.adapters.utils.output_capture import AdapterOutputCapture
from aidb.common.constants import (
    BACKOFF_MULTIPLIER,
    DEFAULT_ADAPTER_HOST,
    EVENT_POLL_TIMEOUT_S,
    INITIAL_RETRY_DELAY_S,
    MAX_PROCESS_WAIT_TIME_S,
    MEDIUM_SLEEP_S,
    PROCESS_CLEANUP_MIN_AGE_S,
    PROCESS_COMMUNICATE_TIMEOUT_S,
    PROCESS_STARTUP_DELAY_S,
    PROCESS_WAIT_TIMEOUT_S,
    RECEIVE_POLL_TIMEOUT_S,
)
from aidb.common.errors import DebugAdapterError, DebugConnectionError
from aidb.patterns.base import Obj
from aidb.resources.ports import PortHandler
from aidb.resources.process_tags import ProcessTags
from aidb_common.io import is_event_loop_error

if TYPE_CHECKING:
    from aidb.adapters.base.config import AdapterConfig
    from aidb.interfaces.context import IContext


class ProcessManager(Obj):
    """Manages process lifecycle for debug adapters.

    This class encapsulates all process-related operations including:
        - Launching debug adapter processes
        - Monitoring process health
        - Stopping processes gracefully
        - Cleaning up orphaned processes
        - Managing output capture

    Parameters
    ----------
    ctx : IContext, optional
        Context for logging and resource management
    adapter_host : str, optional
        Host where the debug adapter will bind (default: "localhost")
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        adapter_host: str = DEFAULT_ADAPTER_HOST,
        config: Optional["AdapterConfig"] = None,
    ):
        """Initialize process manager.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging
        adapter_host : str
            Host for adapter process
        config : AdapterConfig, optional
            Adapter configuration (for timeout values)
        """
        super().__init__(ctx)
        self.adapter_host = adapter_host
        self.config = config
        self._proc: asyncio.subprocess.Process | None = None
        self._attached_pid: int | None = None
        self._output_capture: AdapterOutputCapture | None = None

    @property
    def pid(self) -> int | None:
        """Get the process ID of the debug adapter.

        Returns
        -------
        Optional[int]
            Process ID or None if not running
        """
        return self._attached_pid or (self._proc.pid if self._proc else None)

    @property
    def is_alive(self) -> bool:
        """Check if the process is still running.

        Returns
        -------
        bool
            True if the process is alive, False otherwise
        """
        if self._proc:
            return self._proc.returncode is None
        return False

    async def launch_subprocess(
        self,
        cmd: list[str],
        env: dict[str, str],
        session_id: str,
        language: str,
        process_type: str = "adapter",
        kwargs: dict | None = None,
    ) -> asyncio.subprocess.Process:
        """Launch the debug adapter subprocess with output capture.

        All AIDB-spawned processes are tagged with environment variables to enable
        safe orphan detection and cleanup.

        Parameters
        ----------
        cmd : List[str]
            Command and arguments to launch
        env : Dict[str, str]
            Environment variables for the process
        session_id : str
            Session ID that owns this process
        language : str
            Programming language (python, java, javascript)
        process_type : str, optional
            Type of process (adapter or debuggee), default: "adapter"
        kwargs : Dict, optional
            Additional keyword arguments for create_subprocess_exec

        Returns
        -------
        asyncio.subprocess.Process
            The launched async process

        Raises
        ------
        RuntimeError
            If process exits immediately after launch
        """
        if kwargs is None:
            kwargs = {}

        # Inject AIDB ownership markers into environment
        tagged_env = env.copy()
        tagged_env.update(
            {
                ProcessTags.OWNER: ProcessTags.OWNER_VALUE,
                ProcessTags.SESSION_ID: session_id,
                ProcessTags.PROCESS_TYPE: process_type,
                ProcessTags.LANGUAGE: language,
                ProcessTags.START_TIME: str(int(time.time())),
            },
        )

        self.ctx.info(f"Launching adapter with command: {' '.join(cmd)}")
        self.ctx.debug(
            f"Process tags: session_id={session_id}, type={process_type}, "
            f"language={language}",
        )

        # Use full async subprocess
        self._proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=tagged_env,
            **kwargs,
        )

        # Log the process PID
        self.ctx.info(f"Adapter process started with PID: {self._proc.pid}")

        # Give process a moment to start
        await asyncio.sleep(PROCESS_STARTUP_DELAY_S)

        # Verify process is still running
        if self._proc.returncode is not None:
            # Try to get stderr to see why it failed
            try:
                stdout, stderr = await asyncio.wait_for(
                    self._proc.communicate(),
                    timeout=PROCESS_WAIT_TIMEOUT_S,
                )
                if stderr:
                    stderr_text = stderr.decode("utf-8", errors="replace")
                    self.ctx.error(f"Adapter stderr: {stderr_text}")
                if stdout:
                    stdout_text = stdout.decode("utf-8", errors="replace")
                    self.ctx.debug(f"Adapter stdout: {stdout_text}")
            except Exception as e:
                self.ctx.debug(f"Could not get adapter output: {e}")

            error_msg = (
                f"Adapter process exited immediately with code: {self._proc.returncode}"
            )
            self.ctx.error(error_msg)
            raise DebugAdapterError(error_msg, summary="Adapter startup failed")
        self.ctx.debug("Adapter process is running")

        # Start async output capture
        self._output_capture = AdapterOutputCapture(
            ctx=self.ctx,
            log_initial_output=True,
        )
        # We'll need to update start_capture to handle async processes
        await self._output_capture.start_capture_async(self._proc)
        self.ctx.debug("Started async output capture for adapter process")

        return self._proc

    async def wait_for_adapter_ready(
        self,
        port: int,
        start_time: float,
        max_retries: int = 3,
        base_timeout: float = 3.0,
        max_total_time: float = MAX_PROCESS_WAIT_TIME_S,
    ) -> None:
        """Wait for the debug adapter to be ready for connections.

        Uses exponential backoff for connection attempts to handle slow-starting
        adapters.

        Parameters
        ----------
        port : int
            Port number the adapter should be listening on
        start_time : float
            Time when the launch started (from time.monotonic())
        max_retries : int, optional
            Maximum number of connection attempts
        base_timeout : float, optional
            Initial timeout in seconds
        max_total_time : float, optional
            Maximum total time to wait in seconds

        Raises
        ------
        DebugConnectionError
            If the adapter doesn't become ready within the timeout
        """
        if not self._proc:
            msg = "No process to wait for"
            raise DebugAdapterError(msg)

        port_handler = PortHandler(host=self.adapter_host, ctx=self.ctx)

        for attempt in range(max_retries):
            # Calculate timeout with exponential backoff
            timeout = min(base_timeout * (2**attempt), max_total_time)
            elapsed = time.monotonic() - start_time

            if elapsed >= max_total_time:
                msg = f"Timeout waiting for port {port} after {elapsed:.1f}s"
                raise DebugConnectionError(
                    msg,
                    summary="Connection timeout",
                )

            self.ctx.debug(
                f"Connection attempt {attempt + 1}/{max_retries} "
                f"with timeout {timeout:.1f}s",
            )

            # Check if process is still alive
            if self._proc.returncode is not None:
                msg = f"Debug adapter exited with code {self._proc.returncode}"
                self.ctx.error(msg)
                await self.log_process_output()
                raise DebugConnectionError(msg, summary="Adapter process exited")

            # Try to connect with current timeout
            # Pass detached_process_names for adapters that spawn detached processes
            # (e.g., debugpy spawns adapter with PPID=1)
            detached_names = self.config.detached_process_names if self.config else None
            if await port_handler.wait_for_port(
                port,
                proc=self._proc,
                timeout=timeout,
                detached_process_names=detached_names,
            ):
                self.ctx.debug(
                    f"Port {port} ready after {time.monotonic() - start_time:.3f}s",
                )
                return

            # If not last attempt, wait before retrying
            if attempt < max_retries - 1:
                backoff_delay = INITIAL_RETRY_DELAY_S * (BACKOFF_MULTIPLIER**attempt)
                self.ctx.debug(
                    f"Port not ready, waiting {backoff_delay:.1f}s before retry",
                )
                await asyncio.sleep(backoff_delay)

        # All retries exhausted
        if self._proc.returncode is not None:
            msg = f"Debug adapter exited with code {self._proc.returncode}"
            self.ctx.error(msg)
            await self.log_process_output()
            raise DebugConnectionError(msg, summary="Adapter process exited")
        msg = f"Failed to connect to port {port} after {max_retries} attempts"
        raise DebugConnectionError(
            msg,
            summary="Connection failed",
        )

    def _terminate_child_processes(
        self,
        children: list[psutil.Process],
    ) -> None:
        """Terminate all child processes.

        Parameters
        ----------
        children : list[psutil.Process]
            List of child processes to terminate
        """
        for child in children:
            try:
                self.ctx.debug(f"Terminating child process {child.pid}")
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                self.ctx.debug(f"Could not terminate child {child.pid}: {e}")

    def _kill_remaining_children(
        self,
        children: list[psutil.Process],
    ) -> None:
        """Force kill any remaining child processes.

        Parameters
        ----------
        children : list[psutil.Process]
            List of child processes to force kill
        """
        for child in children:
            try:
                if child.is_running():
                    self.ctx.debug(
                        f"Force killing child process {child.pid}",
                    )
                    child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                self.ctx.debug(f"Could not kill child {child.pid}: {e}")

    async def stop(self) -> None:
        """Stop the debug adapter and attached processes.

        This method is resilient to event loop mismatches that can occur during pytest-
        xdist parallel test execution. If async operations fail due to event loop
        issues, it falls back to synchronous process termination.
        """
        self.ctx.debug("Stopping managed processes")
        await self._stop_output_capture()
        await self._stop_adapter_process()
        await self._stop_attached_process()

        # Clear internal state
        self._attached_pid = None
        self._proc = None
        self._output_capture = None
        self.ctx.debug("Managed processes stopped")

    async def _stop_output_capture(self) -> None:
        """Stop output capture with event loop safety."""
        if not self._output_capture:
            return

        try:
            await self._output_capture.stop_capture_async()
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"Output capture stop skipped (event loop): {e}")
            else:
                raise

        stdout, stderr = self._output_capture.get_captured_output()
        if stdout:
            self.ctx.debug(f"Adapter stdout (last 500 chars): ...{stdout[-500:]}")
        if stderr:
            self.ctx.debug(f"Adapter stderr (last 500 chars): ...{stderr[-500:]}")

    async def _stop_adapter_process(self) -> None:
        """Stop the adapter process tree with event loop safety."""
        if not (self._proc and self._proc.pid):
            return

        try:
            parent = psutil.Process(self._proc.pid)
            children = parent.children(recursive=True)
            self._terminate_child_processes(children)
            self._proc.terminate()

            await self._wait_for_process_exit(children)
            await self._close_process_transports()

        except (ProcessLookupError, OSError, psutil.NoSuchProcess) as e:
            self.ctx.debug(f"Process already terminated or error stopping: {e}")

    async def _wait_for_process_exit(
        self,
        children: list[psutil.Process],
    ) -> None:
        """Wait for process exit with timeout and event loop safety.

        Note: Caller must ensure self._proc is not None before calling.
        """
        # Guard against None (should never happen if called correctly)
        if not self._proc:
            return

        timeout = (
            self.config.process_manager_timeout
            if self.config
            else PROCESS_WAIT_TIMEOUT_S
        )
        try:
            await asyncio.wait_for(self._proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._kill_remaining_children(children)
            self._proc.kill()
            await self._safe_wait_after_kill()
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"Async wait failed (event loop), using sync kill: {e}")
                self._kill_remaining_children(children)
                self._proc.kill()
                self._sync_wait_for_exit()
            else:
                raise

    async def _safe_wait_after_kill(self) -> None:
        """Wait for process after kill, handling event loop errors.

        Note: Caller must ensure self._proc is not None before calling.
        Falls back to synchronous wait if async fails.
        """
        # Guard against None (should never happen if called correctly)
        if not self._proc:
            return

        try:
            await asyncio.wait_for(
                self._proc.wait(),
                timeout=RECEIVE_POLL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            # Async wait timed out, use sync polling as fallback
            self.ctx.debug("Async wait timed out after kill, using sync fallback")
            self._sync_wait_for_exit()
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"Process wait failed (event loop), sync fallback: {e}")
                self._sync_wait_for_exit()
            else:
                raise

    def _sync_wait_for_exit(self, timeout: float = 2.0) -> None:
        """Synchronize wait for process exit when async is unavailable.

        Used as fallback when event loop mismatch prevents async wait.
        Polls process status until exit or timeout.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds
        """
        if not self._proc or not self._proc.pid:
            return

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.returncode is not None:
                self.ctx.debug(f"Process {self._proc.pid} exited (sync wait)")
                return
            try:
                os.kill(self._proc.pid, 0)  # Check if alive
                time.sleep(0.1)
            except OSError:
                self.ctx.debug(f"Process {self._proc.pid} no longer exists")
                return

        self.ctx.warning(f"Process {self._proc.pid} did not exit within {timeout}s")

    async def _close_process_transports(self) -> None:
        """Close subprocess transports with event loop safety."""
        from aidb_common.io.subprocess import close_subprocess_transports

        try:
            await close_subprocess_transports(self._proc, self.ctx, "Adapter")
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"Transport close skipped (event loop): {e}")
            else:
                raise

    async def _stop_attached_process(self) -> None:
        """Stop any separately attached process."""
        if not self._attached_pid or self._attached_pid == (
            self._proc.pid if self._proc else None
        ):
            return

        try:
            os.kill(self._attached_pid, signal.SIGTERM)
            # Brief wait before checking - handle event loop mismatch
            try:
                await asyncio.sleep(MEDIUM_SLEEP_S)
            except RuntimeError as e:
                if is_event_loop_error(e):
                    # Event loop mismatch - skip async sleep (process is already
                    # signaled, will be killed below if still running)
                    pass
                else:
                    raise
            # Check if still running and force kill if needed
            try:
                os.kill(self._attached_pid, 0)  # Check if still alive
                os.kill(self._attached_pid, signal.SIGKILL)  # Force kill
            except OSError:
                pass  # Process already dead
        except (ProcessLookupError, OSError) as e:
            self.ctx.debug(
                f"Attached process already terminated or error stopping: {e}",
            )

    def attach_pid(self, pid: int) -> None:
        """Attach to an existing process for management.

        Parameters
        ----------
        pid : int
            Process ID to attach to
        """
        self._attached_pid = pid
        self.ctx.debug(f"Attached to process PID={pid}")

    async def log_process_output(self) -> None:
        """Log the process output for debugging."""
        if not self._proc:
            return

        try:
            stdout, stderr = await asyncio.wait_for(
                self._proc.communicate(),
                timeout=EVENT_POLL_TIMEOUT_S,
            )
            if stdout:
                self.ctx.debug(
                    f"Process stdout: {stdout.decode('utf-8', errors='replace')}",
                )
            if stderr:
                self.ctx.debug(
                    f"Process stderr: {stderr.decode('utf-8', errors='replace')}",
                )
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            self.ctx.debug(f"Could not get process output: {e}")

    def cleanup_orphaned_processes(
        self,
        pattern: str,
        min_age_seconds: float = PROCESS_CLEANUP_MIN_AGE_S,
        max_scan_ms: float | None = None,
    ) -> dict[str, int]:
        """Clean up orphaned debug adapter processes with optional time budget.

        This should only be called during adapter initialization to clean up
        processes from previous crashed sessions.

        Parameters
        ----------
        pattern : str
            Pattern to match in process command lines
        min_age_seconds : float, optional
            Minimum age in seconds for a process to be considered orphaned
        max_scan_ms : float | None, optional
            Maximum time in milliseconds to spend scanning processes.
            If exceeded, scanning stops early. None means no limit.

        Returns
        -------
        dict[str, int]
            Statistics: {"scanned": N, "matched": M, "killed": K, "elapsed_ms": X}
        """
        start_time = time.monotonic()
        stats = {"scanned": 0, "matched": 0, "killed": 0, "elapsed_ms": 0}

        try:
            orphans = self._find_orphaned_processes(
                pattern,
                min_age_seconds,
                max_scan_ms=max_scan_ms,
                stats=stats,
            )

            for proc in orphans:
                self._terminate_process_gracefully(proc)
                stats["killed"] += 1

            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            stats["elapsed_ms"] = elapsed_ms

            if orphans:
                self.ctx.info(
                    f"[ORPHAN] Cleaned up {len(orphans)} orphaned processes: "
                    f"scanned={stats['scanned']}, matched={stats['matched']}, "
                    f"killed={stats['killed']} ({stats['elapsed_ms']}ms)",
                )

        except Exception as e:
            self.ctx.warning(f"Failed to clean up orphaned processes: {e}")

        return stats

    def _has_aidb_tag(self, proc: psutil.Process) -> bool:
        """Check if process has AIDB ownership tag.

        Parameters
        ----------
        proc : psutil.Process
            Process to check

        Returns
        -------
        bool
            True if process has AIDB tag, False otherwise
        """
        try:
            env = proc.environ()
            owner = env.get(ProcessTags.OWNER, "")
            return owner == ProcessTags.OWNER_VALUE
        except Exception:
            return False

    def _is_parent_missing(self, proc: psutil.Process) -> bool:
        """Check if process parent is missing or not running.

        Parameters
        ----------
        proc : psutil.Process
            Process to check

        Returns
        -------
        bool
            True if process is orphaned (parent missing), False otherwise
        """
        # Check if truly orphaned (ppid=1) or parent doesn't exist
        if proc.info["ppid"] == 1:
            return True

        # Check if parent process exists
        try:
            parent = psutil.Process(proc.info["ppid"])
            return not parent.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Parent doesn't exist or we can't access it
            return True

    def _should_consider_orphan(
        self,
        proc: psutil.Process,
        pattern: str,
        min_age_seconds: float,
        current_time: float,
        registered_pids: set,
        tags_only: bool,
    ) -> bool:
        """Check if process should be considered an orphan.

        Parameters
        ----------
        proc : psutil.Process
            Process to check
        pattern : str
            Pattern to match in cmdline
        min_age_seconds : float
            Minimum age for orphan consideration
        current_time : float
            Current timestamp
        registered_pids : set
            Set of registered process IDs
        tags_only : bool
            Whether to require AIDB tags

        Returns
        -------
        bool
            True if process should be considered an orphan, False otherwise
        """
        # Skip if registered
        if proc.info["pid"] in registered_pids:
            return False

        # Check pattern match
        cmd = proc.info["cmdline"]
        if not (cmd and pattern in " ".join(cmd)):
            return False

        # Check ownership tag if required
        if tags_only and not self._has_aidb_tag(proc):
            return False

        # Check age
        process_age = current_time - proc.info["create_time"]
        if process_age < min_age_seconds:
            self.ctx.debug(
                f"Skipping young process PID={proc.info['pid']} "
                f"(age={process_age:.1f}s)",
            )
            return False

        # Check if parent is missing
        return self._is_parent_missing(proc)

    def _find_orphaned_processes(
        self,
        pattern: str,
        min_age_seconds: float,
        max_scan_ms: float | None = None,
        stats: dict | None = None,
    ) -> list[psutil.Process]:
        """Find orphaned debug adapter processes with optional time budget.

        Only considers processes orphaned if they: 1. Match the debug adapter
        pattern 2. Have been running for > min_age_seconds (avoid race with
        startup) 3. Are not registered with any active session

        Parameters
        ----------
        pattern : str
            Pattern to match in process command lines
        min_age_seconds : float
            Minimum age for a process to be considered orphaned
        max_scan_ms : float | None, optional
            Maximum time in milliseconds to spend scanning.
            If exceeded, scanning stops early. None means no limit.
        stats : dict | None, optional
            Statistics dictionary to update with scan metrics

        Returns
        -------
        List[psutil.Process]
            List of orphaned processes
        """
        start_time = time.monotonic()
        orphans = []
        current_time = time.time()

        # Get all registered PIDs from the process registry
        registered_pids = set()
        try:
            from aidb.resources.pids import ProcessRegistry

            # ProcessRegistry is now a singleton with proper API
            registry = ProcessRegistry()
            registered_pids = registry.get_all_registered_pids()
        except Exception as e:
            self.ctx.debug(f"Could not get registered PIDs: {e}")

        # Determine whether to require AIDB ownership tags for cleanup
        try:
            from aidb_common.env import reader as env_reader

            tags_only = env_reader.read_bool("AIDB_ORPHAN_TAGS_ONLY", True)
        except Exception:
            tags_only = True

        for proc in psutil.process_iter(["pid", "ppid", "cmdline", "create_time"]):
            # Check time budget before processing each process
            if max_scan_ms is not None:
                elapsed_ms = (time.monotonic() - start_time) * 1000
                if elapsed_ms > max_scan_ms:
                    scanned_count = stats.get("scanned", 0) if stats else 0
                    self.ctx.warning(
                        f"[ORPHAN] Scan budget exceeded ({max_scan_ms:.0f}ms), "
                        f"stopping early (scanned={scanned_count})",
                    )
                    break

            if stats is not None:
                stats["scanned"] += 1

            try:
                # Check if should be considered an orphan
                if self._should_consider_orphan(
                    proc,
                    pattern,
                    min_age_seconds,
                    current_time,
                    registered_pids,
                    tags_only,
                ):
                    if stats is not None:
                        stats["matched"] += 1
                    orphans.append(proc)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return orphans

    def _terminate_process_gracefully(self, proc: psutil.Process) -> None:
        """Terminate a process gracefully, escalating to kill if needed.

        Parameters
        ----------
        proc : psutil.Process
            Process to terminate
        """
        try:
            self.ctx.info(f"Cleaning up orphaned debug adapter process PID={proc.pid}")
            proc.terminate()
            try:
                proc.wait(timeout=PROCESS_COMMUNICATE_TIMEOUT_S)
            except psutil.TimeoutExpired:
                proc.kill()
        except Exception as e:
            self.ctx.warning(
                f"Failed to terminate debug adapter process "
                f"PID={getattr(proc, 'pid', proc)}: {e}",
            )

    def get_captured_output(self) -> tuple[str, str] | None:
        """Get captured stdout and stderr from the adapter process.

        Returns
        -------
        Optional[Tuple[str, str]]
            Tuple of (stdout, stderr) if output capture is active, None otherwise
        """
        if self._output_capture:
            return self._output_capture.get_captured_output()
        return None
