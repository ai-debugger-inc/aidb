"""Tests for --lf (last-failed) option in test command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.commands.test import group as test_group
from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService


class TestLastFailedOption:
    """Test cases for the --lf / --last-failed functionality."""

    def test_lf_option_accepted(self):
        """Test that --lf flag is accepted by CLI."""
        runner = CliRunner()

        # Test that --lf flag is recognized in help
        result = runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0
        assert "--last-failed" in result.output or "--lf" in result.output

    def test_lf_passed_to_coordinator(self):
        """Test that --lf flag is passed through to the test coordinator."""
        runner = CliRunner()

        with patch(
            "aidb_cli.commands.test.TestCoordinatorService",
        ) as mock_coordinator_cls:
            mock_coordinator = MagicMock()
            mock_coordinator.determine_execution_environment.return_value = False
            mock_coordinator.validate_prerequisites.return_value = True
            mock_coordinator.execute_tests.return_value = 0
            mock_coordinator.report_results.return_value = None
            mock_coordinator_cls.return_value = mock_coordinator

            # Create proper CLI context
            with runner.isolated_filesystem():
                # Run with --lf flag and proper context injection
                result = runner.invoke(
                    test_group,
                    ["run", "-s", "cli", "--lf", "--local"],
                    catch_exceptions=False,
                    obj=MagicMock(
                        repo_root=Path("/tmp"),
                        command_executor=MagicMock(),
                        test_orchestrator=MagicMock(),
                        verbose=False,
                    ),
                )

            # Verify TestCoordinatorService was instantiated
            assert mock_coordinator_cls.called, (
                f"TestCoordinatorService not instantiated. Exit code: {result.exit_code}, Output: {result.output}"
            )

            # Verify execute_tests was called with last_failed=True
            assert mock_coordinator.execute_tests.called, "execute_tests not called"
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("last_failed") is True

    def test_lf_not_set_by_default(self):
        """Test that last_failed is False when --lf is not provided."""
        runner = CliRunner()

        with patch(
            "aidb_cli.commands.test.TestCoordinatorService",
        ) as mock_coordinator_cls:
            mock_coordinator = MagicMock()
            mock_coordinator.determine_execution_environment.return_value = False
            mock_coordinator.validate_prerequisites.return_value = True
            mock_coordinator.execute_tests.return_value = 0
            mock_coordinator.report_results.return_value = None
            mock_coordinator_cls.return_value = mock_coordinator

            # Create proper CLI context
            with runner.isolated_filesystem():
                # Run without --lf flag
                runner.invoke(
                    test_group,
                    ["run", "-s", "cli", "--local"],
                    catch_exceptions=False,
                    obj=MagicMock(
                        repo_root=Path("/tmp"),
                        command_executor=MagicMock(),
                        test_orchestrator=MagicMock(),
                        verbose=False,
                    ),
                )

            # Verify execute_tests was called with last_failed=False
            assert mock_coordinator.execute_tests.called
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("last_failed") is False

    def test_coordinator_builds_pytest_args_with_lf(self):
        """Test that the coordinator builds correct pytest args with --lf."""
        from pathlib import Path

        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        # Build args with last_failed=True
        args = coordinator.build_pytest_args(
            suite="cli",
            last_failed=True,
            verbose=False,
            failfast=False,
        )

        # Verify --lf is in the arguments
        assert "--lf" in args

    def test_coordinator_builds_pytest_args_without_lf(self):
        """Test that the coordinator doesn't add --lf when not requested."""
        from pathlib import Path

        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        # Build args with last_failed=False
        args = coordinator.build_pytest_args(
            suite="cli",
            last_failed=False,
            verbose=False,
            failfast=False,
        )

        # Verify --lf is NOT in the arguments
        assert "--lf" not in args

    def test_lf_works_with_other_options(self):
        """Test that --lf can be combined with other options."""
        runner = CliRunner()

        with patch(
            "aidb_cli.commands.test.TestCoordinatorService",
        ) as mock_coordinator_cls:
            mock_coordinator = MagicMock()
            mock_coordinator.determine_execution_environment.return_value = False
            mock_coordinator.validate_prerequisites.return_value = True
            mock_coordinator.execute_tests.return_value = 0
            mock_coordinator.report_results.return_value = None
            mock_coordinator_cls.return_value = mock_coordinator

            # Create proper CLI context
            with runner.isolated_filesystem():
                # Run with multiple options
                # Note: -v/--verbose is now a CLI-level flag, not a test run flag.
                # Verbose is passed via ctx.obj.verbose
                runner.invoke(
                    test_group,
                    [
                        "run",
                        "-s",
                        "cli",
                        "--lf",  # last-failed
                        "-x",  # failfast
                        "--local",
                    ],
                    catch_exceptions=False,
                    obj=MagicMock(
                        repo_root=Path("/tmp"),
                        command_executor=MagicMock(),
                        test_orchestrator=MagicMock(),
                        verbose=True,  # Set at CLI level via ctx.obj
                    ),
                )

            # Verify all options were passed
            assert mock_coordinator.execute_tests.called
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("last_failed") is True
            assert call_kwargs.get("failfast") is True
            assert call_kwargs.get("verbose") is True

    def test_lf_in_pytest_args_combination(self):
        """Test that --lf and -x work together in pytest args."""
        from pathlib import Path

        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        # Build args with both last_failed and failfast
        args = coordinator.build_pytest_args(
            suite="cli",
            last_failed=True,
            failfast=True,
            verbose=True,
        )

        # Verify both flags are in the arguments
        assert "--lf" in args
        assert "-x" in args
        assert "-v" in args

    def test_help_text_describes_lf_correctly(self):
        """Test that the help text for --lf is descriptive."""
        runner = CliRunner()

        result = runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0

        # Check for help text
        output_lines = result.output.split("\n")
        lf_help_found = False
        for line in output_lines:
            if "--last-failed" in line or "--lf" in line:
                # Next part of the line or next line should contain description
                assert "failed" in line.lower() or "last" in line.lower()
                lf_help_found = True
                break

        assert lf_help_found, "Help text for --lf option not found"
