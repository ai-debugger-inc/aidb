"""Process termination utilities with SIGTERM->SIGKILL escalation."""

import asyncio
import os
import signal
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import psutil

from aidb.common.constants import PROCESS_TERMINATE_TIMEOUT_S, RECEIVE_POLL_TIMEOUT_S
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext


class ProcessTerminator(Obj):
    """Handle process termination with SIGTERM->SIGKILL escalation.

    Provides utilities for terminating processes and process groups
    with proper timeout handling and escalation strategies. This class
    encapsulates all signal handling and cleanup logic for debug adapter
    processes.

    Parameters
    ----------
    ctx : IContext, optional
        Application context for logging
    term_timeout : float, optional
        Default timeout (seconds) for SIGTERM before escalating to SIGKILL.
        Defaults to PROCESS_TERMINATE_TIMEOUT_S.
    kill_timeout : float, optional
        Default timeout (seconds) for SIGKILL confirmation.
        Defaults to RECEIVE_POLL_TIMEOUT_S.
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        term_timeout: float = PROCESS_TERMINATE_TIMEOUT_S,
        kill_timeout: float = RECEIVE_POLL_TIMEOUT_S,
    ) -> None:
        super().__init__(ctx=ctx)
        self._term_timeout = term_timeout
        self._kill_timeout = kill_timeout

    async def terminate_with_escalation(
        self,
        pid: int,
        kill_func: Callable[[int], None],
        target_desc: str,
        term_timeout: float | None = None,
        kill_timeout: float | None = None,
    ) -> bool:
        """Terminate a process with SIGTERM->SIGKILL escalation.

        Parameters
        ----------
        pid : int
            PID to check for termination
        kill_func : Callable[[int], None]
            Function to send signals (e.g., os.kill or os.killpg).
            Should accept a signal number as its argument.
        target_desc : str
            Description of target for logging
        term_timeout : float, optional
            Timeout after SIGTERM. Defaults to instance default.
        kill_timeout : float, optional
            Timeout after SIGKILL. Defaults to instance default.

        Returns
        -------
        bool
            True if process terminated
        """
        term_timeout = term_timeout or self._term_timeout
        kill_timeout = kill_timeout or self._kill_timeout

        # Try SIGTERM
        self.ctx.debug(f"Sending SIGTERM to {target_desc}")
        kill_func(signal.SIGTERM)
        if await self.wait_pid_terminate(pid, term_timeout):
            self.ctx.debug(f"PID {pid} terminated after SIGTERM")
            return True

        # Escalate to SIGKILL
        self.ctx.warning(
            f"PID {pid} still alive after SIGTERM; escalating to SIGKILL",
        )
        try:
            kill_func(signal.SIGKILL)
            if await self.wait_pid_terminate(pid, kill_timeout):
                self.ctx.debug(f"PID {pid} terminated after SIGKILL")
                return True
        except OSError as e:
            self.ctx.debug(f"Could not SIGKILL {target_desc}: {e}")
        return False

    async def wait_pid_terminate(self, pid: int, timeout: float) -> bool:
        """Wait for a PID to terminate up to timeout seconds.

        Parameters
        ----------
        pid : int
            Process ID to wait for
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if process has terminated (or does not exist), False on timeout.
        """
        try:
            p = psutil.Process(pid)
            await asyncio.wait_for(
                asyncio.create_task(asyncio.to_thread(p.wait)),
                timeout=timeout,
            )
            return True
        except psutil.NoSuchProcess:
            return True
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            self.ctx.debug(f"Error while waiting for PID {pid} termination: {e}")
            return False

    async def try_terminate_process_group(self, pid: int) -> bool | None:
        """Attempt to terminate the process group.

        Parameters
        ----------
        pid : int
            PID of a process in the group to terminate

        Returns
        -------
        bool | None
            True if terminated, False if failed, None if not applicable
            (e.g., on Windows where process groups are not supported)
        """
        if not hasattr(os, "killpg"):
            return None

        try:
            pgid = os.getpgid(pid)

            def kill_func(sig: int) -> None:
                os.killpg(pgid, sig)

            return await self.terminate_with_escalation(
                pid,
                kill_func,
                f"process group {pgid}",
                term_timeout=1.5,
                kill_timeout=0.5,
            )
        except (AttributeError, OSError) as e:
            self.ctx.debug(f"Could not terminate process group: {e}")
            return False

    async def try_terminate_process_directly(self, pid: int) -> bool:
        """Attempt to terminate the process directly.

        Parameters
        ----------
        pid : int
            PID to terminate

        Returns
        -------
        bool
            True if terminated or attempted
        """
        try:

            def kill_func(sig: int) -> None:
                os.kill(pid, sig)

            return await self.terminate_with_escalation(
                pid,
                kill_func,
                f"PID {pid}",
                term_timeout=1.0,
                kill_timeout=0.5,
            )
        except OSError as e:
            self.ctx.debug(f"Could not terminate process directly: {e}")
            return True  # We attempted

    async def terminate_process_group(self, attached_pid: int) -> bool:
        """Terminate the process group for an attached process.

        Tries process group termination first, then falls back to
        direct process termination if group termination is not available
        or fails.

        Parameters
        ----------
        attached_pid : int
            PID of the attached process whose group should be terminated

        Returns
        -------
        bool
            True if termination was attempted, False if skipped
        """
        if not attached_pid:
            return False

        # Try process group termination first
        group_result = await self.try_terminate_process_group(attached_pid)
        if group_result is True:
            return True

        # Fallback to direct process termination
        return await self.try_terminate_process_directly(attached_pid)

    async def cleanup_main_process(self, proc: asyncio.subprocess.Process) -> bool:
        """Clean up a main debug adapter process.

        Attempts graceful termination with SIGTERM, then escalates to
        SIGKILL if the process does not terminate within the timeout.

        Parameters
        ----------
        proc : asyncio.subprocess.Process
            The main process to clean up

        Returns
        -------
        bool
            True if cleanup was successful, False otherwise
        """
        if not proc or proc.returncode is not None:
            return True  # Already terminated

        try:
            args = getattr(proc, "args", None)
            timeout_s = self._term_timeout
            self.ctx.debug(
                f"Sending SIGTERM to main process "
                f"{proc.pid}; args={args}; waiting up to {timeout_s}s",
            )
            proc.terminate()

            # Wait for termination
            await asyncio.wait_for(proc.wait(), timeout=self._term_timeout)

            self.ctx.debug(f"Successfully terminated main process {proc.pid}")
            return True
        except (asyncio.TimeoutError, OSError) as e:
            self.ctx.warning(f"Process did not terminate gracefully: {e}")

            # Check if still running
            if proc.returncode is None:
                self.ctx.warning("Forcing process termination with SIGKILL")
                try:
                    self.ctx.debug(
                        f"Sending SIGKILL to main process "
                        f"{proc.pid}; waiting up to {self._kill_timeout}s",
                    )
                    proc.kill()

                    # Wait for kill to complete
                    await asyncio.wait_for(proc.wait(), timeout=self._kill_timeout)
                    self.ctx.debug(f"Force-killed main process {proc.pid}")
                    return True
                except (asyncio.TimeoutError, OSError) as e:
                    self.ctx.error(f"Failed to kill process: {e}")
                    return False
        return False

    async def terminate_processes_by_pattern(
        self,
        port: int | None,
        process_pattern: str,
    ) -> int:
        """Terminate debug adapter processes using port and pattern matching.

        This is a fallback cleanup method for orphaned processes that weren't
        properly registered with the ResourceManager.

        Parameters
        ----------
        port : int | None
            Port number to match in process command lines
        process_pattern : str
            Pattern to match in process names or command lines

        Returns
        -------
        int
            Number of processes terminated
        """
        if not port:
            self.ctx.debug("No port specified for pattern-based process termination")
            return 0

        terminated_count = 0

        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                if not self._should_terminate_process(proc, port, process_pattern):
                    continue

                terminated_count += await self._terminate_single_process(proc, port)

        except Exception as e:
            self.ctx.warning(f"Error in pattern-based process termination: {e}")

        if terminated_count > 0:
            self.ctx.info(f"Terminated {terminated_count} orphaned adapter processes")
        return terminated_count

    def _should_terminate_process(
        self,
        proc: psutil.Process,
        port: int,
        process_pattern: str,
    ) -> bool:
        """Check if a process should be terminated based on pattern and port.

        Parameters
        ----------
        proc : psutil.Process
            Process to check
        port : int
            Port number that should appear in command line
        process_pattern : str
            Pattern that should appear in command line

        Returns
        -------
        bool
            True if the process matches both pattern and port
        """
        try:
            cmdline = proc.info["cmdline"]
            if not cmdline:
                return False

            has_pattern = any(process_pattern in arg for arg in cmdline)
            has_port = any(str(port) in arg for arg in cmdline)
            return has_pattern and has_port

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.ctx.debug(f"Could not check process: {e}")
            return False

    async def _terminate_single_process(
        self,
        proc: psutil.Process,
        port: int,
    ) -> int:
        """Terminate a single process.

        Parameters
        ----------
        proc : psutil.Process
            Process to terminate
        port : int
            Port for logging purposes

        Returns
        -------
        int
            Success indicator (1 for success, 0 for failure)
        """
        try:
            pid = proc.info["pid"]
            cmdline = proc.info.get("cmdline")
            self.ctx.debug(
                f"Terminating orphaned debug adapter "
                f"process PID={pid} using port {port}; cmdline={cmdline}",
            )

            proc.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.create_task(asyncio.to_thread(proc.wait)),
                    timeout=self._term_timeout,
                )
                return 1
            except asyncio.TimeoutError:
                self.ctx.warning(
                    f"Debug adapter process PID={pid} did not terminate, killing",
                )
                proc.kill()
                return 1

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.ctx.debug(f"Could not terminate process: {e}")
            return 0
