"""Portable port management utilities.

This module provides lightweight, portable port utilities for use across the AIDB
codebase. These utilities have minimal dependencies and can be used by both the core
library and tests without circular imports.

For the full-featured PortRegistry with cross-process coordination and file locking, see
aidb.resources.ports.
"""

import contextlib
import socket
from collections.abc import Generator

from aidb_logging import get_logger

logger = get_logger(__name__)

# Default port ranges for different use cases
DEFAULT_PORT_RANGE_START = 10000
DEFAULT_PORT_RANGE_END = 65535
DEFAULT_MAX_ATTEMPTS = 100

# Hosts that should trigger IPv6 checking
LOCALHOST_HOSTS = ("127.0.0.1", "localhost", "")


def _set_socket_sharing_options(sock: socket.socket) -> None:
    """Set socket options to allow port sharing with other processes.

    Uses SO_REUSEPORT which allows multiple sockets to bind to the same port
    simultaneously. This is essential for port reservation where a test holds
    a port while the debugged program also needs to bind to it.

    Falls back to SO_REUSEADDR on systems where SO_REUSEPORT is unavailable
    (older Linux < 3.9, some BSD variants).

    Parameters
    ----------
    sock : socket.socket
        Socket to configure
    """
    try:
        # SO_REUSEPORT allows multiple sockets on same port (Darwin, Linux 3.9+)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        # Fallback for systems without SO_REUSEPORT
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


def _check_port_on_family(
    port: int,
    host: str,
    family: socket.AddressFamily,
) -> bool:
    """Check if a port is available for binding on a specific address family.

    Parameters
    ----------
    port : int
        Port number to check
    host : str
        Host address to check on
    family : socket.AddressFamily
        Socket address family (AF_INET or AF_INET6)

    Returns
    -------
    bool
        True if port is available for binding on this family
    """
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            _set_socket_sharing_options(sock)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def _is_ipv6_available() -> bool:
    """Check if IPv6 is available on this system.

    Returns
    -------
    bool
        True if IPv6 sockets can be created
    """
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM):
            return True
    except OSError:
        return False


def is_port_available(
    port: int,
    host: str = "127.0.0.1",
    check_ipv6: bool = True,
) -> bool:
    """Check if a port is available for binding on both IPv4 and IPv6.

    Uses socket binding (not connect) to accurately check availability.
    This is more reliable than connect_ex which checks if something is listening.

    For localhost-like hosts, also checks IPv6 availability to prevent conflicts
    with servers that bind to both IPv4 and IPv6 (like Node.js).

    Parameters
    ----------
    port : int
        Port number to check (1-65535)
    host : str
        Host address to check on (default: 127.0.0.1)
    check_ipv6 : bool
        Whether to also check IPv6 availability for localhost hosts (default: True)

    Returns
    -------
    bool
        True if port is available for binding on all required interfaces

    Examples
    --------
    >>> if is_port_available(8000):
    ...     print("Port 8000 is free on both IPv4 and IPv6")
    """
    if not 1 <= port <= 65535:
        return False

    # Check IPv4
    if not _check_port_on_family(port, host, socket.AF_INET):
        return False

    # Check IPv6 if enabled and host is localhost-like
    # This prevents issues with servers (like Node.js) that bind to ::1
    ipv6_check_needed = check_ipv6 and host in LOCALHOST_HOSTS and _is_ipv6_available()
    if ipv6_check_needed and not _check_port_on_family(port, "::1", socket.AF_INET6):
        logger.debug(
            "Port %d available on IPv4 but not IPv6 (::1)",
            port,
        )
        return False

    return True


def find_available_port(
    start_port: int = DEFAULT_PORT_RANGE_START,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    host: str = "127.0.0.1",
    check_ipv6: bool = True,
) -> int | None:
    """Find an available port starting from a given port number.

    Searches sequentially from start_port until an available port is found
    or max_attempts is reached. By default, checks both IPv4 and IPv6 for
    localhost hosts.

    Parameters
    ----------
    start_port : int
        Starting port number to search from
    max_attempts : int
        Maximum number of ports to try
    host : str
        Host address to check on
    check_ipv6 : bool
        Whether to also check IPv6 availability (default: True)

    Returns
    -------
    int | None
        Available port number if found, None otherwise

    Examples
    --------
    >>> port = find_available_port(8000)
    >>> if port:
    ...     print(f"Using port {port}")
    """
    for i in range(max_attempts):
        port = start_port + i
        if port > 65535:
            break
        if is_port_available(port, host, check_ipv6):
            logger.debug("Found available port %d after %d attempts", port, i + 1)
            return port

    logger.warning(
        "No available port found in range %d-%d",
        start_port,
        min(start_port + max_attempts - 1, 65535),
    )
    return None


def get_ephemeral_port(host: str = "127.0.0.1") -> int:
    """Get an ephemeral port assigned by the OS.

    This is the most reliable way to get a free port - let the OS assign one.
    The port is briefly bound then released, so there's a small race window.

    Parameters
    ----------
    host : str
        Host address to bind on

    Returns
    -------
    int
        An available ephemeral port number

    Examples
    --------
    >>> port = get_ephemeral_port()
    >>> # Use port immediately to minimize race window
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        _set_socket_sharing_options(sock)
        sock.bind((host, 0))
        return sock.getsockname()[1]


@contextlib.contextmanager
def reserve_port(
    preferred_port: int | None = None,
    host: str = "127.0.0.1",
    fallback_range_start: int = DEFAULT_PORT_RANGE_START,
    max_fallback_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Generator[int, None, None]:
    """Reserve a port with automatic fallback to alternatives.

    Context manager that reserves a port by binding a socket. The socket is held
    for the duration of the context to prevent other processes from taking the port.

    If preferred_port is unavailable, automatically finds an alternative in the
    fallback range.

    Parameters
    ----------
    preferred_port : int | None
        Preferred port to use. If None, uses ephemeral port.
    host : str
        Host address to bind on
    fallback_range_start : int
        Start of fallback port range if preferred is unavailable
    max_fallback_attempts : int
        Maximum attempts to find fallback port

    Yields
    ------
    int
        The reserved port number

    Raises
    ------
    OSError
        If no port could be reserved after all attempts

    Examples
    --------
    >>> with reserve_port(8000) as port:
    ...     print(f"Reserved port {port}")
    ...     # Port is held until context exits
    ...     start_server(port)
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _set_socket_sharing_options(sock)

    actual_port: int | None = None

    try:
        # Try preferred port first
        if preferred_port is not None:
            try:
                sock.bind((host, preferred_port))
                actual_port = preferred_port
                logger.debug("Reserved preferred port %d", actual_port)
            except OSError:
                logger.debug(
                    "Preferred port %d unavailable, searching for alternative",
                    preferred_port,
                )

        # Fall back to finding an available port
        if actual_port is None:
            for i in range(max_fallback_attempts):
                try_port = fallback_range_start + i
                if try_port > 65535:
                    break
                try:
                    sock.bind((host, try_port))
                    actual_port = try_port
                    logger.debug(
                        "Reserved fallback port %d (preferred was %s)",
                        actual_port,
                        preferred_port,
                    )
                    break
                except OSError:
                    continue

        # Last resort: ephemeral port
        if actual_port is None:
            sock.bind((host, 0))
            actual_port = sock.getsockname()[1]
            logger.debug("Reserved ephemeral port %d", actual_port)

        yield actual_port

    finally:
        with contextlib.suppress(Exception):
            sock.close()
