"""Network port management utilities.

This module provides port handling and session-level port tracking for aidb.
The core cross-process port allocation is delegated to
`aidb_common.network.allocator.CrossProcessPortAllocator`.
"""

import asyncio
import contextlib
import socket
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import psutil

from aidb.common.constants import (
    DEFAULT_ADAPTER_HOST,
    PORT_FALLBACK_RANGE_SIZE,
    SHORT_SLEEP_S,
)
from aidb.common.errors import AidbError, ResourceExhaustedError
from aidb.patterns import Obj
from aidb_common.network.allocator import CrossProcessPortAllocator
from aidb_common.patterns import Singleton

if TYPE_CHECKING:
    from aidb.interfaces import IContext


# Constants
DEFAULT_HOST = DEFAULT_ADAPTER_HOST  # Backward-compatible alias


class PortHandler(Obj):
    """Utility class for managing TCP ports.

    Provides methods to wait for ports to become available and check if processes are
    listening on specific ports.
    """

    def __init__(
        self,
        ctx: Optional["IContext"] = None,
        host: str = DEFAULT_HOST,
        ipv6: bool = False,
        timeout: float = 1.0,
    ) -> None:
        """Initialize a PortHandler instance.

        Parameters
        ----------
        ctx : IContext, optional
            Application context
        host : str
            Hostname to bind/connect to
        ipv6 : bool
            Whether to use IPv6
        timeout : float
            Socket timeout in seconds
        """
        super().__init__(ctx)
        self.host = host
        self.ipv6 = ipv6
        self.timeout = timeout

    def _check_specific_process_port(
        self,
        proc: asyncio.subprocess.Process,
        port: int,
    ) -> bool:
        """Check if a specific process or its children is listening on the port.

        This method checks both the launched process and its child processes.
        This is necessary because some debug adapters (like debugpy) spawn a
        separate adapter subprocess that actually listens on the port.

        Parameters
        ----------
        proc : asyncio.subprocess.Process
            The process to check
        port : int
            The port to check

        Returns
        -------
        bool
            True if process or any child is listening on the port
        """
        try:
            process = psutil.Process(proc.pid)

            # Check the process itself
            for conn in process.net_connections(kind="inet"):
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    self.ctx.debug(
                        f"Process {proc.pid} is listening on port {port}",
                    )
                    return True

            # Check child processes (needed for debugpy adapter subprocess)
            for child in process.children(recursive=True):
                try:
                    for conn in child.net_connections(kind="inet"):
                        is_listening = (
                            conn.laddr.port == port
                            and conn.status == psutil.CONN_LISTEN
                        )
                        if is_listening:
                            self.ctx.debug(
                                f"Child process {child.pid} of {proc.pid} "
                                f"is listening on port {port}",
                            )
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            self.ctx.debug(
                f"Process {proc.pid} (and children) not listening on port {port} yet",
            )
            return False
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self.ctx.debug(f"Cannot check process {proc.pid}: {e}")
            return False

    def _check_all_processes_for_port(self, port: int) -> bool:
        """Check all processes for the port.

        Parameters
        ----------
        port : int
            The port to check

        Returns
        -------
        bool
            True if any process is listening on the port
        """
        try:
            for process in psutil.process_iter(["pid", "name"]):
                try:
                    # Check any process that might be listening on our port
                    for conn in process.net_connections(kind="inet"):
                        if (
                            conn.laddr.port == port
                            and conn.status == psutil.CONN_LISTEN
                        ):
                            proc_name = process.info.get("name", "unknown")
                            self.ctx.debug(
                                f"Process {process.pid} ({proc_name}) "
                                f"is listening on port {port}",
                            )
                            return True
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
            return False
        except Exception as e:
            self.ctx.debug(f"psutil process iteration failed: {e}")
            return False

    def _check_named_processes_for_port(
        self,
        port: int,
        process_names: list[str],
    ) -> bool:
        """Check if any process with matching name is listening on the port.

        Used as fallback for detached adapter processes (e.g., debugpy spawns
        adapter with PPID=1, not as child of the launched process).

        Parameters
        ----------
        port : int
            The port to check
        process_names : list[str]
            Process names to match (case-insensitive substring match)

        Returns
        -------
        bool
            True if a matching process is listening on the port
        """
        try:
            for process in psutil.process_iter(["pid", "name"]):
                try:
                    name = (process.info.get("name") or "").lower()
                    if any(pn.lower() in name for pn in process_names):
                        for conn in process.net_connections(kind="inet"):
                            if (
                                conn.laddr.port == port
                                and conn.status == psutil.CONN_LISTEN
                            ):
                                self.ctx.debug(
                                    f"Process {process.pid} ({name}) is listening "
                                    f"on port {port} (detached adapter)",
                                )
                                return True
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    continue
            return False
        except Exception as e:
            self.ctx.debug(f"Named process check failed: {e}")
            return False

    def _check_process_still_running(
        self,
        proc: asyncio.subprocess.Process | None,
        port: int,
    ) -> None:
        """Check if process is still running and raise if it exited.

        Parameters
        ----------
        proc : asyncio.subprocess.Process | None
            The process to check
        port : int
            The port for error reporting

        Raises
        ------
        AidbError
            If process exited prematurely
        """
        if proc and proc.returncode is not None:
            self.ctx.error(f"Process exited with code {proc.returncode}")
            msg = f"Process exited prematurely with code {proc.returncode}"
            raise AidbError(
                msg,
                details={
                    "port": port,
                    "exit_code": proc.returncode,
                    "process_pid": proc.pid,
                },
                recoverable=False,
            )

    async def _wait_for_port_iteration(
        self,
        port: int,
        proc: asyncio.subprocess.Process | None,
        attempt: int,
        detached_process_names: list[str] | None = None,
    ) -> bool:
        """Perform a single iteration of port checking.

        Parameters
        ----------
        port : int
            The port to check
        proc : asyncio.subprocess.Process | None
            Optional specific process to check
        attempt : int
            Current attempt number
        detached_process_names : list[str] | None
            Process names to check for detached adapter processes

        Returns
        -------
        bool
            True if port is listening
        """
        self.ctx.debug(f"Checking port {port}... (attempt {attempt})")

        # Method 1: If we know the specific process, check only its connections
        # This is the strict check - only our process should be listening
        if proc and proc.returncode is None:
            if self._check_specific_process_port(proc, port):
                return True
            # Fallback for detached adapters (e.g., debugpy spawns adapter
            # with PPID=1, not as child of the launched process)
            if detached_process_names and self._check_named_processes_for_port(
                port,
                detached_process_names,
            ):
                return True
        elif not proc and self._check_all_processes_for_port(port):
            # Method 2: No specific process - check all processes for the port
            # This is used for attach mode where we don't launch the process
            self.ctx.debug(f"Port {port} is LISTENING (open)")
            return True

        self.ctx.debug(f"Port {port} is not LISTENING yet")
        await asyncio.sleep(SHORT_SLEEP_S)

        # Check if process exited
        self._check_process_still_running(proc, port)
        return False

    async def wait_for_port(
        self,
        port: int = 0,
        timeout: float = 10.0,
        proc: asyncio.subprocess.Process | None = None,
        detached_process_names: list[str] | None = None,
    ) -> bool:
        """Wait for a port to become available (LISTEN state, side-effect free).

        Parameters
        ----------
        port : int
            The port to wait for
        timeout : float
            Maximum time to wait in seconds
        proc : asyncio.subprocess.Process | None
            Optional specific process to check
        detached_process_names : list[str] | None
            Process names to check for detached adapter processes

        Raises
        ------
        AidbError
            If the port doesn't open in time or the process exits.
        """
        self.ctx.debug(f"Waiting for port {port} on {self.host} (timeout={timeout}s)")

        start = time.time()
        attempt = 0

        while time.time() - start < timeout:
            attempt += 1
            if await self._wait_for_port_iteration(
                port,
                proc,
                attempt,
                detached_process_names,
            ):
                return True

        # Timeout reached
        msg = f"Timed out waiting for port {port} on {self.host}"
        self.ctx.error(msg)
        raise AidbError(
            msg,
            details={
                "port": port,
                "host": self.host,
                "timeout": timeout,
                "attempts": attempt,
            },
            recoverable=True,
        )


