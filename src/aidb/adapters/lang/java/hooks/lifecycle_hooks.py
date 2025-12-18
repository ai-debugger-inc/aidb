"""Java adapter lifecycle hooks implementation."""

import asyncio
import contextlib
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from aidb.adapters.base.hooks import HookContext
from aidb.common.constants import (
    DEFAULT_WAIT_TIMEOUT_S,
    DISCONNECT_TIMEOUT_S,
    LONG_WAIT_S,
)
from aidb.common.errors import AidbError
from aidb_common.config import config
from aidb_common.constants import Language
from aidb_common.env import reader
from aidb_logging.utils import LogOnce

if TYPE_CHECKING:
    from ..java import JavaAdapter


class JavaEnvironmentValidator:
    """Pre-launch validation hooks for Java environment and target."""

    def __init__(self, adapter: "JavaAdapter") -> None:
        """Initialize validator with adapter reference.

        Parameters
        ----------
        adapter : JavaAdapter
            The Java adapter instance
        """
        self.adapter = adapter

    async def validate_environment(self, context: HookContext) -> None:
        """Pre-launch hook to validate Java environment.

        Parameters
        ----------
        context : HookContext
            Hook context containing launch data
        """
        self.adapter.ctx.debug("Pre-launch hook: Validating Java environment")

        try:
            # Check if Java is available
            java_cmd = await self.adapter._get_java_executable()
            self.adapter.ctx.debug(f"Java executable found: {java_cmd}")

            # If auto-compile is enabled, check for javac
            if self.adapter.config.auto_compile:
                javac_cmd = self.adapter._get_javac_executable()
                self.adapter.ctx.debug(f"Java compiler found: {javac_cmd}")

        except AidbError as e:
            self.adapter.ctx.error(f"Java environment validation failed: {e}")
            context.cancelled = True
            context.result = f"Java environment validation failed: {e}"
            raise

    def validate_target(self, context: HookContext) -> None:
        """Pre-launch hook to validate Java target.

        Parameters
        ----------
        context : HookContext
            Hook context containing launch data
        """
        target = context.data.get("target")
        if not target:
            return

        # Extract env and cwd from context.data
        self.adapter._target_env = context.data.get("env", {})
        self.adapter._target_cwd = context.data.get("cwd")

        self.adapter.ctx.debug(f"Pre-launch hook: Validating Java target: {target}")

        # Determine if target is a file path or identifier using same
        # heuristic as Session
        from aidb.session.adapter_registry import get_all_cached_file_extensions

        known_extensions = get_all_cached_file_extensions()
        target_path = Path(target)
        suffix_lower = target_path.suffix.lower()
        has_known_extension = suffix_lower in known_extensions
        has_path_separator = ("/" in target) or ("\\" in target)

        is_file_path = has_known_extension or has_path_separator

        if is_file_path:
            # Target is a file path - validate it exists
            # Check if target has valid extension
            valid_extensions = self.adapter.config.file_extensions
            if (
                not any(target.endswith(ext) for ext in valid_extensions)
                and not Path(target).is_dir()
            ):
                # Not a valid file extension and not a directory
                self.adapter.ctx.warning(
                    f"Target '{target}' does not appear to be a Java file "
                    f"(expected extensions: {', '.join(valid_extensions)})",
                )

            # Check if target exists
            if not Path(target).exists():
                self.adapter.ctx.error(f"Target file/directory not found: {target}")
                context.cancelled = True
                context.result = f"Target not found: {target}"
                msg = f"Target not found: {target}"
                raise AidbError(msg)
        else:
            # Target is an identifier (class name, module, etc.) - skip file validation
            self.adapter.ctx.debug(
                f"Target '{target}' identified as class name/identifier - "
                "skipping file existence check",
            )


