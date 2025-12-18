"""Resource management for debug sessions."""

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Optional

from aidb.common import acquire_lock
from aidb.common.constants import DEFAULT_REQUEST_TIMEOUT_S
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
        import threading

        from aidb.resources.pids import ProcessRegistry
        from aidb.resources.ports import PortRegistry
        from aidb.session.utils.cleanup_orchestrator import CleanupOrchestrator
        from aidb.session.utils.lifecycle_manager import ResourceLifecycleManager
        from aidb.session.utils.process_terminator import ProcessTerminator

        super().__init__(ctx=ctx)
        # Add sync lock for thread-safe resource management
        self.lock = threading.RLock()
        self.session = session
        # Both are singletons now
        self._process_registry: ProcessRegistry = ProcessRegistry(ctx=self.ctx)
        self._port_registry: PortRegistry = PortRegistry(ctx=self.ctx)
        # Process termination utilities
        self._terminator = ProcessTerminator(ctx=self.ctx)
        # Cleanup orchestration
        self._cleanup = CleanupOrchestrator(
            session=session,
            process_registry=self._process_registry,
            port_registry=self._port_registry,
            terminator=self._terminator,
            ctx=self.ctx,
        )
        # Lifecycle management (must be initialized after _cleanup)
        self._lifecycle = ResourceLifecycleManager(
            session=session,
            process_registry=self._process_registry,
            port_registry=self._port_registry,
            cleanup_func=self.cleanup_all_resources,
            ctx=self.ctx,
        )

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
        dict[str, Any]
            Summary of cleanup results
        """
        return await self._cleanup.cleanup_all_resources()

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
            Comprehensive cleanup results
        """
        return await self._cleanup.comprehensive_cleanup_with_fallback(
            port=port,
            process_pattern=process_pattern,
            attached_pid=attached_pid,
            main_proc=main_proc,
        )

    def get_resource_usage(self) -> dict[str, Any]:
        """Get resource usage statistics for this session.

        Returns
        -------
        dict[str, Any]
            Dictionary containing resource usage statistics
        """
        return self._lifecycle.get_resource_usage()

    @acquire_lock
    async def cleanup_session_resources(self) -> None:
        """Clean up all resources associated with a session.

        This method handles the complete cleanup of session resources, including
        comprehensive fallback cleanup for orphaned processes.
        """
        await self._cleanup.cleanup_session_resources()

    def get_session_resource_usage(self) -> dict:
        """Get resource usage statistics for a session.

        Returns
        -------
        dict
            Dictionary containing resource usage statistics
        """
        return self._lifecycle.get_session_resource_usage()

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
        return await self._terminator.terminate_processes_by_pattern(
            port,
            process_pattern,
        )

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
        return await self._terminator.terminate_process_group(attached_pid)

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
        return await self._terminator.cleanup_main_process(proc)

    # IResourceLifecycle Implementation

    async def acquire_resources(self) -> None:
        """Acquire all necessary resources for this session.

        This is typically called when a session starts to pre-allocate any required
        resources.
        """
        await self._lifecycle.acquire_resources(self.lock)

    async def release_resources(self) -> dict[str, Any]:
        """Release all resources owned by this session.

        Implements the IResourceLifecycle protocol for consistent cleanup.

        Returns
        -------
        dict[str, Any]
            Summary of cleanup results
        """
        return await self._lifecycle.release_resources(self.lock)

    def get_resource_state(self) -> dict[str, Any]:
        """Get current state of managed resources.

        Returns
        -------
        dict[str, Any]
            Current resource state
        """
        return self._lifecycle.get_resource_state()

    @asynccontextmanager
    async def resource_scope(self):
        """Context manager for resource lifecycle.

        Ensures resources are properly acquired and released.
        """
        async with self._lifecycle.resource_scope(self.lock):
            yield self
