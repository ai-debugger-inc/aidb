"""Python-specific configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidb.adapters.base.config import AdapterCapabilities, AdapterConfig
from aidb.adapters.base.initialize import InitializationOp, InitializationOpType
from aidb.adapters.base.launch import BaseLaunchConfig
from aidb.common.constants import DEFAULT_PYTHON_DEBUG_PORT, INIT_WAIT_FOR_INITIALIZED_S
from aidb.common.errors import ConfigurationError
from aidb.models.entities.breakpoint import HitConditionMode
from aidb_common.constants import Language

# Static capabilities from debugpy source code
# Source: debugpy/src/debugpy/adapter/clients.py (initialize_request method)
PYTHON_CAPABILITIES = AdapterCapabilities(
    # Breakpoint capabilities
    conditional_breakpoints=True,
    logpoints=True,
    hit_conditional_breakpoints=True,
    function_breakpoints=True,
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
    restart_frame=False,
    step_in_targets=False,
    goto_targets=True,
    breakpoint_locations=False,
    # Session capabilities
    terminate_debuggee=True,
    restart=False,
    terminate_request=True,
    # Module/source capabilities
    modules=True,
    loaded_sources=False,
    delayed_stack_trace_loading=True,
    # Advanced capabilities
    exception_options=True,
    read_memory=False,
    write_memory=False,
)


@dataclass
class PythonAdapterConfig(AdapterConfig):
    """Python debug adapter configuration."""

    language: str = Language.PYTHON.value
    adapter_id: str = Language.PYTHON.value
    adapter_port: int = DEFAULT_PYTHON_DEBUG_PORT
    adapter_server: str = "debugpy"
    binary_identifier: str = "debugpy"  # Python module name
    default_dap_port: int = DEFAULT_PYTHON_DEBUG_PORT
    fallback_port_ranges: list[int] = field(default_factory=lambda: [6000, 7000])
    file_extensions: list[str] = field(default_factory=lambda: [".py"])
    supported_frameworks: list[str] = field(
        default_factory=lambda: [
            "pytest",
            "django",
            "flask",
            "fastapi",
        ],
    )
    framework_examples: list[str] = field(
        default_factory=lambda: ["pytest"],
    )

    # Core Python debugging flags
    justMyCode: bool = True
    subProcess: bool = False
    showReturnValue: bool = True
    redirectOutput: bool = True

    # Framework-specific debugging flags
    django: bool = False
    flask: bool = False
    jinja: bool = False
    pyramid: bool = False
    gevent: bool = False

    # Override base class default with Python-specific patterns
    non_executable_patterns: list[str] = field(
        default_factory=lambda: ["#", '"""', "'''"],
    )

    # Python (debugpy) supports all hit condition modes
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

    # debugpy spawns a detached adapter process (PPID=1)
    detached_process_names: list[str] = field(
        default_factory=lambda: ["python", "debugpy"],
    )

    # Static capabilities from debugpy source
    capabilities: AdapterCapabilities = field(
        default_factory=lambda: PYTHON_CAPABILITIES,
    )

    def get_initialization_sequence(self) -> list[InitializationOp]:
        """Get debugpy-specific initialization sequence.

        debugpy with --wait-for-client has special requirements:

            1. Must send attach before waiting for initialized event
            2. Attach response is deferred until after configurationDone
            3. Must send continue to start program execution after attach

        Returns
        -------
        List[InitializationOp]
            The debugpy-specific initialization sequence
        """
        return [
            InitializationOp(InitializationOpType.INITIALIZE),
            # debugpy needs attach before initialized event when using
            # --wait-for-client
            InitializationOp(InitializationOpType.ATTACH, wait_for_response=False),
            InitializationOp(
                InitializationOpType.WAIT_FOR_INITIALIZED,
                timeout=INIT_WAIT_FOR_INITIALIZED_S,
            ),
            InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=True),
            InitializationOp(InitializationOpType.CONFIGURATION_DONE),
            # debugpy sends attach response AFTER configurationDone
            InitializationOp(
                InitializationOpType.WAIT_FOR_ATTACH_RESPONSE,
                timeout=INIT_WAIT_FOR_INITIALIZED_S,
            ),
        ]


