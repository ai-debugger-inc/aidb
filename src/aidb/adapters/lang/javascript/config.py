"""JavaScript/Node.js-specific configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidb.adapters.base.config import AdapterCapabilities, AdapterConfig
from aidb.adapters.base.initialize import InitializationOp, InitializationOpType
from aidb.adapters.base.launch import BaseLaunchConfig, LaunchConfigFactory
from aidb.common.constants import (
    DEFAULT_NODE_DEBUG_PORT,
    INIT_WAIT_FOR_INITIALIZED_S,
    INIT_WAIT_FOR_LAUNCH_RESPONSE_S,
)
from aidb.models.entities.breakpoint import HitConditionMode
from aidb_common.constants import Language

# Static capabilities from vscode-js-debug source code
# Source: vscode-js-debug/src/adapter/debugAdapter.ts (static capabilities method)
JAVASCRIPT_CAPABILITIES = AdapterCapabilities(
    # Breakpoint capabilities
    conditional_breakpoints=True,
    logpoints=True,
    hit_conditional_breakpoints=True,
    function_breakpoints=False,
    data_breakpoints=False,
    # Inspection capabilities
    evaluate_for_hovers=True,
    set_variable=True,
    set_expression=True,
    completions=True,
    exception_info=True,
    clipboard_context=True,
    value_formatting_options=True,
    # Navigation capabilities
    restart_frame=True,
    step_in_targets=True,
    goto_targets=False,
    breakpoint_locations=True,
    # Session capabilities
    terminate_debuggee=True,
    restart=True,
    terminate_request=False,
    # Module/source capabilities
    modules=False,
    loaded_sources=True,
    delayed_stack_trace_loading=True,
    # Advanced capabilities
    exception_options=False,
    read_memory=True,
    write_memory=True,
)


@dataclass
class JavaScriptAdapterConfig(AdapterConfig):
    """JavaScript and TypeScript debug adapter configuration."""

    language: str = Language.JAVASCRIPT.value
    adapter_id: str = Language.JAVASCRIPT.value
    adapter_port: int = DEFAULT_NODE_DEBUG_PORT
    binary_identifier: str = "src/dapDebugServer.js"  # Adapter binary filename
    file_extensions: list[str] = field(
        default_factory=lambda: [
            # JavaScript extensions
            ".js",
            ".jsx",
            ".mjs",
            ".cjs",
            # TypeScript extensions
            ".ts",
            ".tsx",
            ".mts",
            ".cts",
        ],
    )
    supported_frameworks: list[str] = field(
        default_factory=lambda: ["jest", "express"],
    )
    framework_examples: list[str] = field(default_factory=lambda: ["node"])
    default_dap_port: int = DEFAULT_NODE_DEBUG_PORT
    # Provide wider, non-overlapping fallback ranges to reduce contention
    # under parallel test execution. Each start adds ~100 candidates.
    fallback_port_ranges: list[int] = field(
        default_factory=lambda: [9230, 9350, 9500, 9650, 9800],
    )

    # vscode-js-debug specific settings
    adapter_server: str = "vscode-js-debug"
    adapter_type: str = "pwa-node"  # Use pwa-node for better debugging support
    js_debug_path: str | None = None  # Path to js-debug DAP server

    # Runtime settings
    node_path: str | None = None  # Path to node executable
    use_ts_node: bool = True  # Enable TypeScript support via ts-node

    requires_separate_child_connections: bool = True
    enable_source_maps: bool = True  # Enable source map support

    # Debugging options
    console: str = "internalConsole"
    output_capture: str = "console"
    show_async_stacks: bool = True

    # Override base class default with JavaScript-specific patterns
    non_executable_patterns: list[str] = field(default_factory=lambda: ["//", "/*"])

    # JavaScript/TypeScript (vscode-js-debug) supports full hit conditions
    # (DAP only returns boolean, not which modes - this is adapter-specific)
    supported_hit_conditions: set[HitConditionMode] = field(
        default_factory=lambda: {
            HitConditionMode.EXACT,
            HitConditionMode.MODULO,
            HitConditionMode.GREATER_THAN,
            HitConditionMode.GREATER_EQUAL,
            HitConditionMode.LESS_THAN,
            HitConditionMode.LESS_EQUAL,
            HitConditionMode.EQUALS,
        },
    )

    # vscode-js-debug may spawn detached node processes
    detached_process_names: list[str] = field(
        default_factory=lambda: ["node"],
    )

    # Static capabilities from vscode-js-debug source
    capabilities: AdapterCapabilities = field(
        default_factory=lambda: JAVASCRIPT_CAPABILITIES,
    )

    def get_initialization_sequence(self) -> list[InitializationOp]:
        """Get JavaScript/TypeScript-specific initialization sequence.

        Returns
        -------
        List[InitializationOp]
            The JavaScript-specific initialization sequence

        Notes
        -----
        For JavaScript parent sessions, breakpoints should NOT be set during
        initialization. vscode-js-debug requires breakpoints to be set on the
        child session after it's created via the startDebugging reverse request.

        Child sessions set breakpoints during their initialization.
        """
        # Check if this is a child session
        is_child = False
        if hasattr(self, "session") and self.session:
            is_child = self.session.is_child

        ops = [
            InitializationOp(InitializationOpType.INITIALIZE),
            InitializationOp(InitializationOpType.LAUNCH, wait_for_response=False),
            InitializationOp(
                InitializationOpType.WAIT_FOR_INITIALIZED,
                timeout=INIT_WAIT_FOR_INITIALIZED_S,
                optional=True,
            ),
        ]

        # Only set breakpoints if this is a child session
        if is_child:
            ops.append(
                InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=True),
            )

        ops.extend(
            [
                InitializationOp(InitializationOpType.CONFIGURATION_DONE),
                InitializationOp(
                    InitializationOpType.WAIT_FOR_LAUNCH_RESPONSE,
                    timeout=INIT_WAIT_FOR_LAUNCH_RESPONSE_S,
                ),
            ],
        )

        return ops


@dataclass
class JavaScriptLaunchConfig(BaseLaunchConfig):
    """JavaScript/Node.js-specific launch configuration.

    Extends BaseLaunchConfig with JavaScript/Node.js-specific fields from
    VS Code's JavaScript debugger launch.json format.

    Attributes
    ----------
    runtimeExecutable : Optional[str]
        Path to runtime executable (default: "node")
    runtimeArgs : List[str]
        Arguments to pass to runtime
    runtimeVersion : Optional[str]
        Node.js version for version managers (nvm, etc.)
    sourceMaps : Optional[bool]
        Enable source maps (default: true)
    outFiles : List[str]
        Glob patterns for transpiled JavaScript files
    resolveSourceMapLocations : List[str]
        Where to resolve source maps from
    skipFiles : List[str]
        Files/patterns to skip during debugging
    smartStep : Optional[bool]
        Automatically step over unmapped code
    trace : Optional[bool]
        Enable diagnostic output for debugging the debugger
    outputCapture : Optional[str]
        From where to capture output ("console" or "std")
    timeout : Optional[int]
        Timeout for runtime to start (milliseconds)
    killBehavior : Optional[str]
        How to handle process termination
    localRoot : Optional[str]
        Local path for remote debugging scenarios
    remoteRoot : Optional[str]
        Remote path for remote debugging scenarios
    address : Optional[str]
        TCP/IP address for remote debugging
    protocol : Optional[str]
        Debug protocol ("auto", "inspector", "legacy")
    continueOnAttach : Optional[bool]
        Continue execution after attaching
    pauseForSourceMap : Optional[bool]
        Pause while waiting for source maps
    cascadeTerminateToConfigurations : List[str]
        Configurations to terminate when this one terminates
    """

    LAUNCH_TYPE_ALIASES = [
        "javascript",
        "node",
        "pwa-node",
        "node2",
        "chrome",
        "pwa-chrome",
    ]

    # Runtime configuration
    runtimeExecutable: str | None = None
    runtimeArgs: list[str] = field(default_factory=list)
    runtimeVersion: str | None = None

    # Source maps and files
    sourceMaps: bool | None = None
    outFiles: list[str] = field(default_factory=list)
    resolveSourceMapLocations: list[str] = field(default_factory=list)
    skipFiles: list[str] = field(default_factory=list)
    smartStep: bool | None = None

    # Debugging behavior
    trace: bool | None = None
    outputCapture: str | None = None
    timeout: int | None = None
    killBehavior: str | None = None

    # Remote debugging
    localRoot: str | None = None
    remoteRoot: str | None = None
    address: str | None = None

    # Protocol and connection
    protocol: str | None = None
    continueOnAttach: bool | None = None
    pauseForSourceMap: bool | None = None

    # Process attachment
    processId: str | None = None
    restart: bool | None = None

    # Multi-configuration support
    cascadeTerminateToConfigurations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JavaScriptLaunchConfig":
        """Create a JavaScript launch configuration from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Raw configuration data from launch.json

        Returns
        -------
        JavaScriptLaunchConfig
            Parsed configuration object
        """
        # Get base fields first
        base_fields = {
            "type",
            "request",
            "name",
            "program",
            "args",
            "cwd",
            "env",
            "envFile",
            "port",
            "console",
            "presentation",
            "preLaunchTask",
            "postDebugTask",
            "internalConsoleOptions",
            "serverReadyAction",
        }

        # JavaScript-specific fields
        js_fields = {
            "runtimeExecutable",
            "runtimeArgs",
            "runtimeVersion",
            "sourceMaps",
            "outFiles",
            "resolveSourceMapLocations",
            "skipFiles",
            "smartStep",
            "trace",
            "outputCapture",
            "timeout",
            "killBehavior",
            "localRoot",
            "remoteRoot",
            "address",
            "protocol",
            "continueOnAttach",
            "pauseForSourceMap",
            "processId",
            "restart",
            "cascadeTerminateToConfigurations",
        }

        # Combine all known fields
        all_fields = base_fields | js_fields

        # Filter to only known fields
        filtered_data = {k: v for k, v in data.items() if k in all_fields}

        return cls(**filtered_data)

    def _add_runtime_config(self, args: dict[str, Any]) -> None:
        """Add runtime configuration to args."""
        field_mappings = [
            ("runtimeExecutable", "runtime_executable"),
            ("runtimeArgs", "runtime_args"),
            ("runtimeVersion", "runtime_version"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_source_map_config(self, args: dict[str, Any]) -> None:
        """Add source maps and file handling configuration to args."""
        field_mappings = [
            ("sourceMaps", "source_maps"),
            ("outFiles", "out_files"),
            ("resolveSourceMapLocations", "resolve_source_map_locations"),
            ("skipFiles", "skip_files"),
            ("smartStep", "smart_step"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_debug_behavior_config(self, args: dict[str, Any]) -> None:
        """Add debugging behavior configuration to args."""
        field_mappings = [
            ("trace", "trace"),
            ("outputCapture", "output_capture"),
            ("timeout", "timeout"),
            ("killBehavior", "kill_behavior"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_remote_debug_config(self, args: dict[str, Any]) -> None:
        """Add remote debugging configuration to args."""
        field_mappings = [
            ("localRoot", "local_root"),
            ("remoteRoot", "remote_root"),
            ("address", "address"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_protocol_config(self, args: dict[str, Any]) -> None:
        """Add protocol and connection options to args."""
        field_mappings = [
            ("protocol", "protocol"),
            ("continueOnAttach", "continue_on_attach"),
            ("pauseForSourceMap", "pause_for_source_map"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_process_config(self, args: dict[str, Any]) -> None:
        """Add process attachment configuration to args."""
        field_mappings = [
            ("processId", "process_id"),
            ("restart", "restart"),
            ("cascadeTerminateToConfigurations", "cascade_terminate"),
            ("envFile", "env_file"),
        ]
        self._add_optional_fields(args, field_mappings)

    def _add_optional_fields(
        self,
        args: dict[str, Any],
        field_mappings: list[tuple[str, str]],
    ) -> None:
        """Add optional fields to args if they have values."""
        for source_field, target_field in field_mappings:
            value = getattr(self, source_field, None)
            if value is not None and value != []:
                args[target_field] = value

    def to_adapter_args(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Convert to JavaScript/Node.js adapter arguments.

        Parameters
        ----------
        workspace_root : Optional[Path]
            Root directory for resolving relative paths

        Returns
        -------
        Dict[str, Any]
            Arguments suitable for the JavaScript debug adapter
        """
        # Start with common arguments
        args = self.get_common_args(workspace_root)

        # Add configuration groups
        self._add_runtime_config(args)
        self._add_source_map_config(args)
        self._add_debug_behavior_config(args)
        self._add_remote_debug_config(args)
        self._add_protocol_config(args)
        self._add_process_config(args)

        # Handle default port for attach requests
        if self.request == "attach" and "port" not in args:
            args["port"] = DEFAULT_NODE_DEBUG_PORT

        return args


# Register JavaScript/Node.js configurations with the factory
LaunchConfigFactory.register("node", JavaScriptLaunchConfig)
LaunchConfigFactory.register("pwa-node", JavaScriptLaunchConfig)
LaunchConfigFactory.register("chrome", JavaScriptLaunchConfig)
LaunchConfigFactory.register("pwa-chrome", JavaScriptLaunchConfig)
LaunchConfigFactory.register("msedge", JavaScriptLaunchConfig)
LaunchConfigFactory.register("pwa-msedge", JavaScriptLaunchConfig)
