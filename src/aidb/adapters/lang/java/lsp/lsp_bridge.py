"""LSP-DAP bridge for Java debugging through Eclipse JDT LS.

This module implements the high-level bridge between LSP (Language Server Protocol) and
DAP (Debug Adapter Protocol) required for Java debugging, coordinating all LSP-related
components.
"""

import asyncio
import contextlib
import hashlib
import tempfile
from pathlib import Path
from typing import Any

from aidb.common.constants import (
    LSP_HEALTH_CHECK_TIMEOUT_S,
    LSP_MAVEN_IMPORT_TIMEOUT_S,
    LSP_PROJECT_IMPORT_TIMEOUT_S,
    LSP_SERVICE_READY_TIMEOUT_S,
)
from aidb.patterns.base import Obj
from aidb_common.constants import Language
from aidb_common.env import reader

from .debug_session_manager import DebugSessionManager
from .jdtls_process_manager import JDTLSProcessManager
from .lsp_client import LSPClient
from .lsp_initialization import LSPInitialization
from .workspace_manager import WorkspaceManager


class JavaLSPDAPBridge(Obj):
    """Bridge between LSP and DAP for Java debugging.

    This class orchestrates all LSP-related components to manage the lifecycle
    of Eclipse JDT LS with the java-debug plugin, handling LSP communication
    for debug session delegation, and providing the DAP port for actual debugging.

    Components:
    - JDTLSProcessManager: Process lifecycle
    - LSPClient: LSP communication
    - LSPInitialization: Initialization helpers
    - WorkspaceManager: Workspace and project management
    - DebugSessionManager: Debug session delegation
    """

    def __init__(
        self,
        jdtls_path: Path,
        java_debug_jar: Path,
        java_command: str = "java",
        ctx=None,
    ):
        """Initialize the LSP-DAP bridge.

        Parameters
        ----------
        jdtls_path : Path
            Path to the Eclipse JDT LS installation directory
        java_debug_jar : Path
            Path to the java-debug-server plugin JAR
        java_command : str
            Java executable command
        ctx : optional
            Context for logging and storage
        """
        super().__init__(ctx)
        self.jdtls_path = jdtls_path
        self.java_debug_jar = java_debug_jar
        self.java_command = java_command

        # Create all component managers upfront
        self.process_manager = JDTLSProcessManager(
            jdtls_path=jdtls_path,
            java_command=java_command,
            ctx=ctx,
        )
        self.initialization = LSPInitialization(
            java_debug_jar=java_debug_jar,
            ctx=ctx,
        )
        self.workspace_manager = WorkspaceManager(ctx=ctx)
        self.debug_session_manager = DebugSessionManager(ctx=ctx)

        # LSP client will be created after process starts
        self.lsp_client: LSPClient | None = None
        # Remember last workspace_folders to allow restart on pooled fallback
        self._last_workspace_folders: list[tuple[Path, str]] | None = None
        # Track pooled failures to allow proactive restart
        self._pooled_failures: int = 0

    def __setattr__(self, name: str, value: Any) -> None:
        """Propagate _is_pooled flag to child components."""
        super().__setattr__(name, value)

        # When pool sets bridge._is_pooled = True, propagate to child components
        # so they can check pooled status without circular references
        if name == "_is_pooled":
            if hasattr(self, "debug_session_manager"):
                self.debug_session_manager._is_pooled = value
            if hasattr(self, "lsp_client") and self.lsp_client is not None:
                self.lsp_client._is_pooled = value

    def is_pooled(self) -> bool:
        """Check if this bridge is managed by a pool.

        Returns True if this bridge was allocated from either the test pool
        or the per-project production pool. Pooled bridges should NOT be
        stopped when a debug session ends - they are returned to the pool.

        This is the SINGLE SOURCE OF TRUTH for pool detection. All code
        should use this method rather than:
        - Querying pool registries directly (expensive)
        - Checking bridge.process state (ambiguous)

        Returns
        -------
        bool
            True if this bridge is managed by a pool, False otherwise.
        """
        return getattr(self, "_is_pooled", False)

    @property
    def process(self) -> asyncio.subprocess.Process | None:
        """Get the JDT LS process from the process manager."""
        return self.process_manager.process

    async def start(
        self,
        project_root: Path | None = None,
        session_id: str | None = None,
        extra_env: dict[str, str] | None = None,
        workspace_folders: list[tuple[Path, str]] | None = None,
    ) -> None:
        """Start Eclipse JDT LS with java-debug plugin.

        Parameters
        ----------
        project_root : Optional[Path]
            The root directory of the Java project to debug
        session_id : Optional[str]
            Session ID for process tagging
        extra_env : Optional[Dict[str, str]]
            Additional environment variables
        workspace_folders : Optional[List[Tuple[Path, str]]]
            Workspace folders to register during initialization

        Raises
        ------
        AidbError
            If JDT LS fails to start or initialize
        """
        # Choose a stable per-project workspace directory
        if project_root and project_root.exists():
            try:
                root_str = str(project_root.resolve())
            except Exception:
                root_str = str(project_root)
            digest = hashlib.sha1(
                root_str.encode("utf-8"),
                usedforsecurity=False,
            ).hexdigest()[:10]
            safe_name = f"{project_root.name}-{digest}"
            stable_ws = (
                Path.home()
                / ".aidb"
                / "adapters"
                / Language.JAVA.value
                / "jdtls"
                / "workspaces"
                / safe_name
            )
            stable_ws.mkdir(parents=True, exist_ok=True)
            workspace = stable_ws
        else:
            workspace = Path(tempfile.mkdtemp(prefix="jdtls_workspace_"))

        # Start JDT LS process
        process = await self.process_manager.start_jdtls(
            workspace=workspace,
            java_debug_jar=self.java_debug_jar,
            session_id=session_id,
            extra_env=extra_env,
        )

        # Create LSP client
        self.lsp_client = LSPClient(process, ctx=self.ctx)
        await self.lsp_client.start()

        # Initialize LSP with java-debug plugin
        init_options = self.initialization.build_initialization_options(
            workspace_folders=workspace_folders,
        )
        # Record for potential restart fallback
        self._last_workspace_folders = workspace_folders

        root_uri = workspace.as_uri()
        self.ctx.info(f"Initializing JDT LS with workspace: {root_uri}")

        try:
            await self.lsp_client.initialize(root_uri, init_options)
            self.ctx.debug("JDT LS capabilities received")

            # Wait for ServiceReady
            self.ctx.info("Waiting for JDT LS ServiceReady notification...")
            service_ready = await self.lsp_client.wait_for_service_ready(
                timeout=LSP_SERVICE_READY_TIMEOUT_S,
            )
            if not service_ready:
                self.ctx.warning(
                    f"JDT LS did not send ServiceReady within "
                    f"{LSP_SERVICE_READY_TIMEOUT_S}s. May not be fully ready.",
                )

            # For Maven/Gradle projects, wait for import
            if workspace_folders:
                project_root_path = workspace_folders[0][0]
                project_name = workspace_folders[0][1]
                self.ctx.info(
                    f"Waiting for Maven/Gradle import for {project_name}...",
                )

                # Try progress-based wait first
                progress_ready = False
                if hasattr(self.lsp_client, "wait_for_maven_import_complete"):
                    try:
                        progress_ready = (
                            await self.lsp_client.wait_for_maven_import_complete(
                                timeout=LSP_MAVEN_IMPORT_TIMEOUT_S,
                            )
                        )
                    except Exception as e:
                        self.ctx.debug(f"Progress wait unavailable: {e}")

                # Fall back to polling
                if not progress_ready:
                    import_ready = await self.workspace_manager.wait_for_project_import(
                        lsp_client=self.lsp_client,
                        project_name=project_name,
                        project_root=project_root_path,
                        timeout=LSP_PROJECT_IMPORT_TIMEOUT_S,
                    )
                    if not import_ready:
                        self.ctx.warning(
                            f"Maven/Gradle import incomplete for {project_name}. "
                            "Classpath may fail.",
                        )

        except Exception as e:
            from aidb.common.errors import AidbError

            msg = f"Failed to initialize JDT LS: {e}"
            raise AidbError(msg) from e

    async def register_workspace_folders(
        self,
        workspace_folders: list[tuple[Path, str]],
    ) -> None:
        """Register workspace folders with JDT LS and wait for Maven/Gradle import."""
        if not self.lsp_client:
            from aidb.common.errors import AidbError

            msg = "LSP client not initialized"
            raise AidbError(msg)
        # Remember last workspace folders for potential restart scenarios
        with contextlib.suppress(Exception):
            self._last_workspace_folders = workspace_folders
        await self.workspace_manager.register_workspace_folders(
            self.lsp_client,
            workspace_folders,
        )

    async def wait_for_project_import(
        self,
        project_name: str,
        project_root: Path | None = None,
        test_class: str = "Object",
        timeout: float = 60.0,
    ) -> bool:
        """Wait for Maven/Gradle project import to complete."""
        if not self.lsp_client:
            return False
        return await self.workspace_manager.wait_for_project_import(
            self.lsp_client,
            project_name,
            project_root,
            test_class,
            timeout,
        )

    async def start_debug_session(
        self,
        main_class: str,
        classpath: list[str],
        target: str | None = None,
        project_name: str | None = None,
        vmargs: list[str] | None = None,
        args: list[str] | None = None,
        skip_file_opening: bool = False,
    ) -> int:
        """Start a debug session through JDT LS and get the DAP port.

        Includes a pooled-bridge fallback: if startDebugSession fails after
        local retries in DebugSessionManager, forcibly restart JDT LS and retry
        once more.
        """
        if not self.lsp_client:
            from aidb.common.errors import AidbError

            msg = "LSP client not initialized"
            raise AidbError(msg)
        try:
            # Proactive restart for unhealthy pooled bridges
            if self.is_pooled():
                threshold = (
                    reader.read_int(
                        "AIDB_JAVA_POOLED_RESTART_THRESHOLD",
                        1,
                    )
                    or 1
                )
                if self._pooled_failures >= threshold:
                    self.ctx.warning(
                        f"Pooled bridge has {self._pooled_failures} consecutive failures; "
                        "restarting JDT LS proactively before startDebugSession",
                    )
                    await self.process_manager.stop_jdtls(force=True)
                    self.lsp_client = None
                    # Use last-known folders if available to keep workspace warm
                    await self.start(
                        project_root=(
                            self._last_workspace_folders[0][0]
                            if self._last_workspace_folders
                            else None
                        ),
                        session_id="jdtls-proactive-restart",
                        workspace_folders=self._last_workspace_folders,
                    )
                    self._pooled_failures = 0
            return await self.debug_session_manager.start_debug_session(
                self.lsp_client,
                main_class,
                classpath,
                target,
                project_name,
                vmargs,
                args,
                skip_file_opening,
            )
        except Exception as e:
            # Final fallback for pooled bridges: restart JDT LS and retry once.
            if self.is_pooled():
                from aidb.common.errors import AidbError

                self.ctx.warning(
                    f"Pooled startDebugSession failed: {e}. Restarting JDT LS and retrying...",
                )
                try:
                    self._pooled_failures += 1
                    # Force stop and restart JDT LS
                    await self.process_manager.stop_jdtls(force=True)
                    # Clear LSP client
                    self.lsp_client = None
                    # Restart with last-known workspace folders (if any)
                    await self.start(
                        project_root=(
                            self._last_workspace_folders[0][0]
                            if self._last_workspace_folders
                            else None
                        ),
                        session_id="jdtls-restart",
                        extra_env=None,
                        workspace_folders=self._last_workspace_folders,
                    )
                    if not self.lsp_client:
                        msg = "LSP client not initialized after restart"
                        raise AidbError(msg)
                    # Retry once after restart
                    result = await self.debug_session_manager.start_debug_session(
                        self.lsp_client,
                        main_class,
                        classpath,
                        target,
                        project_name,
                        vmargs,
                        args,
                        skip_file_opening,
                    )
                    # Success resets failure counter
                    self._pooled_failures = 0
                    return result
                except Exception as restart_err:
                    self.ctx.error(f"JDT LS restart fallback failed: {restart_err}")
                    raise
            raise

    async def attach_to_remote(
        self,
        host: str,
        port: int,
        project_name: str | None = None,
        timeout: int = 10000,
    ) -> int:
        """Attach to a remote JVM through JDT LS and get the DAP port."""
        if not self.lsp_client:
            from aidb.common.errors import AidbError

            msg = "LSP client not initialized"
            raise AidbError(msg)
        return await self.debug_session_manager.attach_to_remote(
            self.lsp_client,
            host,
            port,
            project_name,
            timeout,
        )

    async def resolve_classpath(
        self,
        main_class: str,
        project_name: str | None = None,
        timeout: float | None = None,
    ) -> list[str]:
        """Resolve the classpath for a Java class."""
        if not self.lsp_client:
            return []

        # For pooled bridges, proactively check LSP health and restart if unresponsive
        if self.is_pooled():
            try:
                _ = await self.lsp_client.execute_command(
                    "java.project.getAll",
                    [],
                    timeout=LSP_HEALTH_CHECK_TIMEOUT_S,
                )
                self.ctx.debug(
                    "[POOLED] LSP health check succeeded before resolveClasspath",
                )
            except Exception as e:
                self.ctx.warning(
                    f"[POOLED] LSP health check failed before resolveClasspath: {e}. "
                    "Restarting JDT LS and retrying classpath resolution...",
                )
                try:
                    await self.process_manager.stop_jdtls(force=True)
                    self.lsp_client = None
                    await self.start(
                        project_root=(
                            self._last_workspace_folders[0][0]
                            if self._last_workspace_folders
                            else None
                        ),
                        session_id="jdtls-restart-resolveClasspath",
                        extra_env=None,
                        workspace_folders=self._last_workspace_folders,
                    )
                except Exception as restart_err:
                    self.ctx.error(
                        f"Failed to restart JDT LS after health check failure: {restart_err}",
                    )
                    # Continue to attempt classpath; will likely return []
        return await self.debug_session_manager.resolve_classpath(
            self.lsp_client,
            main_class,
            project_name,
            timeout,
        )

    async def register_project(
        self,
        project_root: Path,
        project_name: str | None = None,
    ) -> None:
        """Register a Maven/Gradle project with JDT LS for classpath resolution."""
        if not self.lsp_client:
            from aidb.common.errors import AidbError

            msg = "LSP client not initialized"
            raise AidbError(msg)
        # Record as last workspace folders for restart logic
        with contextlib.suppress(Exception):
            self._last_workspace_folders = [
                (project_root, project_name or project_root.name),
            ]
        await self.workspace_manager.register_project(
            self.lsp_client,
            project_root,
            project_name,
        )

    async def resolve_main_class(self, uri: str | None = None) -> str | None:
        """Resolve the main class from a file or project."""
        if not self.lsp_client:
            return None
        return await self.debug_session_manager.resolve_main_class(
            self.lsp_client,
            uri,
        )

    async def update_debug_settings(self) -> bool:
        """Update JDT LS debug settings to enable trace logging."""
        if not self.lsp_client:
            return False
        return await self.debug_session_manager.update_debug_settings(self.lsp_client)

    def get_workspace_path(self) -> Path | None:
        """Get the workspace path used by JDT LS."""
        return self.process_manager.get_workspace_path()

    def get_eclipse_log_path(self) -> Path | None:
        """Get the path to the Eclipse Platform log file."""
        return self.process_manager.get_eclipse_log_path()

    async def reset_dap_state(self) -> bool:
        """Reset DAP state without restarting JDT LS."""
        if not self.lsp_client:
            return False
        return await self.debug_session_manager.reset_dap_state(self.lsp_client)

    def get_dap_connection_info(self) -> dict[str, Any]:
        """Get diagnostic info about DAP connection state."""
        return self.debug_session_manager.get_dap_connection_info(self.process_manager)

    async def stop(self, *, force: bool = False) -> None:
        """Stop the JDT LS process and cleanup resources."""
        if not force and self.lsp_client:
            # Graceful shutdown for active sessions
            try:
                await self.lsp_client.shutdown()
                await self.lsp_client.exit()
                await self.lsp_client.stop()
            except Exception as e:
                self.ctx.warning(f"Error during LSP shutdown: {e}")

        # Stop process manager (handles cleanup)
        await self.process_manager.stop_jdtls(force=force)

        self.lsp_client = None

    async def cleanup_children(self) -> None:
        """Clean up child processes without stopping JDT LS."""
        await self.process_manager.cleanup_children()
