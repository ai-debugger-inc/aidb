"""Resource management for debug sessions."""

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Optional

import psutil

from aidb.api.constants import (
    DEFAULT_REQUEST_TIMEOUT_S,
    PROCESS_TERMINATE_TIMEOUT_S,
    RECEIVE_POLL_TIMEOUT_S,
)
from aidb.common import acquire_lock
from aidb.patterns import Obj
from aidb_common.constants import Language

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class ResourceManager(Obj):
    """Manage resources for debug sessions.

    This class owns and manages all resource registries (processes and ports)
    and provides centralized resource management operations. Sessions delegate
    all resource management to their `ResourceManager` instance.

    Implements IResourceLifecycle for consistent cleanup patterns.
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize the resource manager.

        Parameters
        ----------
        session : Session
            The session that owns this resource manager
        ctx : IContext, optional
            Application context, by default `None`
        """
        from aidb.resources.pids import ProcessRegistry
        from aidb.resources.ports import PortRegistry

        super().__init__(ctx=ctx)
        # Add sync lock for thread-safe resource management
        import threading

        self.lock = threading.RLock()
        self.session = session
        # Both are singletons now
        self._process_registry: ProcessRegistry = ProcessRegistry(ctx=self.ctx)
        self._port_registry: PortRegistry = PortRegistry(ctx=self.ctx)
        # Track resource state
        self._resources_acquired = False
        self._cleanup_completed = False

    # ---------------------------
    # Process Management
    # ---------------------------

    def register_process(
        self,
        proc: asyncio.subprocess.Process,
        use_process_group: bool = True,
    ) -> int:
        """Register a process with this session.

        Parameters
        ----------
        proc : asyncio.subprocess.Process
            The process to register
        use_process_group : bool, optional
            Whether to use process groups for this process, by default `True`

        Returns
        -------
        int
            PID of the registered process
        """
        pid = self._process_registry.register_process(
            self.session.id,
            proc,
            use_process_group,
        )
        self.ctx.debug(
            f"Registered process {pid} with process group {use_process_group}",
        )

        # Track with SessionManager if available
        self._track_resource("process", pid)

        return pid

    def _track_resource(self, resource_type: str, resource_id: Any) -> None:
        """Track a resource with the SessionManager.

        Parameters
        ----------
        resource_type : str
            Type of resource
        resource_id : Any
            Resource identifier
        """
        # This is a best-effort tracking - SessionManager integration
        # is optional and shouldn't fail if not available

    def get_process_count(self) -> int:
        """Get the number of processes registered with this session.

        Returns
        -------
        int
            Number of registered processes
        """
        return self._process_registry.get_process_count(self.session.id)

    # ---------------------------
    # Port Management
    # ---------------------------

    async def acquire_port(self, start_port: int = 0) -> int:
        """Acquire an available port for this session.

        Parameters
        ----------
        start_port : int, optional
            Port to start checking from, by default `0`

        Returns
        -------
        int
            Acquired port number

        Raises
        ------
        TimeoutError
            If port acquisition takes longer than 30 seconds
        """
        import asyncio

        language = (
            self.session.language
            if hasattr(self.session, "language")
            else Language.PYTHON.value
        )

        # Get adapter config for port settings
        from aidb.session.adapter_registry import AdapterRegistry

        registry = AdapterRegistry(ctx=self.ctx)
        adapter_config = registry[language]

        # Add timeout to prevent infinite hangs (especially in containers)
        try:
            port = await asyncio.wait_for(
                self._port_registry.acquire_port(
                    language=language,
                    session_id=self.session.id,
                    preferred=start_port if start_port > 0 else None,
                    default_port=adapter_config.default_dap_port,
                    fallback_ranges=adapter_config.fallback_port_ranges,
                ),
                timeout=DEFAULT_REQUEST_TIMEOUT_S,
            )
        except asyncio.TimeoutError as e:
            error_msg = (
                f"Port acquisition timed out after {DEFAULT_REQUEST_TIMEOUT_S}s "
                f"(language={language}, start_port={start_port})"
            )
            self.ctx.error(error_msg)
            raise TimeoutError(error_msg) from e

        # Track with SessionManager
        self._track_resource("port", port)

        return port

    def get_port_count(self) -> int:
        """Get the number of ports registered with this session.

        Returns
        -------
        int
            Number of registered ports
        """
        return self._port_registry.get_port_count(session_id=self.session.id)

    def release_port(self, port: int) -> str | None:
        """Release a port.

        Parameters
        ----------
        port : int
            Port number to release

        Returns
        -------
        Optional[str]
            The session ID the port was registered with, or `None` if not found
        """
        self._port_registry.release_port(port, session_id=self.session.id)
        return self.session.id

    # ---------------------------
    # Comprehensive Management
    # ---------------------------

    @acquire_lock
    async def cleanup_all_resources(self) -> dict[str, Any]:
        """Clean up all resources (processes and ports) for this session.

        Returns
        -------
        Dict[str, Any]
            Summary of cleanup results
        """
        self.ctx.debug("Starting comprehensive resource cleanup")
        self.ctx.debug(
            f"Pre-cleanup resource counts: "
            f"processes={self.get_process_count()}, "
            f"ports={self.get_port_count()}",
        )
        # Use adapter-specific timeout (Java: 5s, Python/JS: 1s)
        timeout = (
            self.session.adapter.config.process_termination_timeout
            if self.session.adapter
            else 1.0  # Fallback if adapter not available
        )
        result = await self._process_registry.terminate_session_processes(
            self.session.id,
            timeout=timeout,
            force=True,  # Enable SIGKILL after timeout to prevent hangs
        )
        self.ctx.debug(
            f"Terminated {result[0]} processes, "
            f"failed to terminate {result[1]} processes",
        )
        if result[1] > 0:
            self.ctx.warning(
                f"{result[1]} process(es) did not terminate "
                f"gracefully during primary cleanup",
            )
        ports_released = self._port_registry.release_session_ports(
            session_id=self.session.id,
        )
        self.ctx.debug(f"Released {len(ports_released)} ports: {ports_released}")
        self.ctx.debug(
            f"Post-cleanup resource counts: "
            f"processes={self.get_process_count()}, "
            f"ports={self.get_port_count()}",
        )
        return {
            "session_id": self.session.id,
            "terminated_processes": result[0],
            "failed_processes": result[1],
            "released_ports": len(ports_released),
        }

    async def comprehensive_cleanup_with_fallback(
        self,
        port: int | None = None,
        process_pattern: str | None = None,
        attached_pid: int | None = None,
        main_proc: asyncio.subprocess.Process | None = None,
    ) -> dict[str, Any]:
        """Cleanup including fallback methods for orphaned processes.

        This method combines standard resource cleanup with pattern-based
        discovery to ensure no processes are left orphaned.

        Parameters
        ----------
        port : Optional[int]
            Port to search for in orphaned processes
        process_pattern : Optional[str]
            Pattern to match for debug adapter processes
        attached_pid : Optional[int]
            PID of attached process whose group should be terminated
        main_proc : Optional[asyncio.subprocess.Process]
            Main debug adapter process to clean up

        Returns
        -------
        Dict[str, Any]
            Comprehensive cleanup results
        """
        # Log cleanup context
        main_pid = getattr(main_proc, "pid", None) if main_proc else None
        main_args = getattr(main_proc, "args", None) if main_proc else None
        self.ctx.debug(
            "Comprehensive cleanup context: "
            f"port={port}, pattern={process_pattern}, attached_pid={attached_pid}, "
            f"main_pid={main_pid}, main_args={main_args}",
        )

        # Start with standard cleanup
        standard_result = await self.cleanup_all_resources()

        orphaned_count = 0
        group_cleanup = False
        main_cleanup = False

        # Fallback: Clean up main process if provided
        if main_proc:
            main_cleanup = await self.cleanup_main_process(main_proc)

        # Fallback: Terminate process group if attached PID provided
        if attached_pid:
            group_cleanup = await self.terminate_process_group(attached_pid)

        # Fallback: Pattern-based cleanup for orphaned processes
        if port and process_pattern:
            orphaned_count = await self.terminate_processes_by_pattern(
                port,
                process_pattern,
            )

        return {
            **standard_result,
            "orphaned_processes_terminated": orphaned_count,
            "process_group_cleanup_attempted": group_cleanup,
            "main_process_cleanup_successful": main_cleanup,
            "comprehensive_cleanup": True,
        }

    def get_resource_usage(self) -> dict[str, Any]:
        """Get resource usage statistics for this session.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing resource usage statistics
        """
        process_count = self.get_process_count()
        port_count = self.get_port_count()

        return {
            "session_id": self.session.id,
            "process_count": process_count,
            "port_count": port_count,
            "total_resources": process_count + port_count,
        }

    @acquire_lock
    async def cleanup_session_resources(self) -> None:
        """Clean up all resources associated with a session.

        This method handles the complete cleanup of session resources, including
        comprehensive fallback cleanup for orphaned processes.
        """
        self.ctx.debug(
            f"Starting comprehensive resource cleanup for session {self.session.id}",
        )

        # Get adapter context for comprehensive cleanup
        adapter_port = None
        adapter_pattern = None
        attached_pid = None
        main_proc = None

        # Extract cleanup context from session's adapter if available
        if hasattr(self.session, "adapter") and self.session.adapter:
            adapter = self.session.adapter
            adapter_port = getattr(adapter, "_port", None)
            attached_pid = getattr(adapter, "_attached_pid", None)
            main_proc = getattr(adapter, "_proc", None)

            # Get process pattern if adapter has the method
            if hasattr(adapter, "_get_process_name_pattern"):
                try:
                    adapter_pattern = adapter._get_process_name_pattern()
                except Exception as e:
                    self.ctx.debug(f"Could not get process pattern: {e}")

        # Use comprehensive cleanup with adapter context
        cleanup_result = await self.comprehensive_cleanup_with_fallback(
            port=adapter_port,
            process_pattern=adapter_pattern,
            attached_pid=attached_pid,
            main_proc=main_proc,
        )

        # Log comprehensive results
        self.ctx.info(
            f"Comprehensive cleanup completed for session {self.session.id}: "
            f"{cleanup_result['terminated_processes']} registered processes "
            f"terminated, {cleanup_result['failed_processes']} failed, "
            f"{cleanup_result['released_ports']} ports released, "
            f"{cleanup_result['orphaned_processes_terminated']} orphaned "
            f"processes terminated",
        )

    def get_session_resource_usage(self) -> dict:
        """Get resource usage statistics for a session.

        Returns
        -------
        dict
            Dictionary containing resource usage statistics
        """
        try:
            return self.get_resource_usage()
        except Exception as e:
            self.ctx.error(
                f"Error getting resource usage for session {self.session.id}: {e}",
            )
            return {
                "session_id": self.session.id,
                "error": str(e),
                "process_count": -1,
                "port_count": -1,
                "total_resources": -1,
            }

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
        port : Optional[int]
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
        """Check if a process should be terminated based on pattern and port."""
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

    async def _terminate_single_process(self, proc: psutil.Process, port: int) -> int:
        """Terminate a single process.

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
                    timeout=PROCESS_TERMINATE_TIMEOUT_S,
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

    async def _terminate_with_escalation(
        self,
        attached_pid: int,
        kill_func,
        target_desc: str,
        term_timeout: float,
        kill_timeout: float,
    ) -> bool:
        """Terminate a process with SIGTERM->SIGKILL escalation.

        Parameters
        ----------
        attached_pid : int
            PID to check for termination
        kill_func : callable
            Function to send signals (os.kill or os.killpg)
        target_desc : str
            Description of target for logging
        term_timeout : float
            Timeout after SIGTERM
        kill_timeout : float
            Timeout after SIGKILL

        Returns
        -------
        bool
            True if process terminated
        """
        # Try SIGTERM
        self.ctx.debug(f"Sending SIGTERM to {target_desc}")
        kill_func(signal.SIGTERM)
        if await self._wait_pid_terminate(attached_pid, term_timeout):
            self.ctx.debug(f"Attached PID {attached_pid} terminated after SIGTERM")
            return True

        # Escalate to SIGKILL
        self.ctx.warning(
            f"Attached PID {attached_pid} still alive "
            f"after SIGTERM; escalating to SIGKILL",
        )
        try:
            kill_func(signal.SIGKILL)
            if await self._wait_pid_terminate(attached_pid, kill_timeout):
                self.ctx.debug(f"Attached PID {attached_pid} terminated after SIGKILL")
                return True
        except OSError as e:
            self.ctx.debug(f"Could not SIGKILL {target_desc}: {e}")
        return False

    async def _try_terminate_process_group(self, attached_pid: int) -> bool | None:
        """Attempt to terminate the process group.

        Parameters
        ----------
        attached_pid : int
            PID of the attached process

        Returns
        -------
        bool | None
            True if terminated, False if failed, None if not applicable
        """
        if not hasattr(os, "killpg"):
            return None

        try:
            pgid = os.getpgid(attached_pid)

            def kill_func(sig):
                return os.killpg(pgid, sig)

            return await self._terminate_with_escalation(
                attached_pid,
                kill_func,
                f"process group {pgid}",
                1.5,
                0.5,
            )
        except (AttributeError, OSError) as e:
            self.ctx.debug(f"Could not terminate process group: {e}")
            return False

    async def _try_terminate_process_directly(self, attached_pid: int) -> bool:
        """Attempt to terminate the process directly.

        Parameters
        ----------
        attached_pid : int
            PID to terminate

        Returns
        -------
        bool
            True if terminated or attempted
        """
        try:

            def kill_func(sig):
                return os.kill(attached_pid, sig)

            return await self._terminate_with_escalation(
                attached_pid,
                kill_func,
                f"attached PID {attached_pid}",
                1.0,
                0.5,
            )
        except OSError as e:
            self.ctx.debug(f"Could not terminate process directly: {e}")
            return True  # We attempted

    async def terminate_process_group(self, attached_pid: int) -> bool:
        """Terminate the process group for an attached process.

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
        group_result = await self._try_terminate_process_group(attached_pid)
        if group_result is True:
            return True

        # Fallback to direct process termination
        return await self._try_terminate_process_directly(attached_pid)

    async def _wait_pid_terminate(self, pid: int, timeout: float) -> bool:
        """Wait for a PID to terminate up to timeout seconds.

        Returns True if process has terminated (or does not exist), False on timeout.
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

    async def cleanup_main_process(self, proc: asyncio.subprocess.Process) -> bool:
        """Clean up a main debug adapter process.

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
            timeout_s = PROCESS_TERMINATE_TIMEOUT_S
            self.ctx.debug(
                f"Sending SIGTERM to main process "
                f"{proc.pid}; args={args}; waiting up to {timeout_s}s",
            )
            proc.terminate()

            # Wait for termination
            await asyncio.wait_for(proc.wait(), timeout=PROCESS_TERMINATE_TIMEOUT_S)

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
                        f"{proc.pid}; waiting up to {RECEIVE_POLL_TIMEOUT_S}s",
                    )
                    proc.kill()

                    # Wait for kill to complete
                    await asyncio.wait_for(proc.wait(), timeout=RECEIVE_POLL_TIMEOUT_S)
                    self.ctx.debug(f"Force-killed main process {proc.pid}")
                    return True
                except (asyncio.TimeoutError, OSError) as e:
                    self.ctx.error(f"Failed to kill process: {e}")
                    return False
        return False

    # IResourceLifecycle Implementation

    async def acquire_resources(self) -> None:
        """Acquire all necessary resources for this session.

        This is typically called when a session starts to pre-allocate any required
        resources.
        """
        with self.lock:
            if self._resources_acquired:
                self.ctx.debug("Resources already acquired")
                return

            # Currently, resources are acquired on-demand
            # This method is here for future pre-allocation needs
            self._resources_acquired = True
            self.ctx.debug(
                f"Resources marked as acquired for session {self.session.id}",
            )

    async def release_resources(self) -> dict[str, Any]:
        """Release all resources owned by this session.

        Implements the IResourceLifecycle protocol for consistent cleanup.

        Returns
        -------
        Dict[str, Any]
            Summary of cleanup results
        """
        with self.lock:
            if self._cleanup_completed:
                self.ctx.debug("Cleanup already completed")
                return {
                    "session_id": self.session.id,
                    "status": "already_cleaned",
                    "terminated_processes": 0,
                    "released_ports": 0,
                }

            # Perform comprehensive cleanup
            result = await self.cleanup_all_resources()
            self._cleanup_completed = True
            return result

    def get_resource_state(self) -> dict[str, Any]:
        """Get current state of managed resources.

        Returns
        -------
        Dict[str, Any]
            Current resource state
        """
        return {
            "session_id": self.session.id,
            "resources_acquired": self._resources_acquired,
            "cleanup_completed": self._cleanup_completed,
            "process_count": self.get_process_count(),
            "port_count": self.get_port_count(),
            "health_status": "healthy" if not self._cleanup_completed else "cleaned",
        }

    @asynccontextmanager
    async def resource_scope(self):
        """Context manager for resource lifecycle.

        Ensures resources are properly acquired and released.
        """
        try:
            await self.acquire_resources()
            yield self
        finally:
            await self.release_resources()
