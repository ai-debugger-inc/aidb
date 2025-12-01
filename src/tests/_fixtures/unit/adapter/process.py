"""Mock process management for unit tests.

Provides mock implementations for asyncio subprocess and ProcessManager for testing
adapter components.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest


@pytest.fixture
def mock_asyncio_process() -> MagicMock:
    """Create a mock asyncio subprocess.

    The mock simulates asyncio.subprocess.Process for testing
    adapter process management without spawning real processes.

    Returns
    -------
    MagicMock
        Mock process with common attributes and methods
    """
    proc = MagicMock(spec=asyncio.subprocess.Process)

    # Process identification
    proc.pid = 12345
    proc.returncode = None  # Process still running

    # Communication methods
    proc.communicate = AsyncMock(return_value=(b"", b""))
    proc.wait = AsyncMock(return_value=0)

    # Termination methods
    proc.terminate = MagicMock()
    proc.kill = MagicMock()

    # I/O streams
    proc.stdout = MagicMock()
    proc.stdout.read = AsyncMock(return_value=b"")
    proc.stdout.readline = AsyncMock(return_value=b"")

    proc.stderr = MagicMock()
    proc.stderr.read = AsyncMock(return_value=b"")
    proc.stderr.readline = AsyncMock(return_value=b"")

    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()

    return proc


@pytest.fixture
def mock_asyncio_process_exited() -> MagicMock:
    """Create a mock process that has exited.

    Returns
    -------
    MagicMock
        Mock process with non-None returncode
    """
    proc = MagicMock(spec=asyncio.subprocess.Process)
    proc.pid = 12345
    proc.returncode = 0  # Process exited successfully
    proc.communicate = AsyncMock(return_value=(b"output", b""))
    proc.wait = AsyncMock(return_value=0)
    return proc


@pytest.fixture
def mock_asyncio_process_failed() -> MagicMock:
    """Create a mock process that failed.

    Returns
    -------
    MagicMock
        Mock process with error returncode
    """
    proc = MagicMock(spec=asyncio.subprocess.Process)
    proc.pid = 12345
    proc.returncode = 1  # Process failed
    proc.communicate = AsyncMock(return_value=(b"", b"error message"))
    proc.wait = AsyncMock(return_value=1)
    return proc


@pytest.fixture
def mock_process_manager() -> MagicMock:
    """Create a mock ProcessManager.

    The mock simulates ProcessManager for testing adapter
    components without spawning real processes.

    Returns
    -------
    MagicMock
        Mock process manager with common methods
    """
    manager = MagicMock()

    # Process lifecycle
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.kill = AsyncMock()

    # State queries
    manager.is_running = MagicMock(return_value=False)
    manager.get_pid = MagicMock(return_value=None)
    manager.get_process = MagicMock(return_value=None)

    # Output capture
    manager.get_stdout = MagicMock(return_value="")
    manager.get_stderr = MagicMock(return_value="")

    return manager


@pytest.fixture
def mock_process_manager_running() -> MagicMock:
    """Create a mock ProcessManager with running process.

    Returns
    -------
    MagicMock
        Mock manager simulating active process
    """
    manager = MagicMock()

    mock_proc = MagicMock(spec=asyncio.subprocess.Process)
    mock_proc.pid = 12345
    mock_proc.returncode = None

    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.kill = AsyncMock()
    manager.is_running = MagicMock(return_value=True)
    manager.get_pid = MagicMock(return_value=12345)
    manager.get_process = MagicMock(return_value=mock_proc)

    return manager
