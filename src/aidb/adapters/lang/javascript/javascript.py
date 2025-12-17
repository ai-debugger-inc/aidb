"""JavaScript/TypeScript debug adapter."""

import asyncio
import contextlib
import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.common.constants import (
    DEFAULT_ADAPTER_HOST,
    INIT_WAIT_FOR_INITIALIZED_S,
    INIT_WAIT_FOR_LAUNCH_RESPONSE_S,
    MEDIUM_SLEEP_S,
    PROCESS_COMMUNICATE_TIMEOUT_S,
)
from aidb.common.errors import AidbError, ConfigurationError, DebugAdapterError
from aidb.models.start_request import StartRequestType
from aidb_common.config import config
from aidb_common.path import normalize_path

from ...base import DebugAdapter
from ...base.config_mapper import ConfigurationMapper
from ...base.hooks import HookContext, LifecycleHook
from ...base.target_resolver import TargetResolver
from .config import JavaScriptAdapterConfig
from .target_resolver import JavaScriptTargetResolver

if TYPE_CHECKING:
    from aidb.adapters.base.source_path_resolver import SourcePathResolver
    from aidb.interfaces import ISession


class JavaScriptAdapter(DebugAdapter):
    """JavaScript and TypeScript debug adapter.

    This adapter handles JavaScript and TypeScript debugging:
        - JavaScript files (.js, .jsx, .mjs, .cjs)
        - TypeScript files (.ts, .tsx, .mts, .cts) via ts-node
        - Uses Microsoft's vscode-js-debug for proper DAP protocol support
    """

    config: JavaScriptAdapterConfig  # Override parent type annotation
    post_launch_delay = MEDIUM_SLEEP_S  # Reduced from 3.0 to avoid test timeouts

    # -----------------------
    # Public API / Lifecycle
    # -----------------------

    def __init__(
        self,
        session: "ISession",
        ctx=None,
        adapter_host=DEFAULT_ADAPTER_HOST,
        adapter_port=None,
        target_host=DEFAULT_ADAPTER_HOST,
        target_port=None,
        config: JavaScriptAdapterConfig | None = None,
        runtime_executable: str | None = None,
        runtime_args: list[str] | None = None,
        env_file: str | None = None,
        source_maps: bool | None = None,
        out_files: list[str] | None = None,
        **kwargs,
    ):
        """Initialize JavaScript debug adapter.

        Parameters
        ----------
        session : Session
            The session that owns this adapter
        ctx : AidbContext, optional
            Application context
        adapter_host : str, optional
            Host where vscode-js-debug server binds
        adapter_port : int, optional
            Port where vscode-js-debug server listens
        target_host : str, optional
            Host where the target process runs
        target_port : int, optional
            Port for target process communication
        config : JavaScriptAdapterConfig, optional
            JavaScript adapter configuration
        runtime_executable : str, optional
            Runtime to use (e.g., "node", "npm", "yarn", "pnpm")
        runtime_args : List[str], optional
            Arguments for the runtime (e.g., ["run", "debug"] for npm scripts)
        env_file : str, optional
            Path to .env file to load environment variables from
        source_maps : bool, optional
            Enable/disable source map support
        out_files : List[str], optional
            Glob patterns for transpiled JavaScript files
        ``**kwargs`` : Any
            Additional configuration overrides
        """
        # Use provided config or create default
        if config is None:
            config = JavaScriptAdapterConfig()

        # Update config with JS-specific options from kwargs
        javascript_config_mappings = {
            "sourceMaps": "enable_source_maps",
            "console": "console",
            "outputCapture": "output_capture",
            "showAsyncStacks": "show_async_stacks",
        }
        ConfigurationMapper.apply_kwargs(config, kwargs, javascript_config_mappings)

        # Check if debugger_type is passed and update config
        if "debugger_type" in kwargs:
            debugger_type = kwargs.pop("debugger_type")
            # Update the adapter_type in config to match the debugger type. This
            # determines whether to use pwa-node, pwa-chrome, or pwa-msedge
            if debugger_type in [
                "pwa-node",
                "pwa-chrome",
                "pwa-msedge",
                "node",
                "chrome",
                "msedge",
            ]:
                config.adapter_type = debugger_type
                self.ctx.debug(f"Using debugger type: {debugger_type}")

        super().__init__(
            session=session,
            ctx=ctx,
            adapter_host=adapter_host,
            adapter_port=adapter_port,
            target_host=target_host,
            target_port=target_port,
            config=config,
        )

        # JavaScript uses parent-child sessions. Only child sessions should have
        # breakpoints - parent sessions spawn child sessions that do the actual
        # debugging. Clear breakpoints from parent sessions and store them for
        # child session creation.
        bp_count = len(session.breakpoints) if session.breakpoints else 0
        self.ctx.debug(
            f"JavaScript adapter init: session.is_child={session.is_child}, "
            f"session.breakpoints count={bp_count}",
        )
        if not session.is_child and session.breakpoints:
            self.ctx.debug(
                f"JavaScript parent session {session.id} clearing "
                f"{len(session.breakpoints)} breakpoints "
                f"(will be transferred to child session)",
            )
            # Store breakpoints for child session
            session._pending_child_breakpoints = session.breakpoints.copy()
            # Clear from parent
            session.breakpoints = []
            self.ctx.debug(
                f"JavaScript parent session {session.id}: "
                f"Transferred {len(session._pending_child_breakpoints)} breakpoints "
                f"to _pending_child_breakpoints",
            )
        elif not session.is_child:
            self.ctx.warning(
                f"JavaScript parent session {session.id} has NO breakpoints! "
                f"This will prevent child session from getting breakpoints.",
            )

        # JavaScript-specific state
        self._js_debug_server_path: Path | None = None
        self._node_path: str | None = None
        self._ts_node_available: bool | None = None
        self._target_file: str | None = None
        self._target_args: list[str] = []
        self._target_cwd: str | None = None
        self._project_config: dict | None = None

        # Store launch.json configuration passed through
        self.runtime_executable = runtime_executable
        self.runtime_args = runtime_args or []
        self.env_file = env_file
        self.source_maps = (
            source_maps if source_maps is not None else config.enable_source_maps
        )
        self.out_files = out_files or []

        # Register JavaScript-specific hooks
        self._register_javascript_hooks()

    def _create_target_resolver(self) -> TargetResolver:
        """Create JavaScript-specific target resolver.

        Returns
        -------
        TargetResolver
            JavaScriptTargetResolver instance for file type detection
        """
        return JavaScriptTargetResolver(adapter=self, ctx=self.ctx)

    def _create_source_path_resolver(self) -> "SourcePathResolver":
        """Create JavaScript-specific source path resolver.

        Returns
        -------
        SourcePathResolver
            JavaScriptSourcePathResolver instance for node_modules resolution
        """
        from .source_path_resolver import JavaScriptSourcePathResolver

        return JavaScriptSourcePathResolver(adapter=self, ctx=self.ctx)

    async def attach(self, pid: int, session_id: str) -> None:
        """Attach to a running Node.js process.

        Note: vscode-js-debug attach mode requires additional configuration that
        is not yet fully implemented.

        Parameters
        ----------
        pid : int
            Process ID (not directly used for Node.js)
        session_id : str
            Session identifier
        """
        self.ctx.warning(
            "Attach mode for Node.js debugging requires additional setup. "
            "Consider using launch mode or configuring attach via debugger port.",
        )
        await super().attach(pid, session_id)

    # ----------------------
    # Hook Registration
    # ----------------------

    def _register_javascript_hooks(self) -> None:
        """Register JavaScript-specific lifecycle hooks."""
        # Pre-launch hooks (high priority = run first)
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._validate_js_environment,
            priority=90,  # Very high priority - validate environment first
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._cleanup_orphan_js_debug_pre_launch,
            priority=85,  # High priority - clean orphans before launch
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._detect_project_config,
            priority=80,  # High priority - detect config early
        )
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._prepare_vscode_js_debug,
            priority=70,  # Prepare binary before launch
        )

        # Post-launch hooks (low priority = run later)
        # No artificial wait — readiness is confirmed by initialized event
        # kept for compatibility but as a no-op
        self.register_hook(
            LifecycleHook.POST_LAUNCH,
            self._wait_for_js_debug_server,
            priority=20,
        )

        # Post-stop hooks
        self.register_hook(
            LifecycleHook.POST_STOP,
            self._cleanup_js_debug_logs,
            priority=10,  # Clean up logs after stop
        )
        # Proactively clean orphaned js-debug/node DAP server processes to
        # prevent hangs on subsequent launches due to lingering servers or
        # sockets left from pytest finalizer issues.
        self.register_hook(
            LifecycleHook.POST_STOP,
            self._cleanup_orphan_js_debug,
            priority=15,  # Run before log cleanup
        )

    # ----------------------
    # Pre-Launch Hooks
    # ----------------------

    async def _validate_js_environment(self, context: HookContext) -> None:
        """Pre-launch hook to validate JavaScript environment.

        Parameters
        ----------
        context : HookContext
            Hook execution context
        """
        # Get target from context
        target = context.data.get("target")
        if not target:
            return

        self._target_file = target
        self._target_args = context.data.get("args", [])
        self._target_env = context.data.get("env", {})
        self._target_cwd = context.data.get("cwd")

        # Validate Node.js is available
        try:
            self._node_path = self._get_node_executable()
            node_version = await self._detect_node_version()
            if node_version:
                self.ctx.debug(f"Node.js version: {node_version}")
        except AidbError as e:
            context.cancelled = True
            context.result = str(e)
            return

        # Check if target file exists
        target_path = Path(target)
        if not target_path.exists():
            self.ctx.error(f"Target file not found: {target}")
            self.ctx.error(f"Absolute path: {target_path.absolute()}")
            context.cancelled = True
            context.result = f"Target file not found: {target}"
            return

        # Check TypeScript support if needed
        if target_path.suffix.lower() in [".ts", ".tsx", ".mts", ".cts"]:
            await self._check_ts_node_available()
            if not self._ts_node_available and self.ctx:
                self.ctx.warning(
                    "TypeScript file detected but ts-node not available. "
                    "Install with: npm install -g ts-node typescript",
                )

    def _detect_project_config(self, _context: HookContext) -> None:
        """Pre-launch hook to detect project configuration.

        Parameters
        ----------
        context : HookContext
            Hook execution context
        """
        if not self._target_file:
            return

        # Detect package.json and tsconfig.json
        self._project_config = {
            "package": self._get_package_json_info(self._target_file),
            "typescript": self._get_tsconfig_info(self._target_file),
        }

        if self._project_config["package"]:
            pkg = self._project_config["package"]
            self.ctx.debug(
                f"Detected Node.js project: {pkg.get('name', 'unnamed')} "
                f"v{pkg.get('version', 'unknown')}",
            )

    async def _prepare_vscode_js_debug(self, context: HookContext) -> None:
        """Pre-launch hook to prepare vscode-js-debug binary.

        Parameters
        ----------
        context : HookContext
            Hook execution context
        """
        try:
            self._js_debug_server_path = await self._resolve_js_debug_binary()
            self.ctx.debug(f"vscode-js-debug server: {self._js_debug_server_path}")
        except AidbError as e:
            self.ctx.error(f"Failed to resolve vscode-js-debug binary: {e}")
            context.cancelled = True
            context.result = str(e)

    # -----------------------------
    # Post-Launch / Post-Stop Hooks
    # -----------------------------

    async def _wait_for_js_debug_server(self, _context: HookContext) -> None:
        """Post-launch hook to wait for vscode-js-debug server readiness.

        Parameters
        ----------
        context : HookContext
            Hook execution context
        """
        # No-op: DAP 'initialized' already observed; avoid fixed sleep
        self.ctx.debug("vscode-js-debug server initialization assumed ready")

    @property
    def prefers_transport_only_disconnect(self) -> bool:
        """Prefer transport-only disconnect to avoid 2s DAP wait."""
        return True

    def _cleanup_js_debug_logs(self, _context: HookContext) -> None:
        """Post-stop hook to clean up vscode-js-debug logs.

        Parameters
        ----------
        context : HookContext
            Hook execution context
        """
        # If trace logging was enabled, manage log files
        if config.is_adapter_trace_enabled() and self._trace_manager:
            # Check the current log file size
            self._trace_manager.check_and_halve_log()

    # ----------------------
    # Command Builders
    # ----------------------

    async def _build_launch_command(
        self,
        target: str,
        adapter_host: str,  # noqa: ARG002
        adapter_port: int,
        args: list[str] | None = None,
    ) -> list[str]:
        """Build command to launch vscode-js-debug DAP server.

        Parameters
        ----------
        target : str
            JavaScript or TypeScript file to debug
        adapter_host : str
            Host for DAP server to bind to (unused - vscode-js-debug binds to
            localhost only)
        adapter_port : int
            Port for DAP server to listen on
        args : List[str], optional
            Additional arguments for the target program

        Returns
        -------
        List[str]
            Command to launch vscode-js-debug DAP server
        """
        # Ensure we have the server path
        if not self._js_debug_server_path:
            self._js_debug_server_path = await self._resolve_js_debug_binary()

        # Build the command to launch the DAP server. The server expects: node
        # dapDebugServer.js <port>
        node_exe = self._node_path or self._get_node_executable()
        cmd = [node_exe, str(self._js_debug_server_path), str(adapter_port)]

        # Store target info for later use
        self._target_file = target
        self._target_args = args or []

        return cmd

    # ----------------------
    # Environment & Process
    # ----------------------

    def _add_adapter_specific_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Add JavaScript-specific environment variables.

        Parameters
        ----------
        env : dict[str, str]
            Current environment variables

        Returns
        -------
        dict[str, str]
            Updated environment with JavaScript-specific variables
        """
        # Set Node.js specific environment variables
        env["NODE_ENV"] = env.get("NODE_ENV", "development")

        # Enable source map support
        if self.config.enable_source_maps:
            env["NODE_OPTIONS"] = env.get("NODE_OPTIONS", "") + " --enable-source-maps"

        # Disable telemetry
        env["DA_TEST_DISABLE_TELEMETRY"] = "1"

        return env

    def _get_process_name_pattern(self) -> str:
        """Get process name pattern for cleanup.

        Returns
        -------
        str
            Pattern to match vscode-js-debug and target processes
        """
        # Use a simple substring that appears in the js-debug DAP server cmdline
        # so ProcessManager's substring match finds it reliably.
        return "dapDebugServer"

    async def _cleanup_orphan_js_debug_pre_launch(
        self,
        _context: HookContext,
    ) -> None:
        """Pre-launch: ensure clean slate before starting adapter.

        Fast, time-budgeted scan to clean up orphans from previous sessions
        before launching new adapter. Prevents hangs from pytest finalizer
        issues.
        """
        try:
            from aidb.common.constants import ORPHAN_SCAN_PRE_LAUNCH_MS
            from aidb_common.env import reader

            min_age = reader.read_float("AIDB_JS_ORPHAN_MIN_AGE", 5.0) or 5.0
            pattern = self._get_process_name_pattern()
            self.ctx.debug(
                f"[PRE-LAUNCH] Cleaning orphaned js-debug "
                f"(min_age={min_age}s, budget={ORPHAN_SCAN_PRE_LAUNCH_MS:.0f}ms)",
            )

            stats = self._process_manager.cleanup_orphaned_processes(
                pattern,
                min_age_seconds=min_age,
                max_scan_ms=ORPHAN_SCAN_PRE_LAUNCH_MS,
            )

            if stats["killed"] > 0:
                killed_count = stats["killed"]
                self.ctx.info(
                    f"[PRE-LAUNCH] Killed {killed_count} orphaned js-debug processes",
                )

        except Exception as e:
            self.ctx.debug(f"Pre-launch orphan cleanup skipped/failed: {e}")

    async def _cleanup_orphan_js_debug(self, _context: HookContext) -> None:
        """Post-stop: clean up orphaned js-debug DAP server processes.

        This mitigates teardown glitches that leave js-debug servers running
        and block the next test.
        """
        try:
            from aidb.common.constants import ORPHAN_SCAN_POST_STOP_MS
            from aidb_common.env import reader

            if reader.read_bool("AIDB_SKIP_POST_STOP_ORPHAN_CLEANUP", False):
                self.ctx.debug("[POST-STOP] Orphan cleanup skipped via env var")
                return

            min_age = reader.read_float("AIDB_JS_ORPHAN_MIN_AGE", 5.0) or 5.0
            pattern = self._get_process_name_pattern()
            self.ctx.debug(
                f"[POST-STOP] Cleaning orphaned js-debug (min_age={min_age}s)",
            )

            stats = self._process_manager.cleanup_orphaned_processes(
                pattern,
                min_age_seconds=min_age,
                max_scan_ms=ORPHAN_SCAN_POST_STOP_MS,
            )

            if stats["killed"] > 0:
                self.ctx.debug(
                    f"[POST-STOP] Killed {stats['killed']} orphaned js-debug processes",
                )

        except Exception as e:
            self.ctx.debug(f"Post-stop orphan cleanup skipped/failed: {e}")

    # -----------------------------
    # Child Session Configuration
    # -----------------------------

    def configure_child_launch(self, launch_args: dict[str, Any]) -> None:
        """Configure launch args for child sessions created via startDebugging.

        For vscode-js-debug, child sessions need specific configuration settings
        to work properly.

        Parameters
        ----------
        launch_args : Dict[str, Any]
            The launch arguments dictionary to modify in-place
        """
        # vscode-js-debug specific configuration for child sessions
        launch_args.setdefault("type", "pwa-node")
        launch_args.setdefault("console", "internalConsole")

        # If program is specified in the target, use it
        if "program" not in launch_args and self.session and self.session.target:
            launch_args["program"] = self.session.target

        # Ensure the pending target ID is present for child sessions when
        # available. vscode-js-debug expects "__pendingTargetId" to route the
        # new child connection.
        if (
            "__pendingTargetId" not in launch_args
            and hasattr(self.session, "_pending_target_id")
            and self.session._pending_target_id
        ):
            launch_args["__pendingTargetId"] = self.session._pending_target_id
            # Best-effort debug log; don't fail if ctx missing
            with contextlib.suppress(Exception):
                self.ctx.debug(
                    f"Added __pendingTargetId to child launch args: "
                    f"{launch_args['__pendingTargetId']}",
                )

    @property
    def requires_child_session_wait(self) -> bool:
        """Javascript adapter requires waiting for child session creation.

        vscode-js-debug creates child sessions asynchronously via startDebugging
        reverse requests and we need to wait for them to be ready before
        proceeding with operations.

        Returns
        -------
        bool
            True - JavaScript requires waiting for child session
        """
        return True

    async def initialize_child_dap(
        self,
        child_session: "ISession",
        _start_request_type: StartRequestType,
        config: dict[str, Any],
    ) -> None:
        """Initialize JavaScript child session's separate DAP connection.

        JavaScript child sessions have their own DAP connection that needs to be
        connected and initialized with __pendingTargetId.

        Parameters
        ----------
        child_session : Session
            The JavaScript child session
        request_type : str
            Either "launch" or "attach"
        config : dict
            Configuration from the startDebugging request
        """
        self.ctx.info(
            f"Creating separate DAP connection for "
            f"JavaScript child session {child_session.id}",
        )

        # Store the pending target ID for use in launch params
        if "__pendingTargetId" in config:
            child_session._pending_target_id = config["__pendingTargetId"]
            self.ctx.debug(
                f"Child session {child_session.id} has "
                f"__pendingTargetId: {child_session._pending_target_id}",
            )

        # Create DAP client for child session - it connects to the same adapter
        # as its parent
        if self.session.adapter_port is None:
            msg = f"Parent session {self.session.id} has no adapter port"
            raise ConfigurationError(
                msg,
            )

        self.ctx.info(
            f"About to call _setup_child_dap_client for {child_session.id} "
            f"at {self.adapter_host}:{self.session.adapter_port}",
        )
        await child_session._setup_child_dap_client(
            self.adapter_host,
            self.session.adapter_port,
        )
        self.ctx.info(f"Completed _setup_child_dap_client for {child_session.id}")

        # Subscribe child to breakpoint events for state synchronization
        # This is the critical bridge that syncs asynchronous breakpoint verification
        # events from the DAP adapter back to child session state
        await child_session._setup_breakpoint_event_subscription()
        self.ctx.info(
            f"Child session {child_session.id} subscribed to breakpoint events",
        )

        # Child doesn't need its own adapter process - it connects to parent's
        child_session._adapter_process = None
        # But it does need to reference the parent's adapter for status checks
        child_session.adapter = self

        self.ctx.info(
            f"Initialized JavaScript child session {child_session.id} DAP connection",
        )

        if hasattr(child_session, "_pending_target_id"):
            # Minimal launch config - only what vscode-js-debug actually uses
            launch_config = {"__pendingTargetId": child_session._pending_target_id}
            child_session._launch_args_override = launch_config
            self.ctx.info(
                f"Child session {child_session.id} will send minimal "
                f"launch with __pendingTargetId: {child_session._pending_target_id}",
            )

        try:
            # Create child-specific initialization sequence that includes
            # breakpoints
            from aidb.adapters.base.initialize import (
                InitializationOp,
                InitializationOpType,
            )

            self.ctx.info(
                f"Creating child-specific initialization "
                f"sequence for JavaScript child {child_session.id}",
            )
            self.ctx.info(
                f"Child {child_session.id} has "
                f"{len(child_session.breakpoints) if child_session.breakpoints else 0} "
                f"breakpoints",
            )

            child_sequence = [
                InitializationOp(InitializationOpType.INITIALIZE),
                InitializationOp(InitializationOpType.LAUNCH, wait_for_response=False),
                InitializationOp(
                    InitializationOpType.WAIT_FOR_INITIALIZED,
                    timeout=INIT_WAIT_FOR_INITIALIZED_S,
                    optional=True,
                ),
                # Set breakpoints AFTER initialized but BEFORE
                # configurationDone. This ensures breakpoints are set while the
                # program is paused and can bind properly.
                InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=False),
                # NOTE: WAIT_FOR_BREAKPOINT_VERIFICATION is intentionally omitted.
                # JavaScript uses LoadedSource proactive rebinding + event sync
                # for breakpoint verification, which happens asynchronously after
                # CONFIGURATION_DONE. The test interface handles waiting for
                # verification to complete.
                InitializationOp(InitializationOpType.CONFIGURATION_DONE),
                InitializationOp(
                    InitializationOpType.WAIT_FOR_LAUNCH_RESPONSE,
                    timeout=INIT_WAIT_FOR_LAUNCH_RESPONSE_S,
                ),
            ]

            self.ctx.info(
                f"Using child-specific initialization "
                f"sequence with SET_BREAKPOINTS for session {child_session.id}",
            )
            self.ctx.debug(
                f"Initialization sequence has {len(child_sequence)} operations",
            )
            for i, op in enumerate(child_sequence):
                self.ctx.debug(f"  Op {i}: {op.type.value}")

            # Execute the initialization sequence
            from aidb.session.ops.initialization import InitializationMixin

            init_ops = InitializationMixin(session=child_session, ctx=self.ctx)
            await init_ops._execute_initialization_sequence(child_sequence)

            self.ctx.info(
                f"JavaScript child session {child_session.id} initialized and active",
            )

        except Exception as e:
            self.ctx.error(f"Failed to initialize JavaScript child DAP: {e}")
            msg = f"JavaScript child session initialization failed: {e}"
            raise DebugAdapterError(
                msg,
            ) from e

    # -------------------------------
    # Launch Configuration & Tracing
    # -------------------------------

    def get_launch_configuration(self) -> dict[str, Any]:
        """Get the launch configuration for vscode-js-debug.

        This method is called by the initialization operations to get the proper
        launch configuration that vscode-js-debug expects.

        Returns
        -------
        Dict[str, Any]
            Launch configuration compatible with vscode-js-debug
        """
        if not self._target_file:
            return {}

        normalized_target = normalize_path(self._target_file)
        target_path = Path(normalized_target)
        is_typescript = target_path.suffix.lower() in [".ts", ".tsx", ".mts", ".cts"]

        # Use provided cwd or default to target's parent directory
        # Normalize cwd to match program path (important for vscode-js-debug)
        if self._target_cwd:
            cwd = normalize_path(self._target_cwd)
        else:
            cwd = str(target_path.parent)

        config = {
            "type": self.config.adapter_type,
            "request": "launch",
            "name": "Debug JavaScript",
            "program": normalized_target,
            "cwd": cwd,
            "console": self.config.console,
            "outputCapture": self.config.output_capture,
            "timeout": 10000,
            "showAsyncStacks": self.config.show_async_stacks,
            "smartStep": True,
            "sourceMaps": self.source_maps,
            "sourceMapRenames": True,
            "pauseForSourceMap": False,
            "skipFiles": ["<node_internals>/**/*.js"],
            "enableContentValidation": True,
            "autoAttachChildProcesses": True,
            "runtimeExecutable": self.runtime_executable or "node",
            "runtimeVersion": "default",
            "runtimeArgs": list(self.runtime_args),
            "args": self._target_args or [],
            # Default source map path overrides
            "sourceMapPathOverrides": {
                "webpack:///./~/*": "${workspaceFolder}/node_modules/*",
                "webpack:////*": "/*",
                "webpack://?:*/*": "${workspaceFolder}/*",
                "meteor://💻app/*": "${workspaceFolder}/*",
                "turbopack://[project]/*": "${workspaceFolder}/*",
            },
            # Merge adapter env with user-provided env (user takes precedence)
            "env": {**self._load_base_environment(), **self._target_env},
            "envFile": self.env_file,
            "localRoot": None,
            "remoteRoot": None,
            # Additional settings
            "profileStartup": False,
            "attachSimplePort": None,
            "experimentalNetworking": "auto",
            "killBehavior": "forceful",
            "restart": False,
            "__workspaceFolder": str(target_path.parent),
            "__breakOnConditionalError": False,
        }

        # Add outFiles if specified (for source map resolution)
        if self.out_files:
            config["outFiles"] = self.out_files

        # Add trace configuration using the dedicated method
        config["trace"] = self.get_trace_config()

        # Add TypeScript support if needed
        if is_typescript and self.config.use_ts_node and self._ts_node_available:
            # Prepend ts-node/register to existing runtime args
            runtime_args_obj = config["runtimeArgs"]
            runtime_args: list[str] = (
                runtime_args_obj if isinstance(runtime_args_obj, list) else []
            )
            if "-r" not in runtime_args and "ts-node/register" not in runtime_args:
                config["runtimeArgs"] = ["-r", "ts-node/register"] + runtime_args

        # Override with custom Node.js path if specified
        if self.config.node_path:
            config["runtimeExecutable"] = self.config.node_path

        # If using npm/yarn/pnpm script execution, adjust the program
        if (
            self.runtime_executable in ["npm", "yarn", "pnpm"]
            and self.runtime_args
            and len(self.runtime_args) >= 2
        ):
            # For package manager scripts, the "program" is not used directly
            # The script name should be in runtime_args (e.g., ["run", "debug"])
            # Set cwd to the directory containing package.json
            package_json_dir = self._find_package_json_dir(target_path)
            if package_json_dir:
                config["cwd"] = str(package_json_dir)
            # Clear program when using npm scripts
            config.pop("program", None)

        self.ctx.debug(
            f"Generated vscode-js-debug launch configuration with {len(config)} fields",
        )

        return config

    def get_trace_config(self) -> dict[str, Any] | None:
        """Get trace configuration for vscode-js-debug.

        Returns the appropriate trace configuration for inclusion in the DAP
        launch request. When tracing is enabled, returns an object with stdio
        and logFile settings. When disabled, returns None.

        Returns
        -------
        Optional[Dict[str, Any]]
            Either None (tracing disabled) or a dict with trace settings
        """
        if not config.is_adapter_trace_enabled():
            return None

        # Get trace log path from trace manager
        log_file_path = None

        if self._trace_manager:
            # Get the trace log path - now returns a stable .log.json path with
            # rotation
            trace_path = self._trace_manager.get_trace_log_path(
                self.config.adapter_id,
            )
            log_file_path = str(trace_path)
            self.ctx.debug(
                f"vscode-js-debug trace log will be written to: {log_file_path}",
            )

        return {"stdio": True, "logFile": log_file_path}

    # ----------------------
    # Helpers
    # ----------------------

    def _get_node_executable(self) -> str:
        """Get the Node.js executable path."""
        if self.config.node_path and Path(self.config.node_path).exists():
            return self.config.node_path

        # Try to find node in PATH
        node_cmd = "node.exe" if platform.system() == "Windows" else "node"
        node_path = shutil.which(node_cmd)

        if node_path:
            return node_path
        msg = "Node.js not found. Please install Node.js or set node_path in config."
        raise AidbError(
            msg,
        )

    async def _resolve_js_debug_binary(self) -> Path:
        """Resolve the vscode-js-debug server binary path."""
        # Check if explicitly configured
        if self.config.js_debug_path:
            js_debug_path = Path(self.config.js_debug_path)
            if js_debug_path.exists():
                return js_debug_path

        # Try to get from binary manager
        try:
            js_debug_binary = await self.locate_adapter_binary()

            # The binary manager should return the dapDebugServer.js path
            if js_debug_binary.name == "dapDebugServer.js" and js_debug_binary.exists():
                return js_debug_binary

            # Search for dapDebugServer.js in common locations
            search_paths = [
                js_debug_binary.parent / "dapDebugServer.js",
                js_debug_binary.parent / "src" / "dapDebugServer.js",
                js_debug_binary.parent.parent / "src" / "dapDebugServer.js",
            ]

            for path in search_paths:
                if path.exists():
                    return path

            # If not found, search recursively (but limit depth)
            for dap_file in js_debug_binary.parent.rglob("dapDebugServer.js"):
                return dap_file  # Return first match

            msg = f"Could not find dapDebugServer.js relative to {js_debug_binary}"
            raise AidbError(
                msg,
            )

        except Exception as e:
            msg = (
                f"Failed to get vscode-js-debug binary: {e}\n"
                "You can install it manually and set AIDB_JAVASCRIPT_PATH or "
                "the js_debug_path config option."
            )
            raise AidbError(msg) from e

    async def _check_ts_node_available(self) -> bool:
        """Check if ts-node is available for TypeScript debugging."""
        if self._ts_node_available is not None:
            return self._ts_node_available

        try:
            # Use async subprocess to avoid blocking
            proc = await asyncio.create_subprocess_exec(
                "npx",
                "ts-node",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(
                proc.communicate(),
                timeout=PROCESS_COMMUNICATE_TIMEOUT_S,
            )
            self._ts_node_available = proc.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            self._ts_node_available = False

        return self._ts_node_available

    async def _detect_node_version(self) -> str | None:
        """Detect installed Node.js version."""
        try:
            node_exe = self._node_path or self._get_node_executable()
            # Use async subprocess to avoid blocking
            proc = await asyncio.create_subprocess_exec(
                node_exe,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=PROCESS_COMMUNICATE_TIMEOUT_S,
            )
            if proc.returncode == 0:
                return stdout.decode().strip() if stdout else ""
        except (subprocess.SubprocessError, FileNotFoundError, AidbError):
            pass
        return None

    def _get_package_json_info(self, target: str) -> dict | None:
        """Get package.json information if available."""
        target_path = normalize_path(target, strict=True, return_path=True)
        for parent in [target_path.parent] + list(target_path.parents):
            package_json = parent / "package.json"
            if package_json.exists():
                try:
                    with package_json.open() as f:
                        data = json.load(f)
                        return {
                            "name": data.get("name", ""),
                            "version": data.get("version", ""),
                            "type": data.get("type", "commonjs"),
                            "scripts": data.get("scripts", {}),
                        }
                except (OSError, json.JSONDecodeError):
                    pass
                break
        return None

    def _get_tsconfig_info(self, target: str) -> dict | None:
        """Get tsconfig.json information if available."""
        target_path = normalize_path(target, strict=True, return_path=True)
        for parent in [target_path.parent] + list(target_path.parents):
            tsconfig = parent / "tsconfig.json"
            if tsconfig.exists():
                try:
                    with tsconfig.open() as f:
                        data = json.load(f)
                        compiler_options = data.get("compilerOptions", {})
                        return {
                            "target": compiler_options.get("target", "ES2015"),
                            "module": compiler_options.get("module", "commonjs"),
                            "sourceMap": compiler_options.get("sourceMap", True),
                        }
                except (OSError, json.JSONDecodeError):
                    pass
                break
        return None

    def _find_package_json_dir(self, target_path: Path) -> Path | None:
        """Find the directory containing package.json.

        Parameters
        ----------
        target_path : Path
            The target file path to start searching from

        Returns
        -------
        Optional[Path]
            The directory containing package.json, or None if not found
        """
        for parent in [target_path.parent] + list(target_path.parents):
            package_json = parent / "package.json"
            if package_json.exists():
                return parent
        return None
