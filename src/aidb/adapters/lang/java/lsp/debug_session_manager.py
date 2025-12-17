"""Debug session manager for DAP session delegation to java-debug.

This module manages debug session creation through JDT LS, including launch
configuration, attach operations, and DAP port management.
"""

import json
from typing import Any

from aidb.common.constants import (
    DEFAULT_WAIT_TIMEOUT_S,
    INIT_CONFIGURATION_DONE_JAVA_S,
    LSP_EXECUTE_COMMAND_TIMEOUT_S,
    LSP_HEALTH_CHECK_TIMEOUT_S,
)
from aidb.common.errors import AidbError
from aidb.patterns.base import Obj
from aidb_common.env import reader

# Import config for default project name
from ..config import JavaAdapterConfig


class DebugSessionManager(Obj):
    """Manager for debug session delegation to java-debug plugin.

    Handles:
    - Debug session launch via LSP workspace/executeCommand
    - Remote JVM attach operations
    - Classpath and main class resolution
    - DAP port caching for pooled bridges (CRITICAL pooling logic)
    - Debug settings configuration
    """

    def __init__(self, ctx=None):
        """Initialize the debug session manager.

        Parameters
        ----------
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self.dap_port: int | None = None
        self._is_pooled = False
        self._java_debug_initialized = False

    async def _ensure_java_debug_ready(self, lsp_client) -> None:
        """Trigger java-debug plugin initialization by calling resolveClasspath.

        The java-debug plugin is lazily loaded by JDT LS. Calling resolveClasspath
        (even with dummy args) triggers the plugin to initialize, ensuring
        startDebugSession has a ready handler. This is idempotent - subsequent
        calls return quickly since the plugin is already loaded.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        """
        if self._java_debug_initialized:
            self.ctx.debug("java-debug plugin already initialized, skipping trigger")
            return

        self.ctx.debug("Triggering java-debug plugin initialization...")
        try:
            await lsp_client.execute_command(
                "vscode.java.resolveClasspath",
                ["", ""],
                timeout=LSP_EXECUTE_COMMAND_TIMEOUT_S,
            )
            self._java_debug_initialized = True
            self.ctx.debug("java-debug plugin initialized successfully")
        except Exception as e:
            # Log but don't fail - the error is expected (empty args), but
            # the side effect of loading the plugin still occurs
            self._java_debug_initialized = True
            self.ctx.debug(f"java-debug init trigger completed (error expected): {e}")

    async def start_debug_session(  # noqa: C901
        self,
        lsp_client,
        main_class: str,
        classpath: list[str],
        target: str | None = None,
        project_name: str | None = None,
        vmargs: list[str] | None = None,
        args: list[str] | None = None,
        skip_file_opening: bool = False,
    ) -> int:
        """Start a debug session through JDT LS and get the DAP port.

        CRITICAL: This method contains pooling logic that must be preserved exactly.

        Each call to startDebugSession launches a new debuggee JVM process and
        returns the DAP port where the java-debug server is listening. The same
        port may be returned for multiple sessions (the JavaDebugServer singleton
        reuses its ServerSocket), but each session gets its own debuggee process
        and isolated ProtocolServer instance.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        main_class : str
            The fully qualified main class name
        classpath : List[str]
            The classpath entries
        target : Optional[str]
            Path to the target Java file
        project_name : Optional[str]
            The project name
        vmargs : Optional[List[str]]
            JVM arguments
        args : Optional[List[str]]
            Program arguments
        skip_file_opening : bool
            If True, skip session reset and file opening

        Returns
        -------
        int
            The DAP port to connect to

        Raises
        ------
        AidbError
            If debug session creation fails
        """
        # For pooled bridges: do NOT reuse cached DAP port. Always request a fresh
        # java-debug session via startDebugSession, but avoid resetting the LSP
        # client session state (which can desynchronize LSP/JDT LS on long-lived
        # connections). Simply clear the cached port and proceed.
        if self._is_pooled and self.dap_port:
            self.ctx.info(
                f"[POOLED] Clearing cached DAP port {self.dap_port} and requesting "
                "fresh java-debug session",
            )
            self.dap_port = None

        # For standalone .java files, reset state and open file here
        # For Maven/Gradle projects, this was already done in launch()
        if not skip_file_opening:
            # Only reset LSP client state for non-pooled bridges. For pooled
            # bridges we keep the LSP connection/state intact and rely on
            # startDebugSession to provision a fresh java-debug ProtocolServer.
            if not self._is_pooled:
                self.ctx.debug(
                    "Resetting LSP client state before requesting DAP port",
                )
                await lsp_client.reset_session_state()

            # Open the target file in JDT LS to trigger invisible project creation
            # Only open .java source files, not .class files
            if target and target.endswith(".java"):
                self.ctx.info(f"Opening target file in JDT LS: {target}")
                await lsp_client.open_file(target)

                # Wait for JDT LS to complete compilation (publishDiagnostics)
                # SKIP for pooled bridges: JDT LS caches analysis and doesn't
                # re-send publishDiagnostics for previously analyzed files
                if self._is_pooled:
                    self.ctx.debug(
                        f"Skipping diagnostic wait for {target} "
                        "(pooled bridge, file likely cached)",
                    )
                else:
                    self.ctx.debug(f"Waiting for JDT LS compilation of {target}...")
                    compilation_complete = await lsp_client.wait_for_diagnostics(
                        file_path=target,
                        timeout=DEFAULT_WAIT_TIMEOUT_S,
                    )

                    if not compilation_complete:
                        self.ctx.warning(
                            f"JDT LS compilation timeout for {target}. "
                            "Proceeding anyway - breakpoints may not work correctly.",
                        )
                    else:
                        self.ctx.debug("JDT LS compilation complete")

        # Build debug configuration for vscode.java.startDebugSession command
        default_project = JavaAdapterConfig.DEFAULT_PROJECT_NAME
        debug_config = {
            "type": "java",
            "request": "launch",
            "mainClass": main_class,
            "classPaths": classpath,
            "projectName": project_name or default_project,
            "vmArgs": " ".join(vmargs) if vmargs else "",
            "args": " ".join(args) if args else "",
            "console": "internalConsole",
            "encoding": "UTF-8",
        }

        self.ctx.info(
            f"Starting java-debug session for {main_class} (pooled={self._is_pooled})",
        )
        self.ctx.debug(f"Debug configuration: {json.dumps(debug_config, indent=2)}")

        # Trigger java-debug plugin initialization before startDebugSession
        # The java-debug plugin is lazily loaded by JDT LS. Calling resolveClasspath
        # (even with dummy args) triggers the plugin to initialize, ensuring
        # startDebugSession has a ready handler.
        await self._ensure_java_debug_ready(lsp_client)

        try:
            # Execute the startDebugSession command
            # Use shorter timeout for pooled bridges to fast-fail and trigger
            # deterministic recovery. Configurable via env.
            # Default: 5.0s for local fast-fail (JDTLS responds in ~0.02-0.05s)
            # CI: Set AIDB_JAVA_STARTDEBUG_TIMEOUT=20 to handle slower I/O,
            #     resource contention, and cold starts
            # Note: Applies to both pooled and non-pooled for consistent CI behavior
            cmd_timeout = (
                reader.read_float(
                    "AIDB_JAVA_STARTDEBUG_TIMEOUT",
                    5.0,
                )
                or 5.0
            )
            result = await lsp_client.execute_command(
                "vscode.java.startDebugSession",
                [json.dumps(debug_config)],
                timeout=cmd_timeout,
            )

            # The result should contain the DAP port
            previous_dap_port = self.dap_port
            if isinstance(result, dict) and "port" in result:
                self.dap_port = result["port"]
                self.ctx.info(
                    f"Debug session started on DAP port: {self.dap_port}"
                    + (
                        " (same as previous)"
                        if previous_dap_port and self.dap_port == previous_dap_port
                        else ""
                    ),
                )
                if self._is_pooled:
                    if previous_dap_port and self.dap_port == previous_dap_port:
                        self.ctx.debug(
                            f"[POOLED] Reused same DAP port {self.dap_port} after "
                            f"reset (server-side session recreated by java-debug)",
                        )
                    elif previous_dap_port:
                        self.ctx.debug(
                            f"[POOLED] Got new DAP port {self.dap_port} after reset "
                            f"(was {previous_dap_port})",
                        )
                    else:
                        self.ctx.debug(
                            f"[POOLED] First session on DAP port {self.dap_port}",
                        )
                elif previous_dap_port and self.dap_port == previous_dap_port:
                    self.ctx.warning(
                        f"JDT LS returned SAME DAP port {self.dap_port} "
                        "as previous session - java-debug server may not "
                        "have restarted!",
                    )
                return self.dap_port or 0
            if isinstance(result, int):
                # Sometimes the result is just the port number
                self.dap_port = result
                self.ctx.info(
                    f"Debug session started on DAP port: {self.dap_port}"
                    + (
                        " (same as previous)"
                        if previous_dap_port and self.dap_port == previous_dap_port
                        else ""
                    ),
                )
                if self._is_pooled:
                    if previous_dap_port and self.dap_port == previous_dap_port:
                        self.ctx.debug(
                            f"[POOLED] Reused same DAP port {self.dap_port} after "
                            f"reset (server-side session recreated by java-debug)",
                        )
                    elif previous_dap_port:
                        self.ctx.debug(
                            f"[POOLED] Got new DAP port {self.dap_port} after reset "
                            f"(was {previous_dap_port})",
                        )
                    else:
                        self.ctx.debug(
                            f"[POOLED] First session on DAP port {self.dap_port}",
                        )
                elif previous_dap_port and self.dap_port == previous_dap_port:
                    self.ctx.warning(
                        f"JDT LS returned SAME DAP port {self.dap_port} "
                        "as previous session - java-debug server may not "
                        "have restarted!",
                    )
                return self.dap_port or 0
            msg = f"Unexpected response from startDebugSession: {result}"
            raise AidbError(msg)

        except Exception as e:
            # Deterministic behavior: for pooled bridges, let higher-level
            # restart logic handle this immediately (fast-fail). For
            # non-pooled, apply a light fallback (poke + quick retry).
            err_msg = str(e)
            if self._is_pooled:
                self.ctx.warning(
                    f"startDebugSession failed quickly on pooled bridge: {err_msg}",
                )
                raise

            self.ctx.warning(
                f"startDebugSession failed: {err_msg}. Applying non-pooled fallback...",
            )
            # Non-pooled: try a quick poke then a single retry
            try:
                _ = await lsp_client.execute_command(
                    "java.project.getAll",
                    [],
                    timeout=LSP_HEALTH_CHECK_TIMEOUT_S,
                )
                self.ctx.debug("LSP poke (java.project.getAll) completed")
            except Exception as poke_err:
                self.ctx.debug(f"LSP poke failed/ignored: {poke_err}")
            result = await lsp_client.execute_command(
                "vscode.java.startDebugSession",
                [json.dumps(debug_config)],
                timeout=INIT_CONFIGURATION_DONE_JAVA_S,
            )
            previous_dap_port = self.dap_port
            if isinstance(result, dict) and "port" in result:
                self.dap_port = result["port"]
                self.ctx.info(
                    f"Debug session started on DAP port: {self.dap_port} (after poke)"
                    + (
                        " (same as previous)"
                        if previous_dap_port and self.dap_port == previous_dap_port
                        else ""
                    ),
                )
                return self.dap_port or 0
            if isinstance(result, int):
                self.dap_port = result
                self.ctx.info(
                    f"Debug session started on DAP port: {self.dap_port} (after poke)"
                    + (
                        " (same as previous)"
                        if previous_dap_port and self.dap_port == previous_dap_port
                        else ""
                    ),
                )
                return self.dap_port or 0

            msg = f"Failed to start debug session after fallback: {result}"
            raise AidbError(msg) from e

    async def attach_to_remote(
        self,
        lsp_client,
        host: str,
        port: int,
        project_name: str | None = None,
        timeout: int = 10000,
    ) -> int:
        """Attach to a remote JVM through JDT LS and get the DAP port.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        host : str
            The hostname or IP address of the remote JVM
        port : int
            The JDWP port of the remote JVM
        project_name : Optional[str]
            The project name for evaluation context
        timeout : int
            Connection timeout in milliseconds

        Returns
        -------
        int
            The DAP port for the debug session

        Raises
        ------
        AidbError
            If the attach operation fails
        """
        self.ctx.info(f"Requesting attach session to {host}:{port}")

        # Trigger java-debug plugin initialization before startDebugSession
        await self._ensure_java_debug_ready(lsp_client)

        # Build attach configuration
        default_project = JavaAdapterConfig.DEFAULT_PROJECT_NAME
        attach_config = {
            "type": "java",
            "request": "attach",
            "hostName": host,
            "port": port,
            "timeout": timeout,
            "projectName": project_name or default_project,
        }

        self.ctx.debug(f"Attach configuration: {json.dumps(attach_config, indent=2)}")

        # Request DAP port from java-debug plugin for attach
        try:
            result = await lsp_client.execute_command(
                "vscode.java.startDebugSession",
                [json.dumps(attach_config)],
            )

            # The result should be the DAP port
            if isinstance(result, int):
                self.dap_port = result
                self.ctx.info(f"Attach session ready on DAP port: {self.dap_port}")
                return self.dap_port or 0
            msg = f"Unexpected response from startDebugSession: {result}"
            raise AidbError(msg)

        except Exception as e:
            msg = f"Failed to attach to remote JVM: {e}"
            raise AidbError(msg) from e

    async def resolve_classpath(
        self,
        lsp_client,
        main_class: str,
        project_name: str | None = None,
        timeout: float | None = None,
    ) -> list[str]:
        """Resolve the classpath for a Java class.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        main_class : str
            The fully qualified main class name
        project_name : Optional[str]
            The project name
        timeout : Optional[float]
            Request timeout in seconds

        Returns
        -------
        List[str]
            The resolved classpath entries
        """
        try:
            result = await lsp_client.execute_command(
                "vscode.java.resolveClasspath",
                [main_class, project_name or ""],
                timeout=timeout if timeout is not None else 30.0,
            )

            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "classpaths" in result:
                return result["classpaths"]
            self.ctx.warning(f"Unexpected classpath result: {result}")
            return []

        except Exception as e:
            self.ctx.warning(f"Failed to resolve classpath: {e}")
            return []

    async def resolve_main_class(
        self,
        lsp_client,
        uri: str | None = None,
    ) -> str | None:
        """Resolve the main class from a file or project.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        uri : Optional[str]
            The file URI to check for main class

        Returns
        -------
        Optional[str]
            The fully qualified main class name if found
        """
        try:
            # Try to resolve main class
            result = await lsp_client.execute_command(
                "vscode.java.resolveMainClass",
                [uri] if uri else [],
            )

            if isinstance(result, str):
                return result
            if isinstance(result, list) and result:
                # Return first main class found
                return result[0]
            if isinstance(result, dict) and "mainClass" in result:
                return result["mainClass"]
            return None

        except Exception as e:
            self.ctx.warning(f"Failed to resolve main class: {e}")
            return None

    async def update_debug_settings(self, lsp_client) -> bool:
        """Update JDT LS debug settings to enable trace logging.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication

        Returns
        -------
        bool
            True if settings were successfully updated
        """
        try:
            # Create the debug settings configuration
            settings_json = json.dumps({"logLevel": "FINEST"})

            self.ctx.info("Updating JDT LS debug settings with log level: FINEST")

            # Execute the updateDebugSettings command
            result = await lsp_client.execute_command(
                "vscode.java.updateDebugSettings",
                [settings_json],
            )

            # Accept multiple return formats
            if result is None or result is True:
                self.ctx.debug("Successfully updated JDT LS debug settings")
                return True

            parsed = result
            if isinstance(result, str):
                try:
                    parsed = json.loads(result)
                except Exception:
                    parsed = result

            if isinstance(parsed, dict) and parsed.get("logLevel"):
                self.ctx.debug(f"JDT LS debug settings updated: {parsed}")
                return True

            # Fallback: treat other truthy responses as success
            if result:
                self.ctx.debug(
                    f"UpdateDebugSettings returned non-standard response: {result}",
                )
                return True

            self.ctx.warning(
                f"Unexpected response from updateDebugSettings: {result}",
            )
            return False

        except Exception as e:
            self.ctx.warning(f"Failed to update debug settings: {e}")
            return False

    async def reset_dap_state(self, lsp_client) -> bool:
        """Reset DAP state without restarting JDT LS.

        This is used for pooled bridges to recover from stale DAP connections.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication

        Returns
        -------
        bool
            True if reset successful, False otherwise
        """
        self.ctx.info("Resetting DAP state for pooled bridge...")

        try:
            # Clear cached DAP port - forces fresh startDebugSession call
            old_port = self.dap_port
            self.dap_port = None

            if old_port:
                self.ctx.debug(
                    f"Cleared cached DAP port {old_port} - next session "
                    "will request fresh port",
                )

            # Reset LSP client session state to clear any pending requests
            await lsp_client.reset_session_state()
            self.ctx.debug("Reset LSP client session state")

            self.ctx.info("DAP state reset complete")
            return True

        except Exception as e:
            self.ctx.error(f"Failed to reset DAP state: {e}")
            return False

    def get_dap_connection_info(self, process_manager) -> dict[str, Any]:
        """Get diagnostic info about DAP connection state.

        Parameters
        ----------
        process_manager : JDTLSProcessManager
            The process manager for checking process state

        Returns
        -------
        dict[str, Any]
            Connection state diagnostics
        """
        return {
            "dap_port": self.dap_port,
            "is_pooled": self._is_pooled,
            "process_running": process_manager.process is not None
            and process_manager.process.returncode is None,
            "workspace": str(process_manager.workspace)
            if process_manager.workspace
            else None,
        }
