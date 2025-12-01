"""Port management utilities for test isolation.

This module provides test-specific port management that wraps aidb's PortRegistry with
additional test isolation features.
"""

import asyncio
import contextlib
import logging
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch

from aidb.common.context import AidbContext
from aidb.resources.ports import PortRegistry
from tests._helpers.constants import Language

logger = logging.getLogger(__name__)


class TestPortManager:
    """Test-specific port manager with isolation guarantees.

    This wraps aidb's PortRegistry with additional features for testing:
    - Automatic cleanup of allocated ports
    - Test isolation through temporary storage
    - Port range segregation for parallel execution
    - Mock/stub support for unit tests
    """

    def __init__(self, test_id: str, base_range: int = 40000):
        """Initialize test port manager.

        Parameters
        ----------
        test_id : str
            Unique test identifier for isolation
        base_range : int
            Base port range for this test (to avoid conflicts)
        """
        self.test_id = test_id
        self.base_range = base_range
        self._allocated_ports: set[int] = set()
        self._temp_storage: Path | None = None
        self._registry: PortRegistry | None = None

    async def __aenter__(self):
        """Enter async context manager."""
        # Create temporary storage for port registry isolation
        self._temp_storage = Path(
            tempfile.mkdtemp(prefix=f"aidb_test_ports_{self.test_id}_"),
        )

        # Mock the storage path to use our temp directory
        self._storage_patcher = patch.object(AidbContext, "get_storage_path")
        mock_storage = self._storage_patcher.start()

        def get_test_storage(category: str, filename: str) -> Path:
            """Get isolated storage path for this test."""
            if self._temp_storage is None:
                msg = "Temp storage not initialized"
                raise RuntimeError(msg)
            path = self._temp_storage / category
            path.mkdir(parents=True, exist_ok=True)
            return path / filename

        mock_storage.side_effect = get_test_storage

        # Create isolated registry
        ctx = AidbContext()
        self._registry = PortRegistry(session_id=self.test_id, ctx=ctx)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager with cleanup."""
        # Release all allocated ports
        if self._registry:
            for port in self._allocated_ports:
                try:
                    self._registry.release_port(port, self.test_id)
                except Exception as e:
                    logger.debug(
                        "Failed to release port %s for test %s: %s",
                        port,
                        self.test_id,
                        e,
                    )

            # Release session ports
            with contextlib.suppress(Exception):
                self._registry.release_session_ports(self.test_id)

        # Stop patching
        if hasattr(self, "_storage_patcher"):
            self._storage_patcher.stop()

        # Clean up temp storage
        if self._temp_storage and self._temp_storage.exists():
            import shutil

            with contextlib.suppress(Exception):
                shutil.rmtree(self._temp_storage)

    async def allocate_port(
        self,
        language: str = Language.PYTHON.value,
        preferred: int | None = None,
    ) -> int:
        """Allocate a port for testing.

        Parameters
        ----------
        language : str
            Language adapter type
        preferred : int, optional
            Preferred port number

        Returns
        -------
        int
            Allocated port number
        """
        if not self._registry:
            msg = "Port manager not initialized. Use 'async with' context."
            raise RuntimeError(
                msg,
            )

        # Generate test-specific port ranges to avoid conflicts
        port_offset = hash(self.test_id) % 1000
        test_base = self.base_range + port_offset

        default_ports = {
            Language.PYTHON.value: test_base + 78,
            Language.JAVASCRIPT.value: test_base + 229,
            Language.JAVA.value: test_base + 5,
        }

        fallback_ranges = {
            Language.PYTHON.value: [test_base + 1000, test_base + 2000],
            Language.JAVASCRIPT.value: [test_base + 3000, test_base + 4000],
            Language.JAVA.value: [test_base + 5000, test_base + 6000],
        }

        port = await self._registry.acquire_port(
            language=language,
            session_id=self.test_id,
            preferred=preferred,
            default_port=default_ports.get(language, test_base + 678),
            fallback_ranges=fallback_ranges.get(language, [test_base + 7000]),
        )

        self._allocated_ports.add(port)
        return port

    async def release_port(self, port: int) -> bool:
        """Release a specific port.

        Parameters
        ----------
        port : int
            Port to release

        Returns
        -------
        bool
            True if port was released successfully
        """
        if not self._registry:
            return False

        success = self._registry.release_port(port, self.test_id)
        if success:
            self._allocated_ports.discard(port)
        return success

    def get_allocated_ports(self) -> set[int]:
        """Get all ports allocated by this manager.

        Returns
        -------
        Set[int]
            Set of allocated port numbers
        """
        return self._allocated_ports.copy()


@contextlib.asynccontextmanager
async def isolated_ports(test_id: str, base_range: int = 40000):
    """Create an isolated port manager for testing.

    Parameters
    ----------
    test_id : str
        Unique test identifier
    base_range : int
        Base port range for isolation

    Yields
    ------
    TestPortManager
        Isolated port manager instance
    """
    async with TestPortManager(test_id, base_range) as manager:
        yield manager


class MockPortRegistry:
    """Mock port registry for unit tests that don't need real ports."""

    def __init__(self):
        """Initialize mock registry."""
        self._next_port = 50000
        self._allocated: dict[str, set[int]] = {}

    async def acquire_port(
        self,
        language: str,
        session_id: str,
        preferred: int | None = None,
        default_port: int | None = None,
        fallback_ranges: list[int] | None = None,
    ) -> int:
        """Mock port allocation.

        Returns predictable port numbers for testing.
        """
        if preferred and preferred not in self._get_all_allocated():
            port = preferred
        else:
            port = self._next_port
            self._next_port += 1

        if session_id not in self._allocated:
            self._allocated[session_id] = set()
        self._allocated[session_id].add(port)

        return port

    def release_port(self, port: int, session_id: str | None = None) -> bool:
        """Mock port release."""
        for sid, ports in self._allocated.items():
            if (not session_id or sid == session_id) and port in ports:
                ports.remove(port)
                return True
        return False

    def release_session_ports(self, session_id: str) -> list[int]:
        """Mock session port release."""
        ports = list(self._allocated.get(session_id, []))
        if session_id in self._allocated:
            del self._allocated[session_id]
        return ports

    def _get_all_allocated(self) -> set[int]:
        """Get all allocated ports across sessions."""
        all_ports = set()
        for ports in self._allocated.values():
            all_ports.update(ports)
        return all_ports


