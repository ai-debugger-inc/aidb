"""Base launch configuration classes for VS Code launch.json support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from aidb_common.path import normalize_path


@dataclass
class BaseLaunchConfig(ABC):
    """Base launch configuration with common fields across all debuggers.

    This abstract base class defines the common fields that are supported
    by most debug adapters and provides the interface for converting
    configurations to adapter-specific arguments.

    Attributes
    ----------
    type : str
        The type of debugger to use (e.g., "python", "node", "java")
    request : str
        The request type ("launch" or "attach")
    name : str
        Display name for the configuration
    program : Optional[str]
        Path to the program to debug (for launch requests)
    args : List[str]
        Command line arguments to pass to the program
    cwd : Optional[str]
        Current working directory for the debug session
    env : Dict[str, str]
        Environment variables to set
    envFile : Optional[str]
        Path to .env file for environment variables
    port : Optional[int]
        Port number for debug connections (attach)
    console : Optional[str]
        Console to use for debugging output
    presentation : Optional[Dict[str, Any]]
        Controls display (order, group, hidden)
    preLaunchTask : Optional[str]
        Task to run before starting the debug session
    postDebugTask : Optional[str]
        Task to run after the debug session ends
    internalConsoleOptions : Optional[str]
        Debug console visibility control
    serverReadyAction : Optional[Dict[str, Any]]
        Auto-open URI for servers
    """

    # Class variable for launch.json type aliases. These are the "type" values
    # that VS Code uses for launch configurations
    LAUNCH_TYPE_ALIASES: ClassVar[list[str]]

    # VS Code-only fields that should be filtered before passing to DAP.
    # These are metadata/UI fields used by VS Code but not part of DAP protocol.
    # Note: 'type' is NOT filtered - adapters may use it internally for multi-mode
    # debug adapters (e.g., vscode-js-debug uses it to distinguish Node/Chrome/Edge)
    VSCODE_ONLY_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            # Metadata fields
            "request",  # VS Code request type ("launch" or "attach")
            "name",  # Display name in VS Code UI
            # UI/Task integration fields
            "presentation",  # Display order/grouping/visibility
            "preLaunchTask",  # Pre-debug task
            "postDebugTask",  # Post-debug task
            "internalConsoleOptions",  # Console visibility
            "serverReadyAction",  # Auto-open URI feature
            # VS Code internal fields (double-underscore prefix)
            "__workspaceFolder",  # Internal workspace path
            "__breakOnConditionalError",  # Internal breakpoint setting
        },
    )

    # Required fields
    type: str
    request: str
    name: str

    # Common optional fields
    program: str | None = None
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    envFile: str | None = None
    port: int | None = None
    console: str | None = None

    # VS Code specific fields
    presentation: dict[str, Any] | None = None
    preLaunchTask: str | None = None
    postDebugTask: str | None = None
    internalConsoleOptions: str | None = None
    serverReadyAction: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseLaunchConfig":
        """Create a launch configuration from a dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Raw configuration data from launch.json

        Returns
        -------
        BaseLaunchConfig
            Parsed configuration object
        """
        # Extract only the fields defined in this class
        known_fields = {
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

        filtered_data = {k: v for k, v in data.items() if k in known_fields}

        return cls(**filtered_data)

    @abstractmethod
    def to_adapter_args(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Convert launch configuration to adapter-specific arguments.

        Parameters
        ----------
        workspace_root : Optional[Path]
            Root directory for resolving relative paths

        Returns
        -------
        Dict[str, Any]
            Arguments suitable for the specific debug adapter
        """

    def resolve_path(self, path: str, workspace_root: Path | None = None) -> str:
        """Resolve a potentially relative path with VS Code variables.

        First resolves any VS Code variables (${workspaceFolder}, etc.), then
        resolves relative paths to absolute paths.

        Parameters
        ----------
        path : str
            Path to resolve (may contain VS Code variables)
        workspace_root : Optional[Path]
            Root directory for resolving relative paths and variables

        Returns
        -------
        str
            Resolved absolute path
        """
        from aidb.adapters.base.vscode_variables import VSCodeVariableResolver

        # First resolve VS Code variables
        resolver = VSCodeVariableResolver(workspace_root)
        resolved_path = resolver.resolve(path)

        # Then resolve relative paths
        path_obj = Path(resolved_path)
        if not path_obj.is_absolute() and workspace_root:
            path_obj = workspace_root / path_obj
        return normalize_path(path_obj, strict=True, return_path=False)

    def get_common_args(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Get common adapter arguments.

        This method extracts the common fields that most adapters use,
        resolves VS Code variables, and resolves any relative paths.

        Parameters
        ----------
        workspace_root : Optional[Path]
            Root directory for resolving relative paths and variables

        Returns
        -------
        Dict[str, Any]
            Common adapter arguments
        """
        from aidb.adapters.base.vscode_variables import VSCodeVariableResolver

        resolver = VSCodeVariableResolver(workspace_root)
        args: dict[str, Any] = {}

        # Resolve program path if provided (handles variables + relative paths)
        # For cross-language support, we need to distinguish between:
        # 1. File paths (Python/JS: "script.py", "app.js", "/path/to/file")
        # 2. Identifiers (Java/C#: "com.example.MainClass", "MyNamespace.Program")
        if self.program:
            program_path = Path(self.program)

            # Get known file extensions from adapter registry (cached for performance)
            from aidb.session.adapter_registry import get_all_cached_file_extensions

            known_extensions = get_all_cached_file_extensions()

            # Check if it's a file path by looking for:
            # 1. Known file extension (e.g., .py, .js, .java as actual files)
            # 2. Path separators (/ or \)
            # Note: Java class names like "com.example.Main" have dots but no
            # file extension, while files like "Main.java" have real extensions.
            suffix_lower = program_path.suffix.lower()
            has_known_extension = suffix_lower in known_extensions
            has_path_separator = ("/" in self.program) or ("\\" in self.program)

            is_file_path = has_known_extension or has_path_separator

            if is_file_path:
                args["target"] = self.resolve_path(self.program, workspace_root)
            else:
                # It's an identifier - use directly without path resolution
                args["target"] = self.program

        # Resolve variables in args list
        if self.args:
            args["args"] = [resolver.resolve(arg) for arg in self.args]

        # Resolve variables and paths in cwd
        if self.cwd:
            resolved_cwd = resolver.resolve(self.cwd)
            # Also resolve relative paths for cwd
            cwd_path = Path(resolved_cwd)
            if not cwd_path.is_absolute() and workspace_root:
                cwd_path = workspace_root / cwd_path
            args["cwd"] = normalize_path(cwd_path, strict=True, return_path=False)

        # Resolve variables in env values
        if self.env:
            args["env"] = {
                key: resolver.resolve(value) if isinstance(value, str) else value
                for key, value in self.env.items()
            }

        # Resolve variables and paths in envFile
        if self.envFile:
            args["env_file"] = self.resolve_path(self.envFile, workspace_root)

        if self.port is not None:
            args["port"] = self.port
        if self.console:
            args["console"] = self.console

        return args


class LaunchConfigFactory:
    """Factory for creating appropriate launch configuration objects."""

    # Registry of configuration types to their respective classes
    _registry: dict[str, type[BaseLaunchConfig]] = {}

    @classmethod
    def register(cls, config_type: str, config_class: type[BaseLaunchConfig]) -> None:
        """Register a launch configuration class for a specific type.

        Parameters
        ----------
        config_type : str
            The debugger type (e.g., "python", "node")
        config_class : type[BaseLaunchConfig]
            The configuration class to use for this type
        """
        cls._registry[config_type] = config_class

    @classmethod
    def create(cls, data: dict[str, Any]) -> BaseLaunchConfig:
        """Create appropriate launch config based on type.

        Parameters
        ----------
        data : Dict[str, Any]
            Raw configuration data from launch.json

        Returns
        -------
        BaseLaunchConfig
            Appropriate configuration object for the debugger type
        """
        config_type = data.get("type", "")

        # Look up the appropriate class
        config_class = cls._registry.get(config_type)

        if config_class:
            return config_class.from_dict(data)
        # Fall back to a generic implementation if type not registered
        # This would need to be a concrete class that just passes through
        msg = f"Unknown debugger type: {config_type}"
        raise ValueError(msg)

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get list of supported debugger types.

        Returns
        -------
        List[str]
            List of registered debugger types
        """
        return list(cls._registry.keys())
