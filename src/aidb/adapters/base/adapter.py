"""Base functionality for debug adapters."""

import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.adapters.utils.binary_locator import AdapterBinaryLocator
from aidb.adapters.utils.output_capture import AdapterOutputCapture
from aidb.adapters.utils.trace_log import AdapterTraceLogManager
from aidb.common.constants import DEFAULT_ADAPTER_HOST
from aidb.common.context import AidbContext
from aidb.common.errors import AdapterCapabilityNotSupportedError
from aidb.dap.protocol.types import Capabilities
from aidb.models import StartRequestType
from aidb.patterns import Obj
from aidb_common.config import config as env_config
from aidb_common.path import normalize_path

from .components.launch_orchestrator import LaunchOrchestrator
from .components.port_manager import PortManager
from .components.process_manager import ProcessManager
from .config import AdapterConfig
from .hooks import AdapterHooksMixin, HookContext, LifecycleHook
from .launch import BaseLaunchConfig
from .source_path_resolver import SourcePathResolver
from .target_resolver import TargetResolver
from .vslaunch import resolve_launch_configuration

if TYPE_CHECKING:
    from aidb.interfaces import ISession
    from aidb.interfaces.adapter import (
        ILaunchOrchestrator,
        IPortManager,
        IProcessManager,
    )


@dataclass
class CompilationStatus:
    """Result of checking if a target is compiled and ready to debug.

    Attributes
    ----------
    is_compiled : bool
        Whether the target is already compiled
    executable_path : str
        Path to the executable (existing or to-be-created)
    compile_command : Optional[str]
        Suggested compilation command if not compiled
    error_message : Optional[str]
        Error message if target is not ready
    """

    is_compiled: bool
    executable_path: str
    compile_command: str | None = None
    error_message: str | None = None


