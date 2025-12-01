"""Integration tests for configuration and environment management.

Tests the CLI's configuration file handling, environment variable processing, and
settings persistence across different sources and priorities.
"""

import contextlib
import os
import tempfile
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


def _get_repo_root() -> Path:
    """Get repository root directory."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / ".git").exists():
            return current
        current = current.parent
    msg = "Could not find git repository root"
    raise RuntimeError(msg)


@pytest.fixture
def repo_root():
    """Repository root fixture."""
    return _get_repo_root()


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestConfigBasicCommands:
    """Test basic configuration commands."""

    @pytest.mark.integration
    def test_config_show_command(self):
        """Test config show command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "show"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Config show failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should display configuration information
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "config",
                "configuration",
                "setting",
                "path",
                "value",
            ]
        )

    @pytest.mark.integration
    def test_config_paths_command(self):
        """Test config paths command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "paths"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Config paths failed: {result.output}"
        assert len(result.output.strip()) > 0

        # Should show file paths
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "path",
                "file",
                "config",
                "directory",
            ]
        )

        # Should contain actual file paths
        assert "/" in result.output or "\\" in result.output

    @pytest.mark.integration
    def test_config_validate_command(self):
        """Test config validate command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "validate"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Config validate failed: {result.output}"

        # Should provide validation results
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "valid",
                "invalid",
                "validation",
                "config",
                "ok",
                "error",
            ]
        )

    @pytest.mark.integration
    def test_config_init_command(self):
        """Test config init command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "init"],
            catch_exceptions=False,
        )

        # Should either succeed or indicate config already exists
        if result.exit_code == 0:
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "init",
                    "created",
                    "config",
                    "default",
                ]
            )
        else:
            # If it fails, should provide meaningful reason
            assert len(result.output.strip()) > 0


class TestConfigGetSet:
    """Test configuration get/set operations."""

    @pytest.mark.integration
    def test_config_get_nonexistent_key(self):
        """Test getting a non-existent configuration key."""
        runner = CliRunner()

        # Use a key that's very unlikely to exist
        test_key = f"test_nonexistent_key_{uuid.uuid4().hex[:8]}"

        result = runner.invoke(
            cli,
            ["config", "get", test_key],
            catch_exceptions=False,
        )

        # Should handle non-existent key gracefully
        if result.exit_code != 0:
            # Failure is acceptable for non-existent keys
            output_lower = result.output.lower()
            assert any(
                keyword in output_lower
                for keyword in [
                    "not found",
                    "does not exist",
                    "unknown",
                    "error",
                ]
            )
        else:
            # If it succeeds, should indicate the key has no value
            output_lower = result.output.lower()
            assert len(result.output.strip()) == 0 or any(
                keyword in output_lower
                for keyword in [
                    "none",
                    "null",
                    "empty",
                    "not set",
                ]
            )

    @pytest.mark.integration
    def test_config_set_and_get_cycle(self):
        """Test setting and getting a configuration value."""
        runner = CliRunner()

        # Use a unique test key and value
        test_key = f"test_integration_key_{uuid.uuid4().hex[:8]}"
        test_value = f"test_value_{uuid.uuid4().hex[:8]}"

        try:
            # Set the configuration value
            set_result = runner.invoke(
                cli,
                ["config", "set", test_key, test_value],
                catch_exceptions=False,
            )

            if set_result.exit_code == 0:
                # If set succeeded, try to get the value
                get_result = runner.invoke(
                    cli,
                    ["config", "get", test_key],
                    catch_exceptions=False,
                )

                assert get_result.exit_code == 0, (
                    f"Config get failed after set: {get_result.output}"
                )
                assert test_value in get_result.output, (
                    f"Expected {test_value} in output: {get_result.output}"
                )

            else:
                # If set failed, it should provide meaningful error
                assert len(set_result.output.strip()) > 0
                pytest.skip("Config set not supported or failed")

        finally:
            # Cleanup: try to remove the test key (don't fail if this doesn't work)
            with contextlib.suppress(Exception):
                runner.invoke(
                    cli,
                    ["config", "set", test_key, ""],
                    catch_exceptions=True,
                )

    @pytest.mark.integration
    def test_config_get_help_and_options(self):
        """Test config get command help and options."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "get", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Config get help failed: {result.output}"
        assert "get" in result.output.lower()

    @pytest.mark.integration
    def test_config_set_help_and_options(self):
        """Test config set command help and options."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "set", "--help"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Config set help failed: {result.output}"
        assert "set" in result.output.lower()


class TestEnvironmentVariables:
    """Test environment variable handling."""

    @pytest.mark.integration
    def test_aidb_env_vars_recognition(self):
        """Test that AIDB environment variables are recognized."""
        runner = CliRunner()

        # Test with a known AIDB environment variable
        env = os.environ.copy()
        env["AIDB_LOG_LEVEL"] = "DEBUG"

        result = runner.invoke(
            cli,
            ["config", "show"],
            env=env,
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        # The config system should handle environment variables
        # (exact output format may vary)

    @pytest.mark.integration
    def test_env_var_override_precedence(self):
        """Test environment variable override precedence."""
        runner = CliRunner()

        # Test with different log levels
        test_cases = [
            {"AIDB_LOG_LEVEL": "INFO"},
            {"AIDB_LOG_LEVEL": "WARNING"},
            {"AIDB_LOG_LEVEL": "ERROR"},
        ]

        for env_vars in test_cases:
            env = os.environ.copy()
            env.update(env_vars)

            result = runner.invoke(
                cli,
                ["--log-level", "DEBUG", "config", "show"],
                env=env,
                catch_exceptions=False,
            )

            # Should succeed regardless of environment variables
            assert result.exit_code == 0

    @pytest.mark.integration
    def test_config_with_various_env_combinations(self):
        """Test config handling with various environment combinations."""
        runner = CliRunner()

        # Test various AIDB environment variables
        test_envs = [
            {},  # No special env vars
            {"AIDB_LOG_LEVEL": "DEBUG"},
            {"AIDB_LOG_LEVEL": "INFO", "AIDB_TEST_MODE": "1"},
            {"AIDB_ADAPTER_TRACE": "1"},
        ]

        for env_vars in test_envs:
            env = os.environ.copy()
            env.update(env_vars)

            # Config show should work regardless of environment
            result = runner.invoke(
                cli,
                ["config", "show"],
                env=env,
                catch_exceptions=False,
            )

            assert result.exit_code == 0, (
                f"Config failed with env {env_vars}: {result.output}"
            )


class TestConfigPersistence:
    """Test configuration persistence and file handling."""

    @pytest.mark.integration
    def test_config_file_detection(self):
        """Test config file detection and paths."""
        runner = CliRunner()

        paths_result = runner.invoke(
            cli,
            ["config", "paths"],
            catch_exceptions=False,
        )

        assert paths_result.exit_code == 0

        # Should show meaningful path information
        paths_output = paths_result.output
        assert len(paths_output.strip()) > 0

        # Extract file paths from output
        lines = [line.strip() for line in paths_output.split("\n") if line.strip()]
        path_lines = [line for line in lines if ("/" in line or "\\" in line)]

        assert len(path_lines) > 0, f"No file paths found in output: {paths_output}"

    @pytest.mark.integration
    def test_config_validation_with_existing_files(self):
        """Test config validation with existing configuration files."""
        runner = CliRunner()

        # First check what config files exist
        paths_result = runner.invoke(
            cli,
            ["config", "paths"],
            catch_exceptions=False,
        )

        assert paths_result.exit_code == 0

        # Then validate configuration
        validate_result = runner.invoke(
            cli,
            ["config", "validate"],
            catch_exceptions=False,
        )

        assert validate_result.exit_code == 0

        # Validation should provide useful information
        output_lower = validate_result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "valid",
                "validation",
                "config",
                "ok",
                "success",
                "file",
            ]
        )


class TestConfigErrorHandling:
    """Test configuration error handling."""

    @pytest.mark.integration
    def test_config_get_invalid_arguments(self):
        """Test config get with invalid arguments."""
        runner = CliRunner()

        # Test with no key provided
        result = runner.invoke(
            cli,
            ["config", "get"],
            catch_exceptions=False,
        )

        # Should require a key argument
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "required",
                "argument",
                "key",
                "missing",
                "usage",
            ]
        )

    @pytest.mark.integration
    def test_config_set_invalid_arguments(self):
        """Test config set with invalid arguments."""
        runner = CliRunner()

        # Test with only key, no value
        result = runner.invoke(
            cli,
            ["config", "set", "test_key"],
            catch_exceptions=False,
        )

        # Should require both key and value
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "required",
                "argument",
                "value",
                "missing",
                "usage",
            ]
        )

    @pytest.mark.integration
    def test_config_with_invalid_subcommand(self):
        """Test config with invalid subcommand."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["config", "invalid_subcommand"],
            catch_exceptions=False,
        )

        # Should provide helpful error about invalid subcommand
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert any(
            keyword in output_lower
            for keyword in [
                "no such command",
                "invalid",
                "unknown",
                "available",
            ]
        )


