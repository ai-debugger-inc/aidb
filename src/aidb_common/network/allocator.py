"""Cross-process atomic port allocation with file locking.

This module provides a centralized port allocation mechanism that coordinates
across multiple processes using file-based locking. All port allocation in
AIDB should go through this module to prevent race conditions.

Key features:
- File locking (fcntl.flock) for atomic cross-process operations
- Socket binding verification to handle TIME_WAIT states
- Lease mechanism with automatic cleanup for crashed processes
- Simple API: allocate_port() and release_port()
"""

import contextlib
import errno
import fcntl
import json
import os
import socket
import time
from collections.abc import Generator
from pathlib import Path

from aidb_logging import get_logger

logger = get_logger(__name__)

# Lock acquisition timeout - prevents indefinite blocking under heavy parallel load
LOCK_TIMEOUT_S = 30.0
LOCK_RETRY_INTERVAL_S = 0.1

# Default registry location
DEFAULT_REGISTRY_DIR = Path.home() / ".aidb"
DEFAULT_REGISTRY_FILE = "port_registry.json"
DEFAULT_LOCK_FILE = "port_registry.lock"

# Lease timeout - ports older than this can be reclaimed
DEFAULT_LEASE_TIMEOUT_S = 300.0  # 5 minutes

# Default port ranges
DEFAULT_PORT_RANGE_START = 10000
DEFAULT_PORT_RANGE_SIZE = 1000


class CrossProcessPortAllocator:
    """Atomic cross-process port allocation using file locks.

    This allocator ensures no two processes can allocate the same port
    by using:
    1. File-based registry with fcntl.flock() for atomicity
    2. Socket binding verification (catches TIME_WAIT states)
    3. Lease mechanism for automatic cleanup of crashed processes

    Parameters
    ----------
    registry_dir : Path, optional
        Directory for registry files. Defaults to ~/.aidb
    lease_timeout : float
        Time in seconds before a lease can be reclaimed. Default 300s (5 min)

    Examples
    --------
    >>> allocator = CrossProcessPortAllocator()
    >>> port = allocator.allocate(range_start=8000, range_size=100)
    >>> # Use the port...
    >>> allocator.release(port)
    """

    def __init__(
        self,
        registry_dir: Path | None = None,
        lease_timeout: float = DEFAULT_LEASE_TIMEOUT_S,
    ):
        self.registry_dir = registry_dir or DEFAULT_REGISTRY_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.registry_dir / DEFAULT_REGISTRY_FILE
        self.lock_file = self.registry_dir / DEFAULT_LOCK_FILE
        self.lease_timeout = lease_timeout

    @contextlib.contextmanager
    def _lock(self) -> Generator[None, None, None]:
        """Acquire exclusive lock on registry with timeout.

        Uses fcntl.flock() with LOCK_NB (non-blocking) and retry loop for
        cross-process synchronization. The lock is held for the duration of
        the context.

        Raises
        ------
        TimeoutError
            If lock cannot be acquired within LOCK_TIMEOUT_S seconds.
        """
        # Use 'a+' to create if not exists, but not truncate
        with self.lock_file.open("a+") as f:
            start_time = time.monotonic()
            acquired = False
            retry_count = 0

            while time.monotonic() - start_time < LOCK_TIMEOUT_S:
                try:
                    # Try non-blocking lock acquisition
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError as e:
                    if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                        # Lock held by another process, wait and retry
                        retry_count += 1
                        if retry_count % 50 == 0:  # Log every 5 seconds
                            logger.warning(
                                "Port registry lock contention: %d retries (%.1fs)",
                                retry_count,
                                time.monotonic() - start_time,
                            )
                        time.sleep(LOCK_RETRY_INTERVAL_S)
                    else:
                        raise

            if not acquired:
                elapsed = time.monotonic() - start_time
                msg = (
                    f"Port registry lock timeout after {elapsed:.1f}s - "
                    f"heavy parallel load detected"
                )
                logger.warning(msg)
                raise TimeoutError(msg)

            lock_elapsed = time.monotonic() - start_time
            if lock_elapsed > 0.5:
                logger.warning(
                    "Slow port registry lock: %.2fs (retries=%d)",
                    lock_elapsed,
                    retry_count,
                )

            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def _is_port_bindable(
        self,
        port: int,
        host: str = "127.0.0.1",
        check_ipv6: bool = True,
    ) -> bool:
        """Check if port can actually be bound on both IPv4 and IPv6.

        This catches ports in TIME_WAIT state that appear free in the registry
        but cannot actually be bound. Also checks IPv6 to prevent conflicts
        with servers (like Node.js) that bind to both IPv4 and IPv6.

        Parameters
        ----------
        port : int
            Port to check
        host : str
            Host to bind on
        check_ipv6 : bool
            Whether to also check IPv6 availability (default: True)

        Returns
        -------
        bool
            True if port can be bound on all required interfaces
        """
        # Check IPv4
        # NOTE: Do NOT use SO_REUSEADDR here! We need to verify the port is
        # truly free, not just "bindable with address reuse". Otherwise we'll
        # return ports in TIME_WAIT state that will fail actual reservation.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((host, port))
        except OSError:
            return False

        # Check IPv6 if enabled and host is localhost-like
        if check_ipv6 and host in ("127.0.0.1", "localhost", ""):
            try:
                with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
                    sock.bind(("::1", port))
            except OSError:
                return False

        return True

    def allocate(
        self,
        preferred: int | None = None,
        range_start: int = DEFAULT_PORT_RANGE_START,
        range_size: int = DEFAULT_PORT_RANGE_SIZE,
        host: str = "127.0.0.1",
    ) -> int:
        """Atomically allocate a port.

        Acquires a file lock, cleans up stale leases, then finds an available
        port by checking both the registry and actual socket bindability.

        Parameters
        ----------
        preferred : int, optional
            Preferred port to try first
        range_start : int
            Start of fallback port range (default: 10000)
        range_size : int
            Number of ports in fallback range (default: 1000)
        host : str
            Host to bind on (default: 127.0.0.1)

        Returns
        -------
        int
            Allocated port number

        Raises
        ------
        RuntimeError
            If no port could be allocated in the range
        """
        with self._lock():
            registry = self._load()
            self._cleanup_stale(registry)

            # Build candidate list - preferred first, then range
            candidates: list[int] = []
            if preferred is not None:
                candidates.append(preferred)
            candidates.extend(range(range_start, range_start + range_size))

            for port in candidates:
                port_key = str(port)

                # Skip if already leased (and lease is still valid)
                if port_key in registry:
                    continue

                # Verify actually bindable (catches TIME_WAIT)
                if not self._is_port_bindable(port, host):
                    continue

                # Success - record lease
                registry[port_key] = {
                    "pid": os.getpid(),
                    "timestamp": time.time(),
                }
                self._save(registry)

                logger.debug("Allocated port %d (pid=%d)", port, os.getpid())
                return port

            msg = (
                f"No available ports in range {range_start}-{range_start + range_size}"
            )
            raise RuntimeError(msg)

    def release(self, port: int) -> None:
        """Release a previously allocated port.

        Parameters
        ----------
        port : int
            Port to release
        """
        with self._lock():
            registry = self._load()
            port_key = str(port)
            if port_key in registry:
                del registry[port_key]
                self._save(registry)
                logger.debug("Released port %d (pid=%d)", port, os.getpid())

    def _load(self) -> dict:
        """Load registry from file.

        Returns
        -------
        dict
            Registry data with port -> lease info mappings
        """
        try:
            if self.registry_file.exists():
                content = self.registry_file.read_text()
                if content.strip():
                    return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load port registry: %s", e)
        return {}

    def _save(self, registry: dict) -> None:
        """Save registry to file.

        Parameters
        ----------
        registry : dict
            Registry data to save
        """
        try:
            self.registry_file.write_text(json.dumps(registry, indent=2))
        except OSError as e:
            logger.warning("Failed to save port registry: %s", e)

    def _cleanup_stale(self, registry: dict) -> None:
        """Remove leases older than timeout.

        NOTE: We only use timeout-based cleanup. We previously checked if ports
        were bindable (to detect crashed processes), but this was wrong: we
        intentionally release socket reservations before the adapter binds,
        making ports appear "free" while still validly leased.

        Parameters
        ----------
        registry : dict
            Registry to clean (modified in place)
        """
        now = time.time()
        stale: list[str] = []

        for port_key, info in registry.items():
            if now - info.get("timestamp", 0) > self.lease_timeout:
                stale.append(port_key)

        for port_key in stale:
            del registry[port_key]

        if stale:
            logger.debug("Cleaned up %d stale port leases (timeout)", len(stale))


