"""Launch orchestration for debug adapters.

This module provides the LaunchOrchestrator class that manages the complex launch
sequence for debug adapters, including VS Code launch.json configuration resolution and
adapter-specific launch flows.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from aidb.adapters.base.launch import BaseLaunchConfig
from aidb.common.errors import AidbError, DebugConnectionError
from aidb.patterns.base import Obj
from aidb.resources.process_tags import ProcessType

if TYPE_CHECKING:
    from aidb.adapters.base.adapter import DebugAdapter
    from aidb.interfaces.adapter import IPortManager, IProcessManager


class LaunchOrchestrator(Obj):
    """Orchestrates the launch sequence for debug adapters.

    This class manages the complex launch flow including:
        - VS Code launch.json configuration resolution
        - Launch environment preparation
        - Process startup coordination
        - Port acquisition and verification
        - Adapter readiness checking

    Parameters
    ----------
    adapter : DebugAdapter
        The adapter instance being orchestrated
    process_manager : IProcessManager
        Process manager for handling subprocess lifecycle
    port_manager : IPortManager
        Port manager for port acquisition and release
    """

    def __init__(
        self,
        adapter: "DebugAdapter",
        process_manager: "IProcessManager",
        port_manager: "IPortManager",
        ctx=None,
    ) -> None:
        """Initialize the launch orchestrator.

        Parameters
        ----------
        adapter : DebugAdapter
            The adapter instance to orchestrate launches for
        process_manager : ProcessManager
            Process manager for subprocess operations
        port_manager : PortManager
            Port manager for port operations
        ctx : AidbContext, optional
            Context to use, defaults to adapter's context
        """
        super().__init__(ctx=ctx or adapter.ctx)
        self.adapter = adapter
        self.session = adapter.session
        self.config = adapter.config
        self.process_manager = process_manager
        self.port_manager = port_manager

    async def _launch_with_config(
        self,
        launch_config: BaseLaunchConfig,
        port: int | None = None,
        workspace_root: str | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Launch using a VS Code launch configuration.

        Parameters
        ----------
        launch_config : BaseLaunchConfig
            VS Code launch configuration to use
        port : int, optional
            Specific port to use, if None will use config port or find available
        workspace_root : str, optional
            Root directory for resolving relative paths

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on
        """
        # Convert launch config to adapter arguments
        workspace_path = Path(workspace_root) if workspace_root else None
        adapter_args = launch_config.to_adapter_args(workspace_path)
        self.ctx.debug(f"Launch config adapter_args: {adapter_args}")

        # Override port if specified
        if port:
            adapter_args["port"] = port
        elif launch_config.port:
            port = launch_config.port

        # Set working directory if specified
        if launch_config.cwd:
            os.chdir(launch_config.cwd)

        # Merge environment variables
        if launch_config.env:
            os.environ.update(launch_config.env)

        # Call the internal launch method
        return await self._launch_internal(
            target=adapter_args.get("target", ""),
            port=adapter_args.get("port"),
            args=adapter_args.get("args"),
        )

    async def launch(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Launch debug adapter without VS Code config resolution.

        Parameters
        ----------
        target : str
            Path to the target file to debug
        port : int, optional
            Specific port to use, if None will find available port
        args : List[str], optional
            Additional arguments for the target

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on
        """
        return await self._launch_internal(target, port, args)

    async def launch_with_config(
        self,
        launch_config: BaseLaunchConfig,
        port: int | None = None,
        workspace_root: str | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Launch using a VS Code launch configuration.

        Parameters
        ----------
        launch_config : BaseLaunchConfig
            VS Code launch configuration to use
        port : int, optional
            Specific port to use
        workspace_root : str, optional
            Root directory for resolving relative paths

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on
        """
        return await self._launch_with_config(launch_config, port, workspace_root)

    async def _launch_internal(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """Handle launch args without launch.json resolution.

        Parameters
        ----------
        target : str
            Path to the target file to debug
        port : int, optional
            Specific port to use, if None will find available port
        args : List[str], optional
            Additional arguments for the target

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on

        Raises
        ------
        ValueError
            If the target is invalid
        DebugConnectionError
            If unable to connect to debug adapter
        """
        # Language-specific adapters handle orphan cleanup via PRE_LAUNCH hooks

        # Acquire port
        self.ctx.debug(f"Requested port: {port}")

        try:
            acquired_port = await self.port_manager.acquire(requested_port=port)
        except AidbError as e:
            self.ctx.error(f"Failed to find available port for debug adapter: {e}")
            raise

        if port and acquired_port != port:
            self.ctx.warning(
                f"Requested port {port} not available, "
                f"acquired {acquired_port} instead",
            )
        else:
            self.ctx.debug(f"Successfully acquired port {acquired_port}")

        # Update adapter port
        self.adapter.adapter_port = acquired_port

        # Release the socket reservation so the adapter can bind to the port
        # The port remains allocated to the session, just the socket is released
        from aidb.resources.ports import PortRegistry

        port_registry = PortRegistry(ctx=self.ctx)
        port_registry.release_reserved_port(acquired_port)

        # Prepare launch
        self.ctx.debug(f"Using dynamic adapter port {acquired_port} (requested={port})")
        cmd = await self.adapter._build_launch_command(
            target,
            self.adapter.adapter_host,
            acquired_port,
            args,
        )
        env = self.adapter._prepare_environment()

        self._log_launch_info(cmd, env)

        # Launch the process using ProcessManager with session tagging
        proc = await self.process_manager.launch_subprocess(
            cmd=cmd,
            env=env,
            session_id=self.session.id,
            language=self.adapter.config.language,
            process_type=ProcessType.ADAPTER,
            kwargs={},
        )

        self.ctx.debug(f"Launched debug adapter process with PID: {proc.pid}")

        # Register process with ResourceManager for cleanup
        if hasattr(self.session, "resource") and self.session.resource:
            self.session.resource.register_process(proc)
            self.ctx.debug(
                f"Registered process {proc.pid} with ResourceManager for cleanup",
            )

        self.ctx.debug(f"Waiting for debug adapter to listen on port {acquired_port}")

        # Wait for adapter to be ready
        start_time = time.monotonic()
        try:
            await self.process_manager.wait_for_adapter_ready(acquired_port, start_time)
        except Exception as e:
            await self._handle_launch_failure(e, start_time)
            msg = f"Failed to connect to debug adapter: {e}"
            raise DebugConnectionError(
                msg,
            ) from e

        return proc, acquired_port

    async def _handle_launch_failure(self, error: Exception, start_time: float) -> None:
        """Handle launch failure by logging process output.

        Parameters
        ----------
        error : Exception
            The error that occurred
        start_time : float
            When the launch started
        """
        port_wait_end = time.monotonic()
        self.ctx.error(
            f"Error waiting for debug adapter "
            f"(waited {port_wait_end - start_time:.3f}s): {error}",
        )
        # Use process manager's logging method instead of duplicated code
        await self.process_manager.log_process_output()

    def _log_launch_info(self, cmd: list[str], env: dict[str, str]) -> None:
        """Log detailed launch information for debugging.

        Parameters
        ----------
        cmd : List[str]
            Command being launched
        env : Dict[str, str]
            Environment variables
        """
        self.ctx.debug(f"CWD before launching debug adapter: {Path.cwd()}")
        self.ctx.debug(f"Launching subprocess: {cmd}")
        self.ctx.debug(f"Debug adapter launch command: {cmd}")

        # Log relevant environment variables
        filtered_env = {
            k: env[k]
            for k in sorted(env)
            if any(k.startswith(prefix) for prefix in ["PY", "VIRTUAL", "DEBUG"])
            or k == "PATH"
        }
        self.ctx.debug(f"Debug adapter launch env: {filtered_env}")
        self.ctx.debug(f"Debug adapter launch cwd: {Path.cwd()}")
