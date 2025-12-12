"""Cleanup orchestration utilities for session resources."""

import asyncio
from typing import TYPE_CHECKING, Any

from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.resources.pids import ProcessRegistry
    from aidb.resources.ports import PortRegistry
    from aidb.session import Session
    from aidb.session.utils.process_terminator import ProcessTerminator


class CleanupOrchestrator(Obj):
    """Orchestrate cleanup of session resources.

    This class handles comprehensive cleanup of debug session resources including:
    - Process termination via ProcessRegistry
    - Port release via PortRegistry
    - Pattern-based orphan process cleanup
    - Process group cleanup for attached PIDs

    Parameters
    ----------
    session : Session
        The session whose resources to clean up
    process_registry : ProcessRegistry
        Registry for process management
    port_registry : PortRegistry
        Registry for port management
    terminator : ProcessTerminator
        Utility for process termination
    ctx : IContext, optional
        Application context for logging
    """

    def __init__(
        self,
        session: "Session",
        process_registry: "ProcessRegistry",
        port_registry: "PortRegistry",
        terminator: "ProcessTerminator",
        ctx: "IContext | None" = None,
    ) -> None:
        super().__init__(ctx=ctx)
        self.session = session
        self._process_registry = process_registry
        self._port_registry = port_registry
        self._terminator = terminator

    async def cleanup_all_resources(self) -> dict[str, Any]:
        """Clean up all resources (processes and ports) for this session.

        Returns
        -------
        dict[str, Any]
            Summary of cleanup results with keys:
            - session_id: Session identifier
            - terminated_processes: Number of processes terminated
            - failed_processes: Number of processes that failed to terminate
            - released_ports: Number of ports released
        """
        self.ctx.debug("Starting comprehensive resource cleanup")
        self.ctx.debug(
            f"Pre-cleanup resource counts: "
            f"processes={self._process_registry.get_process_count(self.session.id)}, "
            f"ports={self._port_registry.get_port_count(self.session.id)}",
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
            f"processes={self._process_registry.get_process_count(self.session.id)}, "
            f"ports={self._port_registry.get_port_count(self.session.id)}",
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
        port : int, optional
            Port to search for in orphaned processes
        process_pattern : str, optional
            Pattern to match for debug adapter processes
        attached_pid : int, optional
            PID of attached process whose group should be terminated
        main_proc : asyncio.subprocess.Process, optional
            Main debug adapter process to clean up

        Returns
        -------
        dict[str, Any]
            Comprehensive cleanup results including standard cleanup results
            plus orphan and process group cleanup information
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
            main_cleanup = await self._terminator.cleanup_main_process(main_proc)

        # Fallback: Terminate process group if attached PID provided
        if attached_pid:
            group_cleanup = await self._terminator.terminate_process_group(attached_pid)

        # Fallback: Pattern-based cleanup for orphaned processes
        if port and process_pattern:
            orphaned_count = await self._terminator.terminate_processes_by_pattern(
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

    async def cleanup_session_resources(self) -> None:
        """Clean up all resources associated with a session.

        This method handles the complete cleanup of session resources, including
        comprehensive fallback cleanup for orphaned processes. It extracts adapter
        context automatically from the session.
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