class JDTLSSetupHooks:
    """Pre-launch hooks for JDT LS setup and bridge initialization."""

    def __init__(self, adapter: "JavaAdapter") -> None:
        """Initialize setup hooks with adapter reference.

        Parameters
        ----------
        adapter : JavaAdapter
            The Java adapter instance
        """
        self.adapter = adapter

    def prepare_workspace(self, context: HookContext) -> None:
        """Pre-launch hook to prepare JDT LS workspace.

        Parameters
        ----------
        context : HookContext
            Hook context containing launch data
        """
        self.adapter.ctx.debug("Pre-launch hook: Preparing JDT LS workspace")

        # Check if we're using pooling - if so, skip workspace creation
        # The pooled bridge already has its workspace configured

        use_pool = reader.read_bool("AIDB_JAVA_LSP_POOL", default=True)
        use_test_pool = reader.read_bool("AIDB_TEST_JAVA_LSP_POOL", default=False)

        if use_pool or use_test_pool:
            self.adapter.ctx.debug(
                "Skipping workspace creation - will use pooled bridge workspace",
            )
            # Placeholder - will be overridden by _initialize_lsp_dap_bridge
            context.data["jdtls_workspace"] = None
            return

        # Setup workspace directory
        if self.adapter.config.jdtls_workspace:
            workspace_dir = Path(self.adapter.config.jdtls_workspace)
        else:
            # Use a temp workspace directory
            workspace_dir = Path(tempfile.mkdtemp(prefix="jdtls_workspace_"))
            self.adapter._jdtls_workspace_dir = workspace_dir

        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.adapter.ctx.debug(f"JDT LS workspace directory: {workspace_dir}")

        # Store in context for use by other hooks
        context.data["jdtls_workspace"] = workspace_dir

    async def initialize_bridge(self, context: HookContext) -> None:
        """Pre-launch hook to initialize LSP-DAP bridge.

        Parameters
        ----------
        context : HookContext
            Hook context containing launch data
        """
        self.adapter.ctx.debug("Pre-launch hook: Initializing LSP-DAP bridge")

        try:
            await self.ensure_bridge_initialized()
        except Exception as e:
            self.adapter.ctx.error(f"Failed to initialize LSP-DAP bridge: {e}")
            context.cancelled = True
            context.result = f"Failed to initialize LSP-DAP bridge: {e}"
            raise

    async def ensure_bridge_initialized(self) -> None:
        """Ensure the LSP-DAP bridge is initialized.

        This method can be called directly (e.g., for remote attach scenarios)
        or via the initialize_bridge hook during normal launch.

        Raises
        ------
        AidbError
            If the bridge cannot be initialized
        """
        # Skip if already initialized
        if self.adapter._lsp_dap_bridge is not None:
            self.adapter.ctx.debug("LSP-DAP bridge already initialized")
            return

        # Get necessary paths using binary locator
        from aidb.adapters.utils.binary_locator import AdapterBinaryLocator

        from ..lsp.lsp_bridge import JavaLSPDAPBridge

        locator = AdapterBinaryLocator(ctx=self.adapter.ctx)
        java_debug_jar = locator.locate(Language.JAVA.value)

        # Locate JDT LS - check in priority order:
        # 1. AIDB_JDT_LS_HOME environment variable (explicit override)
        # 2. Bundled with adapter (in ~/.aidb/adapters/java/jdtls/)
        # 3. System installation (/opt/jdtls)

        jdtls_home_env = reader.read_str("AIDB_JDT_LS_HOME", default=None)

        if jdtls_home_env:
            # User specified explicit path via environment variable
            jdtls_path = Path(jdtls_home_env)
            self.adapter.ctx.debug(
                f"Using JDT LS from AIDB_JDT_LS_HOME: {jdtls_path}",
            )
        else:
            # Check bundled location (in adapter directory)
            try:
                adapter_dir = locator.get_adapter_dir(Language.JAVA.value)
                bundled_jdtls = adapter_dir / "jdtls"

                if bundled_jdtls.exists():
                    jdtls_path = bundled_jdtls
                    self.adapter.ctx.debug(f"Using bundled JDT LS: {jdtls_path}")
                else:
                    # Fallback to system location
                    jdtls_path = Path("/opt/jdtls")
                    self.adapter.ctx.debug(f"Using system JDT LS: {jdtls_path}")
            except Exception as e:
                # Adapter directory not found, try system location
                self.adapter.ctx.debug(f"Could not locate adapter directory: {e}")
                jdtls_path = Path("/opt/jdtls")
                self.adapter.ctx.debug(f"Using system JDT LS: {jdtls_path}")

        if not jdtls_path.exists():
            msg = (
                "JDT LS not found. Java debugging requires JDT LS. "
                "Set AIDB_JDT_LS_HOME or install adapter with bundled JDT LS."
            )
            self.adapter.ctx.error(msg)
            raise AidbError(msg)

        java_cmd = await self.adapter._get_java_executable()

        # Try test pool first (test isolation, doesn't need workspace_folders)
        use_test_pool = reader.read_bool("AIDB_TEST_JAVA_LSP_POOL", default=False)
        if use_test_pool:
            try:
                from tests._fixtures.java_lsp_pool import get_test_jdtls_pool

                pool = get_test_jdtls_pool()
                if pool:
                    self.adapter.ctx.info(
                        "Using shared JDT LS pool from test infrastructure",
                    )
                    bridge = await pool.get_or_start_bridge(
                        jdtls_path=jdtls_path,
                        java_debug_jar=java_debug_jar,
                        java_command=java_cmd,
                    )
                    self.adapter._lsp_dap_bridge = bridge
                    self.adapter.ctx.debug(
                        "Test pool bridge initialized successfully",
                    )
                    return  # Early return - test pool satisfied the request
            except ImportError:
                self.adapter.ctx.debug(
                    "Test pool requested but not available (not in test environment)",
                )
            except Exception as e:
                self.adapter.ctx.warning(
                    f"Failed to get test pool: {e}, falling back to "
                    "production pool or standalone",
                )

        # Create lightweight bridge for production pool or standalone use
        # Production pool selection happens in launch() where workspace_folders
        # are available
        self.adapter._lsp_dap_bridge = JavaLSPDAPBridge(
            jdtls_path=jdtls_path,
            java_debug_jar=java_debug_jar,
            java_command=java_cmd,
            ctx=self.adapter.ctx,
        )

        LogOnce.debug(
            self.adapter.ctx,
            "java_lsp_dap_bridge_init",
            "LSP-DAP bridge initialized successfully",
        )


