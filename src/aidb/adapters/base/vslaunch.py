"""VS Code launch.json configuration support.

This module provides management of VS Code launch.json configurations using the factory-
based configuration system with language-specific support.
"""

import warnings
from pathlib import Path
from typing import Any

# Import the new configuration system
from aidb.adapters.base.launch import BaseLaunchConfig, LaunchConfigFactory
from aidb.adapters.base.vscode_variables import (
    VSCodeVariableResolver,
)
from aidb_common.constants import Language
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_common.path import normalize_path

# Import language-specific configurations to ensure they're registered
# These imports register the configuration types in the factory
# Note: We import these lazily to avoid circular imports


class LaunchConfigurationManager:
    """Manages VS Code launch.json configurations.

    This class now uses the new factory-based configuration system for better language-
    specific support.
    """

    def __init__(self, workspace_root: str | Path | None = None):
        """Initialize the launch configuration manager.

        Parameters
        ----------
        workspace_root : Optional[Union[str, Path]]
            Root directory of the workspace. If not provided, uses current directory
        """
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.launch_json_path = self.workspace_root / ".vscode" / "launch.json"
        self.configurations: list[BaseLaunchConfig] = []
        # Store raw configs for lazy resolution
        self.raw_configurations: list[dict[str, Any]] = []
        # Pass ctx to resolver for proper logging
        from aidb.common import ensure_ctx

        ctx = ensure_ctx()
        self.resolver = VSCodeVariableResolver(self.workspace_root, ctx)
        self._ensure_configs_registered()
        self._load_configurations()

    def _ensure_configs_registered(self) -> None:
        """Ensure language-specific configurations are registered.

        This triggers the adapter registry to discover and register all adapters and
        their launch configurations.
        """
        # Import adapter registry to trigger discovery
        from aidb.session.adapter_registry import AdapterRegistry

        # Just instantiate to trigger discovery - configs registered automatically
        AdapterRegistry()

    def _load_configurations(self) -> None:
        """Load configurations from launch.json if it exists."""
        if self.launch_json_path.exists():
            try:
                data = safe_read_json(self.launch_json_path) or {}
                raw_configs = data.get("configurations", [])

                self.raw_configurations = raw_configs
                self.configurations = []
                for cfg in raw_configs:
                    try:
                        # Don't resolve variables yet - just create config objects
                        # Variable resolution happens in get_configuration() when we
                        # have target context available
                        config = LaunchConfigFactory.create(cfg)
                        self.configurations.append(config)
                    except (ValueError, Exception) as e:
                        # Skip configs that can't be parsed
                        # Note: Variable resolution errors caught in get_configuration
                        warnings.warn(
                            f"Skipping configuration: {e}",
                            stacklevel=2,
                        )
            except FileOperationError:
                self.configurations = []
                self.raw_configurations = []

    def get_configuration(
        self,
        name: str | None = None,
        index: int | None = None,
        target: str | None = None,
    ) -> BaseLaunchConfig | None:
        """Get a specific configuration by name or index.

        Parameters
        ----------
        name : Optional[str]
            Name of the configuration to retrieve
        index : Optional[int]
            Index of the configuration in the list
        target : Optional[str]
            Target file path for resolving ${file} variables

        Returns
        -------
        Optional[BaseLaunchConfig]
            The requested configuration or None if not found

        Raises
        ------
        VSCodeVariableError
            If the configuration contains unresolvable VS Code variables
        """
        if not self.configurations:
            return None

        config = None
        raw_cfg_index = None
        if name:
            for i, c in enumerate(self.configurations):
                if c.name == name:
                    config = c
                    raw_cfg_index = i
                    break
        elif index is not None and 0 <= index < len(self.configurations):
            config = self.configurations[index]
            raw_cfg_index = index

        # If target is provided and we found the config, re-resolve with target context
        if config and raw_cfg_index is not None and target:
            raw_cfg = self.raw_configurations[raw_cfg_index]
            context = {"target": target}
            # Validation happens during resolve_dict - if variables can't be resolved,
            # VSCodeVariableError will be raised here
            resolved_cfg = self.resolver.resolve_dict(raw_cfg, context)
            config = LaunchConfigFactory.create(resolved_cfg)

        return config

    def list_configurations(self) -> list[str]:
        """List all available configuration names.

        Returns
        -------
        List[str]
            List of configuration names
        """
        return [config.name for config in self.configurations]

    def find_configuration_for_file(self, file_path: str) -> BaseLaunchConfig | None:
        """Find a suitable configuration for a given file.

        Parameters
        ----------
        file_path : str
            Path to the file to debug

        Returns
        -------
        Optional[BaseLaunchConfig]
            A matching configuration or None
        """
        file_path_obj = normalize_path(file_path, strict=True, return_path=True)

        for config in self.configurations:
            # Check if the program matches
            if config.program:
                config_program = Path(config.program)
                if not config_program.is_absolute():
                    config_program = self.workspace_root / config_program
                config_program = normalize_path(
                    config_program,
                    strict=True,
                    return_path=True,
                )
                if config_program == file_path_obj:
                    return config

        return None

    def create_default_configuration(
        self,
        file_path: str,
        language: str,
    ) -> BaseLaunchConfig:
        """Create a default configuration for a file.

        Parameters
        ----------
        file_path : str
            Path to the file to debug
        language : str
            Programming language

        Returns
        -------
        BaseLaunchConfig
            A default configuration for the file
        """
        file_path_obj = Path(file_path)
        relative_path = (
            file_path_obj.relative_to(self.workspace_root)
            if file_path_obj.is_absolute()
            else file_path_obj
        )

        config_data: dict[str, Any] = {
            "type": language,
            "request": "launch",
            "name": f"Debug {file_path_obj.name}",
            "program": str(relative_path),
        }

        # Language-specific defaults
        if language in (Language.PYTHON, "debugpy"):
            config_data["type"] = "debugpy"  # Ensure correct type
            config_data["console"] = "integratedTerminal"
            config_data["justMyCode"] = True
        elif language in (Language.JAVASCRIPT, "node", "nodejs", "typescript"):
            config_data["type"] = "pwa-node"  # Use modern Node debugger
            config_data["console"] = "integratedTerminal"
            config_data["skipFiles"] = ["<node_internals>/**"]
        elif language == Language.JAVA:
            config_data["type"] = "java"
            config_data["mainClass"] = file_path_obj.stem  # Use filename as class name
        elif language == "go":
            config_data["mode"] = "debug"

        try:
            return LaunchConfigFactory.create(config_data)
        except ValueError as e:
            # Create a generic base config if type not registered
            msg = f"Unsupported language type '{language}': {e}"
            raise ValueError(msg) from e


def resolve_launch_configuration(
    target: str | None = None,
    config_name: str | None = None,
    workspace_root: str | None = None,
    language: str | None = None,
) -> BaseLaunchConfig | None:
    """Resolve a launch configuration from various sources.

    This is a convenience function that tries to find an appropriate launch
    configuration based on the provided parameters.

    Parameters
    ----------
    target : Optional[str]
        Path to the file to debug
    config_name : Optional[str]
        Name of a specific configuration to use
    workspace_root : Optional[str]
        Root directory of the workspace
    language : Optional[str]
        Programming language (used for creating default configs)

    Returns
    -------
    Optional[BaseLaunchConfig]
        A resolved configuration or None
    """
    manager = LaunchConfigurationManager(workspace_root)

    # Try to get by name first
    if config_name:
        config = manager.get_configuration(name=config_name)
        if config:
            return config

    # Try to find a configuration for the target file
    if target:
        config = manager.find_configuration_for_file(target)
        if config:
            return config

        # Create a default configuration if language is specified
        if language:
            return manager.create_default_configuration(target, language)

    # Return the first configuration if available
    if manager.configurations:
        return manager.configurations[0]

    return None