@dataclass
class PythonLaunchConfig(BaseLaunchConfig):
    """Python-specific launch configuration.

    Extends BaseLaunchConfig with Python-specific fields from VS Code's
    Python extension launch.json format.

    Attributes
    ----------
    python : Optional[str]
        Path to Python interpreter (defaults to workspace interpreter)
    pythonArgs : List[str]
        Arguments to pass to Python interpreter
    module : Optional[str]
        Python module to run (alternative to program)
    justMyCode : Optional[bool]
        Debug only user code (skip library code)
    django : Optional[bool]
        Enable Django-specific debugging features
    redirectOutput : Optional[bool]
        Redirect stdout/stderr to debug console
    subProcess : Optional[bool]
        Enable debugging of subprocesses
    purpose : Optional[str]
        Special purpose ("debug-test" or "debug-in-terminal")
    autoReload : Optional[Dict[str, Any]]
        Auto-reload configuration for code changes
    sudo : Optional[bool]
        Run with elevated privileges
    showReturnValue : Optional[bool]
        Show function return values in Variables window
    gevent : Optional[bool]
        Enable gevent compatibility mode
    jinja : Optional[bool]
        Enable Jinja template debugging
    pyramid : Optional[bool]
        Enable Pyramid framework debugging
    """

    LAUNCH_TYPE_ALIASES = ["python", "debugpy"]

    # Python interpreter configuration
    python: str | None = None
    pythonArgs: list[str] = field(default_factory=list)

    # Module vs program execution
    module: str | None = None

    # Debugging behavior
    justMyCode: bool | None = None
    django: bool | None = None
    redirectOutput: bool | None = None
    subProcess: bool | None = None
    purpose: str | None = None
    autoReload: dict[str, Any] | None = None
    sudo: bool | None = None
    showReturnValue: bool | None = None

    # Framework support
    flask: bool | None = None
    gevent: bool | None = None
    jinja: bool | None = None
    pyramid: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PythonLaunchConfig":
        """Create a Python launch configuration from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Raw configuration data from launch.json

        Returns
        -------
        PythonLaunchConfig
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

        # Python-specific fields
        python_fields = {
            "python",
            "pythonArgs",
            "module",
            "justMyCode",
            "django",
            "redirectOutput",
            "subProcess",
            "purpose",
            "autoReload",
            "sudo",
            "showReturnValue",
            "flask",
            "gevent",
            "jinja",
            "pyramid",
        }

        # Combine all known fields
        all_fields = base_fields | python_fields

        # Filter to only known fields
        filtered_data = {k: v for k, v in data.items() if k in all_fields}

        return cls(**filtered_data)

    def _add_module_or_program_config(self, args: dict[str, Any]) -> None:
        """Add module vs program execution configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update

        Raises
        ------
        ConfigurationError
            If neither program nor module is specified
        """
        if self.module:
            args["target"] = self.module
            args["module"] = True
        elif not self.program and not self.module:
            # Neither program nor module specified
            msg = "Either 'program' or 'module' must be specified"
            raise ConfigurationError(msg)

    def _add_python_interpreter_config(self, args: dict[str, Any]) -> None:
        """Add Python interpreter configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        if self.python:
            args["python_path"] = self.python

        if self.pythonArgs:
            args["python_args"] = self.pythonArgs

    def _add_debug_behavior_options(self, args: dict[str, Any]) -> None:
        """Add debugging behavior options to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        field_mappings = [
            ("justMyCode", "justMyCode"),
            ("django", "django"),
            ("redirectOutput", "redirectOutput"),
            ("subProcess", "subProcess"),
            ("showReturnValue", "showReturnValue"),
            ("sudo", "sudo"),
        ]

        for source_field, target_field in field_mappings:
            value = getattr(self, source_field, None)
            if value is not None:
                args[target_field] = value

    def _add_framework_support(self, args: dict[str, Any]) -> None:
        """Add framework-specific support options to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        frameworks = ["flask", "gevent", "jinja", "pyramid"]

        for framework in frameworks:
            value = getattr(self, framework, None)
            if value:
                args[framework] = value

    def _add_special_config(self, args: dict[str, Any]) -> None:
        """Add special purpose and auto-reload configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        if self.purpose:
            args["purpose"] = self.purpose

        if self.autoReload:
            args["autoReload"] = self.autoReload

    def to_adapter_args(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Convert to Python adapter arguments.

        Parameters
        ----------
        workspace_root : Optional[Path]
            Root directory for resolving relative paths

        Returns
        -------
        Dict[str, Any]
            Arguments suitable for the Python debug adapter
        """
        # Start with common arguments
        args = self.get_common_args(workspace_root)

        # Add configuration groups
        self._add_module_or_program_config(args)
        self._add_python_interpreter_config(args)
        self._add_debug_behavior_options(args)
        self._add_framework_support(args)
        self._add_special_config(args)

        return args


# Registration is now handled by AdapterRegistry to avoid circular imports
