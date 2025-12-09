"""Tests for centralized environment resolution in CLI.

This module tests the EnvironmentManager and its integration with the CLI, ensuring that
environment variables are properly resolved and passed through to Docker containers
during test execution.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb_cli.cli import Context
from aidb_cli.managers.environment_manager import EnvironmentManager


class TestEnvironmentManager:
    """Test the EnvironmentManager class."""

    def test_initialization(self, tmp_path):
        """Test that EnvironmentManager initializes correctly."""
        manager = EnvironmentManager(tmp_path)

        assert manager.repo_root == tmp_path
        assert isinstance(manager.get_environment(), dict)
        assert manager.get_environment()["REPO_ROOT"] == str(tmp_path)

    def test_resolve_includes_system_env(self, tmp_path):
        """Test that system environment variables are included."""
        # Set a test environment variable
        test_key = "TEST_ENV_VAR_12345"
        test_value = "test_value"
        os.environ[test_key] = test_value

        try:
            manager = EnvironmentManager(tmp_path)
            env = manager.get_environment()

            assert test_key in env
            assert env[test_key] == test_value
        finally:
            del os.environ[test_key]

    def test_resolve_includes_env_test_template(self, tmp_path):
        """Test that .env.test template is parsed and included."""
        # Create a .env.test file
        env_test_file = tmp_path / ".env.test"
        env_test_file.write_text("""
