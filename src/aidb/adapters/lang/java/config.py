"""Java-specific configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aidb.adapters.base.config import (
    AdapterCapabilities,
    AdapterConfig,
    StartRequestType,
)
from aidb.adapters.base.initialize import InitializationOp, InitializationOpType
from aidb.adapters.base.launch import BaseLaunchConfig, LaunchConfigFactory
from aidb.common.constants import (
    DEFAULT_JAVA_DEBUG_PORT,
    INIT_CONFIGURATION_DONE_JAVA_S,
    INIT_WAIT_FOR_INITIALIZED_JAVA_S,
    INIT_WAIT_FOR_INITIALIZED_S,
    INIT_WAIT_FOR_PLUGIN_READY_S,
)
from aidb.models.entities.breakpoint import HitConditionMode
from aidb_common.constants import Language

# Static capabilities from java-debug source code
# Source: java-debug/com.microsoft.java.debug.core/.../InitializeRequestHandler.java
JAVA_CAPABILITIES = AdapterCapabilities(
    # Breakpoint capabilities
    conditional_breakpoints=True,
    logpoints=True,
    hit_conditional_breakpoints=True,
    function_breakpoints=True,
    data_breakpoints=True,
    # Inspection capabilities
    evaluate_for_hovers=True,
    set_variable=True,
    set_expression=False,
    completions=True,
    exception_info=True,
    clipboard_context=True,
    value_formatting_options=False,
    # Navigation capabilities
    restart_frame=True,
    step_in_targets=True,
    goto_targets=False,
    breakpoint_locations=True,
    # Session capabilities
    terminate_debuggee=True,
    restart=False,
    terminate_request=False,
    # Module/source capabilities
    modules=False,
    loaded_sources=False,
    delayed_stack_trace_loading=False,
    # Advanced capabilities
    exception_options=False,
    read_memory=False,
    write_memory=False,
)


@dataclass
class JavaAdapterConfig(AdapterConfig):
    """Java debug adapter configuration."""

    # JDT LS invisible project name for single-file Java programs
    # This is the project name JDT LS uses when opening standalone .java files
    # that aren't part of a Maven/Gradle/Eclipse project
    DEFAULT_PROJECT_NAME = "jdt.ls-java-project"

    language: str = Language.JAVA.value
    adapter_id: str = Language.JAVA.value
    adapter_port: int = DEFAULT_JAVA_DEBUG_PORT
    binary_identifier: str = "java-debug.jar"  # JAR file name
    adapter_server: str = "java-debug-server"
    default_dap_port: int = DEFAULT_JAVA_DEBUG_PORT
    fallback_port_ranges: list[int] = field(default_factory=lambda: [5006, 5020])
    file_extensions: list[str] = field(
        default_factory=lambda: [".java", ".class", ".jar"],
    )
    supported_frameworks: list[str] = field(
        default_factory=lambda: ["junit", "spring"],
    )
    framework_examples: list[str] = field(default_factory=lambda: ["junit"])

    # Java-specific settings
    jdk_home: str | None = None  # Path to JDK installation
    java_debug_server_path: str | None = None  # Path to java-debug-server JAR
    projectName: str | None = None  # Project name for evaluation context

    # Eclipse JDT LS settings (JDT LS is required for Java debugging)
    jdtls_path: str | None = None  # Path to Eclipse JDT LS installation
    jdtls_workspace: str | None = None  # Workspace directory for JDT LS

    # Compilation settings
    auto_compile: bool = True  # Whether to auto-compile .java files
    compile_output_dir: str | None = None  # Directory for compiled classes

    # Runtime settings used by adapter for classpath building and launch config
    classpath: list[str] = field(default_factory=list)  # Additional classpath entries
    module_path: list[str] = field(
        default_factory=list,
    )  # Module path entries (Java 9+)
    vmargs: list[str] = field(default_factory=list)  # JVM arguments

    # Override base class default with Java-specific patterns
    non_executable_patterns: list[str] = field(
        default_factory=lambda: ["//", "/*", "package ", "import "],
    )

    # Java adapter only supports exact hit counts (no operators)
    # (DAP only returns boolean, not which modes - this is adapter-specific)
    supported_hit_conditions: set[HitConditionMode] = field(
        default_factory=lambda: {
            HitConditionMode.EXACT,  # Only plain integers like "5"
        },
    )

    # Reconnection fallback settings
    enable_dap_reconnection_fallback: bool = True
    dap_reconnection_timeout: float = 5.0
    max_dap_reconnection_attempts: int = 1

    # Java-specific timeout overrides (JVM/JDT LS need longer timeouts)
    terminate_request_timeout: float = 5.0  # Restore original (from 1.0)
    process_termination_timeout: float = 5.0  # Restore original (from 1.0)
    process_manager_timeout: float = 2.0  # Restore original (from 0.5)

    # java-debug may spawn detached Java processes
    detached_process_names: list[str] = field(
        default_factory=lambda: ["java"],
    )

    # Static capabilities from java-debug source
    capabilities: AdapterCapabilities = field(default_factory=lambda: JAVA_CAPABILITIES)

    def get_initialization_sequence(self) -> list[InitializationOp]:
        """Get Java-specific initialization sequence.

        Returns
        -------
        List[InitializationOp]
            The Java-specific initialization sequence with plugin readiness
            polling. Uses ATTACH for remote_attach mode, LAUNCH otherwise.
        """
        # Determine whether to use launch or attach based on dap_start_request_type
        is_attach = self.dap_start_request_type == StartRequestType.ATTACH

        # Choose appropriate operation types
        if is_attach:
            connect_op = InitializationOpType.ATTACH
        else:
            connect_op = InitializationOpType.LAUNCH
        wait_op = (
            InitializationOpType.WAIT_FOR_ATTACH_RESPONSE
            if is_attach
            else InitializationOpType.WAIT_FOR_LAUNCH_RESPONSE
        )

        return [
            InitializationOp(InitializationOpType.INITIALIZE),
            # Send launch/attach without waiting to avoid blocking delays.
            InitializationOp(
                connect_op,
                wait_for_response=False,
            ),
            # Require initialized event before proceeding to breakpoints.
            InitializationOp(
                InitializationOpType.WAIT_FOR_INITIALIZED,
                timeout=INIT_WAIT_FOR_INITIALIZED_JAVA_S,
            ),
            # Also require the deferred launch/attach response before breakpoint/config.
            InitializationOp(
                wait_op,
                timeout=INIT_WAIT_FOR_INITIALIZED_JAVA_S,
            ),
            InitializationOp(
                InitializationOpType.WAIT_FOR_PLUGIN_READY,
                timeout=INIT_WAIT_FOR_PLUGIN_READY_S,
            ),
            InitializationOp(InitializationOpType.SET_BREAKPOINTS, optional=True),
            # Java may take longer to bind breakpoints via JDT LS; wait briefly so
            # initial breakpoints are verified before resuming execution.
            InitializationOp(
                InitializationOpType.WAIT_FOR_BREAKPOINT_VERIFICATION,
                timeout=INIT_WAIT_FOR_INITIALIZED_S,
                optional=True,
            ),
            InitializationOp(
                InitializationOpType.CONFIGURATION_DONE,
                timeout=INIT_CONFIGURATION_DONE_JAVA_S,
            ),
        ]


@dataclass
class JavaLaunchConfig(BaseLaunchConfig):
    """Java-specific launch configuration.

    Extends BaseLaunchConfig with Java-specific fields from VS Code's
    Java extension launch.json format.

    Attributes
    ----------
    mainClass : Optional[str]
        Fully qualified name of the class containing main method
    projectName : Optional[str]
        Preferred project for searching the main class
    classPaths : List[str]
        Classpaths for launching the JVM (special values: $Auto, $Runtime, $Test)
    modulePaths : List[str]
        Module paths for launching the JVM (special values: $Auto, $Runtime, $Test)
    sourcePaths : List[str]
        Extra source directories for debugger to search for source files
    vmArgs : Optional[str]
        JVM options and system properties (e.g., "-Xms256m -Xmx1g")
    encoding : Optional[str]
        File encoding (default: "UTF-8")
    shortenCommandLine : Optional[str]
        Method to shorten command line ("none", "jarmanifest", "argfile")
    hostName : Optional[str]
        Host name or IP address for remote debugging
    timeout : Optional[int]
        Connection timeout in milliseconds for attach requests
    processId : Optional[str]
        Process ID to attach to ("${command:PickJavaProcess}")
    javaExec : Optional[str]
        Path to Java executable (defaults to java.home setting)
    """

    LAUNCH_TYPE_ALIASES = ["java"]

    # Core Java configuration
    mainClass: str | None = None
    projectName: str | None = None

    # Classpath and module configuration
    classPaths: list[str] = field(default_factory=list)
    modulePaths: list[str] = field(default_factory=list)
    sourcePaths: list[str] = field(default_factory=list)

    # JVM configuration
    vmArgs: str | None = None
    encoding: str | None = None
    shortenCommandLine: str | None = None
    javaExec: str | None = None

    # Remote/attach configuration
    hostName: str | None = None
    timeout: int | None = None
    processId: str | None = None

    # Debugging configuration
    stepFilters: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JavaLaunchConfig":
        """Create a Java launch configuration from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Raw configuration data from launch.json

        Returns
        -------
        JavaLaunchConfig
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

        # Java-specific fields
        java_fields = {
            "mainClass",
            "projectName",
            "classPaths",
            "modulePaths",
            "sourcePaths",
            "vmArgs",
            "encoding",
            "shortenCommandLine",
            "hostName",
            "timeout",
            "processId",
            "javaExec",
            "stepFilters",
        }

        # Combine all known fields
        all_fields = base_fields | java_fields

        # Filter to only known fields
        filtered_data = {k: v for k, v in data.items() if k in all_fields}

        return cls(**filtered_data)

    def _add_main_class_config(
        self,
        args: dict[str, Any],
        workspace_root: Path | None,  # noqa: ARG002
    ) -> None:
        """Add main class configuration to args.

        This method sets the main_class field but does NOT overwrite the target
        field. The target field is already set by get_common_args() with the
        full resolved file path, which is needed by the adapter for compilation.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        workspace_root : Path | None
            Root directory for resolving relative paths (unused here)
        """
        if self.mainClass:
            args["main_class"] = self.mainClass
        elif self.program:
            # Extract class name from program path for main_class field
            program_path = Path(self.program)
            if program_path.suffix == ".java":
                # Use just the class name (without .java extension)
                class_name = program_path.stem
                args["main_class"] = class_name
            elif program_path.suffix == ".class":
                # Use class name (without .class extension)
                class_name = program_path.stem
                args["main_class"] = class_name
            # Note: For other cases (e.g., already a class name),
            # we don't set main_class

    def _add_project_config(self, args: dict[str, Any]) -> None:
        """Add project configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        if self.projectName:
            args["project_name"] = self.projectName

    def _add_classpath_config(
        self,
        args: dict[str, Any],
        workspace_root: Path | None,
    ) -> None:
        """Add classpath and module configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        workspace_root : Path | None
            Root directory for resolving relative paths
        """
        if self.classPaths:
            args["class_paths"] = self._resolve_special_paths(
                self.classPaths,
                workspace_root,
            )
        if self.modulePaths:
            args["module_paths"] = self._resolve_special_paths(
                self.modulePaths,
                workspace_root,
            )
        if self.sourcePaths:
            args["source_paths"] = [
                self.resolve_path(path, workspace_root) for path in self.sourcePaths
            ]

    def _add_jvm_config(self, args: dict[str, Any]) -> None:
        """Add JVM configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        jvm_fields = [
            ("vmArgs", "vm_args"),
            ("encoding", "encoding"),
            ("shortenCommandLine", "shorten_command_line"),
            ("javaExec", "java_exec"),
        ]

        for source_field, target_field in jvm_fields:
            value = getattr(self, source_field, None)
            if value:
                args[target_field] = value

    def _add_remote_config(self, args: dict[str, Any]) -> None:
        """Add remote/attach configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        if self.hostName:
            args["host"] = self.hostName
        if self.timeout is not None:
            args["timeout"] = self.timeout
        if self.processId:
            args["process_id"] = self.processId

    def _add_debug_config(self, args: dict[str, Any]) -> None:
        """Add debugging configuration to args.

        Parameters
        ----------
        args : dict[str, Any]
            Arguments dictionary to update
        """
        if self.stepFilters:
            args["step_filters"] = self.stepFilters

    def to_adapter_args(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Convert to Java adapter arguments.

        Parameters
        ----------
        workspace_root : Optional[Path]
            Root directory for resolving relative paths

        Returns
        -------
        Dict[str, Any]
            Arguments suitable for the Java debug adapter
        """
        # Start with common arguments
        args = self.get_common_args(workspace_root)

        # Add configuration sections
        self._add_main_class_config(args, workspace_root)
        self._add_project_config(args)
        self._add_classpath_config(args, workspace_root)
        self._add_jvm_config(args)
        self._add_remote_config(args)
        self._add_debug_config(args)

        return args

    def _resolve_special_paths(
        self,
        paths: list[str],
        workspace_root: Path | None = None,
    ) -> list[str]:
        """Resolve special Java path values.

        Parameters
        ----------
        paths : List[str]
            List of paths that may contain special values
        workspace_root : Optional[Path]
            Root directory for resolving relative paths

        Returns
        -------
        List[str]
            Resolved paths
        """
        resolved = []
        special_values = {"$Auto", "$Runtime", "$Test"}

        for path in paths:
            if path in special_values:
                # Keep special values as-is for the adapter to handle
                resolved.append(path)
            else:
                # Resolve regular paths
                resolved.append(self.resolve_path(path, workspace_root))

        return resolved


LaunchConfigFactory.register("java", JavaLaunchConfig)