class JDTLSReadinessHooks:
    """Post-launch hooks for JDT LS readiness and configuration."""

    def __init__(self, adapter: "JavaAdapter") -> None:
        """Initialize readiness hooks with adapter reference.

        Parameters
        ----------
        adapter : JavaAdapter
            The Java adapter instance
        """
        self.adapter = adapter

    async def wait_for_ready(self, _context: HookContext) -> None:
        """Post-launch hook to wait for JDT LS initialization.

        Parameters
        ----------
        _context : HookContext
            Hook context containing launch result (unused)
        """
        # Skip wait for pooled bridges - they're already initialized
        if self.adapter._lsp_dap_bridge and self.adapter._lsp_dap_bridge.is_pooled():
            self.adapter.ctx.debug(
                "Post-launch hook: Skipping wait for pooled JDT LS bridge "
                "(already initialized)",
            )
            return

        wait_time = LONG_WAIT_S
        self.adapter.ctx.debug(
            f"Post-launch hook: Waiting {wait_time}s for JDT LS initialization",
        )
        await asyncio.sleep(wait_time)

        # Verify LSP-DAP bridge is responding
        if self.adapter._lsp_dap_bridge:
            # The bridge should be ready now
            self.adapter.ctx.debug("JDT LS is ready for debugging")

    def enable_trace_logging(self, _context: HookContext) -> None:
        """Post-launch hook to enable trace logging if configured.

        Parameters
        ----------
        _context : HookContext
            Hook context containing launch result (unused)
        """
        if not (config.is_adapter_trace_enabled() and self.adapter._lsp_dap_bridge):
            return

        self.adapter.ctx.debug("Post-launch hook: Enabling JDT LS trace logging")

        try:
            # When reusing a pooled bridge with a cached DAP port, avoid sending
            # LSP executeCommand between sessions as JDT LS may stop responding
            # on long-lived connections. Only configure trace on first use or
            # for non-pooled bridges.
            if self.adapter._lsp_dap_bridge.is_pooled() and getattr(
                self.adapter._lsp_dap_bridge,
                "dap_port",
                None,
            ):
                self.adapter.ctx.debug(
                    "Skipping JDT LS trace update for pooled bridge reuse",
                )
                return

            # When trace is enabled, always use FINEST for maximum verbosity
            self.adapter.ctx.info("Enabling JDT LS trace logging with level: FINEST")

            # Since hooks are sync but update_debug_settings is async,
            # we need to handle this carefully
            try:
                loop = asyncio.get_running_loop()
                # Create task to run async method without blocking
                loop.create_task(
                    self.adapter._lsp_dap_bridge.update_debug_settings(),
                )
                # Log that we've scheduled it
                self.adapter.ctx.debug("Scheduled JDT LS trace logging enablement")
            except RuntimeError:
                # No running loop, can't call async method from sync context
                self.adapter.ctx.warning(
                    "Cannot enable JDT LS trace logging: no async event loop available",
                )

        except Exception as e:
            self.adapter.ctx.warning(f"Error enabling JDT LS trace logging: {e}")


