"""Debug adapter configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aidb.common.constants import (
    INIT_WAIT_FOR_INITIALIZED_S,
    PROCESS_TERMINATE_TIMEOUT_S,
    PROCESS_WAIT_TIMEOUT_S,
)
from aidb.models.entities.breakpoint import HitConditionMode
from aidb.models.start_request import StartRequestType

from .initialize import InitializationOp, InitializationOpType


@dataclass
class AdapterCapabilities:
    """Static DAP capabilities from adapter source code.

    These capabilities are hardcoded in the upstream debug adapter implementations
    and do not change at runtime. We extract them from source to avoid the overhead
    of spawning processes just to query static values.

    Sources:
    - debugpy: src/debugpy/adapter/clients.py (initialize_request)
    - vscode-js-debug: src/adapter/debugAdapter.ts (static capabilities)
    - java-debug: InitializeRequestHandler.java

    Attributes
    ----------
    conditional_breakpoints : bool
        Supports breakpoints with conditions (e.g., x > 5)
    logpoints : bool
        Supports log message breakpoints that don't pause execution
    hit_conditional_breakpoints : bool
        Supports hit count conditions (e.g., break after 5 hits)
    function_breakpoints : bool
        Supports setting breakpoints on function names
    data_breakpoints : bool
        Supports watchpoints/data breakpoints (break on variable change)
    evaluate_for_hovers : bool
        Supports evaluating expressions for hover information
    set_variable : bool
        Supports modifying variable values during debugging
    restart_frame : bool
        Supports restarting execution from a stack frame
    step_in_targets : bool
        Supports choosing which function to step into
    completions : bool
        Supports code completion in debug console
    exception_info : bool
        Supports detailed exception information
    clipboard_context : bool
        Supports clipboard context for copy operations
    breakpoint_locations : bool
        Supports querying valid breakpoint locations
    terminate_debuggee : bool
        Supports terminating the debuggee process
    restart : bool
        Supports restarting the debug session
    modules : bool
        Supports listing loaded modules
    loaded_sources : bool
        Supports listing loaded source files
    goto_targets : bool
        Supports goto targets for jumping to locations
    set_expression : bool
        Supports setting expressions (watch expressions)
    terminate_request : bool
        Supports the terminate request
    delayed_stack_trace_loading : bool
        Supports lazy loading of stack trace frames
    value_formatting_options : bool
        Supports custom value formatting
    exception_options : bool
        Supports exception breakpoint options
    read_memory : bool
        Supports reading memory directly
    write_memory : bool
        Supports writing memory directly
    """

    # Breakpoint capabilities
    conditional_breakpoints: bool = False
    logpoints: bool = False
    hit_conditional_breakpoints: bool = False
    function_breakpoints: bool = False
    data_breakpoints: bool = False  # watchpoints

    # Inspection capabilities
    evaluate_for_hovers: bool = False
    set_variable: bool = False
    set_expression: bool = False
    completions: bool = False
    exception_info: bool = False
    clipboard_context: bool = False
    value_formatting_options: bool = False

    # Navigation capabilities
    restart_frame: bool = False
    step_in_targets: bool = False
    goto_targets: bool = False
    breakpoint_locations: bool = False

    # Session capabilities
    terminate_debuggee: bool = False
    restart: bool = False
    terminate_request: bool = False

    # Module/source capabilities
    modules: bool = False
    loaded_sources: bool = False
    delayed_stack_trace_loading: bool = False

    # Advanced capabilities
    exception_options: bool = False
    read_memory: bool = False
    write_memory: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert capabilities to a dictionary for API responses.

        Returns
        -------
        dict[str, Any]
            Dictionary with capability names and boolean values
        """
        return {
            "conditional_breakpoints": self.conditional_breakpoints,
            "logpoints": self.logpoints,
            "hit_conditional_breakpoints": self.hit_conditional_breakpoints,
            "function_breakpoints": self.function_breakpoints,
            "watchpoints": self.data_breakpoints,  # Alias for API consistency
            "data_breakpoints": self.data_breakpoints,
            "evaluate_for_hovers": self.evaluate_for_hovers,
            "set_variable": self.set_variable,
            "set_expression": self.set_expression,
            "completions": self.completions,
            "exception_info": self.exception_info,
            "clipboard_context": self.clipboard_context,
            "value_formatting_options": self.value_formatting_options,
            "restart_frame": self.restart_frame,
            "step_in_targets": self.step_in_targets,
            "goto_targets": self.goto_targets,
            "breakpoint_locations": self.breakpoint_locations,
            "terminate_debuggee": self.terminate_debuggee,
            "restart": self.restart,
            "terminate_request": self.terminate_request,
            "modules": self.modules,
            "loaded_sources": self.loaded_sources,
            "delayed_stack_trace_loading": self.delayed_stack_trace_loading,
            "exception_options": self.exception_options,
            "read_memory": self.read_memory,
            "write_memory": self.write_memory,
        }

    def to_raw_dap(self) -> dict[str, bool]:
        """Convert to raw DAP capability names.

        Returns
        -------
        dict[str, bool]
            Dictionary using official DAP capability names
        """
        return {
            "supportsConditionalBreakpoints": self.conditional_breakpoints,
            "supportsLogPoints": self.logpoints,
            "supportsHitConditionalBreakpoints": self.hit_conditional_breakpoints,
            "supportsFunctionBreakpoints": self.function_breakpoints,
            "supportsDataBreakpoints": self.data_breakpoints,
            "supportsEvaluateForHovers": self.evaluate_for_hovers,
            "supportsSetVariable": self.set_variable,
            "supportsSetExpression": self.set_expression,
            "supportsCompletionsRequest": self.completions,
            "supportsExceptionInfoRequest": self.exception_info,
            "supportsClipboardContext": self.clipboard_context,
            "supportsValueFormattingOptions": self.value_formatting_options,
            "supportsRestartFrame": self.restart_frame,
            "supportsStepInTargetsRequest": self.step_in_targets,
            "supportsGotoTargetsRequest": self.goto_targets,
            "supportsBreakpointLocationsRequest": self.breakpoint_locations,
            "supportTerminateDebuggee": self.terminate_debuggee,
            "supportsRestartRequest": self.restart,
            "supportsTerminateRequest": self.terminate_request,
            "supportsModulesRequest": self.modules,
            "supportsLoadedSourcesRequest": self.loaded_sources,
            "supportsDelayedStackTraceLoading": self.delayed_stack_trace_loading,
            "supportsExceptionOptions": self.exception_options,
            "supportsReadMemoryRequest": self.read_memory,
            "supportsWriteMemoryRequest": self.write_memory,
        }


