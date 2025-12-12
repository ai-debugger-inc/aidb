"""Adapter protocol interfaces."""

import asyncio
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from aidb.adapters.base.launch import BaseLaunchConfig


class IProcessManager(Protocol):
    """Protocol interface for process management component."""

    @property
    def pid(self) -> int | None:
        """Get the process ID of the debug adapter."""
        ...

    @property
    def is_alive(self) -> bool:
        """Check if the process is still running."""
        ...

    async def launch_subprocess(
        self,
        cmd: list[str],
        env: dict[str, str],
        kwargs: dict | None = None,
    ) -> asyncio.subprocess.Process:
        """Launch the debug adapter subprocess with output capture."""
        ...

    async def wait_for_adapter_ready(
        self,
        port: int,
        start_time: float,
        max_retries: int = 3,
        base_timeout: float = 3.0,
        max_total_time: float = 15.0,
    ) -> None:
        """Wait for the debug adapter to be ready to accept connections."""
        ...

    async def stop(self) -> None:
        """Stop the debug adapter process gracefully."""
        ...

    def attach_pid(self, pid: int) -> None:
        """Attach to an existing process ID."""
        ...

    async def log_process_output(self) -> None:
        """Log process output in the background."""
        ...

    def cleanup_orphaned_processes(
        self,
        pattern: str,
        min_age_seconds: float = 5.0,
    ) -> None:
        """Clean up orphaned debug adapter processes."""
        ...

    def get_captured_output(self) -> tuple[str, str] | None:
        """Get captured stdout and stderr from the process."""
        ...


class IPortManager(Protocol):
    """Protocol interface for port management component."""

    @property
    def port(self) -> int | None:
        """Get the currently assigned port."""
        ...

    async def acquire(
        self,
        requested_port: int | None = None,
        fallback_start: int = 10000,
    ) -> int:
        """Acquire a free port for the debug adapter."""
        ...

    def release(self) -> None:
        """Release the allocated port."""
        ...


class ILaunchOrchestrator(Protocol):
    """Protocol interface for launch orchestration component."""

    async def launch(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Launch the debug adapter with the given target."""
        ...

    async def launch_with_config(
        self,
        launch_config: "BaseLaunchConfig",
        port: int | None = None,
        workspace_root: str | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Launch using a resolved launch configuration."""
        ...