class JDTLSCleanupHooks:
    """Post-stop hooks for JDT LS cleanup and resource management."""

    def __init__(self, adapter: "JavaAdapter") -> None:
        """Initialize cleanup hooks with adapter reference.

        Parameters
        ----------
        adapter : JavaAdapter
            The Java adapter instance
        """
        self.adapter = adapter

    def collect_logs(self, _context: HookContext) -> None:
        """Post-stop hook to collect Eclipse Platform logs.

        Parameters
        ----------
        _context : HookContext
            Hook context containing stop information
        """
        if not config.is_adapter_trace_enabled():
            return

        self.adapter.ctx.debug("Post-stop hook: Collecting Eclipse Platform logs")

        try:
            if not self.adapter._lsp_dap_bridge:
                self.adapter.ctx.debug(
                    "No LSP-DAP bridge active, skipping Eclipse log collection",
                )
                return

            eclipse_log = self.adapter._lsp_dap_bridge.get_eclipse_log_path()
            if not eclipse_log:
                self.adapter.ctx.debug("No Eclipse Platform log found")
                return

            if self.adapter._trace_manager:
                trace_dir = Path(
                    self.adapter._trace_manager.get_trace_log_path(
                        Language.JAVA.value,
                        "log",
                    ),
                ).parent
                eclipse_trace_path = trace_dir / "java.eclipse.log"

                # Append Eclipse log contents to the rotating file
                with eclipse_trace_path.open("a") as dest_file:
                    dest_file.write(
                        f"\n\n# === Eclipse Platform Log - "
                        f"{datetime.now(timezone.utc).isoformat()} ===\n",
                    )
                    with Path(eclipse_log).open() as src_file:
                        dest_file.write(src_file.read())

                self.adapter.ctx.info(
                    f"Appended Eclipse Platform log to {eclipse_trace_path}",
                )

        except Exception as e:
            self.adapter.ctx.warning(f"Failed to collect Eclipse logs: {e}")

    async def cleanup_bridge(self, _context: HookContext) -> None:
        """Post-stop hook to clean up LSP-DAP bridge.

        Parameters
        ----------
        _context : HookContext
            Hook context containing cleanup information
        """
        # Clean up dummy process first
        if self.adapter._dummy_process:
            self.adapter.ctx.debug("Post-stop hook: Terminating dummy process")
            try:
                self.adapter._dummy_process.terminate()
                try:
                    await asyncio.wait_for(
                        self.adapter._dummy_process.wait(),
                        timeout=DISCONNECT_TIMEOUT_S,
                    )
                except asyncio.TimeoutError:
                    self.adapter._dummy_process.kill()
                    await self.adapter._dummy_process.wait()

                # Close all subprocess transports to avoid ResourceWarnings
                from aidb_common.io.subprocess import close_subprocess_transports

                await close_subprocess_transports(
                    self.adapter._dummy_process,
                    self.adapter.ctx,
                    "Dummy process",
                )

            except Exception as e:
                self.adapter.ctx.debug(f"Error terminating dummy process: {e}")
            finally:
                self.adapter._dummy_process = None

        self.adapter.ctx.debug(
            f"[CLEANUP] Bridge exists: {self.adapter._lsp_dap_bridge is not None}",
        )
        if self.adapter._lsp_dap_bridge:
            # Check if this is a pooled bridge using helper method
            is_pooled_bridge = self._is_bridge_pooled()

            self.adapter.ctx.debug(
                f"[CLEANUP] Final is_pooled_bridge decision: {is_pooled_bridge}",
            )
            if is_pooled_bridge:
                # For pooled bridges, keep the cached DAP port so subsequent
                # sessions can bypass LSP and connect directly to the java-debug
                # server. This keeps JDT LS hot and avoids the 8-9s startup cost.
                self.adapter.ctx.info(
                    "[CLEANUP] Pooled bridge detected - "
                    "skipping stop (managed by pool)",
                )
                # Allow the java-debug server to fully recycle the previous
                # connection before the next session connects to the same port.
                # Without this, the next session may occasionally time out on
                # DAP initialize/launch due to immediate reconnect.
                with contextlib.suppress(Exception):
                    delay = (
                        reader.read_float(
                            "AIDB_JAVA_POOLED_POST_DISCONNECT_DELAY",
                            1.5,
                        )
                        or 1.5
                    )
                    await asyncio.sleep(delay)

                # Just clear our reference, don't stop the pooled bridge
                self.adapter._lsp_dap_bridge = None
                return

            # Only stop non-pooled bridges
            self.adapter.ctx.debug("Post-stop hook: Stopping non-pooled LSP-DAP bridge")
            try:
                await self.adapter._lsp_dap_bridge.stop()
            except Exception as e:
                self.adapter.ctx.warning(f"Error stopping LSP-DAP bridge: {e}")
            self.adapter._lsp_dap_bridge = None

    def cleanup_workspace(self, _context: HookContext) -> None:
        """Post-stop hook to clean up JDT LS workspace and processes.

        Parameters
        ----------
        _context : HookContext
            Hook context containing cleanup information
        """
        # Stop JDT LS if running (fallback cleanup)
        if self.adapter._jdtls_process:
            self.adapter.ctx.debug("Post-stop hook: Terminating JDT LS process")
            try:
                self.adapter._jdtls_process.terminate()
                self.adapter._jdtls_process.wait(timeout=DEFAULT_WAIT_TIMEOUT_S)
            except Exception:
                with contextlib.suppress(Exception):
                    self.adapter._jdtls_process.kill()
            self.adapter._jdtls_process = None

        # Clean up temporary workspace
        if (
            self.adapter._jdtls_workspace_dir
            and self.adapter._jdtls_workspace_dir.exists()
        ):
            ws_dir = self.adapter._jdtls_workspace_dir
            self.adapter.ctx.debug(f"Post-stop hook: Removing workspace {ws_dir}")
            try:
                shutil.rmtree(self.adapter._jdtls_workspace_dir)
            except Exception as e:
                self.adapter.ctx.warning(f"Failed to remove workspace: {e}")
            self.adapter._jdtls_workspace_dir = None

        # Clean up compilation manager
        if self.adapter._compilation_manager:
            self.adapter.ctx.debug("Post-stop hook: Cleaning up compilation manager")
            self.adapter._compilation_manager.cleanup()
            self.adapter._compilation_manager = None

    def _is_bridge_pooled(self) -> bool:
        """Check if the current LSP-DAP bridge is managed by a pool.

        Uses the _is_pooled flag (via bridge.is_pooled()) which is set when
        the bridge is allocated from a pool. This is the authoritative check -
        no need to query pool registries directly.

        Returns
        -------
        bool
            True if bridge is pooled, False otherwise
        """
        if self.adapter._lsp_dap_bridge:
            is_pooled = self.adapter._lsp_dap_bridge.is_pooled()
            self.adapter.ctx.debug(f"[CLEANUP] Bridge.is_pooled(): {is_pooled}")
            return is_pooled
        return False