@dataclass
class AdapterConfig:
    """Base configuration class for debug adapters.

    Attributes
    ----------
    language : str
        The language identifier
    adapter_id : str
        The adapter ID required for DAP client initialization
    adapter_port : int
        The debug adapter's default port
    adapter_server : str
        The DAP server to use
    binary_identifier : str
        Path or glob pattern to locate the adapter binary within the adapter
        directory (e.g., ``dist/dapDebugServer.js`` or ``*.jar``)
    fallback_port_ranges : List[int]
        List of fallback port ranges to use if the default port is not available
    file_extensions : List[str]
        List of file extensions associated with the language
    supported_frameworks : List[str]
        List of frameworks supported by this adapter (e.g., pytest, django for
        Python)
    framework_examples : List[str]
        Top frameworks to show as examples when no framework specified (e.g.,
        ["pytest", "django"])
    dap_start_request_type : StartRequestType
        The type of DAP start request to use after initialization
    non_executable_patterns : List[str]
        Patterns for non-executable lines (comments, imports, etc.)
    supported_hit_conditions : Set[HitConditionMode]
        Set of hit condition modes supported by this adapter (DAP only returns
        a boolean for hit condition support, not which specific modes)
    terminate_request_timeout : float
        Timeout in seconds for DAP terminate request (default: 1.0)
    process_termination_timeout : float
        Timeout in seconds for process termination via ProcessRegistry (default:
        1.0)
    process_manager_timeout : float
        Timeout in seconds for ProcessManager to wait for process exit (default:
        0.5)
    detached_process_names : List[str]
        Process names to check when adapter spawns detached processes that won't
        appear as children (e.g., debugpy spawns adapter with PPID=1)
    capabilities : AdapterCapabilities
        Static DAP capabilities for this adapter (from upstream source code)
    """

    language: str = ""
    adapter_id: str = ""
    adapter_port: int = 0
    adapter_server: str = ""
    binary_identifier: str = ""  # Override in subclasses with specific pattern
    fallback_port_ranges: list[int] = field(default_factory=list)
    file_extensions: list[str] = field(default_factory=list)
    supported_frameworks: list[str] = field(default_factory=list)
    framework_examples: list[str] = field(default_factory=list)
    dap_start_request_type: StartRequestType = StartRequestType.ATTACH
    non_executable_patterns: list[str] = field(default_factory=list)

    # Hit condition modes (DAP only returns boolean, not which modes are supported)
    supported_hit_conditions: set[HitConditionMode] = field(default_factory=set)

    # Timeout configurations (seconds)
    terminate_request_timeout: float = PROCESS_TERMINATE_TIMEOUT_S  # DAP terminate
    process_termination_timeout: float = PROCESS_TERMINATE_TIMEOUT_S  # Registry cleanup
    process_manager_timeout: float = PROCESS_WAIT_TIMEOUT_S  # ProcessManager wait

    # Process names to check when adapter spawns detached processes
    # (e.g., debugpy spawns adapter with PPID=1, not as child)
    detached_process_names: list[str] = field(default_factory=list)

    # Static DAP capabilities (from upstream adapter source code)
    capabilities: AdapterCapabilities = field(default_factory=AdapterCapabilities)

    def get_initialization_sequence(self) -> list[InitializationOp]:
        """Get the DAP initialization sequence for this adapter.

        Default implementation returns standard DAP sequence. Subclasses can
        override for adapter-specific sequences.

        Returns
        -------
        List[InitializationOp]
            The ordered list of operations to perform during initialization
        """
        # Use dap_start_request_type to determine launch vs attach
        connect_op = (
            InitializationOpType.LAUNCH
            if self.dap_start_request_type == StartRequestType.LAUNCH
            else InitializationOpType.ATTACH
        )

        # Standard DAP sequence
        return [
            InitializationOp(InitializationOpType.INITIALIZE),
            InitializationOp(
                InitializationOpType.WAIT_FOR_INITIALIZED,
                timeout=INIT_WAIT_FOR_INITIALIZED_S,
                optional=True,
            ),
            InitializationOp(connect_op),
            InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=True),
            InitializationOp(InitializationOpType.CONFIGURATION_DONE),
        ]

    def supports_hit_condition(self, expression: str) -> bool:
        """Check if adapter supports a specific hit condition expression.

        Parameters
        ----------
        expression : str
            The hit condition expression to check

        Returns
        -------
        bool
            True if the adapter supports this hit condition format
        """
        try:
            mode, _ = HitConditionMode.parse(expression)
            return mode in self.supported_hit_conditions
        except ValueError:
            return False
