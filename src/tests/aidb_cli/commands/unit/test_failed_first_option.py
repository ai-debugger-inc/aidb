"""Tests for --ff (failed-first) option in test command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.commands.test import group as test_group
from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService


class TestFailedFirstOption:
    """Test cases for the --ff / --failed-first functionality."""

    def test_ff_option_accepted(self):
        """Test that --ff flag is accepted by CLI."""
        runner = CliRunner()

        result = runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0
        assert "--failed-first" in result.output or "--ff" in result.output

    def test_ff_passed_to_coordinator(self):
        """Test that --ff flag is passed through to the test coordinator."""
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

            with runner.isolated_filesystem():
                result = runner.invoke(
                    test_group,
                    ["run", "-s", "cli", "--ff", "--local"],
                    catch_exceptions=False,
                    obj=MagicMock(
                        repo_root=Path("/tmp"),
                        command_executor=MagicMock(),
                        test_orchestrator=MagicMock(),
                        verbose=False,
                    ),
                )

            assert mock_coordinator_cls.called, (
                f"TestCoordinatorService not instantiated. Exit code: {result.exit_code}, Output: {result.output}"
            )

            assert mock_coordinator.execute_tests.called, "execute_tests not called"
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("failed_first") is True

    def test_ff_not_set_by_default(self):
        """Test that failed_first is False when --ff is not provided."""
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

            with runner.isolated_filesystem():
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

            assert mock_coordinator.execute_tests.called
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("failed_first") is False

    def test_coordinator_builds_pytest_args_with_ff(self):
        """Test that the coordinator builds correct pytest args with --ff."""
        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        args = coordinator.build_pytest_args(
            suite="cli",
            failed_first=True,
            verbose=False,
            failfast=False,
        )

        assert "--ff" in args

    def test_coordinator_builds_pytest_args_without_ff(self):
        """Test that the coordinator doesn't add --ff when not requested."""
        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        args = coordinator.build_pytest_args(
            suite="cli",
            failed_first=False,
            verbose=False,
            failfast=False,
        )

        assert "--ff" not in args

    def test_ff_works_with_other_options(self):
        """Test that --ff can be combined with other options."""
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

            with runner.isolated_filesystem():
                # Note: -v/--verbose is now a CLI-level flag, not a test run flag.
                # Verbose is passed via ctx.obj.verbose
                runner.invoke(
                    test_group,
                    [
                        "run",
                        "-s",
                        "cli",
                        "--ff",
                        "-x",
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

            assert mock_coordinator.execute_tests.called
            call_kwargs = mock_coordinator.execute_tests.call_args.kwargs
            assert call_kwargs.get("failed_first") is True
            assert call_kwargs.get("failfast") is True
            assert call_kwargs.get("verbose") is True

    def test_ff_in_pytest_args_combination(self):
        """Test that --ff and -x work together in pytest args."""
        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        args = coordinator.build_pytest_args(
            suite="cli",
            failed_first=True,
            failfast=True,
            verbose=True,
        )

        assert "--ff" in args
        assert "-x" in args
        assert "-v" in args

    def test_help_text_describes_ff_correctly(self):
        """Test that the help text for --ff is descriptive."""
        runner = CliRunner()

        result = runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0

        output_lines = result.output.split("\n")
        ff_help_found = False
        for line in output_lines:
            if "--failed-first" in line or "--ff" in line:
                assert "failed" in line.lower() or "first" in line.lower()
                ff_help_found = True
                break

        assert ff_help_found, "Help text for --ff option not found"

    def test_ff_and_lf_can_be_combined(self):
        """Test that --ff and --lf can be used together (pytest allows this)."""
        coordinator = TestCoordinatorService(
            repo_root=Path("/tmp"),
            command_executor=MagicMock(),
            test_orchestrator=MagicMock(),
        )

        args = coordinator.build_pytest_args(
            suite="cli",
            last_failed=True,
            failed_first=True,
            verbose=False,
        )

        assert "--lf" in args
        assert "--ff" in args
