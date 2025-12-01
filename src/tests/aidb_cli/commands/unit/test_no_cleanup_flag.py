"""Unit tests for the --no-cleanup flag in test command."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


class TestNoCleanupFlag:
    """Test the --no-cleanup flag functionality."""

    @patch("aidb_cli.commands.test.TestCoordinatorService")
    @patch("aidb_cli.commands.test.ResourceCleaner")
    def test_no_cleanup_flag_skips_cleanup_handler(
        self,
        mock_resource_cleaner,
        mock_coordinator,
    ):
        """Test that --no-cleanup flag prevents cleanup handler registration."""
        runner = CliRunner()

        # Mock the coordinator methods
        mock_coordinator_instance = MagicMock()
        mock_coordinator.return_value = mock_coordinator_instance
        mock_coordinator_instance.determine_execution_environment.return_value = (
            True  # Use Docker
        )
        mock_coordinator_instance.validate_prerequisites.return_value = True
        mock_coordinator_instance.execute_tests.return_value = 0

        # Mock ResourceCleaner
        mock_cleaner_instance = MagicMock()
        mock_resource_cleaner.return_value = mock_cleaner_instance

        # Run with --no-cleanup flag
        runner.invoke(
            cli,
            ["test", "run", "--no-cleanup", "-s", "mcp"],
        )

        # Verify cleanup handler was NOT registered
        mock_resource_cleaner.assert_not_called()
        mock_cleaner_instance.register_cleanup_handler.assert_not_called()

        # Verify the test execution was called with no_cleanup=True
        mock_coordinator_instance.execute_tests.assert_called_once()
        call_kwargs = mock_coordinator_instance.execute_tests.call_args.kwargs
        assert call_kwargs.get("no_cleanup") is True

    @patch("aidb_cli.commands.test.TestCoordinatorService")
    @patch("aidb_cli.commands.test.ResourceCleaner")
    def test_without_no_cleanup_flag_registers_handler(
        self,
        mock_resource_cleaner,
        mock_coordinator,
    ):
        """Test that without --no-cleanup flag, cleanup handler is registered."""
        runner = CliRunner()

        # Mock the coordinator methods
        mock_coordinator_instance = MagicMock()
        mock_coordinator.return_value = mock_coordinator_instance
        mock_coordinator_instance.determine_execution_environment.return_value = (
            True  # Use Docker
        )
        mock_coordinator_instance.validate_prerequisites.return_value = True
        mock_coordinator_instance.execute_tests.return_value = 0

        # Mock ResourceCleaner
        mock_cleaner_instance = MagicMock()
        mock_resource_cleaner.return_value = mock_cleaner_instance

        # Run without --no-cleanup flag
        runner.invoke(
            cli,
            ["test", "run", "-s", "mcp"],
        )

        # Verify cleanup handler WAS registered
        mock_resource_cleaner.assert_called_once()
        mock_cleaner_instance.register_cleanup_handler.assert_called_once()

        # Verify the test execution was called with no_cleanup=False
        mock_coordinator_instance.execute_tests.assert_called_once()
        call_kwargs = mock_coordinator_instance.execute_tests.call_args.kwargs
        assert call_kwargs.get("no_cleanup") is False

    def test_no_cleanup_help_text(self):
        """Test that --no-cleanup flag has proper help text."""
        runner = CliRunner()
        result = runner.invoke(cli, ["test", "run", "--help"])

        assert result.exit_code == 0
        assert "--no-cleanup" in result.output
        assert "Skip Docker cleanup for postmortem inspection" in result.output