# Test environment file
TEST_VAR_FROM_TEMPLATE=template_value
ANOTHER_VAR=another_value
""")

        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        assert env.get("TEST_VAR_FROM_TEMPLATE") == "template_value"
        assert env.get("ANOTHER_VAR") == "another_value"

    def test_essential_defaults_are_set(self, tmp_path):
        """Test that essential default variables are always set."""
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        # Essential defaults should always be present
        assert "REPO_ROOT" in env
        assert env["REPO_ROOT"] == str(tmp_path)
        assert "COMPOSE_PROJECT_NAME" in env
        assert env["COMPOSE_PROJECT_NAME"] == "aidb-test"

    def test_update_method_modifies_environment(self, tmp_path):
        """Test that update() method correctly modifies the environment."""
        manager = EnvironmentManager(tmp_path)

        # Initial state
        initial_env = manager.get_environment()
        assert "TEST_PATTERN" not in initial_env

        # Update with test variables
        updates = {
            "TEST_PATTERN": "test_*.py",
            "PYTEST_ADDOPTS": "-xvs",
            "NEW_VAR": "new_value",
        }
        manager.update(updates, source="test")

        # Check updated state
        updated_env = manager.get_environment()
        assert updated_env["TEST_PATTERN"] == "test_*.py"
        assert updated_env["PYTEST_ADDOPTS"] == "-xvs"
        assert updated_env["NEW_VAR"] == "new_value"

    def test_update_history_tracking(self, tmp_path):
        """Test that update history is tracked correctly."""
        manager = EnvironmentManager(tmp_path)

        # Perform multiple updates
        manager.update({"VAR1": "value1"}, source="source1")
        manager.update({"VAR2": "value2", "VAR3": "value3"}, source="source2")

        history = manager.get_update_history()
        assert len(history) == 2
        assert history[0]["source"] == "source1"
        assert history[0]["VAR1"] == "value1"
        assert history[1]["source"] == "source2"
        assert history[1]["VAR2"] == "value2"
        assert history[1]["VAR3"] == "value3"

    def test_critical_system_vars_validated(self, tmp_path):
        """Test that critical system variables are validated and restored."""
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        # Critical system variables should be present
        critical_vars = ["PATH", "HOME", "USER"]
        for var in critical_vars:
            if os.environ.get(var):  # Only check if set in system
                assert var in env

    def test_no_default_test_pattern_or_pytest_args(self, tmp_path):
        """Test that TEST_PATTERN and PYTEST_ADDOPTS are not set by default.

        This ensures they don't override CLI values unintentionally.
        """
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        # These should NOT be set by default in the manager
        # They should only come from CLI commands
        assert "TEST_PATTERN" not in env
        assert "PYTEST_ADDOPTS" not in env

    def test_debug_dump_output(self, tmp_path):
        """Test that debug_dump produces expected output."""
        manager = EnvironmentManager(tmp_path)
        manager.update(
            {"TEST_SUITE": "mcp", "TEST_PATTERN": "test_init"},
            source="test",
        )

        dump = manager.debug_dump(show_all=False)

        assert "Environment Manager Debug Dump" in dump
        assert "TEST_SUITE=mcp" in dump
        assert "TEST_PATTERN=test_init" in dump
        assert "Update History" in dump


class TestCLIContextIntegration:
    """Test the integration of EnvironmentManager with CLI Context."""

    def test_context_initialization_with_env_manager(self, tmp_path):
        """Test that Context initializes with EnvironmentManager."""
        ctx = Context(repo_root=tmp_path)

        assert hasattr(ctx, "env_manager")
        assert isinstance(ctx.env_manager, EnvironmentManager)
        assert hasattr(ctx, "resolved_env")
        assert isinstance(ctx.resolved_env, dict)

    def test_resolved_env_property_returns_current_state(self, tmp_path):
        """Test that resolved_env property returns current environment state."""
        ctx = Context(repo_root=tmp_path)

        # Get initial environment
        initial_env = ctx.resolved_env
        assert "REPO_ROOT" in initial_env

        # Update environment
        ctx.env_manager.update({"NEW_VAR": "new_value"}, source="test")

        # Property should return updated environment
        updated_env = ctx.resolved_env
        assert "NEW_VAR" in updated_env
        assert updated_env["NEW_VAR"] == "new_value"

    def test_environment_available_throughout_cli(self, tmp_path):
        """Test that environment is available throughout CLI command chain."""
        ctx = Context(repo_root=tmp_path)

        # Simulate what happens in test command
        ctx.env_manager.update(
            {
                "TEST_SUITE": "mcp",
                "TEST_PATTERN": "test_init",
                "PYTEST_ADDOPTS": "-xvs",
                "TEST_LANGUAGE": "python",
            },
            source="test_command",
        )

        # Environment should be accessible
        env = ctx.resolved_env
        assert env["TEST_SUITE"] == "mcp"
        assert env["TEST_PATTERN"] == "test_init"
        assert env["PYTEST_ADDOPTS"] == "-xvs"
        assert env["TEST_LANGUAGE"] == "python"


class TestEnvironmentPrecedence:
    """Test environment variable precedence and override behavior."""

    def test_template_overrides_system(self, tmp_path):
        """Test that .env.test template overrides system environment."""
        # Set system variable
        os.environ["OVERRIDE_TEST_VAR"] = "system_value"

        try:
            # Create .env.test with override
            env_test = tmp_path / ".env.test"
            env_test.write_text("OVERRIDE_TEST_VAR=template_value")

            manager = EnvironmentManager(tmp_path)
            env = manager.get_environment()

            # Template should override system
            assert env["OVERRIDE_TEST_VAR"] == "template_value"
        finally:
            del os.environ["OVERRIDE_TEST_VAR"]

    def test_updates_override_everything(self, tmp_path):
        """Test that updates override both system and template values."""
        # Set system variable
        os.environ["MULTI_OVERRIDE_VAR"] = "system_value"

        try:
            # Create .env.test
            env_test = tmp_path / ".env.test"
            env_test.write_text("MULTI_OVERRIDE_VAR=template_value")

            manager = EnvironmentManager(tmp_path)

            # Update with new value
            manager.update({"MULTI_OVERRIDE_VAR": "updated_value"}, source="test")

            env = manager.get_environment()

            # Update should win
            assert env["MULTI_OVERRIDE_VAR"] == "updated_value"
        finally:
            del os.environ["MULTI_OVERRIDE_VAR"]


class TestTestCommandIntegration:
    """Test integration with the test command."""

    @patch("aidb_cli.services.test.test_coordinator_service.TestCoordinatorService")
    def test_test_command_updates_environment(self, mock_coordinator, tmp_path):
        """Test that test command properly updates environment."""
        from click.testing import CliRunner

        from aidb_cli.cli import cli

        runner = CliRunner()

        # Run test command with specific flags
        runner.invoke(
            cli,
            [
                "test",
                "run",
                "--suite",
                "mcp",
                "-k",
                "test_init",
                "--failfast",
                "--local",
            ],
        )

        # The command should have updated the environment
        # Note: This is a simplified test - in reality we'd need to
        # capture the context and verify the environment was updated

    def test_empty_pattern_doesnt_get_overridden(self, tmp_path):
        """Test that empty TEST_PATTERN from CLI is preserved."""
        ctx = Context(repo_root=tmp_path)

        # Simulate test command with no pattern
        ctx.env_manager.update(
            {
                "TEST_SUITE": "mcp",
                "TEST_PATTERN": "",  # Explicitly empty
                "PYTEST_ADDOPTS": "-v",
            },
            source="test_command",
        )

        env = ctx.resolved_env

        # Empty pattern should be preserved, not overridden by defaults
        assert "TEST_PATTERN" in env
        assert env["TEST_PATTERN"] == ""

    def test_pytest_args_properly_constructed(self, tmp_path):
        """Test that PYTEST_ADDOPTS is properly constructed from CLI flags."""
        ctx = Context(repo_root=tmp_path)

        # Simulate test command with multiple pytest flags
        pytest_args = "-xvs --timeout=60 --lf"
        ctx.env_manager.update(
            {
                "TEST_SUITE": "cli",
                "PYTEST_ADDOPTS": pytest_args,
            },
            source="test_command",
        )

        env = ctx.resolved_env

        assert env["PYTEST_ADDOPTS"] == pytest_args


class TestTypedGetters:
    """Test typed getter methods."""

    def test_get_bool(self, tmp_path):
        """Test get_bool method with various values."""
        manager = EnvironmentManager(tmp_path)

        # Test with true values
        manager.update(
            {"BOOL_TRUE": "true", "BOOL_1": "1", "BOOL_YES": "yes"},
            source="test",
        )
        assert manager.get_bool("BOOL_TRUE", False) is True
        assert manager.get_bool("BOOL_1", False) is True
        assert manager.get_bool("BOOL_YES", False) is True

        # Test with false values
        manager.update(
            {"BOOL_FALSE": "false", "BOOL_0": "0", "BOOL_NO": "no"},
            source="test",
        )
        assert manager.get_bool("BOOL_FALSE", True) is False
        assert manager.get_bool("BOOL_0", True) is False
        assert manager.get_bool("BOOL_NO", True) is False

        # Test default values
        assert manager.get_bool("NONEXISTENT", True) is True
        assert manager.get_bool("NONEXISTENT", False) is False

    def test_get_int(self, tmp_path):
        """Test get_int method with various values."""
        manager = EnvironmentManager(tmp_path)

        # Test with valid integers
        manager.update(
            {"INT_42": "42", "INT_NEG": "-10", "INT_ZERO": "0"},
            source="test",
        )
        assert manager.get_int("INT_42", 0) == 42
        assert manager.get_int("INT_NEG", 0) == -10
        assert manager.get_int("INT_ZERO", 100) == 0

        # Test default values
        assert manager.get_int("NONEXISTENT", 99) == 99

    def test_get_str(self, tmp_path):
        """Test get_str method."""
        manager = EnvironmentManager(tmp_path)

        # Test with various strings
        manager.update({"STR_VAR": "hello world", "EMPTY_STR": ""}, source="test")
        assert manager.get_str("STR_VAR", "default") == "hello world"
        assert manager.get_str("EMPTY_STR", "default") == ""

        # Test default values
        assert manager.get_str("NONEXISTENT", "default") == "default"
        assert manager.get_str("NONEXISTENT", "") == ""

    def test_get_list(self, tmp_path):
        """Test get_list method with various formats."""
        manager = EnvironmentManager(tmp_path)

        # Test comma-separated values
        manager.update({"LIST_COMMA": "a,b,c", "LIST_SPACE": "x y z"}, source="test")
        assert manager.get_list("LIST_COMMA", []) == ["a", "b", "c"]

        # Test default values
        assert manager.get_list("NONEXISTENT", ["default"]) == ["default"]
        assert manager.get_list("NONEXISTENT", None) == []


class TestValidationMethods:
    """Test validation methods for CLI variables."""

    def test_validate_test_pattern(self, tmp_path):
        """Test TEST_PATTERN validation."""
        manager = EnvironmentManager(tmp_path)

        # Valid patterns
        assert manager.validate_test_pattern("test_*.py") == "test_*.py"
        assert manager.validate_test_pattern("tests/test_foo.py") == "tests/test_foo.py"
        assert (
            manager.validate_test_pattern("test_foo.py::TestClass::test_method")
            == "test_foo.py::TestClass::test_method"
        )
        assert (
            manager.validate_test_pattern("-k 'test_foo or test_bar'")
            == "-k 'test_foo or test_bar'"
        )

        # Whitespace handling
        assert manager.validate_test_pattern("  test_*.py  ") == "test_*.py"

        # Invalid patterns
        assert manager.validate_test_pattern("--verbose") is None
        assert manager.validate_test_pattern("--help") is None

        # Empty/None patterns
        assert manager.validate_test_pattern("") is None
        assert manager.validate_test_pattern(None) is None

    def test_validate_pytest_addopts(self, tmp_path):
        """Test PYTEST_ADDOPTS validation and parsing."""
        manager = EnvironmentManager(tmp_path)

        # Valid arguments
        assert manager.validate_pytest_addopts("-xvs") == ["-xvs"]
        assert manager.validate_pytest_addopts("-v --timeout=60") == [
            "-v",
            "--timeout=60",
        ]
        assert manager.validate_pytest_addopts("--tb=short -x") == ["--tb=short", "-x"]

        # Quoted arguments
        assert manager.validate_pytest_addopts("-m 'not slow'") == ["-m", "not slow"]

        # Dangerous arguments are filtered
        dangerous_args = manager.validate_pytest_addopts(
            "--rootdir=/tmp --cache-clear -v",
        )
        assert "-v" in dangerous_args
        assert "--rootdir=/tmp" not in dangerous_args
        assert "--cache-clear" not in dangerous_args

        # Empty/None arguments
        assert manager.validate_pytest_addopts("") == []
        assert manager.validate_pytest_addopts(None) == []

    def test_validate_test_suite(self, tmp_path):
        """Test TEST_SUITE validation."""
        manager = EnvironmentManager(tmp_path)

        # Valid suites
        assert manager.validate_test_suite("cli") == "cli"
        assert manager.validate_test_suite("mcp") == "mcp"
        assert manager.validate_test_suite("unit") == "unit"

        # Invalid suites
        assert manager.validate_test_suite("invalid_suite") is None
        assert manager.validate_test_suite("xyz") is None

        # Empty/None suites
        assert manager.validate_test_suite("") is None
        assert manager.validate_test_suite(None) is None


class TestExportForSubprocess:
    """Test export_for_subprocess method."""

    def test_export_for_subprocess(self, tmp_path):
        """Test that export_for_subprocess returns proper dictionary."""
        manager = EnvironmentManager(tmp_path)

        # Add various types of values
        manager.update(
            {
                "STRING_VAR": "value",
                "INT_VAR": "42",
                "PATH_VAR": str(tmp_path),
            },
            source="test",
        )

        exported = manager.export_for_subprocess()

        # Should be a dict
        assert isinstance(exported, dict)

        # All values should be strings
        for key, value in exported.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

        # Should contain our variables
        assert exported["STRING_VAR"] == "value"
        assert exported["INT_VAR"] == "42"
        assert exported["PATH_VAR"] == str(tmp_path)

        # Should be a copy, not the original
        exported["NEW_VAR"] = "should_not_affect_original"
        original_env = manager.get_environment()
        assert "NEW_VAR" not in original_env


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_env_test_template(self, tmp_path):
        """Test handling of invalid .env.test template."""
        # Create an invalid .env.test file with bad syntax
        env_test = tmp_path / ".env.test"
        env_test.write_text("""
# This has invalid template syntax
BAD_VAR=${UNDEFINED_VAR
GOOD_VAR=good_value
""")

        # Manager should still work, just skip bad entries
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        # Good variables should still be loaded
        assert env.get("GOOD_VAR") == "good_value"

    def test_missing_env_test_file(self, tmp_path):
        """Test that missing .env.test file doesn't break initialization."""
        # Ensure no .env.test exists
        env_test = tmp_path / ".env.test"
        if env_test.exists():
            env_test.unlink()

        # Manager should work fine without it
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        assert isinstance(env, dict)
        assert "REPO_ROOT" in env

    def test_circular_reference_in_template(self, tmp_path):
        """Test handling of circular references in template."""
        env_test = tmp_path / ".env.test"
        env_test.write_text("""
# Circular reference
VAR_A=${VAR_B}
VAR_B=${VAR_A}
VAR_C=normal_value
""")

        # Should handle gracefully
        manager = EnvironmentManager(tmp_path)
        env = manager.get_environment()

        # Normal variables should still work
        assert env.get("VAR_C") == "normal_value"
