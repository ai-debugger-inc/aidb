"""Process registry for tracking and managing debug processes."""

import asyncio
import os
import signal
import threading
from typing import TYPE_CHECKING, Any, Optional

from aidb.common import acquire_lock
from aidb.common.constants import PROCESS_WAIT_TIMEOUT_S
from aidb.patterns import Obj
from aidb_common.patterns import Singleton
from aidb_logging.utils import LogOnce

if TYPE_CHECKING:
    from aidb.interfaces import IContext


class ProcessRegistry(Singleton["ProcessRegistry"], Obj):
    """Registry for tracking and managing debug processes.

    The registry uses process groups (on Unix systems) to ensure all child processes are
    terminated properly, preventing process leaks.
    """

    _initialized: bool

    def __init__(self, ctx: Optional["IContext"] = None) -> None:
        """Initialize the process registry.

        Parameters
        ----------
        ctx : IContext, optional
            Application context
        """
        super().__init__(ctx)
        # Add sync lock for thread-safe process management
        self.lock = threading.RLock()
        # Check if already initialized (singleton pattern)
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._processes: dict[str, dict[int, asyncio.subprocess.Process]] = {}
        self._process_groups: dict[str, set[int]] = {}
        self._initialized = True
        LogOnce.debug(
            self.ctx,
            "process_registry_init",
            "ProcessRegistry singleton initialized",
        )

    @acquire_lock
    def register_process(
        self,
        session_id: str,
        proc: asyncio.subprocess.Process,
        use_process_group: bool = True,
    ) -> int:
        """Register a process with the registry.

        Parameters
        ----------
        session_id : str
            The session ID that owns this process
        proc : asyncio.subprocess.Process
            The process to register
        use_process_group : bool, default=True
            Whether to use process groups for this process

        Returns
        -------
        int
            PID of the registered process
        """
        if session_id not in self._processes:
            self._processes[session_id] = {}
            self._process_groups[session_id] = set()

        pid = proc.pid
        self._processes[session_id][pid] = proc

        if use_process_group:
            try:
                pgid = os.getpgid(pid)
                self._process_groups[session_id].add(pgid)
                self.ctx.debug(
                    f"Registered process group {pgid} for session {session_id}",
                )
            except (AttributeError, OSError) as e:
                # Windows or process no longer exists
                self.ctx.warning(f"Could not get process group for PID {pid}: {e}")

        self.ctx.debug(f"Registered process {pid} for session {session_id}")
        return pid

    @acquire_lock
    def unregister_process(self, session_id: str, pid: int) -> None:
        """Unregister a process from the registry.

        Parameters
        ----------
        session_id : str
            The session ID that owns this process
        pid : int
            PID of the process to unregister
        """
        if session_id in self._processes and pid in self._processes[session_id]:
            del self._processes[session_id][pid]
            self.ctx.debug(f"Unregistered process {pid} from session {session_id}")

    def _terminate_process_groups(self, session_id: str) -> None:
        """Terminate process groups for a session.

        Parameters
        ----------
        session_id : str
            The session ID
        """
        if session_id not in self._process_groups:
            return

        pgids = list(self._process_groups[session_id])
        self.ctx.debug(
            f"Attempting SIGTERM for {len(pgids)} process group(s): {pgids}",
        )
        for pgid in pgids:
            try:
                os.killpg(pgid, signal.SIGTERM)
                self.ctx.debug(f"Sent SIGTERM to process group {pgid}")
            except (AttributeError, OSError) as e:
                self.ctx.warning(f"Failed to terminate process group {pgid}: {e}")

    async def _terminate_single_process(
        self,
        pid: int,
        proc: Any,
        timeout: float,
        force: bool,
    ) -> tuple[bool, bool]:
        """Terminate a single process.

        Parameters
        ----------
        pid : int
            Process ID
        proc : Any
            Process object
        timeout : float
            Timeout for graceful termination
        force : bool
            If True, use SIGKILL after timeout

        Returns
        -------
        tuple[bool, bool]
            (terminated_success, failed)
        """
        # Check if process is still running
        if proc.returncode is not None:
            self.ctx.debug(
                f"Process {pid} already terminated with code "
                f"{getattr(proc, 'returncode', None)}",
            )
            return (True, False)

        # Attempt graceful termination
        self.ctx.debug(f"Terminating process {pid}")
        proc.terminate()
        self.ctx.debug(
            f"Sent SIGTERM to process {pid}; waiting up to {timeout:.1f}s",
        )

        # Wait for process to terminate
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            self.ctx.debug(
                f"Process {pid} exited after SIGTERM with code "
                f"{getattr(proc, 'returncode', None)}",
            )
            return (True, False)
        except asyncio.TimeoutError:
            return await self._handle_timeout(
                pid,
                proc,
                force,
            )

    async def _handle_timeout(
        self,
        pid: int,
        proc: Any,
        force: bool,
    ) -> tuple[bool, bool]:
        """Handle timeout when terminating a process.

        Parameters
        ----------
        pid : int
            Process ID
        proc : Any
            Process object
        force : bool
            If True, use SIGKILL

        Returns
        -------
        tuple[bool, bool]
            (terminated_success, failed)
        """
        if not force:
            _args = getattr(proc, "args", None)
            self.ctx.warning(
                f"Process {pid} did not terminate within timeout; args={_args}",
            )
            return (False, True)

        # Force kill
        self.ctx.warning(
            f"Process {pid} did not terminate, sending SIGKILL",
        )
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=PROCESS_WAIT_TIMEOUT_S)
            self.ctx.debug(
                f"Process {pid} killed with SIGKILL; return "
                f"code {getattr(proc, 'returncode', None)}",
            )
            return (True, False)
        except asyncio.TimeoutError:
            self.ctx.error(f"Failed to kill process {pid}")
            return (False, True)

    def _log_process_details(self, session_id: str, session_procs: dict) -> None:
        """Log details about processes to be terminated.

        Parameters
        ----------
        session_id : str
            Session ID
        session_procs : dict
            Dictionary of processes
        """
        self.ctx.debug(
            f"Preparing to terminate {len(session_procs)} processes "
            f"for session {session_id}: {list(session_procs.keys())}",
        )
        for _pid, _proc in session_procs.items():
            try:
                _pgid = os.getpgid(_pid)
            except Exception:
                _pgid = None
            _args = getattr(_proc, "args", None)
            self.ctx.debug(f"Process {_pid} details: pgid={_pgid}, args={_args}")

    @acquire_lock
    async def terminate_session_processes(
        self,
        session_id: str,
        timeout: float = 5.0,
        force: bool = False,
    ) -> tuple[int, int]:
        """Terminate all processes for a session.

        Parameters
        ----------
        session_id : str
            The session ID whose processes to terminate
        timeout : float, default=5.0
            Timeout in seconds to wait for graceful termination
        force : bool, default=False
            If True, use SIGKILL after timeout

        Returns
        -------
        Tuple[int, int]
            (terminated_count, failed_count)
        """
        if session_id not in self._processes:
            self.ctx.debug(f"No processes to terminate for session {session_id}")
            return (0, 0)

        session_procs = dict(self._processes.get(session_id, {}))
        self._log_process_details(session_id, session_procs)

        terminated = 0
        failed = 0

        # Terminate process groups first
        self._terminate_process_groups(session_id)

        # Terminate individual processes
        for pid, proc in list(self._processes[session_id].items()):
            try:
                success, fail = await self._terminate_single_process(
                    pid,
                    proc,
                    timeout,
                    force,
                )
                if success:
                    terminated += 1
                if fail:
                    failed += 1
            except Exception as e:
                self.ctx.error(f"Error terminating process {pid}: {e}")
                failed += 1

            # Remove from registry regardless of success
            self.unregister_process(session_id, pid)

        # Cleanup
        if not self._processes[session_id]:
            del self._processes[session_id]
            if session_id in self._process_groups:
                del self._process_groups[session_id]

        self.ctx.debug(
            f"Terminated {terminated} processes, failed to terminate {failed} "
            f"processes for session {session_id}",
        )
        return (terminated, failed)

    @acquire_lock
    def is_pid_registered(self, pid: int) -> bool:
        """Check if a PID is registered with any session.

        Parameters
        ----------
        pid : int
            The PID to check

        Returns
        -------
        bool
            True if the PID is registered with any session
        """
        for session_processes in self._processes.values():
            if pid in session_processes:
                return True
        return False

    @acquire_lock
    def get_all_registered_pids(self) -> set[int]:
        """Get all registered PIDs across all sessions.

        Returns
        -------
        Set[int]
            Set of all registered PIDs
        """
        all_pids: set[int] = set()
        for session_processes in self._processes.values():
            all_pids.update(session_processes.keys())
        return all_pids

    @acquire_lock
    def get_process_count(self, session_id: str) -> int:
        """Get the number of registered processes for a session.

        Parameters
        ----------
        session_id : str
            The session ID to check

        Returns
        -------
        int
            Number of registered processes
        """
        return len(self._processes.get(session_id, {}))
