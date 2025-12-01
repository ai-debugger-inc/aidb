"""Integration tests for full variable resolution pipeline.

Tests end-to-end variable resolution with real filesystem paths, environment variables,
and configuration objects.
"""

import json
import os
from pathlib import Path

import pytest

from aidb.adapters.base.vscode_variables import VSCodeVariableResolver
from aidb.adapters.base.vslaunch import LaunchConfigurationManager
from aidb.common.errors import VSCodeVariableError
from tests._helpers.launch_test_utils import LaunchConfigTestHelper
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class TestVariableResolution(BaseDebugTest):
    """Test full variable resolution pipeline with filesystem interaction."""

    def test_resolve_variables_to_absolute_paths(self, temp_workspace: Path):
        """Resolve all variables to absolute filesystem paths.

        Verifies:
        - ${workspaceFolder} -> absolute workspace path
        - ${file} -> absolute file path (with context)
        - ${env:HOME} -> actual environment value
        - All paths are absolute and valid

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Create test file structure
        src_dir = temp_workspace / "src"
        src_dir.mkdir(exist_ok=True)
        test_file = src_dir / "main.py"
        test_file.write_text("print('test')")

        context = {"target": str(test_file)}

        # Resolve workspaceFolder
        workspace_path = resolver.resolve("${workspaceFolder}")
        assert Path(workspace_path).is_absolute()
        assert Path(workspace_path) == temp_workspace

        # Resolve file with context
        file_path = resolver.resolve("${file}", context=context)
        assert Path(file_path).is_absolute()
        assert Path(file_path) == test_file
        assert Path(file_path).exists()

        # Resolve env var
        home_path = resolver.resolve("${env:HOME}")
        assert Path(home_path).is_absolute()
        assert Path(home_path).exists()

    def test_resolve_nested_paths(self, temp_workspace: Path):
        """Resolve deeply nested paths with variables.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Create nested directory structure
        deep_path = temp_workspace / "src" / "main" / "python" / "pkg"
        deep_path.mkdir(parents=True, exist_ok=True)

        # Resolve nested path
        result = resolver.resolve("${workspaceFolder}/src/main/python/pkg/module.py")
        expected = str(temp_workspace / "src/main/python/pkg/module.py")
        assert result == expected

    def test_full_resolution_pipeline(self, temp_workspace: Path):
        """Test complete resolution pipeline: parse -> substitute -> resolve.

        Verifies the full workflow:
        1. Create launch.json with variables
        2. Load configuration
        3. Resolve all variables
        4. Verify final config has concrete values

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Set environment variable for test
        os.environ["AIDB_TEST_ENV"] = "development"

        try:
            # Create test file
            app_file = temp_workspace / "app.py"
            app_file.write_text("print('app')")

            # Create launch.json with variables
            helper.create_test_launch_json(
                [
                    {
                        "type": "debugpy",
                        "request": "launch",
                        "name": "Debug App",
                        "program": "${workspaceFolder}/app.py",
                        "cwd": "${workspaceFolder}",
                        "env": {
                            "ENVIRONMENT": "${env:AIDB_TEST_ENV}",
                        },
                    },
                ],
            )

            # Load configuration
            manager = LaunchConfigurationManager(workspace_root=temp_workspace)
            config = manager.get_configuration(name="Debug App")
            assert config is not None

            # Verify variables in config (before resolution via target)
            assert "${workspaceFolder}" in config.program
            assert "${workspaceFolder}" in config.cwd

            # Resolve variables using helper
            resolved_config = helper.resolve_config_variables(config)

            # Verify all variables resolved to absolute paths
            assert str(temp_workspace) in resolved_config.program
            assert "app.py" in resolved_config.program
            assert Path(resolved_config.program).is_absolute()

            assert str(temp_workspace) == resolved_config.cwd
            assert Path(resolved_config.cwd).is_absolute()

        finally:
            del os.environ["AIDB_TEST_ENV"]

    def test_resolve_with_environment_variables(self, temp_workspace: Path):
        """Resolve environment variables to actual values.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Set multiple test environment variables
        os.environ["AIDB_TEST_PATH"] = "/custom/test/path"
        os.environ["AIDB_TEST_NAME"] = "myproject"
        os.environ["AIDB_TEST_VERSION"] = "1.0.0"

        try:
            # Resolve single env var
            result1 = resolver.resolve("${env:AIDB_TEST_PATH}")
            assert result1 == "/custom/test/path"

            # Resolve env var in path
            result2 = resolver.resolve("${env:AIDB_TEST_PATH}/config.json")
            assert result2 == "/custom/test/path/config.json"

            # Multiple env vars
            result3 = resolver.resolve("${env:AIDB_TEST_NAME}-${env:AIDB_TEST_VERSION}")
            assert result3 == "myproject-1.0.0"

            # Mix with workspace variable
            result4 = resolver.resolve(
                "${workspaceFolder}/${env:AIDB_TEST_NAME}/output",
            )
            assert result4 == f"{temp_workspace}/myproject/output"

        finally:
            del os.environ["AIDB_TEST_PATH"]
            del os.environ["AIDB_TEST_NAME"]
            del os.environ["AIDB_TEST_VERSION"]

    def test_handle_missing_variables_in_config(self, temp_workspace: Path):
        """Handle unresolvable variables in configuration gracefully.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)

        # Create config with ${file} variable (needs context)
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Current File",
                    program="${file}",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Current File")
        assert config is not None

        # Trying to validate without target context should raise error
        with pytest.raises(VSCodeVariableError) as exc_info:
            helper.assert_config_valid(config, "Current File")

        error_msg = str(exc_info.value)
        assert "${file}" in error_msg
        assert "target" in error_msg.lower()

    def test_variable_resolution_edge_cases(self, temp_workspace: Path):
        """Test edge cases in variable resolution.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Empty string after resolution
        result1 = resolver.resolve("")
        assert result1 == ""

        # Only variables, no surrounding text
        result2 = resolver.resolve("${workspaceFolder}")
        assert result2 == str(temp_workspace)

        # Variables at different positions
        result3 = resolver.resolve(
            "prefix-${workspaceFolder}-suffix",
        )
        assert result3 == f"prefix-{temp_workspace}-suffix"

        # Multiple same variables
        result4 = resolver.resolve(
            "${workspaceFolder}:${workspaceFolder}",
        )
        assert result4 == f"{temp_workspace}:{temp_workspace}"
