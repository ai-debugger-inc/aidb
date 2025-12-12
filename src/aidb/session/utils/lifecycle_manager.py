"""Resource lifecycle management utilities for debug sessions."""

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext
    from aidb.resources.pids import ProcessRegistry
    from aidb.resources.ports import PortRegistry
    from aidb.session import Session


class ResourceLifecycleManager(Obj):
    """Manage resource lifecycle operations for debug sessions.

    This class handles resource lifecycle operations including:
    - Resource usage statistics
    - Resource state tracking
    - Resource acquisition and release
    - Resource scope context management

    Parameters
    ----------
    session : Session
        The session whose resources to manage
    process_registry : ProcessRegistry
        Registry for process management
    port_registry : PortRegistry
        Registry for port management
    cleanup_func : Callable
        Async function to call for cleanup operations
    ctx : IContext, optional
        Application context for logging
    """

    def __init__(
        self,
        session: "Session",
        process_registry: "ProcessRegistry",
        port_registry: "PortRegistry",
        cleanup_func: Callable[[], Any],
        ctx: "IContext | None" = None,
    ) -> None:
        super().__init__(ctx=ctx)
        self.session = session
        self._process_registry = process_registry
        self._port_registry = port_registry
        self._cleanup_func = cleanup_func
        # Track resource state
        self._resources_acquired = False
        self._cleanup_completed = False

    def get_process_count(self) -> int:
        """Get the number of processes registered with this session.

        Returns
        -------
        int
            Number of registered processes
        """
        return self._process_registry.get_process_count(self.session.id)

    def get_port_count(self) -> int:
        """Get the number of ports allocated to this session.

        Returns
        -------
        int
            Number of allocated ports
        """
        return self._port_registry.get_port_count(self.session.id)

    def get_resource_usage(self) -> dict[str, Any]:
        """Get resource usage statistics for this session.

        Returns
        -------
        dict[str, Any]
            Dictionary containing resource usage statistics with keys:
            - session_id: Session identifier
            - process_count: Number of registered processes
            - port_count: Number of allocated ports
            - total_resources: Combined count
        """
        process_count = self.get_process_count()
        port_count = self.get_port_count()

        return {
            "session_id": self.session.id,
            "process_count": process_count,
            "port_count": port_count,
            "total_resources": process_count + port_count,
        }

    def get_session_resource_usage(self) -> dict:
        """Get resource usage statistics for a session with error handling.

        Returns
        -------
        dict
            Dictionary containing resource usage statistics, or error info
            if retrieval fails
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

    def get_resource_state(self) -> dict[str, Any]:
        """Get current state of managed resources.

        Returns
        -------
        dict[str, Any]
            Current resource state including:
            - session_id: Session identifier
            - resources_acquired: Whether resources have been acquired
            - cleanup_completed: Whether cleanup has been completed
            - process_count: Number of registered processes
            - port_count: Number of allocated ports
            - health_status: 'healthy' or 'cleaned'
        """
        return {
            "session_id": self.session.id,
            "resources_acquired": self._resources_acquired,
            "cleanup_completed": self._cleanup_completed,
            "process_count": self.get_process_count(),
            "port_count": self.get_port_count(),
            "health_status": "healthy" if not self._cleanup_completed else "cleaned",
        }

    async def acquire_resources(self, lock) -> None:
        """Acquire all necessary resources for this session.

        This is typically called when a session starts to pre-allocate any
        required resources.

        Parameters
        ----------
        lock : threading.RLock
            Lock to ensure thread-safe resource acquisition
        """
        with lock:
            if self._resources_acquired:
                self.ctx.debug("Resources already acquired")
                return

            # Currently, resources are acquired on-demand
            # This method is here for future pre-allocation needs
            self._resources_acquired = True
            self.ctx.debug(
                f"Resources marked as acquired for session {self.session.id}",
            )

    async def release_resources(self, lock) -> dict[str, Any]:
        """Release all resources owned by this session.

        Implements the IResourceLifecycle protocol for consistent cleanup.

        Parameters
        ----------
        lock : threading.RLock
            Lock to ensure thread-safe resource release

        Returns
        -------
        dict[str, Any]
            Summary of cleanup results
        """
        with lock:
            if self._cleanup_completed:
                self.ctx.debug("Cleanup already completed")
                return {
                    "session_id": self.session.id,
                    "status": "already_cleaned",
                    "terminated_processes": 0,
                    "released_ports": 0,
                }

            # Perform comprehensive cleanup
            result = await self._cleanup_func()
            self._cleanup_completed = True
            return result

    @asynccontextmanager
    async def resource_scope(self, lock):
        """Context manager for resource lifecycle.

        Ensures resources are properly acquired and released.

        Parameters
        ----------
        lock : threading.RLock
            Lock for thread-safe operations
        """
        try:
            await self.acquire_resources(lock)
            yield self
        finally:
            await self.release_resources(lock)

    @property
    def resources_acquired(self) -> bool:
        """Whether resources have been acquired."""
        return self._resources_acquired

    @property
    def cleanup_completed(self) -> bool:
        """Whether cleanup has been completed."""
        return self._cleanup_completed