class PortRegistry(Singleton["PortRegistry"], Obj):
    """Session-level port tracking with cross-process coordination.

    This class provides:
    - Cross-process port allocation via CrossProcessPortAllocator
    - Session-to-port mappings for cleanup on session termination
    - Socket reservation to prevent race conditions during adapter startup

    The actual port allocation is delegated to CrossProcessPortAllocator
    in aidb_common.network.allocator.
    """

    _current_session_id: str | None
    _initialized: bool

    def __init__(
        self,
        session_id: str | None = None,
        ctx: Optional["IContext"] = None,
    ) -> None:
        """Initialize the port registry.

        Parameters
        ----------
        session_id : str, optional
            The session ID requesting port management
        ctx : IContext, optional
            Application context (uses singleton if not provided)
        """
        # Singleton pattern - only initialize once
        if hasattr(self, "_initialized") and self._initialized:
            # Update current session ID if provided
            if session_id:
                self._current_session_id = session_id
            return

        super().__init__(ctx)

        # Thread lock for in-process safety
        self.lock = threading.RLock()

        # Session-level tracking
        self._session_ports: dict[str, set[int]] = {}
        self._port_to_session: dict[int, str] = {}
        self._reserved_sockets: dict[int, socket.socket] = {}
        self._current_session_id = session_id

        # Delegate to cross-process allocator
        # Use ctx storage path if available for consistency
        registry_dir = Path(self.ctx.get_storage_path("ports", "")).parent
        self._allocator = CrossProcessPortAllocator(registry_dir=registry_dir)

        self._initialized = True

    async def acquire_port(
        self,
        language: str,
        session_id: str | None = None,
        preferred: int | None = None,
        default_port: int | None = None,
        fallback_ranges: list[int] | None = None,
    ) -> int:
        """Acquire a port with complete safety.

        Uses CrossProcessPortAllocator for atomic allocation, then reserves
        a socket to prevent race conditions during adapter startup.

        Parameters
        ----------
        language : str
            Programming language (for logging)
        session_id : str, optional
            Session ID requesting the port
        preferred : int, optional
            Preferred port to try first
        default_port : int, optional
            Default port for the adapter (e.g., 5678 for Python)
        fallback_ranges : List[int], optional
            List of port range start points to try

        Returns
        -------
        int
            Allocated port number

        Raises
        ------
        ResourceExhaustedError
            If no ports are available
        """
        sid = session_id or self._current_session_id
        if not sid:
            msg = "No session_id provided and no current session ID set"
            raise ValueError(msg)

        # Validate inputs
        if not default_port or not fallback_ranges:
            msg = "default_port and fallback_ranges must be provided"
            raise ValueError(msg)

        # Build candidate range for allocator
        # Start with default port, then fallback ranges
        range_start = fallback_ranges[0] if fallback_ranges else default_port
        total_range_size = len(fallback_ranges) * PORT_FALLBACK_RANGE_SIZE

        max_retries = 10  # Limit retries to prevent infinite loop
        with self.lock:
            for attempt in range(max_retries):
                try:
                    # Delegate to cross-process allocator
                    port = self._allocator.allocate(
                        preferred=preferred or default_port,
                        range_start=range_start,
                        range_size=total_range_size,
                    )

                    # Reserve socket to prevent race conditions
                    # If reservation fails, release port and try next one
                    if not self._reserve_socket(port):
                        self.ctx.debug(
                            f"Port {port} reservation failed (attempt {attempt + 1}), "
                            "releasing and retrying",
                        )
                        self._allocator.release(port)
                        continue

                    # Track session ownership
                    if sid not in self._session_ports:
                        self._session_ports[sid] = set()
                    self._session_ports[sid].add(port)
                    self._port_to_session[port] = sid

                    self.ctx.debug(
                        f"Acquired port {port} for {language} session {sid[:8]}",
                    )
                    return port

                except RuntimeError as e:
                    raise ResourceExhaustedError(
                        str(e),
                        resource_type="port",
                        details={
                            "language": language,
                            "attempted_ranges": fallback_ranges,
                            "session_id": sid,
                        },
                    ) from e

            # If we exhausted retries
            msg = f"Failed to acquire port after {max_retries} attempts"
            raise ResourceExhaustedError(
                msg,
                resource_type="port",
                details={
                    "language": language,
                    "attempted_ranges": fallback_ranges,
                    "session_id": sid,
                },
            )

    def _reserve_socket(self, port: int) -> bool:
        """Reserve a socket on the port to prevent races.

        Parameters
        ----------
        port : int
            Port to reserve

        Returns
        -------
        bool
            True if reservation succeeded, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # NOTE: Do NOT use SO_REUSEADDR here! The whole point of reservation
            # is to prevent other processes from binding to this port.
            # SO_REUSEADDR allows multiple binds to the same port.
            sock.bind((DEFAULT_HOST, port))
            sock.listen(1)
            self._reserved_sockets[port] = sock
            return True
        except OSError:
            return False

    def release_reserved_port(self, port: int) -> None:
        """Release just the socket reservation for a port.

        This is used when the adapter needs to bind to the port.
        The port remains allocated to the session.

        Parameters
        ----------
        port : int
            Port whose socket reservation to release
        """
        with self.lock:
            sock = self._reserved_sockets.pop(port, None)
            if sock:
                with contextlib.suppress(Exception):
                    sock.close()

    def release_port(self, port: int, session_id: str | None = None) -> bool:
        """Release a port back to the pool.

        Parameters
        ----------
        port : int
            Port to release
        session_id : str, optional
            Session releasing the port (for validation)

        Returns
        -------
        bool
            True if port was successfully released, False otherwise
        """
        with self.lock:
            # Validate session owns this port
            if session_id:
                owner = self._port_to_session.get(port)
                if owner and owner != session_id:
                    self.ctx.warning(
                        f"Session {session_id} trying to "
                        f"release port {port} owned by {owner}",
                    )
                    return False

            # Check if port is actually allocated
            if port not in self._port_to_session:
                self.ctx.debug(
                    f"Port {port} not in registry, nothing to release",
                )
                return False

            # Release socket reservation
            sock = self._reserved_sockets.pop(port, None)
            if sock:
                with contextlib.suppress(Exception):
                    sock.close()

            # Update session tracking
            owner_session = self._port_to_session.pop(port, None)
            if owner_session and owner_session in self._session_ports:
                self._session_ports[owner_session].discard(port)
                if not self._session_ports[owner_session]:
                    del self._session_ports[owner_session]

            # Release from cross-process allocator
            self._allocator.release(port)

            self.ctx.debug(f"Successfully released port {port}")
            return True

    def get_port_count(self, session_id: str | None = None) -> int:
        """Get the number of ports allocated to a session.

        Parameters
        ----------
        session_id : str, optional
            Session ID to check. If None, uses current session.

        Returns
        -------
        int
            Number of ports allocated to the session
        """
        sid = session_id or self._current_session_id
        if not sid:
            return 0

        with self.lock:
            return len(self._session_ports.get(sid, set()))

    def release_session_ports(self, session_id: str | None = None) -> list[int]:
        """Release all ports for a session.

        Called automatically when session ends.

        Parameters
        ----------
        session_id : str, optional
            Session ID whose ports to release

        Returns
        -------
        List[int]
            Ports that were successfully released
        """
        sid = session_id or self._current_session_id
        if not sid:
            return []

        with self.lock:
            ports = list(self._session_ports.get(sid, []))

        if not ports:
            self.ctx.debug(f"No ports to release for session {sid}")
            return []

        # Release each port
        released = []
        for port in ports:
            if self.release_port(port, sid):
                released.append(port)
            else:
                self.ctx.warning(f"Failed to release port {port} for session {sid}")

        self.ctx.info(
            f"Released {len(released)}/{len(ports)} ports for session {sid}: "
            f"{released}",
        )
        return released

    def cleanup_stale_allocations(self) -> int:
        """Clean up stale port allocations from crashed processes.

        This is delegated to the CrossProcessPortAllocator which handles
        stale lease cleanup automatically on each allocation.

        Returns
        -------
        int
            Number of stale allocations cleaned up (always 0, cleanup is automatic)
        """
        # Cleanup is now automatic in CrossProcessPortAllocator._cleanup_stale()
        # This method is kept for backward compatibility
        return 0
