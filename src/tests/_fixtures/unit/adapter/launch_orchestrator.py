"""Mock launch orchestrator for unit tests.

Provides mock implementations of LaunchOrchestrator for testing adapter launch sequences
without actual process spawning.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.adapters.base.launch import BaseLaunchConfig


@pytest.fixture
def mock_launch_orchestrator() -> MagicMock:
    """Create a mock LaunchOrchestrator.

    The mock simulates launch orchestration for testing adapter
    launch sequences without spawning actual processes.

    Returns
    -------
    MagicMock
        Mock launch orchestrator with common methods
    """
    orchestrator = MagicMock()

    # Create mock process
    mock_proc = MagicMock(spec=asyncio.subprocess.Process)
    mock_proc.pid = 12345
    mock_proc.returncode = None

    # Async methods that return (process, port) tuple
    orchestrator.launch = AsyncMock(return_value=(mock_proc, 5678))
    orchestrator.launch_with_config = AsyncMock(return_value=(mock_proc, 5678))
    orchestrator._launch_internal = AsyncMock(return_value=(mock_proc, 5678))
    orchestrator._launch_with_config = AsyncMock(return_value=(mock_proc, 5678))
    orchestrator._handle_launch_failure = AsyncMock()

    # Sync methods
    orchestrator._log_launch_info = MagicMock()

    # Component references
    orchestrator.adapter = MagicMock()
    orchestrator.session = MagicMock()
    orchestrator.config = MagicMock()
    orchestrator.process_manager = MagicMock()
    orchestrator.port_manager = MagicMock()

    return orchestrator


@pytest.fixture
def mock_launch_orchestrator_with_port() -> MagicMock:
    """Create a mock LaunchOrchestrator with specific port.

    Returns
    -------
    MagicMock
        Mock orchestrator configured for port 9999
    """
    orchestrator = MagicMock()

    mock_proc = MagicMock(spec=asyncio.subprocess.Process)
    mock_proc.pid = 54321
    mock_proc.returncode = None

    orchestrator.launch = AsyncMock(return_value=(mock_proc, 9999))
    orchestrator.launch_with_config = AsyncMock(return_value=(mock_proc, 9999))
    orchestrator._launch_internal = AsyncMock(return_value=(mock_proc, 9999))
    orchestrator._handle_launch_failure = AsyncMock()
    orchestrator._log_launch_info = MagicMock()

    orchestrator.adapter = MagicMock()
    orchestrator.session = MagicMock()
    orchestrator.config = MagicMock()
    orchestrator.process_manager = MagicMock()
    orchestrator.port_manager = MagicMock()

    return orchestrator


@pytest.fixture
def mock_launch_orchestrator_failing() -> MagicMock:
    """Create a mock LaunchOrchestrator that fails to launch.

    Returns
    -------
    MagicMock
        Mock orchestrator that raises on launch
    """
    from aidb.common.errors import DebugConnectionError

    orchestrator = MagicMock()

    orchestrator.launch = AsyncMock(
        side_effect=DebugConnectionError("Failed to connect to debug adapter")
    )
    orchestrator.launch_with_config = AsyncMock(
        side_effect=DebugConnectionError("Failed to connect to debug adapter")
    )
    orchestrator._launch_internal = AsyncMock(
        side_effect=DebugConnectionError("Failed to connect to debug adapter")
    )
    orchestrator._handle_launch_failure = AsyncMock()
    orchestrator._log_launch_info = MagicMock()

    orchestrator.adapter = MagicMock()
    orchestrator.session = MagicMock()
    orchestrator.config = MagicMock()
    orchestrator.process_manager = MagicMock()
    orchestrator.port_manager = MagicMock()

    return orchestrator


class MockLaunchOrchestrator:
    """Launch orchestrator mock with tracking.

    Use this when you need to verify launch sequences.

    Examples
    --------
    >>> orchestrator = MockLaunchOrchestrator()
    >>> proc, port = await orchestrator.launch("test.py")
    >>> assert orchestrator.launches[0]["target"] == "test.py"
    """

    def __init__(
        self,
        default_port: int = 5678,
        default_pid: int = 12345,
    ) -> None:
        """Initialize the mock orchestrator.

        Parameters
        ----------
        default_port : int
            Default port to return from launch
        default_pid : int
            Default PID for mock process
        """
        self.default_port = default_port
        self.default_pid = default_pid

        # Tracking
        self.launches: list[dict[str, Any]] = []
        self.config_launches: list[dict[str, Any]] = []

        # Mock components
        self.adapter = MagicMock()
        self.session = MagicMock()
        self.config = MagicMock()
        self.process_manager = MagicMock()
        self.port_manager = MagicMock()

        # Failure injection
        self._should_fail = False
        self._failure_error: Exception | None = None

    def set_failure(self, error: Exception) -> None:
        """Configure the orchestrator to fail on next launch."""
        self._should_fail = True
        self._failure_error = error

    def clear_failure(self) -> None:
        """Clear any configured failure."""
        self._should_fail = False
        self._failure_error = None

    def _create_mock_process(self, pid: int | None = None) -> MagicMock:
        """Create a mock process."""
        proc = MagicMock(spec=asyncio.subprocess.Process)
        proc.pid = pid or self.default_pid
        proc.returncode = None
        return proc

    async def launch(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
    ) -> tuple[MagicMock, int]:
        """Mock launch method with tracking."""
        if self._should_fail and self._failure_error:
            raise self._failure_error

        used_port = port or self.default_port

        self.launches.append(
            {
                "target": target,
                "port": used_port,
                "args": args,
            }
        )

        return self._create_mock_process(), used_port

    async def launch_with_config(
        self,
        launch_config: BaseLaunchConfig,
        port: int | None = None,
        workspace_root: str | None = None,
    ) -> tuple[MagicMock, int]:
        """Mock launch_with_config method with tracking."""
        if self._should_fail and self._failure_error:
            raise self._failure_error

        used_port = port or launch_config.port or self.default_port

        self.config_launches.append(
            {
                "launch_config": launch_config,
                "port": used_port,
                "workspace_root": workspace_root,
            }
        )

        return self._create_mock_process(), used_port

    async def _launch_internal(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
    ) -> tuple[MagicMock, int]:
        """Mock internal launch method."""
        return await self.launch(target, port, args)

    async def _handle_launch_failure(
        self,
        error: Exception,
        start_time: float,
    ) -> None:
        """Mock failure handler."""

    def _log_launch_info(self, cmd: list[str], env: dict[str, str]) -> None:
        """Mock log method."""

    def reset(self) -> None:
        """Reset tracking state."""
        self.launches.clear()
        self.config_launches.clear()
        self.clear_failure()


@pytest.fixture
def mock_launch_orchestrator_tracking() -> MockLaunchOrchestrator:
    """Create a launch orchestrator that tracks operations.

    Returns
    -------
    MockLaunchOrchestrator
        Mock with operation tracking for verification
    """
    return MockLaunchOrchestrator()
