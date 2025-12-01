"""Thin wrappers around core launch.json infrastructure for test convenience.

This module provides minimal helper utilities for tests that work with
VS Code launch configurations. It wraps core's LaunchConfigurationManager
and VSCodeVariableResolver without reimplementing their functionality.

The goal is test convenience only - all real work is delegated to core.
"""

from pathlib import Path
from typing import Any

from aidb.adapters.base.vscode_variables import VSCodeVariableResolver
from aidb.adapters.base.vslaunch import LaunchConfigurationManager


class LaunchConfigTestHelper:
    """Test helper for working with launch configurations.

    Thin wrapper around core's LaunchConfigurationManager and
    VSCodeVariableResolver for common test patterns.

    Examples
    --------
    >>> helper = LaunchConfigTestHelper(workspace_root=Path("/workspace"))
    >>> helper.create_test_launch_json([
    ...     {
    ...         "type": "debugpy",
    ...         "request": "launch",
    ...         "name": "Test Config",
    ...         "program": "${workspaceFolder}/app.py"
    ...     }
    ... ])
    >>> config = helper.get_config("Test Config")
    >>> assert config is not None
    """

    def __init__(self, workspace_root: Path | None = None):
        """Initialize helper with workspace root.

        Parameters
        ----------
        workspace_root : Path, optional
            Workspace root directory, defaults to current directory
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.launch_json_path = self.workspace_root / ".vscode" / "launch.json"
        self.manager: LaunchConfigurationManager | None = None
        self.resolver = VSCodeVariableResolver(self.workspace_root)

    def create_test_launch_json(
        self,
        configurations: list[dict[str, Any]],
        version: str = "0.2.0",
    ) -> Path:
        """Create a test launch.json file with given configurations.

        Parameters
        ----------
        configurations : list[dict[str, Any]]
            List of launch configuration dictionaries
        version : str
            Launch.json schema version, default "0.2.0"

        Returns
        -------
        Path
            Path to created launch.json file

        Examples
        --------
        >>> helper.create_test_launch_json([
        ...     {
        ...         "type": "debugpy",
        ...         "request": "launch",
        ...         "name": "Python: Current File",
        ...         "program": "${file}"
        ...     }
        ... ])
        """
        import json

        self.launch_json_path.parent.mkdir(parents=True, exist_ok=True)

        launch_data = {"version": version, "configurations": configurations}

        self.launch_json_path.write_text(json.dumps(launch_data, indent=4))

        self.manager = LaunchConfigurationManager(self.workspace_root)

        return self.launch_json_path

    def get_config(self, name: str) -> Any:
        """Get a configuration by name using core's manager.

        Parameters
        ----------
        name : str
            Configuration name

        Returns
        -------
        BaseLaunchConfig, optional
            Configuration object or None
        """
        if not self.manager:
            self.manager = LaunchConfigurationManager(self.workspace_root)

        return self.manager.get_configuration(name=name)

    def get_all_configs(self) -> list[str]:
        """Get all configuration names using core's manager.

        Returns
        -------
        list[str]
            List of configuration names
        """
        if not self.manager:
            self.manager = LaunchConfigurationManager(self.workspace_root)

        return self.manager.list_configurations()

    def resolve_variables(self, value: str) -> str:
        """Resolve VS Code variables in a string using core's resolver.

        Parameters
        ----------
        value : str
            String potentially containing variables

        Returns
        -------
        str
            String with resolved variables

        Examples
        --------
        >>> helper.resolve_variables("${workspaceFolder}/src")
        '/workspace/src'
        """
        return self.resolver.resolve(value)

    def resolve_config_variables(self, config: Any) -> Any:
        """Resolve all variables in a configuration.

        Parameters
        ----------
        config : BaseLaunchConfig
            Configuration with potential variables

        Returns
        -------
        BaseLaunchConfig
            Configuration with resolved variables
        """
        if hasattr(config, "program") and config.program:
            config.program = self.resolver.resolve(config.program)

        if hasattr(config, "cwd") and config.cwd:
            config.cwd = self.resolver.resolve(config.cwd)

        if hasattr(config, "args") and config.args:
            config.args = [
                self.resolver.resolve(arg) if isinstance(arg, str) else arg
                for arg in config.args
            ]

        return config

    def assert_config_valid(self, config: Any, config_name: str = "unknown"):
        """Assert that a configuration is valid using core's validator.

        Parameters
        ----------
        config : BaseLaunchConfig
            Configuration to validate
        config_name : str
            Configuration name for error messages

        Raises
        ------
        AssertionError
            If configuration is invalid
        VSCodeVariableError
            If configuration has unresolvable variables
        """
        assert config is not None, f"Configuration '{config_name}' not found"

        self.resolver.validate_launch_config(config, config_name)

    def create_python_launch_config(
        self,
        name: str,
        program: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a Python launch configuration dictionary.

        Convenience method for creating Python debug configurations.

        Parameters
        ----------
        name : str
            Configuration name
        program : str
            Python file to debug
        **kwargs
            Additional configuration fields

        Returns
        -------
        dict[str, Any]
            Launch configuration dictionary
        """
        config = {
            "type": "debugpy",
            "request": "launch",
            "name": name,
            "program": program,
            "console": "integratedTerminal",
            "justMyCode": True,
        }
        config.update(kwargs)
        return config

    def create_javascript_launch_config(
        self,
        name: str,
        program: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a JavaScript/Node launch configuration dictionary.

        Parameters
        ----------
        name : str
            Configuration name
        program : str
            JavaScript file to debug
        **kwargs
            Additional configuration fields

        Returns
        -------
        dict[str, Any]
            Launch configuration dictionary
        """
        config = {
            "type": "pwa-node",
            "request": "launch",
            "name": name,
            "program": program,
            "console": "integratedTerminal",
            "skipFiles": ["<node_internals>/**"],
        }
        config.update(kwargs)
        return config

    def create_java_launch_config(
        self,
        name: str,
        main_class: str,
        **kwargs,
    ) -> dict[str, Any]:
        """Create a Java launch configuration dictionary.

        Parameters
        ----------
        name : str
            Configuration name
        main_class : str
            Main class name
        **kwargs
            Additional configuration fields

        Returns
        -------
        dict[str, Any]
            Launch configuration dictionary
        """
        config = {
            "type": "java",
            "request": "launch",
            "name": name,
            "mainClass": main_class,
        }
        config.update(kwargs)
        return config
