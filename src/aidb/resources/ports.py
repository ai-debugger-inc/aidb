"""Network port management utilities."""

import asyncio
import contextlib
import errno
import fcntl
import random
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import psutil

from aidb.common.errors import AidbError, ResourceExhaustedError
from aidb.patterns import Obj
from aidb_common.env import reader
from aidb_common.io import safe_read_json, safe_write_json
from aidb_common.io.files import FileOperationError
from aidb_common.patterns import Singleton

if TYPE_CHECKING:
    from aidb.interfaces import IContext


# Constants
DEFAULT_HOST = "localhost"
REGISTRY_KEY_ALLOCATED_PORTS = "allocated_ports"
REGISTRY_KEY_UPDATED_AT = "updated_at"


class PortHandler(Obj):
    """Utility class for managing TCP ports."""

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
        await asyncio.sleep(0.1)

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
    """Unified port registry with complete cross-process coordination.

    This class handles ALL port management for aidb:
    - Cross-process port allocation via file locking
    - In-process thread safety via self.lock (from Obj)
    - Session-to-port mappings
    - Socket reservation to prevent race conditions
    - Automatic cleanup on session termination

    Benefits for production:
    - Multiple debug sessions without conflicts
    - Parallel test execution
    - Multi-user debugging on shared systems
    - CI/CD pipeline compatibility
    """

    _current_session_id: str | None
    _initialized: bool

    def __init__(
        self,
        session_id: str | None = None,
        ctx: Optional["IContext"] = None,
    ) -> None:
        """Initialize the unified port registry.

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
        # Add sync lock for thread-safe registry operations
        self.lock = threading.RLock()

        # In-process tracking
        self._session_ports: dict[str, set[int]] = {}
        self._port_to_session: dict[int, str] = {}
        self._reserved_sockets: dict[int, socket.socket] = {}
        self._current_session_id = session_id

        # Cross-process coordination - uses ctx storage (auto-creates dirs)
        self.registry_file = self.ctx.get_storage_path("ports", "allocated_ports.json")
        self.lock_file = self.ctx.get_storage_path("ports", "ports.lock")

        # Cleanup rate limiting
        self._last_cleanup_time = 0.0
        self._cleanup_min_interval = 5.0  # Minimum 5 seconds between cleanups
        self._cleanup_in_progress = False

        # Cleanup stale ports on initialization
        self._cleanup_on_init()

        self._initialized = True

    def _cleanup_on_init(self) -> None:
        """Clean up stale ports on initialization.

        This runs once when the registry is first created to remove any stale port
        allocations from previous runs.
        """
        try:
            # Use a short timeout for init cleanup
            with Path(self.lock_file).open("a+") as lock_fd:
                # Try to acquire lock with timeout
                max_wait = 0.5  # 500ms max wait on init
                start = time.time()

                while (time.time() - start) < max_wait:
                    try:
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Got the lock, do cleanup
                        allocated = self._read_cross_process_registry()
                        if allocated:
                            cleaned = self._cleanup_stale_ports(allocated)
                            if len(cleaned) < len(allocated):
                                self._write_cross_process_registry(cleaned)
                                self.ctx.debug(
                                    f"Init cleanup: removed "
                                    f"{len(allocated) - len(cleaned)} stale ports",
                                )
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                        break
                    except OSError as e:
                        if e.errno != errno.EAGAIN:
                            raise
                        # Lock is held by another process, wait a bit
                        time.sleep(0.05)
        except Exception as e:
            # Don't fail init if cleanup fails
            self.ctx.debug(f"Could not perform init cleanup: {e}")

    async def acquire_port(
        self,
        language: str,
        session_id: str | None = None,
        preferred: int | None = None,
        default_port: int | None = None,
        fallback_ranges: list[int] | None = None,
    ) -> int:
        """Acquire a port with complete safety.

        This is THE method for getting ports. It handles:
        1. Cross-process coordination via file locking
        2. AidbThread safety via self.lock
        3. Socket reservation
        4. Registry updates

        Parameters
        ----------
        language : str
            Programming language (for adapter-specific port ranges)
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
        AidbError
            If no ports are available
        """
        sid = session_id or self._current_session_id
        if not sid:
            msg = "No session_id provided and no current session ID set"
            raise ValueError(msg)

        # File lock for cross-process safety with non-blocking attempts and timeout.
        lock_timeout = reader.read_float("AIDB_PORT_LOCK_TIMEOUT_SEC", default=15.0)
        lock_start = time.time()
        lock_acquired = False
        wait_time = 0.0

        # Use non-blocking flock with exponential backoff + jitter
        with Path(self.lock_file).open("a+") as lock_fd:  # noqa: ASYNC230
            delay = 0.02  # 20ms initial backoff
            while True:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    break
                except OSError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    wait_time = time.time() - lock_start
                    if wait_time >= lock_timeout:
                        break
                    # Backoff with jitter, cap at 500ms between tries
                    sleep_for = min(delay, 0.5) + random.uniform(0, 0.01)
                    # Async-friendly backoff to avoid blocking the event loop
                    await asyncio.sleep(sleep_for)
                    delay = min(delay * 2.0, 0.5)

            if lock_acquired:
                try:
                    # AidbThread lock for in-process safety (uses self.lock from Obj)
                    with self.lock:
                        # Read cross-process registry
                        cross_process_allocated = self._read_cross_process_registry()

                        # Use provided configuration or defaults
                        if not default_port or not fallback_ranges:
                            msg = "default_port and fallback_ranges must be provided"
                            raise ValueError(
                                msg,
                            )

                        # Create config object for compatibility
                        @dataclass
                        class AdapterConfig:
                            default_dap_port: int = 0
                            fallback_port_ranges: list = field(default_factory=list)

                        adapter_config = AdapterConfig(
                            default_dap_port=default_port,
                            fallback_port_ranges=fallback_ranges,
                        )

                        # Try preferred port first
                        if preferred:
                            if preferred in cross_process_allocated:
                                # Test if actually available (might be stale entry)
                                sock = None
                                try:
                                    sock = self._create_bound_socket(preferred)
                                    # Port is free! Remove stale entry from registry
                                    self.ctx.debug(
                                        f"Port {preferred} marked as allocated but is "
                                        f"free, removing stale entry",
                                    )
                                    cross_process_allocated.discard(preferred)
                                    sock.close()  # Close immediately, don't hold it
                                    # Now try to acquire normally
                                    if await self._try_acquire_port(
                                        preferred,
                                        sid,
                                        cross_process_allocated,
                                    ):
                                        self.ctx.info(
                                            f"Acquired preferred port {preferred} for "
                                            f"{language} (was stale)",
                                        )
                                        return preferred
                                except OSError:
                                    # Port actually in use
                                    if sock:
                                        sock.close()
                                    self.ctx.debug(
                                        f"Preferred port {preferred} is actually in use",
                                    )
                            else:
                                # Not in registry, acquire normally
                                if await self._try_acquire_port(
                                    preferred,
                                    sid,
                                    cross_process_allocated,
                                ):
                                    self.ctx.info(
                                        f"Acquired preferred port "
                                        f"{preferred} for {language}",
                                    )
                                    return preferred

                        # Find available port from language ranges
                        port = await self._find_and_acquire_port(
                            language,
                            sid,
                            cross_process_allocated,
                            adapter_config,
                        )

                        if port:
                            if wait_time > 0.5:
                                self.ctx.debug(
                                    f"Port lock acquired after {wait_time:.2f}s; "
                                    f"allocated port {port}",
                                )
                            else:
                                self.ctx.debug(
                                    f"Port lock acquired quickly; allocated port {port}",
                                )
                            self.ctx.info(
                                f"Acquired port {port} for {language} session {sid[:8]}",
                            )
                            return port

                        msg = f"No available ports for {language}"
                        raise ResourceExhaustedError(
                            msg,
                            resource_type="port",
                            details={
                                "language": language,
                                "attempted_ranges": fallback_ranges,
                                "session_id": self._current_session_id,
                            },
                        )

                finally:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

        # Fallback path: lock not acquired within timeout. Avoid blocking.
        # Allocate optimistically by binding sockets; update cross-process
        # registry on a best-effort basis without waiting.
        self.ctx.warning(
            f"Port lock busy for {wait_time:.2f}s (>= {lock_timeout}s timeout). "
            f"Falling back to optimistic allocation.",
        )

        # Validate inputs
        if not default_port or not fallback_ranges:
            msg = "default_port and fallback_ranges must be provided"
            raise ValueError(msg)

        # Build candidate list similar to _find_and_acquire_port but without
        # consulting cross-process registry (we don't have the lock here).
        candidates: list[int] = []
        candidates.append(int(default_port))
        for start in fallback_ranges:
            for offset in range(100):
                candidates.append(int(start) + offset)
        random.shuffle(candidates)

        # Try a larger number of candidates to improve success rate under load
        max_attempts = min(len(candidates), 200)
        attempts = 0

        with self.lock:
            for port in candidates:
                if attempts >= max_attempts:
                    break
                attempts += 1
                if self._optimistic_try_acquire(port, sid):
                    # Best-effort registry update without blocking the event loop
                    await self._best_effort_registry_add(port)

                    self.ctx.info(
                        f"Optimistically acquired port {port} for {language} "
                        f"session {sid[:8]} after {attempts} attempts",
                    )
                    return port

        msg = f"No available ports for {language} (optimistic path exhausted)"
        raise ResourceExhaustedError(
            msg,
            resource_type="port",
            details={
                "language": language,
                "attempted_ranges": fallback_ranges,
                "session_id": self._current_session_id,
                "mode": "optimistic",
            },
        )

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
                self.ctx.debug(f"Released socket reservation for port {port}")

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
        with Path(self.lock_file).open("a+") as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                with self.lock:  # Use self.lock from Obj
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
                        try:
                            sock.close()
                        except Exception as e:
                            self.ctx.debug(f"Error closing socket for port {port}: {e}")

                    # Update in-process registry
                    owner_session = self._port_to_session.pop(port, None)
                    if owner_session and owner_session in self._session_ports:
                        self._session_ports[owner_session].discard(port)
                        if not self._session_ports[owner_session]:
                            del self._session_ports[owner_session]

                    # Update cross-process registry
                    allocated = self._read_cross_process_registry()
                    if port in allocated:
                        allocated.discard(port)
                        self._write_cross_process_registry(allocated)

                    self.ctx.debug(f"Successfully released port {port}")
                    return True

            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

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

        Returns
        -------
        List[int]
            Ports that were successfully released
        """
        sid = session_id or self._current_session_id
        if not sid:
            return []

        with self.lock:  # Use self.lock from Obj
            ports = list(self._session_ports.get(sid, []))

        if not ports:
            self.ctx.debug(f"No ports to release for session {sid}")
            return []

        # Release each port (handles locking internally)
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

    async def _find_and_acquire_port(
        self,
        _language: str,
        session_id: str,
        allocated: set[int],
        adapter_config,
    ) -> int | None:
        """Find and acquire an available port.

        MUST be called with both locks held!
        """
        # Build candidate list
        candidates = []

        # Default port
        if adapter_config.default_dap_port not in allocated:
            candidates.append(adapter_config.default_dap_port)

        # Fallback ranges
        for start in adapter_config.fallback_port_ranges:
            for offset in range(100):
                port = start + offset
                if port not in allocated:
                    candidates.append(port)

        # Randomize to reduce conflicts in parallel execution
        random.shuffle(candidates)

        # Try each candidate (limit attempts for performance)
        # Increase attempt budget to better handle high test parallelism
        attempt_cap = min(len(candidates), 200)
        for port in candidates[:attempt_cap]:
            if await self._try_acquire_port(port, session_id, allocated):
                return port

        return None

    async def _try_acquire_port(
        self,
        port: int,
        session_id: str,
        cross_process_allocated: set[int],
    ) -> bool:
        """Try to acquire a specific port.

        MUST be called with both locks held!
        """
        # Check if already allocated in-process
        if port in self._port_to_session:
            return False

        # Try to bind socket (ultimate test of availability)
        sock = None
        try:
            sock = self._create_bound_socket(port)
            sock.listen(1)

            # Success! Update all registries
            # 1. Reserve socket (prevents race conditions)
            self._reserved_sockets[port] = sock

            # 2. Update in-process registry
            if session_id not in self._session_ports:
                self._session_ports[session_id] = set()
            self._session_ports[session_id].add(port)
            self._port_to_session[port] = session_id

            # 3. Update cross-process registry
            cross_process_allocated.add(port)
            self._write_cross_process_registry(cross_process_allocated)

            self.ctx.debug(
                f"Successfully acquired port {port} for session {session_id}",
            )
            return True

        except OSError:
            if sock:
                sock.close()
            return False

    def _optimistic_try_acquire(self, port: int, session_id: str) -> bool:
        """Try to acquire a port without holding the file lock.

        Uses OS-level bind to ensure exclusivity across processes, and only
        updates in-process registries. Cross-process registry updates are
        attempted on a best-effort basis by the caller when convenient.

        Parameters
        ----------
        port : int
            Port to acquire
        session_id : str
            Session ID requesting the port

        Returns
        -------
        bool
            True if acquired, False otherwise
        """
        # Avoid duplicate allocation within the same process
        if port in self._port_to_session:
            return False

        sock = None
        try:
            sock = self._create_bound_socket(port)
            sock.listen(1)

            # Reserve socket and update in-process registries only
            self._reserved_sockets[port] = sock
            if session_id not in self._session_ports:
                self._session_ports[session_id] = set()
            self._session_ports[session_id].add(port)
            self._port_to_session[port] = session_id

            self.ctx.debug(
                f"Optimistically acquired port {port} for session {session_id}",
            )
            return True
        except OSError:
            if sock:
                with contextlib.suppress(Exception):
                    sock.close()
            return False

    async def _best_effort_registry_add(self, port: int) -> None:
        """Attempt to add a port to the cross-process registry without blocking.

        Runs blocking file I/O in a thread via ``asyncio.to_thread`` and uses
        a non-blocking flock to avoid waiting if another process holds the lock.

        Parameters
        ----------
        port : int
            Port to add to the cross-process registry
        """

        def _do_update() -> None:
            try:
                with Path(self.lock_file).open("a+") as lock_fd:  # noqa: ASYNC230
                    try:
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        allocated = self._read_cross_process_registry()
                        allocated.add(port)
                        self._write_cross_process_registry(allocated)
                    except OSError as e:  # Lock busy; skip
                        if e.errno != errno.EAGAIN:
                            raise
                    finally:
                        with contextlib.suppress(Exception):
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except Exception as e:
                # Do not surface errors from best-effort path
                self.ctx.debug(f"Best-effort registry update skipped: {e}")

        await asyncio.to_thread(_do_update)

    def _read_cross_process_registry(self) -> set[int]:
        """Read the cross-process port registry.

        MUST be called with file lock held!
        """
        try:
            path = Path(self.registry_file)
            if path.exists():
                data = safe_read_json(path) or {}
                return set(data.get(REGISTRY_KEY_ALLOCATED_PORTS, []))
        except FileOperationError:
            pass
        return set()

    def _write_cross_process_registry(self, allocated: set[int]) -> None:
        """Write the cross-process port registry.

        MUST be called with file lock held!
        """
        safe_write_json(
            Path(self.registry_file),
            {
                REGISTRY_KEY_ALLOCATED_PORTS: list(allocated),
                REGISTRY_KEY_UPDATED_AT: time.time(),
            },
        )

    def _cleanup_stale_ports(self, allocated: set[int]) -> set[int]:
        """Remove stale port allocations.

        Checks if ports are actually in use and removes those that aren't.
        This handles cases where processes exit without cleanup.

        Parameters
        ----------
        allocated : Set[int]
            Currently allocated ports from registry

        Returns
        -------
        Set[int]
            Cleaned set of actually allocated ports
        """
        if not allocated:
            return allocated

        cleaned = set()
        stale = set()

        for port in allocated:
            # Check if port is actually in use
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # Try to bind to the port - if we can, it's not in use
                sock.bind(("127.0.0.1", port))
                # Port is free, it was stale
                stale.add(port)
                sock.close()
            except OSError:
                # Port is in use, keep it in the registry
                cleaned.add(port)
            finally:
                with contextlib.suppress(Exception):
                    sock.close()

        if stale:
            self.ctx.info(
                f"Cleaned {len(stale)} stale port allocations: {sorted(stale)}",
            )

        return cleaned

    def _create_bound_socket(self, port: int) -> socket.socket:
        """Create and bind a socket to the specified port.

        Parameters
        ----------
        port : int
            Port to bind to

        Returns
        -------
        socket.socket
            Bound socket

        Raises
        ------
        OSError
            If binding fails
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((DEFAULT_HOST, port))
        return sock

    def _check_cleanup_rate_limit(self, current_time: float) -> bool:
        """Check if cleanup should proceed based on rate limiting.

        Parameters
        ----------
        current_time : float
            Current timestamp

        Returns
        -------
        bool
            True if cleanup should proceed, False if rate-limited
        """
        with self.lock:  # AidbThread safety
            if self._cleanup_in_progress:
                self.ctx.debug("Cleanup already in progress, skipping")
                return False

            if current_time - self._last_cleanup_time < self._cleanup_min_interval:
                self.ctx.debug(
                    f"Skipping cleanup, last run "
                    f"{current_time - self._last_cleanup_time:.1f}s ago",
                )
                return False

            self._cleanup_in_progress = True
            return True

    def _acquire_cleanup_lock(self, lock_fd) -> bool:
        """Try to acquire file lock for cleanup operation.

        Parameters
        ----------
        lock_fd : file descriptor
            File descriptor for lock file

        Returns
        -------
        bool
            True if lock acquired, False otherwise
        """
        for _ in range(10):  # Try for up to 1 second
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError as e:
                if e.errno != errno.EAGAIN:
                    raise
                time.sleep(0.1)

        self.ctx.debug("Could not acquire lock for cleanup, skipping")
        return False

    def _find_active_ports(self, allocated: set[int]) -> set[int]:
        """Find which allocated ports are actually still in use.

        Parameters
        ----------
        allocated : set[int]
            Set of allocated ports from registry

        Returns
        -------
        set[int]
            Set of ports that are actually in use
        """
        active = set()

        for port in allocated:
            sock = None
            try:
                sock = self._create_bound_socket(port)
                sock.close()
                # Port is free, don't keep it in registry
            except OSError:
                # Port is in use, keep it
                if sock:
                    sock.close()
                active.add(port)

        return active

    def _perform_cleanup(self, allocated: set[int], active: set[int]) -> int:
        """Perform the actual cleanup of stale allocations.

        Parameters
        ----------
        allocated : set[int]
            Set of allocated ports from registry
        active : set[int]
            Set of ports actually in use

        Returns
        -------
        int
            Number of ports cleaned up
        """
        cleaned = 0
        if len(active) < len(allocated):
            cleaned = len(allocated) - len(active)
            self._write_cross_process_registry(active)
            self.ctx.info(f"Cleaned up {cleaned} stale port allocations")

        return cleaned

    def cleanup_stale_allocations(self) -> int:
        """Clean up stale port allocations from crashed processes.

        This is rate-limited to prevent excessive cleanup operations and uses
        both thread and file locks for safety.

        Returns
        -------
        int
            Number of stale allocations cleaned up
        """
        # Rate limiting check
        current_time = time.time()
        if not self._check_cleanup_rate_limit(current_time):
            return 0

        try:
            with Path(self.lock_file).open("a+") as lock_fd:
                # Try to acquire lock with timeout
                if not self._acquire_cleanup_lock(lock_fd):
                    return 0

                try:
                    # Read current allocations
                    allocated = self._read_cross_process_registry()

                    # Find which ports are actually in use
                    active = self._find_active_ports(allocated)

                    # Perform cleanup if needed
                    return self._perform_cleanup(allocated, active)

                finally:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            self.ctx.warning(f"Could not clean up stale allocations: {e}")
            return 0
        finally:
            with self.lock:
                self._cleanup_in_progress = False
                self._last_cleanup_time = current_time
