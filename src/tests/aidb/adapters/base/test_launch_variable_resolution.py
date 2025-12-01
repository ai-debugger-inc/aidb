"""Tests for VS Code variable resolution in launch configurations."""

import os
from pathlib import Path

import pytest

from aidb.adapters.lang.python.config import PythonLaunchConfig
from aidb.common.errors import VSCodeVariableError


class TestLaunchConfigVariableResolution:
    """Test variable resolution in BaseLaunchConfig.get_common_args()."""

    @pytest.fixture
    def workspace_root(self, tmp_path: Path) -> Path:
        """Create a temporary workspace directory.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture

        Returns
        -------
        Path
            Temporary workspace directory
        """
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        return workspace

    def test_resolve_program_with_workspace_folder(self, workspace_root: Path):
        """Test resolving ${workspaceFolder} in program field."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="${workspaceFolder}/src/app.py",
        )

        args = config.get_common_args(workspace_root)

        assert "target" in args
        assert args["target"] == str(workspace_root / "src/app.py")
        assert "${workspaceFolder}" not in args["target"]

    def test_resolve_cwd_with_workspace_folder(self, workspace_root: Path):
        """Test resolving ${workspaceFolder} in cwd field."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            cwd="${workspaceFolder}/src",
        )

        args = config.get_common_args(workspace_root)

        assert "cwd" in args
        assert args["cwd"] == str(workspace_root / "src")
        assert "${workspaceFolder}" not in args["cwd"]

    def test_resolve_args_with_workspace_folder(self, workspace_root: Path):
        """Test resolving ${workspaceFolder} in args list."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            args=["--config", "${workspaceFolder}/config.json", "--verbose"],
        )

        args = config.get_common_args(workspace_root)

        assert "args" in args
        assert len(args["args"]) == 3
        assert args["args"][0] == "--config"
        assert args["args"][1] == str(workspace_root / "config.json")
        assert args["args"][2] == "--verbose"
        assert "${workspaceFolder}" not in args["args"][1]

    def test_resolve_env_values_with_workspace_folder(self, workspace_root: Path):
        """Test resolving ${workspaceFolder} in environment variable values."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            env={
                "DATA_DIR": "${workspaceFolder}/data",
                "DEBUG": "true",
                "LOG_PATH": "${workspaceFolder}/logs/app.log",
            },
        )

        args = config.get_common_args(workspace_root)

        assert "env" in args
        assert args["env"]["DATA_DIR"] == str(workspace_root / "data")
        assert args["env"]["DEBUG"] == "true"
        assert args["env"]["LOG_PATH"] == str(workspace_root / "logs/app.log")
        assert "${workspaceFolder}" not in args["env"]["DATA_DIR"]
        assert "${workspaceFolder}" not in args["env"]["LOG_PATH"]

    def test_resolve_env_file_with_workspace_folder(self, workspace_root: Path):
        """Test resolving ${workspaceFolder} in envFile field."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            envFile="${workspaceFolder}/.env",
        )

        args = config.get_common_args(workspace_root)

        assert "env_file" in args
        assert args["env_file"] == str(workspace_root / ".env")
        assert "${workspaceFolder}" not in args["env_file"]

    def test_resolve_workspace_folder_basename(self, workspace_root: Path):
        """Test resolving ${workspaceFolderBasename} variable."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            args=["--project", "${workspaceFolderBasename}"],
        )

        args = config.get_common_args(workspace_root)

        assert "args" in args
        assert args["args"][1] == workspace_root.name
        assert "${workspaceFolderBasename}" not in args["args"][1]

    def test_resolve_env_variable(self, workspace_root: Path):
        """Test resolving ${env:VAR_NAME} environment variables."""
        # Set a test environment variable
        os.environ["TEST_VAR"] = "test_value"

        try:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program="app.py",
                args=["--value", "${env:TEST_VAR}"],
            )

            args = config.get_common_args(workspace_root)

            assert "args" in args
            assert args["args"][1] == "test_value"
            assert "${env:TEST_VAR}" not in args["args"][1]
        finally:
            del os.environ["TEST_VAR"]

    def test_resolve_missing_env_variable_raises_error(self, workspace_root: Path):
        """Test that referencing undefined env variable raises error."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
            args=["${env:UNDEFINED_VAR}"],
        )

        with pytest.raises(VSCodeVariableError, match="Environment variable"):
            config.get_common_args(workspace_root)

    def test_mixed_variables_and_relative_paths(self, workspace_root: Path):
        """Test resolving both variables and relative paths."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="${workspaceFolder}/src/app.py",
            cwd="${workspaceFolder}",
            args=["--data", "${workspaceFolder}/data", "--output", "output.txt"],
        )

        args = config.get_common_args(workspace_root)

        # Check program (variables resolved, then made absolute)
        assert args["target"] == str(workspace_root / "src/app.py")

        # Check cwd (variables resolved, then made absolute)
        assert args["cwd"] == str(workspace_root)

        # Check args (variables resolved, but relative paths stay relative)
        assert args["args"][1] == str(workspace_root / "data")
        assert args["args"][3] == "output.txt"  # Relative path preserved

    def test_absolute_path_without_variables(self, workspace_root: Path):
        """Test that absolute paths without variables still work."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="/absolute/path/to/app.py",
        )

        args = config.get_common_args(workspace_root)

        assert args["target"] == "/absolute/path/to/app.py"

    def test_relative_path_without_variables(self, workspace_root: Path):
        """Test that relative paths without variables are resolved."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="src/app.py",
        )

        args = config.get_common_args(workspace_root)

        assert args["target"] == str(workspace_root / "src/app.py")

    def test_no_workspace_root_with_variables_raises_error(self):
        """Test that variables without workspace_root use cwd as fallback."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="${workspaceFolder}/app.py",
        )

        # When workspace_root is None, VSCodeVariableResolver uses Path.cwd()
        args = config.get_common_args(workspace_root=None)

        # Should resolve to current working directory
        assert args["target"] == str(Path.cwd() / "app.py")

    def test_empty_fields_not_in_output(self, workspace_root: Path):
        """Test that empty optional fields are not included in output."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
        )

        args = config.get_common_args(workspace_root)

        # Only target should be present (from program)
        assert "target" in args
        assert "args" not in args
        assert "cwd" not in args
        assert "env" not in args
        assert "env_file" not in args

    def test_resolve_path_method_directly(self, workspace_root: Path):
        """Test the resolve_path method directly."""
        config = PythonLaunchConfig(
            type="python",
            request="launch",
            name="Test",
            program="app.py",
        )

        # Test with workspace variable
        result = config.resolve_path("${workspaceFolder}/src/app.py", workspace_root)
        assert result == str(workspace_root / "src/app.py")
        assert "${workspaceFolder}" not in result

        # Test with relative path only
        result = config.resolve_path("src/app.py", workspace_root)
        assert result == str(workspace_root / "src/app.py")

        # Test with absolute path
        result = config.resolve_path("/absolute/path.py", workspace_root)
        assert result == "/absolute/path.py"

    def test_complex_nested_variables(self, workspace_root: Path):
        """Test complex scenarios with multiple variables in single string."""
        os.environ["PROJECT_NAME"] = "myproject"

        try:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program="app.py",
                env={
                    "CONFIG": "${workspaceFolder}/configs/${env:PROJECT_NAME}.json",
                },
            )

            args = config.get_common_args(workspace_root)

            expected = f"{workspace_root}/configs/myproject.json"
            assert args["env"]["CONFIG"] == expected
        finally:
            del os.environ["PROJECT_NAME"]


