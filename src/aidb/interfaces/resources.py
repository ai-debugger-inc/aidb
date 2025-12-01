"""Interface definitions for resource management components."""

from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Protocol


class ResourceType(Enum):
    """Types of resources that can be managed."""

    PORT = "port"
    PROCESS = "process"
    FILE = "file"
    SESSION = "session"


class IResourceLifecycle(Protocol):
    """Interface for components that manage resource lifecycle.

    This protocol defines a consistent cleanup pattern that all resource-owning
    components must implement. It ensures:
    - Predictable resource acquisition and release
    - Proper error handling during cleanup
    - Tracking of resource state
    - Safe concurrent access
    """

    async def acquire_resources(self) -> None:
        """Acquire all necessary resources for this component.

        This method should:
        - Acquire any needed system resources (ports, processes, files)
        - Register resources with appropriate registries
        - Set up internal tracking structures

        Raises
        ------
        ResourceError
            If resources cannot be acquired
        """
        ...

    async def release_resources(self) -> dict[str, Any]:
        """Release all resources owned by this component.

        This method should:
        - Release all acquired resources in reverse order
        - Handle partial cleanup if some releases fail
        - Return a summary of what was cleaned up

        Returns
        -------
        Dict[str, Any]
            Summary of cleanup results including:
            - resources_released: count of successfully released resources
            - resources_failed: count of resources that failed to release
            - errors: list of error messages for failed releases
        """
        ...

    def get_resource_state(self) -> dict[str, Any]:
        """Get current state of managed resources.

        Returns
        -------
        Dict[str, Any]
            Current resource state including:
            - active_resources: list or count of active resources
            - resource_details: detailed info about each resource
            - health_status: overall health of resource management
        """
        ...

    @asynccontextmanager
    async def resource_scope(self):
        """Context manager for resource lifecycle.

        Ensures resources are properly acquired and released even if
        errors occur during operation.

        Usage
        -----
        async with component.resource_scope():
            # Use resources
            pass
        # Resources automatically released
        """
        try:
            await self.acquire_resources()
            yield self
        finally:
            await self.release_resources()


class IResourceTracker(Protocol):
    """Interface for tracking resource allocation across sessions."""

    def track_resource(
        self,
        resource_type: str,
        resource_id: Any,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Track a resource allocation.

        Parameters
        ----------
        resource_type : str
            Type of resource (use ResourceType enum values)
        resource_id : Any
            Unique identifier for the resource
        session_id : str
            Session that owns this resource
        metadata : Dict[str, Any], optional
            Additional metadata about the resource
        """
        ...

    def untrack_resource(self, resource_type: str, resource_id: Any) -> str | None:
        """Stop tracking a resource.

        Parameters
        ----------
        resource_type : str
            Type of resource
        resource_id : Any
            Resource identifier

        Returns
        -------
        Optional[str]
            Session ID that owned the resource, or None if not tracked
        """
        ...

    def get_session_resources(self, session_id: str) -> dict[str, list[Any]]:
        """Get all resources owned by a session.

        Parameters
        ----------
        session_id : str
            Session to query

        Returns
        -------
        Dict[str, List[Any]]
            Resources by type owned by the session
        """
        ...

    def get_resource_owner(self, resource_type: str, resource_id: Any) -> str | None:
        """Get the session that owns a resource.

        Parameters
        ----------
        resource_type : str
            Type of resource
        resource_id : Any
            Resource identifier

        Returns
        -------
        Optional[str]
            Session ID of the owner, or None if not tracked
        """
        ...

    def get_all_resources(self) -> dict[str, dict[str, Any]]:
        """Get all tracked resources across all sessions.

        Returns
        -------
        Dict[str, Dict[str, Any]]
            Nested dict: {session_id: {resource_type: [resource_ids]}}
        """
        ...

    def clear_session_resources(self, session_id: str) -> dict[str, int]:
        """Clear all resource tracking for a session.

        Parameters
        ----------
        session_id : str
            Session to clear

        Returns
        -------
        Dict[str, int]
            Count of resources cleared by type
        """
        ...


class IPortManager(Protocol):
    """Interface for port management operations."""

    async def acquire_port(
        self,
        session_id: str,
        preferred: int | None = None,
        language: str | None = None,
    ) -> int:
        """Acquire an available port.

        Parameters
        ----------
        session_id : str
            Session requesting the port
        preferred : int, optional
            Preferred port number
        language : str, optional
            Language for adapter-specific port ranges

        Returns
        -------
        int
            Allocated port number

        Raises
        ------
        ResourceExhaustedError
            If no ports are available
        """
        ...

    def release_port(self, port: int, session_id: str) -> bool:
        """Release a port back to the pool.

        Parameters
        ----------
        port : int
            Port to release
        session_id : str
            Session releasing the port

        Returns
        -------
        bool
            True if port was released, False if not owned by session
        """
        ...

    def get_session_ports(self, session_id: str) -> set[int]:
        """Get all ports owned by a session.

        Parameters
        ----------
        session_id : str
            Session to query

        Returns
        -------
        Set[int]
            Ports owned by the session
        """
        ...

    def release_all_session_ports(self, session_id: str) -> list[int]:
        """Release all ports for a session.

        Parameters
        ----------
        session_id : str
            Session whose ports to release

        Returns
        -------
        List[int]
            Ports that were released
        """
        ...


class IProcessManager(Protocol):
    """Interface for process management operations."""

    def register_process(
        self,
        session_id: str,
        process: Any,
        use_process_group: bool = True,
    ) -> int:
        """Register a process with the manager.

        Parameters
        ----------
        session_id : str
            Session that owns the process
        process : Any
            Process object to register
        use_process_group : bool
            Whether to track as process group

        Returns
        -------
        int
            Process ID
        """
        ...

    async def terminate_process(self, pid: int, timeout: float = 2.0) -> bool:
        """Terminate a specific process.

        Parameters
        ----------
        pid : int
            Process ID to terminate
        timeout : float
            Time to wait for graceful termination

        Returns
        -------
        bool
            True if process was terminated
        """
        ...

    async def terminate_session_processes(self, session_id: str) -> tuple[int, int]:
        """Terminate all processes for a session.

        Parameters
        ----------
        session_id : str
            Session whose processes to terminate

        Returns
        -------
        tuple[int, int]
            (terminated_count, failed_count)
        """
        ...

    def get_session_processes(self, session_id: str) -> list[int]:
        """Get all process IDs for a session.

        Parameters
        ----------
        session_id : str
            Session to query

        Returns
        -------
        List[int]
            Process IDs owned by the session
        """
        ...
