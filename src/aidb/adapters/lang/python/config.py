"""Python-specific configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidb.adapters.base.config import AdapterConfig
from aidb.adapters.base.initialize import InitializationOp, InitializationOpType
from aidb.adapters.base.launch import BaseLaunchConfig
from aidb.common.errors import ConfigurationError
from aidb.models.entities.breakpoint import HitConditionMode


@dataclass
class PythonAdapterConfig(AdapterConfig):
    """Python debug adapter configuration."""

    language: str = "python"
    adapter_id: str = "python"
    adapter_port: int = 5678
    adapter_server: str = "debugpy"
    binary_identifier: str = "debugpy"  # Python module name
    default_dap_port: int = 5678
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
    supports_conditional_breakpoints: bool = True
    supports_logpoints: bool = True

    # debugpy spawns a detached adapter process (PPID=1)
    detached_process_names: list[str] = field(
        default_factory=lambda: ["python", "debugpy"],
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
            InitializationOp(InitializationOpType.WAIT_FOR_INITIALIZED, timeout=5.0),
            InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=True),
            InitializationOp(InitializationOpType.CONFIGURATION_DONE),
            # debugpy sends attach response AFTER configurationDone
            InitializationOp(
                InitializationOpType.WAIT_FOR_ATTACH_RESPONSE,
                timeout=5.0,
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
