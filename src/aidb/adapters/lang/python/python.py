"""Python debug adapter - refactored to use component architecture."""

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

from aidb.common.constants import DEFAULT_ADAPTER_HOST
from aidb_common.config import config as env_config
from aidb_common.constants import Language
from aidb_common.path import get_aidb_adapters_dir

from ...base import DebugAdapter
from ...base.config_mapper import ConfigurationMapper
from ...base.hooks import HookContext, LifecycleHook
from ...base.target_resolver import TargetResolver
from .config import PythonAdapterConfig
from .target_resolver import PythonTargetResolver
from .trace import PythonTraceManager

if TYPE_CHECKING:
    from aidb.adapters.base.source_path_resolver import SourcePathResolver
    from aidb.interfaces import ISession


class PythonAdapter(DebugAdapter):
    """Python debug adapter using component architecture.

    This refactored adapter delegates responsibilities to specialized components and
    uses lifecycle hooks for customization.
    """

    # ----------------------
    # Public API / Lifecycle
    # ----------------------

    def __init__(
        self,
        session: "ISession",
        ctx=None,
        adapter_host=DEFAULT_ADAPTER_HOST,
        adapter_port=None,
        target_host=DEFAULT_ADAPTER_HOST,
        target_port=None,
        config: PythonAdapterConfig | None = None,
        module: bool = False,
        python_path: str | None = None,
        env_file: str | None = None,
        **kwargs,
    ):
        """Initialize Python debug adapter.

        Parameters
        ----------
        session : Session
            The session that owns this adapter
        ctx : AidbContext, optional
            Application context
        adapter_host : str, optional
            Host where debugpy server binds, by default "localhost"
        adapter_port : int, optional
            Port where debugpy server listens
        target_host : str, optional
            Host where the target process runs, by default "localhost"
        target_port : int, optional
            Port for target process communication
        config : PythonAdapterConfig, optional
            Python adapter configuration
        module : bool, optional
            If True, treat target as a Python module name (e.g., "pytest"). If
            False, treat target as a file path. By default False
        python_path : str, optional
            Path to custom Python interpreter. If None, uses sys.executable
        env_file : str, optional
            Path to .env file to load environment variables from
        ``**kwargs`` : Any
            Additional parameters including framework flags (justMyCode, django,
            flask, jinja, pyramid, gevent, etc.)
        """
        # Use provided config or create default
        if config is None:
            config = PythonAdapterConfig()

        # Update config with any framework-specific flags from kwargs
        # This allows launch.json settings to override default config
        python_config_mappings = {
            "justMyCode": "justMyCode",
            "subProcess": "subProcess",
            "showReturnValue": "showReturnValue",
            "redirectOutput": "redirectOutput",
            "django": "django",
            "flask": "flask",
            "jinja": "jinja",
            "pyramid": "pyramid",
            "gevent": "gevent",
        }
        ConfigurationMapper.apply_kwargs(config, kwargs, python_config_mappings)

        super().__init__(
            session=session,
            ctx=ctx,
            adapter_host=adapter_host,
            adapter_port=adapter_port,
            target_host=target_host,
            target_port=target_port,
            config=config,
        )

        self.module = module
        self.python_path = python_path
        self.env_file = env_file

        # Override module flag if passed via kwargs from launch config
        if "module" in kwargs:
            self.module = kwargs["module"]
            self.ctx.debug(f"Set module flag to {self.module} from launch config")
        self._debugpy_log_manager: PythonTraceManager | None = None
        self._target_cwd: str | None = None

        # Register Python-specific hooks
        self._register_python_hooks()

    def _create_target_resolver(self) -> TargetResolver:
        """Create Python-specific target resolver.

        Returns
        -------
        TargetResolver
            PythonTargetResolver instance for module vs file detection
        """
        return PythonTargetResolver(adapter=self, ctx=self.ctx)

    def _create_source_path_resolver(self) -> "SourcePathResolver":
        """Create Python-specific source path resolver.

        Returns
        -------
        SourcePathResolver
            PythonSourcePathResolver instance for site-packages resolution
        """
        from .source_path_resolver import PythonSourcePathResolver

        return PythonSourcePathResolver(adapter=self, ctx=self.ctx)

    def _validate_target_hook(self, context: HookContext) -> None:
        """Override target validation to handle Python modules.

        For Python, targets can be either:
        - File paths (e.g., 'script.py')
        - Module names with -m flag (e.g., 'pytest', 'unittest')
        """
        target = context.data.get("target")
        if not target:
            return

        # If module mode, skip file validation - module names are validated at runtime
        if self.module:
            self.ctx.debug(f"Module mode: skipping file validation for '{target}'")
            return

        # For file mode, use base validation
        super()._validate_target_hook(context)

    async def attach(self, pid: int, session_id: str) -> None:
        """Attach to an existing Python process using debugpy.

        This method overrides the base attach to add debugpy-specific behavior.

        Parameters
        ----------
        pid : int
            Process ID to attach to
        session_id : str
            Session identifier
        """
        # Call parent attach to store PID and execute attach hooks
        await super().attach(pid, session_id)

        # Execute Python-specific attach logic via hook
        await self.execute_hook(
            LifecycleHook.POST_ATTACH,
            {"pid": pid, "session_id": session_id},
        )

        # If debugpy connection is needed (not handled by DAP client)
        if self.port:
            try:
                debugpy = self._import_debugpy_from_adapter()
                if debugpy and hasattr(debugpy, "connect"):
                    # debugpy.connect() is a blocking network operation, run in thread
                    await asyncio.to_thread(debugpy.connect, ("localhost", self.port))
                    self.ctx.debug(
                        f"Connected to debugpy on port {self.port} for PID {pid}",
                    )
            except Exception as e:
                self.ctx.warning(f"Could not connect debugpy to port {self.port}: {e}")

    # ----------------------
    # Hook Registration
    # ----------------------

    def _register_python_hooks(self) -> None:
        """Register Python-specific lifecycle hooks."""
        # Register pre-launch hook to set up trace configuration
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._setup_trace_before_launch,
            priority=90,  # Very high priority to run first
        )

        # Register pre-launch hook to clean up orphaned debugpy processes
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._cleanup_orphan_debugpy_pre_launch,
            priority=85,  # High priority - clean orphans before launch
        )

        # Register a post-launch hook to wait for debugpy initialization
        self.register_hook(
            LifecycleHook.POST_LAUNCH,
            self._wait_for_debugpy,
            priority=20,  # Low priority to run after other hooks
        )

        # Register pre-launch hook to extract env/cwd context
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._extract_launch_context,
            priority=80,  # High priority to extract context early
        )

        # Register post-stop hook to manage debugpy logs
        self.register_hook(
            LifecycleHook.POST_STOP,
            self._consolidate_debugpy_logs,
            priority=10,  # Low priority to run after cleanup
        )

        # Register post-stop hook to proactively clean up orphaned debugpy
        # processes. This prevents teardown glitches (e.g., event loop
        # finalizer issues) from leaving stray debugpy processes that stall
        # subsequent launches.
        self.register_hook(
            LifecycleHook.POST_STOP,
            self._cleanup_orphan_debugpy,
            priority=15,  # Run before log consolidation
        )

    # ----------------------
    # Pre-Launch Hooks
    # ----------------------

    def _setup_trace_before_launch(self, _context: HookContext) -> None:
        """Pre-launch hook to set up trace configuration.

        This ensures the PythonTraceManager is initialized before the debug
        session starts, allowing proper log consolidation on stop.

        Parameters
        ----------
        _context : HookContext
            Hook context containing launch data (unused)
        """
        self.ctx.debug("Pre-launch hook: Setting up trace configuration")
        self._setup_trace_configuration()

    def _extract_launch_context(self, context: HookContext) -> None:
        """Pre-launch hook to extract environment context.

        Target resolution (module vs file detection) now happens in the base
        adapter via TargetResolver. This hook only extracts env and cwd for
        later use in launch configuration.

        Parameters
        ----------
        context : HookContext
            Hook context containing launch data
        """
        # Extract env and cwd from context.data for use in launch config
        self._target_env = context.data.get("env", {})
        self._target_cwd = context.data.get("cwd")

    # ------------------------------
    # Post-Launch / Post-Stop Hooks
    # ------------------------------

    async def _wait_for_debugpy(self, _context: HookContext) -> None:
        """Post-launch hook for debugpy initialization.

        No-op: The DAP 'initialized' event is the authoritative readiness signal.
        The session's WAIT_FOR_INITIALIZED operation in the init sequence handles
        waiting for debugpy to be ready. This matches the JavaScript adapter pattern.

        Parameters
        ----------
        _context : HookContext
            Hook context containing launch result (unused)
        """
        self.ctx.debug("debugpy initialization: relying on DAP initialized event")

    def _consolidate_debugpy_logs(self, _context: HookContext) -> None:
        """Post-stop hook to check and manage debugpy log files.

        This method uses PythonTraceManager to consolidate debugpy's per-PID log
        files into properly rotated logs matching the standard pattern.

        Parameters
        ----------
        _context : HookContext
            Hook context (unused) containing stop information
        """
        if self._debugpy_log_manager:
            self._debugpy_log_manager.consolidate_session_logs()
            self.ctx.debug("Consolidated and rotated debugpy log files")

    # ----------------------
    # Command Builders
    # ----------------------

    async def _build_launch_command(
        self,
        target: str,
        adapter_host: str,
        adapter_port: int,
        args: list[str] | None = None,
    ) -> list[str]:
        """Build the debugpy launch command.

        Supports both script paths and Python modules. The module vs script
        decision is made by the session's module flag.

        Parameters
        ----------
        target : str
            Either a module name (e.g., "pytest") or a file path
        adapter_host : str
            Host for the debug adapter
        adapter_port : int
            Port for the debug adapter
        args : List[str], optional
            Additional command-line arguments

        Returns
        -------
        List[str]
            The complete command to launch debugpy
        """
        # Use custom Python interpreter if provided, otherwise use
        # sys.executable
        python_executable = self.python_path or sys.executable

        if self.python_path:
            if not Path(self.python_path).is_file():
                self.ctx.warning(
                    f"Custom Python path '{self.python_path}' does not exist, "
                    f"falling back to {sys.executable}",
                )
                python_executable = sys.executable
            else:
                self.ctx.debug(f"Using custom Python interpreter: {self.python_path}")

        listen_address = f"{adapter_host}:{adapter_port}"
        base = [
            python_executable,
            "-m",
            "debugpy",
            "--listen",
            listen_address,
            "--wait-for-client",
        ]

        # Normalize arguments list
        argv: list[str] = list(args or [])
        self.ctx.debug(f"Building launch command with args: {argv}")

        if self.module:
            return base + ["-m", target, *argv]
        return base + [target, *argv]

    # ----------------------
    # Environment & Process
    # ----------------------

    def _get_adapter_dir(self) -> Path | None:
        """Get the Python adapter directory, checking env var first.

        Returns
        -------
        Path | None
            Path to the adapter directory if it exists, None otherwise
        """
        # First check environment variable (used in CI)
        env_path = env_config.get_binary_override(Language.PYTHON.value)
        if env_path and env_path.exists():
            return env_path

        # Fall back to default location
        adapter_dir = get_aidb_adapters_dir() / Language.PYTHON.value
        if adapter_dir.exists():
            return adapter_dir
        return None

    def _import_debugpy_from_adapter(self) -> ModuleType | None:
        """Dynamically import debugpy from the adapter directory.

        This loads debugpy directly from the adapter directory rather than
        relying on Python's import system, which ensures we always use our
        bundled adapter version regardless of what's installed in the environment.

        Returns
        -------
        ModuleType | None
            The debugpy module if found, None otherwise
        """
        adapter_dir = self._get_adapter_dir()
        if not adapter_dir:
            self.ctx.warning("Python adapter directory not found")
            return None

        debugpy_init = adapter_dir / "debugpy" / "__init__.py"

        if not debugpy_init.exists():
            self.ctx.warning(f"debugpy not found in adapter directory: {adapter_dir}")
            return None

        try:
            spec = importlib.util.spec_from_file_location(
                "debugpy",
                debugpy_init,
                submodule_search_locations=[str(adapter_dir / "debugpy")],
            )
            if spec is None or spec.loader is None:
                self.ctx.warning("Failed to create module spec for debugpy")
                return None

            debugpy = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(debugpy)
            self.ctx.debug(f"Loaded debugpy from adapter directory: {adapter_dir}")
            return debugpy
        except Exception as e:
            self.ctx.warning(f"Failed to load debugpy from adapter directory: {e}")
            return None

    def _get_adapter_pythonpath(self) -> str | None:
        """Get the adapter directory path for PYTHONPATH injection.

        Returns
        -------
        str | None
            Path to adapter directory if it exists, None otherwise
        """
        adapter_dir = self._get_adapter_dir()
        if adapter_dir:
            self.ctx.debug(f"Using adapter path for PYTHONPATH: {adapter_dir}")
            return str(adapter_dir)
        return None

    def _load_env_file(self, env_file_path: str) -> dict[str, str]:
        """Load environment variables from a .env file.

        Parameters
        ----------
        env_file_path : str
            Path to the .env file

        Returns
        -------
        Dict[str, str]
            Dictionary of environment variables loaded from the file
        """
        env_vars: dict[str, str] = {}

        if not Path(env_file_path).is_file():
            self.ctx.warning(f"Environment file '{env_file_path}' not found")
            return env_vars

        try:
            with Path(env_file_path).open() as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE format
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Remove quotes if present
                        if (
                            value.startswith('"')
                            and value.endswith('"')
                            or value.startswith("'")
                            and value.endswith("'")
                        ):
                            value = value[1:-1]

                        env_vars[key] = value

            self.ctx.debug(
                f"Loaded {len(env_vars)} environment variables from {env_file_path}",
            )
        except Exception as e:
            self.ctx.warning(f"Error loading environment file '{env_file_path}': {e}")

        return env_vars

    def _load_base_environment(self) -> dict[str, str]:
        """Load base environment including .env file if specified.

        Returns
        -------
        Dict[str, str]
            Base environment variables
        """
        env = super()._load_base_environment()

        # Load environment variables from .env file if specified
        if self.env_file:
            env_vars = self._load_env_file(self.env_file)
            env.update(env_vars)

        return env

    def _add_adapter_specific_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Add Python-specific environment variables.

        Parameters
        ----------
        env : Dict[str, str]
            Current environment variables

        Returns
        -------
        Dict[str, str]
            Updated environment with Python-specific variables
        """
        # Prepend adapter path to PYTHONPATH so subprocess finds our debugpy first
        adapter_path = self._get_adapter_pythonpath()
        if adapter_path:
            existing_pythonpath = env.get("PYTHONPATH", "")
            if existing_pythonpath:
                env["PYTHONPATH"] = f"{adapter_path}:{existing_pythonpath}"
            else:
                env["PYTHONPATH"] = adapter_path
            self.ctx.debug(f"Prepended adapter path to PYTHONPATH: {adapter_path}")

        # Use trace manager's directory if available, otherwise fallback
        if hasattr(self, "_debugpy_log_dir"):
            env["DEBUGPY_LOG_DIR"] = self._debugpy_log_dir
        else:
            # Check if trace manager is available
            if self._trace_manager:
                # Generate a log directory path
                trace_path = self._trace_manager.get_trace_log_path(
                    self.config.adapter_id,
                )
                env["DEBUGPY_LOG_DIR"] = str(Path(trace_path).parent)
                self.ctx.debug(
                    f"Using trace manager directory for "
                    f"debugpy logs: {env['DEBUGPY_LOG_DIR']}",
                )
            else:
                # Fallback to system temp directory with debugpy-logs subdirectory
                temp_dir = Path(tempfile.gettempdir()) / "debugpy-logs"
                env["DEBUGPY_LOG_DIR"] = str(temp_dir)
                self.ctx.debug("Using default debugpy log directory: %s", temp_dir)

        # Don't write bytecode files during debugging
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        # Set PYDEVD environment variable to disable file validation checks
        env["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"

        return env

    def _get_process_name_pattern(self) -> str:
        """Get the process name pattern for debugpy cleanup operations.

        Returns
        -------
        str
            Pattern to match in process names/cmdlines for debugpy processes
        """
        return "debugpy"

    async def _cleanup_orphan_debugpy_pre_launch(
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

            min_age = reader.read_float("AIDB_PYTHON_ORPHAN_MIN_AGE", 5.0) or 5.0
            pattern = self._get_process_name_pattern()
            self.ctx.debug(
                f"[PRE-LAUNCH] Cleaning orphaned debugpy "
                f"(min_age={min_age}s, budget={ORPHAN_SCAN_PRE_LAUNCH_MS:.0f}ms)",
            )

            stats = self._process_manager.cleanup_orphaned_processes(
                pattern,
                min_age_seconds=min_age,
                max_scan_ms=ORPHAN_SCAN_PRE_LAUNCH_MS,
            )

            if stats["killed"] > 0:
                self.ctx.info(
                    f"[PRE-LAUNCH] Killed {stats['killed']} orphaned debugpy processes",
                )

        except Exception as e:
            self.ctx.debug(f"Pre-launch orphan cleanup skipped/failed: {e}")

    async def _cleanup_orphan_debugpy(self, _context: HookContext) -> None:
        """Post-stop hook: clean up orphaned debugpy processes.

        Uses a small age threshold to aggressively reap stray debugpy
        instances from previous sessions that could block the next launch.
        """
        try:
            from aidb.common.constants import ORPHAN_SCAN_POST_STOP_MS
            from aidb_common.env import reader

            if reader.read_bool("AIDB_SKIP_POST_STOP_ORPHAN_CLEANUP", False):
                self.ctx.debug("[POST-STOP] Orphan cleanup skipped via env var")
                return

            min_age = reader.read_float("AIDB_PYTHON_ORPHAN_MIN_AGE", 5.0) or 5.0
            pattern = self._get_process_name_pattern()
            self.ctx.debug(
                f"[POST-STOP] Cleaning orphaned debugpy (min_age={min_age}s)",
            )

            stats = self._process_manager.cleanup_orphaned_processes(
                pattern,
                min_age_seconds=min_age,
                max_scan_ms=ORPHAN_SCAN_POST_STOP_MS,
            )

            if stats["killed"] > 0:
                self.ctx.debug(
                    f"[POST-STOP] Killed {stats['killed']} orphaned debugpy processes",
                )

        except Exception as e:
            self.ctx.debug(f"Post-stop orphan cleanup skipped/failed: {e}")

    # ------------------------------
    # Launch Configuration & Tracing
    # ------------------------------

    @property
    def prefers_transport_only_disconnect(self) -> bool:
        """Prefer transport-only disconnect to avoid 2s DAP wait."""
        return True

    def _add_core_debugging_flags(self, config: dict[str, Any]) -> None:
        """Add core debugging behavior flags to configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Configuration dictionary to update
        """
        if not isinstance(self.config, PythonAdapterConfig):
            return

        config["justMyCode"] = self.config.justMyCode
        config["subProcess"] = self.config.subProcess
        config["showReturnValue"] = self.config.showReturnValue
        config["redirectOutput"] = self.config.redirectOutput

    def _add_framework_flags(self, config: dict[str, Any]) -> None:
        """Add framework-specific flags to configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Configuration dictionary to update
        """
        if not isinstance(self.config, PythonAdapterConfig):
            return

        frameworks = {
            "django": self.config.django,
            "flask": self.config.flask,
            "jinja": self.config.jinja,
            "pyramid": self.config.pyramid,
            "gevent": self.config.gevent,
        }

        for framework_name, enabled in frameworks.items():
            if enabled:
                config[framework_name] = True

    def _add_adapter_settings(self, config: dict[str, Any]) -> None:
        """Add adapter-level settings to configuration.

        Parameters
        ----------
        config : dict[str, Any]
            Configuration dictionary to update
        """
        if self.module:
            config["module"] = True
        if self.python_path:
            config["python"] = self.python_path
        if self.env_file:
            config["envFile"] = self.env_file

        # Add env and cwd from launch parameters
        if self._target_env:
            config["env"] = self._target_env
        if self._target_cwd:
            config["cwd"] = self._target_cwd

    def get_launch_configuration(self) -> dict[str, Any]:
        """Get the launch configuration for debugpy.

        This method is called by the initialization operations to get the proper
        launch configuration that debugpy expects. Following the same pattern as
        the JavaScript adapter.

        Returns
        -------
        Dict[str, Any]
            Launch configuration compatible with debugpy
        """
        self.ctx.debug("Python adapter get_launch_configuration called")
        config: dict[str, Any] = {}

        # Initialize trace configuration if tracing is enabled
        # This ensures _debugpy_log_manager is set up for POST_STOP hook
        self._setup_trace_configuration()
        self.ctx.debug(
            f"After setup, _debugpy_log_manager is: {self._debugpy_log_manager}",
        )

        # Add configuration sections
        self._add_core_debugging_flags(config)
        self._add_framework_flags(config)
        self._add_adapter_settings(config)

        self.ctx.debug(
            f"Generated debugpy launch configuration with {len(config)} fields",
        )

        return config

    def _setup_trace_configuration(self) -> None:
        """Set up trace configuration for debugpy.

        This method initializes the PythonTraceManager which handles log rotation and
        consolidation. It's called from get_launch_configuration to ensure it's set up
        before the debug session starts.
        """
        self.ctx.debug("_setup_trace_configuration called")
        if self._debugpy_log_manager is not None:
            self.ctx.debug("_debugpy_log_manager already initialized")
            # Already initialized
            return

        if self._trace_manager:
            trace_path = self._trace_manager.get_trace_log_path(self.config.adapter_id)
            trace_dir = str(Path(trace_path).parent)
            self.ctx.debug(f"Using trace manager directory: {trace_dir}")
        else:
            # Use a default directory when trace manager is not available (under log/)
            trace_dir = self.ctx.get_storage_path(
                "log/adapter_traces",
                Language.PYTHON.value,
            )
            Path(trace_dir).mkdir(parents=True, exist_ok=True)
            self.ctx.debug(f"Using default trace directory: {trace_dir}")

        self._debugpy_log_manager = PythonTraceManager(
            ctx=self.ctx,
            trace_dir=trace_dir,
        )

        cleaned = self._debugpy_log_manager.cleanup_old_pid_logs()
        if cleaned > 0:
            self.ctx.debug(f"Cleaned up {cleaned} old debugpy PID log files")

        self._debugpy_log_manager.rotate_logs_on_start()

        # Store for use in _prepare_environment
        self._debugpy_log_dir = trace_dir
        self.ctx.debug(f"Configured debugpy log directory: {trace_dir}")

    def get_trace_config(self) -> dict[str, Any] | None:
        """Get trace configuration for debugpy.

        debugpy uses environment variables for logging configuration rather than
        DAP protocol trace settings. This method sets up the logging directory
        that will be used in _prepare_environment().

        Returns
        -------
        Optional[Dict[str, Any]]
            Trace configuration dictionary (for consistency with base class)
        """
        # Ensure trace configuration is set up
        self._setup_trace_configuration()

        if self._trace_manager:
            trace_path = self._trace_manager.get_trace_log_path(self.config.adapter_id)
            # debugpy doesn't use DAP trace config directly, but we return it for
            # consistency.
            return {"trace": True, "logFile": trace_path}

        return None