class DebugAdapter(ABC, Obj, AdapterHooksMixin):
    """AIDB debug adapter base class.

    The adapter delegates responsibilities to components:
        - ProcessManager: Process lifecycle management
        - PortManager: Port acquisition and management
        - LaunchOrchestrator: Launch sequence orchestration
        - AdapterHooksMixin: Lifecycle hooks for extension
        - Auxiliary components: Lazy-initialized via properties

    Attributes
    ----------
    adapter_host : str
        Host where this adapter server binds
    adapter_port : int
        Port where this adapter server listens
    config : AdapterConfig
        Adapter configuration
    capabilities : Capabilities
        Adapter capabilities
    target_host : str
        Host where the target process being debugged runs
    target_port : int, optional
        Port for target process communication if needed
    """

    config: AdapterConfig
    capabilities: Capabilities  # Set during initialization
    post_launch_delay = 0.0

    # Component type annotations
    _process_manager: "IProcessManager"
    _port_manager: "IPortManager"
    _launch_orchestrator: "ILaunchOrchestrator"
    _target_resolver: TargetResolver
    _source_path_resolver: SourcePathResolver

    # ----------------------
    # Public API / Lifecycle
    # ----------------------

    def __init__(
        self,
        session: "ISession",
        ctx: AidbContext | None = None,
        adapter_host: str = DEFAULT_ADAPTER_HOST,
        adapter_port: int | None = None,
        target_host: str = DEFAULT_ADAPTER_HOST,
        target_port: int | None = None,
        config: AdapterConfig | None = None,
        **_kwargs,
    ):
        """Initialize debug adapter with component architecture.

        Parameters
        ----------
        session : ISession
            The session that owns this adapter
        ctx : AidbContext, optional
            Application context, by default `None`
        adapter_host : str, optional
            Host where this adapter server binds, by default `"localhost"`
        adapter_port : int, optional
            Port where this adapter server listens, by default `None`
        target_host : str, optional
            Host where the target process being debugged runs, by default
            `"localhost"`
        target_port : int, optional
            Port for target process communication if needed, by default `None`
        config : AdapterConfig, optional
            Adapter configuration, by default `AdapterConfig()`
        **_kwargs : Any
            Additional adapter-specific parameters
        """
        super().__init__(ctx)

        # Set attributes before initializing hooks
        self.session = session
        self.config = config if config is not None else AdapterConfig()
        self.adapter_host = adapter_host
        self.adapter_port = adapter_port
        self.target_host = target_host
        self.target_port = target_port

        # Initialize hooks after attributes are set
        AdapterHooksMixin.__init__(self)

        # Initialize core components
        self._process_manager = ProcessManager(
            ctx=self.ctx,
            adapter_host=adapter_host,
            config=self.config,
        )

        self._port_manager = PortManager(
            resource_manager=session.resource,
            ctx=self.ctx,
        )

        self._launch_orchestrator = LaunchOrchestrator(
            adapter=self,
            process_manager=self._process_manager,
            port_manager=self._port_manager,
            ctx=self.ctx,
        )

        # Target resolver - language-specific target normalization
        self._target_resolver = self._create_target_resolver()

        # Source path resolver - language-specific source path resolution
        self._source_path_resolver = self._create_source_path_resolver()

        self._trace_manager: AdapterTraceLogManager | None = None
        self._output_capture: AdapterOutputCapture | None = None
        self._adapter_locator: AdapterBinaryLocator | None = None

        # Target env vars provided by the user
        self._target_env: dict[str, str] = {}

        # Register default lifecycle hooks
        self._register_default_hooks()

        # Initialize trace manager if enabled via environment variable
        if env_config.is_adapter_trace_enabled():
            self._init_trace_manager()

    # ----------------------
    # Initialization Helpers
    # ----------------------

    def _register_default_hooks(self) -> None:
        """Register default lifecycle hooks."""
        # Pre-launch validation hook
        self.register_hook(
            LifecycleHook.PRE_LAUNCH,
            self._validate_target_hook,
            priority=10,  # High priority
        )

        # Post-launch delay hook
        if self.post_launch_delay > 0:
            self.register_hook(
                LifecycleHook.POST_LAUNCH,
                self._post_launch_delay_hook,
                priority=80,  # Low priority
            )

    async def _post_launch_delay_hook(self, _context: HookContext) -> None:
        """Add a hook to delay after launching the adapter."""
        await asyncio.sleep(self.post_launch_delay)

    def _init_trace_manager(self) -> None:
        """Initialize trace manager if tracing is enabled."""
        self.ctx.debug(f"Adapter {self.__class__.__name__} tracing enabled")
        self._trace_manager = AdapterTraceLogManager(ctx=self.ctx)
        self.ctx.debug(
            f"Trace manager initialized for adapter {self.__class__.__name__}",
        )

    # ----------------------
    # Component Accessors
    # ----------------------

    @property
    def trace_manager(self) -> AdapterTraceLogManager:
        """Get or create the trace manager.

        Returns
        -------
        AdapterTraceLogManager
            The trace manager instance
        """
        if self._trace_manager is None:
            self._trace_manager = AdapterTraceLogManager(ctx=self.ctx)
        return self._trace_manager

    @property
    def output_capture(self) -> AdapterOutputCapture:
        """Get or create the output capture component.

        Returns
        -------
        AdapterOutputCapture
            The output capture instance
        """
        if self._output_capture is None:
            self._output_capture = AdapterOutputCapture(
                ctx=self.ctx,
                log_initial_output=True,
            )
        return self._output_capture

    @property
    def adapter_locator(self) -> AdapterBinaryLocator:
        """Get or create the adapter binary locator.

        Returns
        -------
        AdapterBinaryLocator
            The adapter binary locator instance
        """
        if self._adapter_locator is None:
            self._adapter_locator = AdapterBinaryLocator(ctx=self.ctx)
        return self._adapter_locator

    @property
    def source_path_resolver(self) -> SourcePathResolver:
        """Get the source path resolver.

        Returns
        -------
        SourcePathResolver
            Language-specific source path resolver instance
        """
        return self._source_path_resolver

    @property
    def binary_path(self) -> Path:
        """Get the path to the adapter binary.

        This is a convenience property that uses the adapter_locator
        to find the binary for this adapter's language.

        Returns
        -------
        Path
            Path to the adapter binary

        Raises
        ------
        AdapterNotFoundError
            If the adapter binary cannot be found
        """
        binary_path = self.adapter_locator.locate(self.config.language)

        # Perform version validation when adapter is accessed
        self._validate_adapter_version(binary_path)

        return binary_path

    # ----------------------
    # Public API Methods
    # ----------------------

    def ensure_capability(self, capability: str) -> None:
        """Ensure the adapter supports the capability or raise an error.

        Parameters
        ----------
        capability : str
            The capability to check for

        Raises
        ------
        AdapterCapabilityNotSupportedError
            If the adapter does not support the capability
        """
        if not self.session.has_capability(capability):
            adapter_id = self.config.adapter_id if self.config else "unknown"
            msg = f"Adapter {adapter_id} does not have capability {capability}"
            raise AdapterCapabilityNotSupportedError(msg)

    def is_line_executable(self, line: str) -> bool:
        """Check if a line is potentially executable.

        Base implementation checks against non_executable_patterns.
        Subclasses can override for more complex logic.

        Parameters
        ----------
        line : str
            The line of code to check

        Returns
        -------
        bool
            True if the line appears to be executable
        """
        stripped = line.strip()

        # Empty lines are never executable
        if not stripped:
            return False

        # Check language-specific patterns from config
        for pattern in self.config.non_executable_patterns:
            if stripped.startswith(pattern):
                return False

        return True

    def validate_syntax(self, target: str) -> tuple[bool, str | None]:
        """Validate syntax of the target file.

        Parameters
        ----------
        target : str
            Path to the target file to validate

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct
        """
        from .syntax_validator import SyntaxValidator

        # Get a validator for this language
        validator = SyntaxValidator.for_language(self.config.language)

        # If no validator available for this language, skip validation
        if validator is None:
            return True, None

        # Perform validation
        return validator.validate(target)

    def check_compilation_status(self, target: str) -> CompilationStatus:
        """Check if target is compiled and ready to debug.

        Default implementation checks for common source file extensions and
        provides compilation suggestions. Language adapters should override for
        more specific behavior.

        Parameters
        ----------
        target : str
            Path to target file

        Returns
        -------
        CompilationStatus
            Status indicating if target is ready to debug
        """
        from .compilation_patterns import get_compilation_info

        path = Path(target)
        compilation_info = get_compilation_info(path)

        if compilation_info:
            return CompilationStatus(
                is_compiled=False,
                executable_path=str(compilation_info["output_path"]),
                compile_command=compilation_info["compile_command"],
                error_message=compilation_info["error_message"],
            )

        # For Python and other interpreted languages, or already compiled files
        return CompilationStatus(is_compiled=True, executable_path=target)

    async def locate_adapter_binary(self) -> Path:
        """Locate the debug adapter binary.

        Returns
        -------
        Path
            Path to the debug adapter binary

        Raises
        ------
        AdapterNotFoundError
            If the adapter binary cannot be found
        """
        return self.binary_path

    async def launch(
        self,
        target: str,
        port: int | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        launch_config_name: str | None = None,
        workspace_root: str | None = None,
    ) -> tuple["asyncio.subprocess.Process", int]:
        """Launch the debug adapter and wait for it to be ready.

        Parameters
        ----------
        target : str
            Path to the target file to debug
        port : int, optional
            Specific port to use, if `None` will find available port
        args : List[str], optional
            Additional arguments for the target
        env : dict[str, str], optional
            Environment variables for the target process
        cwd : str, optional
            Working directory for the target process
        launch_config_name : str, optional
            Name of VS Code launch configuration to use
        workspace_root : str, optional
            Root directory for resolving launch.json

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on
        """
        # Try to resolve a launch configuration
        if launch_config_name or workspace_root:
            launch_config = resolve_launch_configuration(
                target=target,
                config_name=launch_config_name,
                workspace_root=workspace_root,
                language=self.config.language,
            )
            if launch_config:
                self.ctx.debug(f"Using launch configuration: {launch_config.name}")
                return await self.launch_with_config(
                    launch_config,
                    port,
                    workspace_root,
                )

        # Resolve target FIRST, before any hooks or DAP operations
        # This handles module detection, -m syntax, etc.
        resolved = self._target_resolver.resolve(target)
        target = resolved.target

        # Proceed with regular launch
        context = await self.execute_hook(
            LifecycleHook.PRE_LAUNCH,
            data={
                "target": target,
                "port": port,
                "args": args,
                "env": env or {},
                "cwd": cwd,
                "resolved_target": resolved,  # Pass resolution info to hooks
            },
        )

        if context.cancelled:
            # Use the result message if available, otherwise generic message
            error_msg = context.result if context.result else "Launch cancelled by hook"
            raise RuntimeError(error_msg)

        # Hooks may further modify target
        target = context.data.get("target", target)

        proc, port = await self._launch_orchestrator.launch(target, port, args)

        context = await self.execute_hook(
            LifecycleHook.POST_LAUNCH,
            data={"process": proc, "port": port},
        )

        return proc, port

    async def launch_with_config(
        self,
        launch_config: BaseLaunchConfig,
        port: int | None = None,
        workspace_root: str | None = None,
    ) -> tuple["asyncio.subprocess.Process", int]:
        """Launch the debug adapter using a VS Code launch configuration.

        Parameters
        ----------
        launch_config : BaseLaunchConfig
            VS Code launch configuration to use
        port : int, optional
            Specific port to use, if `None` will use config port or find
            available
        workspace_root : Optional[str]
            Root directory for resolving relative paths

        Returns
        -------
        Tuple[asyncio.subprocess.Process, int]
            The launched process and the port it's listening on
        """
        return await self._launch_orchestrator.launch_with_config(
            launch_config,
            port,
            workspace_root,
        )

    async def attach(self, pid: int, session_id: str) -> None:
        """Attach to an existing process.

        Parameters
        ----------
        pid : int
            Process ID to attach to
        session_id : str
            Session identifier
        """
        context = await self.execute_hook(
            LifecycleHook.PRE_ATTACH,
            data={"pid": pid, "session_id": session_id},
        )

        if not context.cancelled:
            self._process_manager.attach_pid(pid)
            self.ctx.debug(f"Attached to process {pid} for session {session_id}")

        await self.execute_hook(LifecycleHook.POST_ATTACH, data={"pid": pid})

    async def stop(self) -> None:
        """Stop the debug adapter and clean up resources."""
        self.ctx.debug(f"Stopping debug adapter for session {self.session.id}")

        context = await self.execute_hook(LifecycleHook.PRE_STOP)

        if not context.cancelled:
            # Stop process manager (handles output capture cleanup)
            await self._process_manager.stop()

            # Release port if acquired
            if self.port:
                self._port_manager.release()

            # Clean up component registry
            # Clean up auxiliary components if initialized
            if self._trace_manager and hasattr(self._trace_manager, "cleanup"):
                self._trace_manager.cleanup()
            if self._output_capture and hasattr(self._output_capture, "cleanup"):
                self._output_capture.cleanup()

        await self.execute_hook(LifecycleHook.POST_STOP)

        self.ctx.debug(f"Debug adapter stopped for session {self.session.id}")

    def cleanup(self) -> None:
        """Clean up adapter resources."""
        # Check and halve trace log if needed
        if self._trace_manager:
            self._trace_manager.check_and_halve_log()

    def cleanup_orphaned_processes(self) -> None:
        """Clean up orphaned debug adapter processes."""
        pattern = self._get_process_name_pattern()
        self._process_manager.cleanup_orphaned_processes(pattern)

    async def initialize_child_dap(
        self,
        child_session: "ISession",
        _start_request_type: StartRequestType,
        _config: dict[str, Any],
    ) -> None:
        """Initialize child session DAP connection.

        Base implementation: child sessions inherit parent's DAP connection.
        Language-specific adapters can override this for custom behavior.

        Parameters
        ----------
        child_session : Session
            The child session to initialize
        _start_request_type : StartRequestType
            The type of start request (launch or attach)
        _config : dict
            Configuration from the startDebugging request
        """
        # Default: Child sessions share parent's adapter process and DAP
        # connection - no need to set them again.
        self.ctx.debug(
            f"Child session {child_session.id} initialized "
            "and active (inheriting parent's DAP connection)",
        )

    # ----------------------
    # Property Accessors
    # ----------------------

    @property
    def pid(self) -> int | None:
        """Get the process ID of the debug adapter.

        Returns
        -------
        Optional[int]
            Process ID or `None` if not running
        """
        return self._process_manager.pid

    @property
    def port(self) -> int | None:
        """Get the port the debug adapter is listening on.

        Returns
        -------
        Optional[int]
            Port number or `None` if not set
        """
        return self._port_manager.port

    @property
    def is_alive(self) -> bool:
        """Check if the attached process is still alive.

        Returns
        -------
        bool
            `True` if process is alive, `False` otherwise
        """
        return self._process_manager.is_alive

    @property
    def connected(self) -> bool:
        """Check if the debug adapter is connected.

        Returns
        -------
        bool
            `True` if adapter is connected, `False` otherwise
        """
        return self.is_alive and self.port is not None

    @property
    def captured_output(self) -> tuple[str, str] | None:
        """Get captured stdout and stderr from the adapter process.

        Returns
        -------
        Optional[Tuple[str, str]]
            Tuple of (stdout, stderr) if output capture is active, None
            otherwise
        """
        return self._process_manager.get_captured_output()

    # ---------------------------
    # Launch/Trace Config Getters
    # ---------------------------

    def get_launch_configuration(self) -> dict[str, Any] | None:
        """Get adapter-specific launch configuration for DAP Launch request.

        Returns
        -------
        Optional[Dict[str, Any]]
            Dictionary of launch configuration fields to include in the Launch
            request, or None if no custom configuration is needed.
        """
        return None

    def get_trace_config(self) -> dict[str, Any] | None:
        """Get trace configuration for DAP server if trace is enabled.

        Returns
        -------
        Optional[Dict[str, Any]]
            Trace configuration dictionary or None if trace is disabled
        """
        if not self._trace_manager:
            return None

        adapter_name = self.__class__.__name__.lower().replace("adapter", "")
        trace_path = self._trace_manager.get_trace_log_path(adapter_name)

        return {"trace": True, "logFile": trace_path}

    def get_trace_log_path(self) -> str | None:
        """Get the path to the current trace log file.

        Returns
        -------
        Optional[str]
            Path to the trace log file if available
        """
        if self._trace_manager:
            return self._trace_manager.get_current_log_path()
        return None

    def configure_child_launch(self, launch_args: dict[str, Any]) -> None:
        """Configure launch args for child sessions created via startDebugging.

        This method allows language-specific adapters to add their own
        configuration to child session launch arguments.

        Parameters
        ----------
        launch_args : Dict[str, Any]
            The launch arguments dictionary to modify in-place
        """

    # ----------------------
    # Abstract Methods
    # ----------------------

    @abstractmethod
    def _create_target_resolver(self) -> TargetResolver:
        """Create language-specific target resolver.

        Each adapter MUST implement this to provide language-specific
        target resolution (file vs module vs class detection).

        Target resolution happens at the start of launch(), before any
        hooks or DAP operations.

        Returns
        -------
        TargetResolver
            Language-specific target resolver instance
        """

    @abstractmethod
    def _create_source_path_resolver(self) -> "SourcePathResolver":
        """Create language-specific source path resolver.

        Each adapter MUST implement this to provide language-specific
        source path resolution for remote debugging scenarios.

        Source path resolution maps debug adapter paths (which may be
        container paths, JAR-internal paths, etc.) to local source files.

        Returns
        -------
        SourcePathResolver
            Language-specific source path resolver instance
        """

    @abstractmethod
    async def _build_launch_command(
        self,
        target: str,
        adapter_host: str,
        adapter_port: int,
        args: list[str] | None = None,
    ) -> list[str]:
        """Build the command to launch the debug adapter.

        Parameters
        ----------
        target : str
            Path to the target file to debug
        adapter_host : str
            Host where this adapter server binds
        adapter_port : int
            Port where this adapter server listens
        args : List[str], optional
            Additional arguments for the target

        Returns
        -------
        List[str]
            Command list ready for `asyncio.create_subprocess_exec`
        """

    def _prepare_environment(self) -> dict[str, str]:
        """Prepare environment variables for the debug adapter.

        This is a template method that provides the common structure for
        environment preparation. Subclasses can override specific steps.

        Returns
        -------
        Dict[str, str]
            Environment variables dictionary
        """
        # Step 1: Load base environment
        env = self._load_base_environment()

        # Step 2: Merge user-provided target environment variables
        env = self._merge_target_env(env)

        # Step 3: Add trace configuration if enabled
        env = self._add_trace_configuration(env)

        # Step 4: Add adapter-specific variables
        return self._add_adapter_specific_vars(env)

    def _load_base_environment(self) -> dict[str, str]:
        """Load base environment variables.

        Returns
        -------
        Dict[str, str]
            Copy of current environment variables
        """
        return os.environ.copy()

    def _merge_target_env(self, env: dict[str, str]) -> dict[str, str]:
        """Merge user-provided target environment variables.

        This ensures user's environment variables (e.g., PYTHONPATH, NODE_PATH)
        are included in the subprocess environment. This is done early in the
        pipeline so adapter-specific logic can further modify these values
        (e.g., prepending adapter paths to PYTHONPATH).

        Parameters
        ----------
        env : Dict[str, str]
            Current environment variables

        Returns
        -------
        Dict[str, str]
            Updated environment with user's target env vars merged
        """
        if self._target_env:
            env.update(self._target_env)
            self.ctx.debug(
                f"Merged {len(self._target_env)} user env vars into subprocess env",
            )
        return env

    def _add_trace_configuration(self, env: dict[str, str]) -> dict[str, str]:
        """Add trace-related environment variables if tracing is enabled.

        Parameters
        ----------
        env : Dict[str, str]
            Current environment variables

        Returns
        -------
        Dict[str, str]
            Updated environment variables
        """
        # Add AIDB trace configuration if needed
        if self._trace_manager:
            # This could be extended to add trace-specific env vars
            pass
        return env

    @abstractmethod
    def _add_adapter_specific_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Add adapter-specific environment variables.

        This method must be overridden by each language adapter to add
        its specific environment variables.

        Parameters
        ----------
        env : Dict[str, str]
            Current environment variables

        Returns
        -------
        Dict[str, str]
            Updated environment variables with adapter-specific additions
        """

    @abstractmethod
    def _get_process_name_pattern(self) -> str:
        """Get the process name pattern for cleanup operations.

        Returns
        -------
        str
            Pattern to match in process names/cmdlines
        """

    def _validate_adapter_version(self, binary_path: Path) -> None:
        """Validate adapter version compatibility with current AIDB version.

        Parameters
        ----------
        binary_path : Path
            Path to the adapter binary or directory
        """
        metadata = self.adapter_locator._load_metadata(binary_path)
        if not metadata:
            self.ctx.debug(f"No metadata.json found for {self.config.language} adapter")
            return

        adapter_aidb_version = metadata.get("aidb_version")
        if not adapter_aidb_version:
            self.ctx.debug(
                f"No AIDB version in metadata for {self.config.language} adapter",
            )
            return

        # Get current AIDB version
        try:
            from aidb import __version__ as current_aidb_version
        except ImportError:
            self.ctx.debug("Could not determine current AIDB version")
            return

        if adapter_aidb_version != current_aidb_version:
            adapter_name = metadata.get("adapter_name", self.config.language)
            adapter_version = metadata.get("adapter_version", "unknown")
            self.ctx.warning(
                (
                    f"Adapter version mismatch: {adapter_name} adapter "
                    f"(v{adapter_version}) was built with AIDB "
                    f"v{adapter_aidb_version}, current AIDB is "
                    f"v{current_aidb_version}. Use the MCP adapter tool "
                    "(action='download') or update the adapter manually."
                ),
            )
        else:
            self.ctx.debug(f"Adapter version OK: AIDB v{adapter_aidb_version}")

    # ----------------------
    # Hooks
    # ----------------------

    def _validate_target_hook(self, context: HookContext) -> None:
        """Validate target before launch."""
        target = context.data.get("target")
        if not target:
            return

        # Determine if target is a file path or identifier (same heuristic as Session)
        from aidb.session.adapter_registry import get_all_cached_file_extensions

        known_extensions = get_all_cached_file_extensions()
        target_path_obj = Path(target)
        suffix_lower = target_path_obj.suffix.lower()
        has_known_extension = suffix_lower in known_extensions
        has_path_separator = ("/" in target) or ("\\" in target)

        is_file_path = has_known_extension or has_path_separator

        if not is_file_path:
            # Target is an identifier (class name, module, etc.) - skip file validation
            self.ctx.debug(
                f"Target '{target}' is identifier - skipping file validation",
            )
            return

        # Target is a file path - validate it
        # Always resolve to absolute path for consistent validation
        target_path = normalize_path(Path(target), strict=True, return_path=True)

        # Check if target exists
        if not target_path.exists():
            self.ctx.error(f"Target not found: {target_path}")
            context.cancelled = True
            context.result = f"Target not found: {target_path}"
            return

        # Check file extension if config has file_extensions
        if hasattr(self.config, "file_extensions") and self.config.file_extensions:
            ext = target_path.suffix.lower()
            if ext not in self.config.file_extensions:
                self.ctx.warning(
                    f"Target {target} has extension {ext}, "
                    f"expected one of {self.config.file_extensions}",
                )

        # Validate syntax before launching
        is_valid, error_msg = self.validate_syntax(str(target_path))
        if not is_valid:
            self.ctx.error(f"Syntax error in {target_path}: {error_msg}")
            context.cancelled = True
            context.result = error_msg
            return

    # ----------------------
    # Adapter Behavior Flags
    # ----------------------

    @property
    def requires_child_session_wait(self) -> bool:
        """Check if adapter requires waiting for child session creation.

        Some adapters (like JavaScript) create child sessions asynchronously and
        require waiting for them to be ready before proceeding.

        Returns
        -------
        bool
            True if should wait for child session, False otherwise
        """
        return False

    @property
    def should_send_disconnect_request(self) -> bool:
        """Whether to send DAP DisconnectRequest when stopping the adapter.

        Some adapters (like Java with pooled bridges) keep debug servers alive
        across sessions. Sending DisconnectRequest has shutdown semantics that
        can cause the server to freeze/deadlock.

        Override in language adapters that use pooled servers.

        Returns
        -------
        bool
            True to send DisconnectRequest (default), False to skip it
        """
        return True

    @property
    def prefers_transport_only_disconnect(self) -> bool:
        """Whether to skip DAP DisconnectRequest and close transport directly.

        Adapters like Python and JavaScript often don't need a protocol-level
        DisconnectRequest during teardown. Skipping it avoids waiting for an
        acknowledgment that may never arrive and speeds up test runs and UX.

        Returns
        -------
        bool
            True to skip DisconnectRequest (transport-only), False otherwise
        """
        return False