class TestProgramPathVsIdentifierHeuristic:
    """Test path vs identifier heuristic for cross-language support.

    Java and C# use fully qualified class names as program identifiers, while Python and
    JavaScript use file paths. The heuristic distinguishes between these cases to avoid
    incorrectly resolving class names as paths.
    """

    @pytest.fixture
    def workspace_root(self, tmp_path: Path) -> Path:
        """Create a temporary workspace directory.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory fixture

        Returns
        -------
        Path
            Temporary workspace directory
        """
        workspace = tmp_path / "test_workspace"
        workspace.mkdir()
        return workspace

    def test_file_path_with_extension_gets_resolved(self, workspace_root: Path):
        """Test that file paths with extensions are resolved as paths.

        This test only uses extensions from currently registered adapters (Python,
        JavaScript, Java). Future adapters like C# and Go will automatically be
        supported once registered.
        """
        test_cases = [
            ("app.py", str(workspace_root / "app.py")),
            ("script.js", str(workspace_root / "script.js")),
            ("app.ts", str(workspace_root / "app.ts")),
            ("Main.java", str(workspace_root / "Main.java")),
        ]

        for program, expected in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            assert args["target"] == expected, (
                f"File path '{program}' should be resolved to '{expected}'"
            )

    def test_file_path_with_separator_gets_resolved(self, workspace_root: Path):
        """Test that file paths with separators are resolved as paths."""
        test_cases = [
            ("src/app.py", str(workspace_root / "src/app.py")),
            ("src/main.js", str(workspace_root / "src/main.js")),
            ("com/example/Main", str(workspace_root / "com/example/Main")),
        ]

        for program, expected in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            assert args["target"] == expected, (
                f"File path '{program}' with separator should be resolved"
            )

    def test_java_class_name_not_resolved_as_path(self, workspace_root: Path):
        """Test that Java fully qualified class names are NOT resolved as paths."""
        test_cases = [
            "org.junit.platform.console.ConsoleLauncher",
            "com.example.demo.DemoApplication",
            "com.example.Main",
            "MyClass",
        ]

        for program in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            # Should use the class name directly, NOT prepend workspace_root
            assert args["target"] == program, (
                f"Java class name '{program}' should not be resolved as file path"
            )
            assert str(workspace_root) not in args["target"], (
                f"Workspace root should not be prepended to class name '{program}'"
            )

    def test_csharp_class_name_not_resolved_as_path(self, workspace_root: Path):
        """Test that C# fully qualified class names are NOT resolved as paths.

        Note: C# adapter is not yet implemented, but this test ensures that
        dotted identifiers without known extensions are treated as identifiers
        rather than paths. Once C# adapter is registered with .cs extension,
        "Program.cs" will be resolved as a path (tested separately).
        """
        test_cases = [
            "MyNamespace.Program",
            "MyApp.Services.MainService",
            "Program",
        ]

        for program in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            assert args["target"] == program, (
                f"C# class name '{program}' should not be resolved as file path"
            )

    def test_module_identifier_not_resolved_as_path(self, workspace_root: Path):
        """Test that module identifiers (no extension, no separator) stay as-is."""
        test_cases = [
            "pytest",
            "main",
            "mymodule",
        ]

        for program in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            assert args["target"] == program, (
                f"Module identifier '{program}' should not be resolved as file path"
            )

    def test_absolute_path_preserved(self, workspace_root: Path):
        """Test that absolute paths are preserved (regression test)."""
        test_cases = [
            "/absolute/path/to/app.py",
            "/usr/bin/python",
        ]

        for program in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            # Absolute paths should stay as-is (may be normalized)
            assert str(workspace_root) not in args["target"], (
                f"Absolute path '{program}' should not have workspace_root prepended"
            )

    def test_edge_case_dots_in_filename(self, workspace_root: Path):
        """Test edge cases with dots in filenames vs class names."""
        test_cases = [
            # Has extension → file path (resolved)
            ("app.config.py", str(workspace_root / "app.config.py")),
            # No extension → identifier (not resolved)
            ("app.config", "app.config"),
        ]

        for program, expected in test_cases:
            config = PythonLaunchConfig(
                type="python",
                request="launch",
                name="Test",
                program=program,
            )

            args = config.get_common_args(workspace_root)

            assert args["target"] == expected, (
                f"Program '{program}' should resolve to '{expected}'"
            )