# Global allocator instance (lazy initialized)
_allocator: CrossProcessPortAllocator | None = None


def get_allocator(registry_dir: Path | None = None) -> CrossProcessPortAllocator:
    """Get the global port allocator instance.

    Parameters
    ----------
    registry_dir : Path, optional
        Override registry directory (only used on first call)

    Returns
    -------
    CrossProcessPortAllocator
        The global allocator instance
    """
    global _allocator
    if _allocator is None:
        _allocator = CrossProcessPortAllocator(registry_dir=registry_dir)
    return _allocator


def allocate_port(
    preferred: int | None = None,
    range_start: int = DEFAULT_PORT_RANGE_START,
    range_size: int = DEFAULT_PORT_RANGE_SIZE,
    host: str = "127.0.0.1",
) -> int:
    """Manage atomic port allocation.

    Parameters
    ----------
    preferred : int, optional
        Preferred port to try first
    range_start : int
        Start of fallback port range
    range_size : int
        Number of ports in fallback range
    host : str
        Host to bind on

    Returns
    -------
    int
        Allocated port number

    Examples
    --------
    >>> port = allocate_port(range_start=8000, range_size=100)
    >>> # Use the port...
    >>> release_port(port)
    """
    return get_allocator().allocate(preferred, range_start, range_size, host)


def release_port(port: int) -> None:
    """Manage port releases.

    Parameters
    ----------
    port : int
        Port to release
    """
    get_allocator().release(port)