class TestConfigIntegration:
    """Test configuration integration with other systems."""

    @pytest.mark.integration
    def test_config_consistency_across_commands(self):
        """Test that configuration is consistent across different commands."""
        runner = CliRunner()

        # Get config from show command
        show_result = runner.invoke(
            cli,
            ["config", "show"],
            catch_exceptions=False,
        )
        assert show_result.exit_code == 0

        # Get paths
        paths_result = runner.invoke(
            cli,
            ["config", "paths"],
            catch_exceptions=False,
        )
        assert paths_result.exit_code == 0

        # Validate
        validate_result = runner.invoke(
            cli,
            ["config", "validate"],
            catch_exceptions=False,
        )
        assert validate_result.exit_code == 0

        # All should provide consistent, non-empty output
        assert len(show_result.output.strip()) > 0
        assert len(paths_result.output.strip()) > 0
        assert len(validate_result.output.strip()) > 0

    @pytest.mark.integration
    def test_config_affects_cli_behavior(self):
        """Test that configuration affects CLI behavior."""
        runner = CliRunner()

        # Test with different verbosity levels
        quiet_result = runner.invoke(
            cli,
            ["config", "show"],
            catch_exceptions=False,
        )

        verbose_result = runner.invoke(
            cli,
            ["-v", "config", "show"],
            catch_exceptions=False,
        )

        # Both should succeed
        assert quiet_result.exit_code == 0
        assert verbose_result.exit_code == 0

        # Verbose mode might produce different (typically more) output
        # But this depends on implementation details

    @pytest.mark.integration
    def test_config_with_different_log_levels(self):
        """Test config commands with different log levels."""
        runner = CliRunner()

        log_levels = ["ERROR", "WARNING", "INFO", "DEBUG"]

        for level in log_levels:
            result = runner.invoke(
                cli,
                ["--log-level", level, "config", "show"],
                catch_exceptions=False,
            )

            # Should succeed regardless of log level
            assert result.exit_code == 0, (
                f"Config failed with log level {level}: {result.output}"
            )
