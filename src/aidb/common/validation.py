"""Common validation utilities for aidb.

This module provides shared validation functions used across API and session layers to
ensure consistency and reduce duplication.
"""

from .errors import AidbError


def validate_thread_id(thread_id: int | None, default: int = 1) -> int:
    """Validate and resolve thread ID.

    Parameters
    ----------
    thread_id : int, optional
        Thread ID to validate
    default : int
        Default value if thread_id is None (default: 1)

    Returns
    -------
    int
        Validated thread ID with default if None

    Raises
    ------
    ValueError
        If thread ID is invalid
    """
    if thread_id is not None:
        if thread_id < 0:
            msg = f"Thread ID must be non-negative, got {thread_id}"
            raise ValueError(msg)
        return thread_id
    return default


def validate_frame_id(frame_id: int | None, default: int = 0) -> int:
    """Validate and resolve frame ID.

    Parameters
    ----------
    frame_id : int, optional
        Frame ID to validate
    default : int
        Default value if frame_id is None (default: 0)

    Returns
    -------
    int
        Validated frame ID with default if None

    Raises
    ------
    ValueError
        If frame ID is invalid
    """
    if frame_id is not None:
        if frame_id < 0:
            msg = f"Frame ID must be non-negative, got {frame_id}"
            raise ValueError(msg)
        return frame_id
    return default


def validate_memory_reference(memory_ref: str) -> str:
    """Validate memory reference string.

    Parameters
    ----------
    memory_ref : str
        Memory reference to validate

    Returns
    -------
    str
        Validated memory reference

    Raises
    ------
    ValueError
        If memory reference is invalid
    """
    if not memory_ref:
        msg = "Memory reference cannot be empty"
        raise ValueError(msg)

    # Basic validation - could be enhanced with format checking
    if not isinstance(memory_ref, str):
        msg = f"Memory reference must be a string, got {type(memory_ref)}"
        raise ValueError(msg)

    return memory_ref


def validate_port(port: int | None) -> int | None:
    """Validate network port number.

    Parameters
    ----------
    port : int, optional
        Port number to validate

    Returns
    -------
    int, optional
        Validated port number

    Raises
    ------
    ValueError
        If port is out of valid range
    """
    if port is not None and (port <= 0 or port > 65535):
        msg = f"Port must be between 1 and 65535, got {port}"
        raise ValueError(msg)
    return port


def validate_timeout(timeout: int, max_timeout: int = 600000) -> int:
    """Validate timeout value.

    Parameters
    ----------
    timeout : int
        Timeout in milliseconds
    max_timeout : int
        Maximum allowed timeout in ms (default: 600000 - 10 minutes)

    Returns
    -------
    int
        Validated timeout

    Raises
    ------
    ValueError
        If timeout is invalid
    """
    if timeout <= 0:
        msg = f"Timeout must be positive, got {timeout}"
        raise ValueError(msg)

    if timeout > max_timeout:
        msg = (
            f"Timeout cannot exceed {max_timeout}ms ({max_timeout // 60000} minutes), "
            f"got {timeout}"
        )
        raise ValueError(
            msg,
        )

    return timeout


def validate_process_id(pid: int | None) -> int | None:
    """Validate process ID.

    Parameters
    ----------
    pid : int, optional
        Process ID to validate

    Returns
    -------
    int, optional
        Validated process ID

    Raises
    ------
    AidbError
        If process ID is invalid
    """
    if pid is not None and pid <= 0:
        msg = f"Invalid process ID: {pid}"
        raise AidbError(msg)
    return pid


def validate_attach_config(
    pid: int | None,
    host: str | None,
    port: int | None,
) -> None:
    """Validate attach configuration parameters.

    Parameters
    ----------
    pid : int, optional
        Process ID for local attach
    host : str, optional
        Host for remote attach
    port : int, optional
        Port for remote attach

    Raises
    ------
    AidbError
        If attach configuration is invalid
    """
    if pid and (host or port):
        msg = "Cannot specify both pid (local attach) and host/port (remote attach)"
        raise AidbError(
            msg,
        )

    if (host and not port) or (port and not host):
        msg = "Both host and port must be specified for remote attach"
        raise AidbError(msg)

    # Validate individual components
    validate_process_id(pid)
    validate_port(port)