# Convenience functions for common test patterns


def create_mock_port_registry() -> MockPortRegistry:
    """Create a mock port registry for unit tests.

    Returns
    -------
    MockPortRegistry
        Mock registry instance
    """
    return MockPortRegistry()


async def allocate_test_ports(
    count: int,
    test_id: str,
    language: str = Language.PYTHON.value,
) -> list[int]:
    """Allocate multiple ports for testing.

    Parameters
    ----------
    count : int
        Number of ports to allocate
    test_id : str
        Test identifier
    language : str
        Language adapter type

    Returns
    -------
    List[int]
        List of allocated port numbers
    """
    async with isolated_ports(test_id) as port_manager:
        ports = []
        for _ in range(count):
            port = await port_manager.allocate_port(language)
            ports.append(port)
        return ports


class PortAssertions:
    """Port-related assertion helpers for tests."""

    @staticmethod
    def assert_port_available(port: int) -> None:
        """Assert that a port is available for binding.

        Parameters
        ----------
        port : int
            Port to check

        Raises
        ------
        AssertionError
            If port is not available
        """
        import socket

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
        except OSError as e:
            msg = f"Port {port} is not available: {e}"
            raise AssertionError(msg) from e
        finally:
            if sock:
                sock.close()

    @staticmethod
    def assert_port_in_use(port: int) -> None:
        """Assert that a port is currently in use.

        Parameters
        ----------
        port : int
            Port to check

        Raises
        ------
        AssertionError
            If port is not in use
        """
        import socket

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("localhost", port))
            # If we get here, port is available (not in use)
            msg = f"Port {port} is available (not in use)"
            raise AssertionError(msg)
        except OSError:
            # Port is in use - this is what we want
            pass
        finally:
            if sock:
                sock.close()

    @staticmethod
    async def assert_port_becomes_available(
        port: int,
        timeout: float = 5.0,
        interval: float = 0.1,
    ) -> None:
        """Assert that a port becomes available within timeout.

        Parameters
        ----------
        port : int
            Port to monitor
        timeout : float
            Maximum wait time in seconds
        interval : float
            Check interval in seconds

        Raises
        ------
        AssertionError
            If port doesn't become available within timeout
        """
        import time

        start = time.time()
        while time.time() - start < timeout:
            try:
                PortAssertions.assert_port_available(port)
                return  # Port is available
            except AssertionError:
                await asyncio.sleep(interval)

        msg = f"Port {port} did not become available within {timeout}s"
        raise AssertionError(msg)
