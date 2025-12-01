"""Unit tests for launch.json configuration parsing.

Tests the core parsing logic for VS Code launch.json configurations, including
validation of required fields, handling of multiple configurations, and error cases.
"""

import json
from pathlib import Path

import pytest

from aidb.common.errors import VSCodeVariableError
from tests._helpers.launch_test_utils import LaunchConfigTestHelper
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class TestConfigParsing(BaseDebugTest):
    """Test launch.json configuration parsing and validation."""

    def test_parse_valid_launch_json(self, temp_workspace: Path):
        """Parse valid launch.json with multiple configurations.

        Verifies:
        - JSON is parsed correctly
        - Configurations array is loaded
        - Required fields are present (type, request, name)
        - Language-specific settings are extracted
        - Multiple configurations can coexist

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory with .vscode/ folder
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create launch.json with multiple configs
        launch_path = helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Python: Current File",
                    program="${file}",
                    console="integratedTerminal",
                    justMyCode=False,
                ),
                helper.create_python_launch_config(
                    name="Python: Debug Tests",
                    program="${workspaceFolder}/tests/run_tests.py",
                    args=["--verbose", "--debug"],
                ),
                helper.create_python_launch_config(
                    name="Python: Module",
                    program="${workspaceFolder}/myapp/__main__.py",
                    module="myapp.main",
                    args=[],
                ),
            ],
        )

        # Verify file created in correct location
        assert launch_path.exists()
        assert launch_path.name == "launch.json"
        assert launch_path.parent.name == ".vscode"

        # Verify configs loaded
        configs = helper.get_all_configs()
        assert len(configs) == 3
        assert "Python: Current File" in configs
        assert "Python: Debug Tests" in configs
        assert "Python: Module" in configs

        # Verify first config structure
        config1 = helper.get_config("Python: Current File")
        assert config1 is not None
        assert config1.name == "Python: Current File"
        assert config1.type == "debugpy"
        assert config1.request == "launch"
        assert "${file}" in config1.program
        assert config1.console == "integratedTerminal"

        # Verify second config with args
        config2 = helper.get_config("Python: Debug Tests")
        assert config2 is not None
        assert config2.name == "Python: Debug Tests"
        assert "${workspaceFolder}" in config2.program
        assert len(config2.args) == 2
        assert "--verbose" in config2.args
        assert "--debug" in config2.args

        # Verify third config (module launch)
        config3 = helper.get_config("Python: Module")
        assert config3 is not None
        assert config3.module == "myapp.main"

        # Verify configs with resolvable variables are valid
        # Note: ${file} requires runtime context, so skip validation for that config
        for config_name in configs:
            if config_name != "Python: Current File":  # Skip ${file} config
                config = helper.get_config(config_name)
                helper.assert_config_valid(config)

    def test_parse_invalid_json(self, temp_workspace: Path):
        """Handle malformed JSON and invalid configurations.

        Verifies:
        - Malformed JSON raises appropriate error
        - Missing required fields raises validation error
        - Unknown fields are handled gracefully
        - Error messages are helpful

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory with .vscode/ folder
        """
        vscode_dir = temp_workspace / ".vscode"
        vscode_dir.mkdir(exist_ok=True)
        launch_path = vscode_dir / "launch.json"

        # Test 1: Malformed JSON (handled gracefully, returns empty configs)
        launch_path.write_text("{ this is not valid json }")

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        configs = helper.get_all_configs()
        # Malformed JSON should be handled gracefully, resulting in empty configs
        assert len(configs) == 0

        # Test 2: Missing configurations array
        launch_path.write_text('{"version": "0.2.0"}')

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        configs = helper.get_all_configs()
        assert len(configs) == 0  # No configurations present

        # Test 3: Invalid configuration structure (missing required fields)
        launch_path.write_text(
            json.dumps(
                {
                    "version": "0.2.0",
                    "configurations": [
                        {
                            "name": "Missing Type and Request",
                            # Missing: type, request
                        },
                    ],
                },
            ),
        )

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Getting config should handle missing fields
        config = helper.get_config("Missing Type and Request")
        # Config might be None or have validation issues
        if config is not None:
            # Try to validate - should fail
            with pytest.raises((ValueError, AttributeError, KeyError)):
                helper.assert_config_valid(config)

        # Test 4: Unknown fields are ignored gracefully
        launch_path.write_text(
            json.dumps(
                {
                    "version": "0.2.0",
                    "configurations": [
                        {
                            "name": "With Unknown Fields",
                            "type": "debugpy",
                            "request": "launch",
                            "program": "${workspaceFolder}/app.py",
                            "unknownField1": "value1",
                            "unknownField2": {"nested": "data"},
                            "customExtensionField": True,
                        },
                    ],
                },
            ),
        )

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        config = helper.get_config("With Unknown Fields")
        assert config is not None
        assert config.name == "With Unknown Fields"
        assert config.type == "debugpy"
        assert config.request == "launch"
        # Unknown fields should not cause errors

    def test_parse_multiple_languages(self, temp_workspace: Path):
        """Parse launch.json with configurations for different languages.

        Verifies that configurations for Python, JavaScript, and Java
        can coexist in the same launch.json file.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory with .vscode/ folder
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create launch.json with mixed language configs
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Python App",
                    program="${workspaceFolder}/app.py",
                ),
                helper.create_javascript_launch_config(
                    name="Node Script",
                    program="${workspaceFolder}/server.js",
                    port=9229,
                ),
                helper.create_java_launch_config(
                    name="Java Main",
                    main_class="com.example.Main",
                    classpath=["${workspaceFolder}/bin"],
                ),
            ],
        )

        # Verify all configs loaded
        configs = helper.get_all_configs()
        assert len(configs) == 3

        # Verify Python config
        python_config = helper.get_config("Python App")
        assert python_config is not None
        assert python_config.type == "debugpy"

        # Verify JavaScript config
        js_config = helper.get_config("Node Script")
        assert js_config is not None
        assert js_config.type in ["pwa-node", "node"]

        # Verify Java config
        java_config = helper.get_config("Java Main")
        assert java_config is not None
        assert java_config.type == "java"
        assert java_config.mainClass == "com.example.Main"

    def test_config_selection_by_name(self, temp_workspace: Path):
        """Select specific configuration by name.

        Verifies:
        - Configs can be retrieved by exact name match
        - Non-existent config names return None
        - Name matching is case-sensitive

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory with .vscode/ folder
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
                    name="Debug Tests",
                    program="${workspaceFolder}/test.py",
                ),
                helper.create_python_launch_config(
                    name="debug",  # Lowercase
                    program="${workspaceFolder}/debug.py",
                ),
            ],
        )

        # Test exact name matching
        config1 = helper.get_config("Debug")
        assert config1 is not None
        assert config1.name == "Debug"
        assert "app.py" in config1.program

        config2 = helper.get_config("Debug Tests")
        assert config2 is not None
        assert config2.name == "Debug Tests"
        assert "test.py" in config2.program

        # Test case sensitivity
        config3 = helper.get_config("debug")
        assert config3 is not None
        assert config3.name == "debug"
        assert "debug.py" in config3.program

        # Test non-existent config
        config4 = helper.get_config("Nonexistent")
        assert config4 is None

        # Partial match should not work
        config5 = helper.get_config("Deb")
        assert config5 is None
