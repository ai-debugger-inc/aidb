"""Unit tests for VS Code variable substitution.

Tests the core variable substitution logic using VSCodeVariableResolver, including
workspaceFolder, file, env vars, and error handling.
"""

import os
from pathlib import Path

import pytest

from aidb.adapters.base.vscode_variables import VSCodeVariableResolver
from aidb.common.errors import VSCodeVariableError
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class TestVariableSubstitution(BaseDebugTest):
    """Test VS Code variable substitution logic."""

    def test_substitute_workspace_folder(self, temp_workspace: Path):
        """Substitute ${workspaceFolder} variable.

        Verifies:
        - ${workspaceFolder} replaced with workspace root path
        - Handles nested paths correctly
        - Supports multiple occurrences in same string
        - Path separators handled correctly

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Simple substitution
        result1 = resolver.resolve("${workspaceFolder}/app.py")
        assert result1 == str(temp_workspace / "app.py")

        # Nested path
        result2 = resolver.resolve("${workspaceFolder}/src/main/python/app.py")
        assert result2 == str(temp_workspace / "src/main/python/app.py")

        # Multiple occurrences
        result3 = resolver.resolve(
            "${workspaceFolder}/input.txt:${workspaceFolder}/output.txt",
        )
        expected3 = f"{temp_workspace}/input.txt:{temp_workspace}/output.txt"
        assert result3 == expected3

        # At start, middle, and end
        result4 = resolver.resolve(
            "${workspaceFolder} ${workspaceFolder}/middle ${workspaceFolder}",
        )
        expected4 = f"{temp_workspace} {temp_workspace}/middle {temp_workspace}"
        assert result4 == expected4

        # No variable - should return unchanged
        result5 = resolver.resolve("/absolute/path/app.py")
        assert result5 == "/absolute/path/app.py"

    def test_substitute_workspace_folder_basename(self, temp_workspace: Path):
        """Substitute ${workspaceFolderBasename} variable.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        workspace_name = temp_workspace.name

        # Simple substitution
        result = resolver.resolve("Project: ${workspaceFolderBasename}")
        assert result == f"Project: {workspace_name}"

    def test_substitute_file_with_context(self, temp_workspace: Path):
        """Substitute ${file} variable when target context provided.

        Verifies:
        - ${file} replaced when target in context
        - File path is absolute
        - Related variables work (fileBasename, fileDirname, etc.)

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Create test file
        test_file = temp_workspace / "src" / "app.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("print('hello')")

        context = {"target": str(test_file)}

        # ${file} substitution
        result1 = resolver.resolve("${file}", context=context)
        assert result1 == str(test_file)

        # ${fileBasename}
        result2 = resolver.resolve("${fileBasename}", context=context)
        assert result2 == "app.py"

        # ${fileBasenameNoExtension}
        result3 = resolver.resolve("${fileBasenameNoExtension}", context=context)
        assert result3 == "app"

        # ${fileExtname}
        result4 = resolver.resolve("${fileExtname}", context=context)
        assert result4 == ".py"

        # ${fileDirname}
        result5 = resolver.resolve("${fileDirname}", context=context)
        assert result5 == str(test_file.parent)

    def test_substitute_file_without_context_raises_error(self, temp_workspace: Path):
        """Verify ${file} without target context raises helpful error.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # ${file} without context should raise error
        with pytest.raises(VSCodeVariableError) as exc_info:
            resolver.resolve("${file}")

        error_msg = str(exc_info.value)
        assert "${file}" in error_msg
        assert "target" in error_msg.lower()

    def test_substitute_env_variables(self, temp_workspace: Path):
        """Substitute ${env:VAR_NAME} environment variables.

        Verifies:
        - Environment variables are substituted
        - Multiple env vars supported
        - Undefined vars handled gracefully

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Set test environment variable
        os.environ["AIDB_TEST_VAR"] = "test_value"
        os.environ["AIDB_TEST_PATH"] = "/custom/path"

        try:
            # Simple env var
            result1 = resolver.resolve("${env:AIDB_TEST_VAR}")
            assert result1 == "test_value"

            # Env var in path
            result2 = resolver.resolve("${env:AIDB_TEST_PATH}/file.txt")
            assert result2 == "/custom/path/file.txt"

            # Multiple env vars
            result3 = resolver.resolve(
                "${env:AIDB_TEST_VAR}-${env:AIDB_TEST_PATH}",
            )
            assert result3 == "test_value-/custom/path"

            # Mixed with other variables
            result4 = resolver.resolve(
                "${workspaceFolder}/${env:AIDB_TEST_VAR}/output",
            )
            assert result4 == f"{temp_workspace}/test_value/output"

        finally:
            # Cleanup
            del os.environ["AIDB_TEST_VAR"]
            del os.environ["AIDB_TEST_PATH"]

    def test_substitute_undefined_env_variable(self, temp_workspace: Path):
        """Handle undefined environment variables.

        Verifies:
        - Undefined env vars raise clear error
        - Error message includes variable name

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Ensure variable doesn't exist
        if "AIDB_UNDEFINED_VAR_12345" in os.environ:
            del os.environ["AIDB_UNDEFINED_VAR_12345"]

        # Should raise error for undefined var
        with pytest.raises(VSCodeVariableError) as exc_info:
            resolver.resolve("${env:AIDB_UNDEFINED_VAR_12345}")

        error_msg = str(exc_info.value)
        assert "AIDB_UNDEFINED_VAR_12345" in error_msg
        assert "not defined" in error_msg.lower() or "not set" in error_msg.lower()

    def test_substitute_mixed_variables(self, temp_workspace: Path):
        """Substitute multiple variable types in single string.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Set environment variable
        os.environ["AIDB_TEST_ENV"] = "production"

        try:
            # Create test file
            test_file = temp_workspace / "app.py"
            test_file.write_text("print('test')")

            context = {"target": str(test_file)}

            # Mix workspaceFolder, file, and env vars
            result = resolver.resolve(
                "${workspaceFolder}/logs/${env:AIDB_TEST_ENV}/${fileBasename}.log",
                context=context,
            )

            expected = f"{temp_workspace}/logs/production/app.py.log"
            assert result == expected

        finally:
            del os.environ["AIDB_TEST_ENV"]

    def test_no_substitution_when_no_variables(self, temp_workspace: Path):
        """Return string unchanged when no variables present.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Plain strings
        assert resolver.resolve("hello") == "hello"
        assert resolver.resolve("/path/to/file.py") == "/path/to/file.py"
        assert resolver.resolve("$not_a_variable") == "$not_a_variable"
        assert resolver.resolve("${incomplete") == "${incomplete"

    def test_escaped_variables(self, temp_workspace: Path):
        """Handle escaped variable syntax.

        Verifies that literal $ characters work correctly.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Dollar signs that aren't variables
        result1 = resolver.resolve("Cost: $100")
        assert result1 == "Cost: $100"

        result2 = resolver.resolve("Price $$ Double")
        assert result2 == "Price $$ Double"

    def test_variable_case_sensitivity(self, temp_workspace: Path):
        """Verify variable names are case-sensitive.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Correct case
        result1 = resolver.resolve("${workspaceFolder}")
        assert result1 == str(temp_workspace)

        # Wrong case - should raise error (treated as unknown variable)
        with pytest.raises(VSCodeVariableError) as exc_info:
            resolver.resolve("${WorkspaceFolder}")

        error_msg = str(exc_info.value)
        assert "WorkspaceFolder" in error_msg
        assert "Unknown" in error_msg or "unknown" in error_msg

    def test_empty_string_handling(self, temp_workspace: Path):
        """Handle empty strings and edge cases.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory
        """
        resolver = VSCodeVariableResolver(workspace_root=temp_workspace)

        # Empty string
        assert resolver.resolve("") == ""

        # Only whitespace
        assert resolver.resolve("   ") == "   "

        # Variable with no surrounding text
        result = resolver.resolve("${workspaceFolder}")
        assert result == str(temp_workspace)
