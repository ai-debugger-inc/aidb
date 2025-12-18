"""Unified cleanup registry for test resources.

This module consolidates cleanup patterns from multiple base classes, providing a single
registry for managing test resources like ports, processes, sessions, and temporary
files.
"""

import asyncio
import os
import shutil
import signal
import tempfile
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from pathlib import Path
from typing import Any, Optional, Union

from aidb.resources.ports import PortRegistry
from aidb_logging import get_test_logger

logger = get_test_logger(__name__)


class CleanupRegistry:
    """Unified registry for managing test resource cleanup.

    This class consolidates cleanup patterns that are currently scattered across
    multiple base classes and helpers.
    """

    def __init__(self):
        """Initialize the cleanup registry."""
        self._resources: dict[str, list[Any]] = {
            "ports": [],
            "processes": [],
            "sessions": [],
            "temp_files": [],
            "temp_dirs": [],
            "callbacks": [],
        }
        self._port_registry = PortRegistry()
        self._cleanup_order = [
            "callbacks",  # Custom cleanup first
            "sessions",  # Stop debug sessions
            "processes",  # Kill processes
            "ports",  # Release ports
            "temp_files",  # Remove temp files
            "temp_dirs",  # Remove temp directories
        ]

    def register_port(self, port: int) -> None:
        """Register a port for cleanup.

        Parameters
        ----------
        port : int
            Port number to track
        """
        if port not in self._resources["ports"]:
            self._resources["ports"].append(port)

    def register_process(self, pid: int) -> None:
        """Register a process for cleanup.

        Parameters
        ----------
        pid : int
            Process ID to track
        """
        if pid not in self._resources["processes"]:
            self._resources["processes"].append(pid)

    def register_session(
        self,
        session_id: str,
        cleanup_func: Callable | None = None,
    ) -> None:
        """Register a debug session for cleanup.

        Parameters
        ----------
        session_id : str
            Session ID to track
        cleanup_func : Optional[Callable]
            Custom cleanup function for the session
        """
        self._resources["sessions"].append({"id": session_id, "cleanup": cleanup_func})

    def register_temp_file(self, file_path: str | Path) -> None:
        """Register a temporary file for cleanup.

        Parameters
        ----------
        file_path : Union[str, Path]
            File path to track
        """
        path = Path(file_path)
        if path not in self._resources["temp_files"]:
            self._resources["temp_files"].append(path)

    def register_temp_dir(self, dir_path: str | Path) -> None:
        """Register a temporary directory for cleanup.

        Parameters
        ----------
        dir_path : Union[str, Path]
            Directory path to track
        """
        path = Path(dir_path)
        if path not in self._resources["temp_dirs"]:
            self._resources["temp_dirs"].append(path)

    def register_cleanup(self, callback: Callable) -> None:
        """Register a custom cleanup callback.

        Parameters
        ----------
        callback : Callable
            Cleanup function to call during cleanup
        """
        self._resources["callbacks"].append(callback)

    async def cleanup_ports(self) -> None:
        """Release all registered ports."""
        for port in self._resources["ports"]:
            try:
                self._port_registry.release_port(port)
            except Exception as e:
                logger.debug("Failed to release port %s: %s", port, e)
        self._resources["ports"].clear()

    async def cleanup_processes(self) -> None:
        """Terminate all registered processes."""
        for pid in self._resources["processes"]:
            with suppress(ProcessLookupError, PermissionError):
                # Process already gone or no permission
                os.kill(pid, signal.SIGTERM)
        self._resources["processes"].clear()

    async def cleanup_sessions(self) -> None:
        """Clean up all registered debug sessions."""
        for session_info in self._resources["sessions"]:
            try:
                if session_info["cleanup"]:
                    if asyncio.iscoroutinefunction(session_info["cleanup"]):
                        await session_info["cleanup"]()
                    else:
                        session_info["cleanup"]()
            except Exception as e:
                logger.debug("Failed to cleanup session: %s", e)
        self._resources["sessions"].clear()

    async def cleanup_temp_files(self) -> None:
        """Remove all registered temporary files."""
        for file_path in self._resources["temp_files"]:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.debug("Failed to remove temp file %s: %s", file_path, e)
        self._resources["temp_files"].clear()

    async def cleanup_temp_dirs(self) -> None:
        """Remove all registered temporary directories."""
        for dir_path in self._resources["temp_dirs"]:
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
            except Exception as e:
                logger.debug("Failed to remove temp dir %s: %s", dir_path, e)
        self._resources["temp_dirs"].clear()

    async def cleanup_callbacks(self) -> None:
        """Execute all registered cleanup callbacks."""
        for callback in self._resources["callbacks"]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.debug("Cleanup callback failed: %s", e)
        self._resources["callbacks"].clear()

    async def cleanup_all(self) -> None:
        """Execute all cleanup operations in the correct order."""
        for resource_type in self._cleanup_order:
            cleanup_method = getattr(self, f"cleanup_{resource_type}")
            await cleanup_method()

    def cleanup_all_sync(self) -> None:
        """Clean up all resources synchronously for non-async contexts."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.cleanup_all())
        finally:
            loop.close()

    @contextmanager
    def temp_file(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
    ) -> Iterator[Path]:
        """Create a temporary file that will be cleaned up.

        Parameters
        ----------
        suffix : Optional[str]
            File suffix
        prefix : Optional[str]
            File prefix

        Yields
        ------
        Path
            Path to the temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        file_path = Path(path)
        self.register_temp_file(file_path)
        try:
            yield file_path
        finally:
            # Immediate cleanup if needed
            pass

    @contextmanager
    def temp_dir(
        self,
        suffix: str | None = None,
        prefix: str | None = None,
    ) -> Iterator[Path]:
        """Create a temporary directory that will be cleaned up.

        Parameters
        ----------
        suffix : Optional[str]
            Directory suffix
        prefix : Optional[str]
            Directory prefix

        Yields
        ------
        Path
            Path to the temporary directory
        """
        dir_path = Path(tempfile.mkdtemp(suffix=suffix, prefix=prefix))
        self.register_temp_dir(dir_path)
        try:
            yield dir_path
        finally:
            # Immediate cleanup if needed
            pass

    @contextmanager
    def allocated_port(self, preferred: int | None = None) -> Iterator[int]:
        """Allocate a port that will be released on cleanup.

        Parameters
        ----------
        preferred : Optional[int]
            Preferred port number

        Yields
        ------
        int
            Allocated port number
        """
        port = self._port_registry.allocate_port(preferred=preferred)
        self.register_port(port)
        try:
            yield port
        finally:
            # Port will be released during cleanup
            pass

    @asynccontextmanager
    async def managed_session(self, session_id: str, cleanup_func: Callable):
        """Manage a debug session with automatic cleanup.

        Parameters
        ----------
        session_id : str
            Session identifier
        cleanup_func : Callable
            Function to clean up the session

        Yields
        ------
        str
            The session ID
        """
        self.register_session(session_id, cleanup_func)
        try:
            yield session_id
        finally:
            # Session will be cleaned up during cleanup
            pass

    def get_resource_counts(self) -> dict[str, int]:
        """Get counts of registered resources.

        Returns
        -------
        Dict[str, int]
            Resource type to count mapping
        """
        return {
            resource_type: len(resources)
            for resource_type, resources in self._resources.items()
        }

    def has_resources(self) -> bool:
        """Check if there are any resources registered.

        Returns
        -------
        bool
            True if any resources are registered
        """
        return any(len(resources) > 0 for resources in self._resources.values())


# Global registry instance for use across tests
_global_registry: CleanupRegistry | None = None


def get_cleanup_registry() -> CleanupRegistry:
    """Get the global cleanup registry instance.

    Returns
    -------
    CleanupRegistry
        The global registry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = CleanupRegistry()
    return _global_registry


def reset_cleanup_registry() -> None:
    """Reset the global cleanup registry.

    This should be called between test runs to ensure isolation.
    """
    global _global_registry
    if _global_registry is not None:
        _global_registry.cleanup_all_sync()
    _global_registry = None


class ScopedCleanupRegistry(CleanupRegistry):
    """Scoped version of CleanupRegistry for test-specific isolation.

    This version automatically cleans up when the context exits.
    """

    @asynccontextmanager
    async def scope(self):
        """Create a scoped cleanup context.

        Yields
        ------
        ScopedCleanupRegistry
            The registry instance
        """
        try:
            yield self
        finally:
            await self.cleanup_all()

    @contextmanager
    def sync_scope(self):
        """Create a synchronous scoped cleanup context.

        Yields
        ------
        ScopedCleanupRegistry
            The registry instance
        """
        try:
            yield self
        finally:
            self.cleanup_all_sync()
