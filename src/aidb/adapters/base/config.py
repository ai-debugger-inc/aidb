"""Debug adapter configuration."""

from dataclasses import dataclass, field

from aidb.models.entities.breakpoint import HitConditionMode
from aidb.models.start_request import StartRequestType

from .initialize import InitializationOp, InitializationOpType


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
        directory (e.g., "dist/dapDebugServer.js" or "*.jar")
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
        Set of hit condition modes supported by this adapter
    supports_conditional_breakpoints : bool
        Whether the adapter supports conditional breakpoints
    supports_logpoints : bool
        Whether the adapter supports logpoints (log messages without stopping)
    supports_data_breakpoints : bool
        Whether the adapter supports data breakpoints (watchpoints)
    supports_function_breakpoints : bool
        Whether the adapter supports function breakpoints
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

    # Capability declarations
    supported_hit_conditions: set[HitConditionMode] = field(default_factory=set)
    supports_conditional_breakpoints: bool = True
    supports_logpoints: bool = True
    supports_data_breakpoints: bool = False
    supports_function_breakpoints: bool = True

    # Timeout configurations (seconds)
    terminate_request_timeout: float = 1.0  # DAP terminate request timeout
    process_termination_timeout: float = 1.0  # ProcessRegistry cleanup timeout
    process_manager_timeout: float = 0.5  # ProcessManager wait timeout

    # Process names to check when adapter spawns detached processes
    # (e.g., debugpy spawns adapter with PPID=1, not as child)
    detached_process_names: list[str] = field(default_factory=list)

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
                timeout=5.0,
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
