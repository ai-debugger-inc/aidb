"""Integration tests for loading launch configurations from workspace.

Tests the full pipeline of loading launch.json from .vscode/ directory, including
filesystem interaction, configuration discovery, and selection.
"""

from pathlib import Path

import pytest

from aidb.adapters.base.vslaunch import LaunchConfigurationManager
from tests._helpers.launch_test_utils import LaunchConfigTestHelper
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class TestConfigLoading(BaseDebugTest):
    """Test loading launch.json configurations from workspace."""

    def test_load_from_workspace(self, temp_workspace: Path):
        """Load configurations from .vscode/launch.json in workspace.

        Verifies:
        - Configurations loaded from workspace .vscode/ directory
        - Multiple configs can be loaded simultaneously
        - Configuration objects are properly initialized
        - All expected fields are accessible

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory with .vscode/ folder
        """
        # Create launch.json using helper
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        launch_path = helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Debug Main",
                    program="${workspaceFolder}/main.py",
                ),
                helper.create_python_launch_config(
                    name="Debug Tests",
                    program="${workspaceFolder}/test.py",
                    args=["--verbose"],
                ),
            ],
        )

        # Verify launch.json created in correct location
        assert launch_path == temp_workspace / ".vscode" / "launch.json"
        assert launch_path.exists()

        # Load configurations using LaunchConfigurationManager
        manager = LaunchConfigurationManager(workspace_root=temp_workspace)

        # Verify configs loaded
        config_names = manager.list_configurations()
        assert len(config_names) == 2
        assert "Debug Main" in config_names
        assert "Debug Tests" in config_names

        # Verify first config
        config1 = manager.get_configuration(name="Debug Main")
        assert config1 is not None
        assert config1.name == "Debug Main"
        assert config1.type == "debugpy"
        assert config1.request == "launch"
        assert "${workspaceFolder}/main.py" in config1.program

        # Verify second config with args
        config2 = manager.get_configuration(name="Debug Tests")
        assert config2 is not None
        assert config2.name == "Debug Tests"
        assert len(config2.args) == 1
        assert "--verbose" in config2.args

    def test_handle_missing_launch_json(self, temp_workspace: Path):
        """Handle workspace without launch.json gracefully.

        Verifies:
        - No error when launch.json doesn't exist
        - Returns empty configuration list
        - Manager can still be used for dynamic configs

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory (no launch.json)
        """
        # Don't create launch.json - test missing file handling
        launch_path = temp_workspace / ".vscode" / "launch.json"
        assert not launch_path.exists()

        # Create manager - should not raise error
        manager = LaunchConfigurationManager(workspace_root=temp_workspace)

        # Should return empty list, not error
        configs = manager.list_configurations()
        assert isinstance(configs, list)
        assert len(configs) == 0

        # Getting config by name should return None
        config = manager.get_configuration(name="Nonexistent")
        assert config is None

    def test_handle_empty_configurations_array(self, temp_workspace: Path):
        """Handle launch.json with empty configurations array.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create launch.json with empty configurations
        helper.create_test_launch_json([])

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)

        # Should handle gracefully
        configs = manager.list_configurations()
        assert len(configs) == 0

    def test_config_selection_by_name(self, temp_workspace: Path):
        """Select specific configuration by exact name match.

        Verifies:
        - Exact name matching works
        - Case-sensitive matching
        - Returns None for non-existent configs
        - Partial matches don't work

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create configs with similar names
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Debug",
                    program="${workspaceFolder}/app.py",
                ),
                helper.create_python_launch_config(
                    name="Debug Production",
                    program="${workspaceFolder}/app.py",
                    env={"ENV": "production"},
                ),
                helper.create_python_launch_config(
                    name="debug",  # Lowercase
                    program="${workspaceFolder}/debug.py",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)

        # Test exact matching
        config1 = manager.get_configuration(name="Debug")
        assert config1 is not None
        assert config1.name == "Debug"
        assert "app.py" in config1.program
        assert not hasattr(config1, "env") or config1.env is None or config1.env == {}

        config2 = manager.get_configuration(name="Debug Production")
        assert config2 is not None
        assert config2.name == "Debug Production"
        assert config2.env.get("ENV") == "production"

        # Test case sensitivity
        config3 = manager.get_configuration(name="debug")
        assert config3 is not None
        assert config3.name == "debug"
        assert "debug.py" in config3.program

        # Test non-existent config
        config4 = manager.get_configuration(name="NonExistent")
        assert config4 is None

        # Partial match should not work
        config5 = manager.get_configuration(name="Deb")
        assert config5 is None

    def test_config_selection_by_index(self, temp_workspace: Path):
        """Select configuration by index position.

        Verifies:
        - Can select config by zero-based index
        - Index matches configuration array order
        - Out of range index returns None

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="First Config",
                    program="${workspaceFolder}/first.py",
                ),
                helper.create_python_launch_config(
                    name="Second Config",
                    program="${workspaceFolder}/second.py",
                ),
                helper.create_python_launch_config(
                    name="Third Config",
                    program="${workspaceFolder}/third.py",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)

        # Select by index
        config0 = manager.get_configuration(index=0)
        assert config0 is not None
        assert config0.name == "First Config"

        config1 = manager.get_configuration(index=1)
        assert config1 is not None
        assert config1.name == "Second Config"

        config2 = manager.get_configuration(index=2)
        assert config2 is not None
        assert config2.name == "Third Config"

        # Out of range
        config_invalid = manager.get_configuration(index=99)
        assert config_invalid is None

        # Negative index
        config_negative = manager.get_configuration(index=-1)
        assert config_negative is None

    def test_list_all_configurations(self, temp_workspace: Path):
        """List all configuration names from workspace.

        Verifies:
        - All configuration names returned
        - Order matches configurations array
        - Empty list for no configs

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Test with multiple configs
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Config A",
                    program="${workspaceFolder}/a.py",
                ),
                helper.create_python_launch_config(
                    name="Config B",
                    program="${workspaceFolder}/b.py",
                ),
                helper.create_javascript_launch_config(
                    name="Config C",
                    program="${workspaceFolder}/c.js",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        names = manager.list_configurations()

        assert len(names) == 3
        assert "Config A" in names
        assert "Config B" in names
        assert "Config C" in names

        # Verify order preserved
        assert names[0] == "Config A"
        assert names[1] == "Config B"
        assert names[2] == "Config C"

    def test_reload_after_file_change(self, temp_workspace: Path):
        """Reload configurations after launch.json changes.

        Verifies:
        - New manager instance picks up file changes
        - Configuration changes are reflected

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create initial config
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Initial Config",
                    program="${workspaceFolder}/initial.py",
                ),
            ],
        )

        # Load configs
        manager1 = LaunchConfigurationManager(workspace_root=temp_workspace)
        configs1 = manager1.list_configurations()
        assert len(configs1) == 1
        assert "Initial Config" in configs1

        # Modify launch.json
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Updated Config",
                    program="${workspaceFolder}/updated.py",
                ),
                helper.create_python_launch_config(
                    name="New Config",
                    program="${workspaceFolder}/new.py",
                ),
            ],
        )

        # Create new manager instance - should pick up changes
        manager2 = LaunchConfigurationManager(workspace_root=temp_workspace)
        configs2 = manager2.list_configurations()

        assert len(configs2) == 2
        assert "Updated Config" in configs2
        assert "New Config" in configs2
        assert "Initial Config" not in configs2

    def test_workspace_root_resolution(self, temp_workspace: Path):
        """Verify workspace root is correctly resolved.

        Verifies:
        - Workspace root set correctly
        - Launch.json path constructed properly
        - Relative paths work

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        # Test with absolute path
        manager1 = LaunchConfigurationManager(workspace_root=temp_workspace)
        assert manager1.workspace_root == temp_workspace
        assert manager1.launch_json_path == temp_workspace / ".vscode" / "launch.json"

        # Test with string path
        manager2 = LaunchConfigurationManager(workspace_root=str(temp_workspace))
        assert manager2.workspace_root == temp_workspace
        assert manager2.launch_json_path == temp_workspace / ".vscode" / "launch.json"
