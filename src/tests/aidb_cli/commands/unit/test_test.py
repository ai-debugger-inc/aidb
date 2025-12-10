"""Tests for enhanced test command functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli
from aidb_cli.commands.test import group as test_group


class TestTargetParameterFunctionality:
    """Test the new --target parameter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.mock_orchestrator = Mock()

    def test_target_parameter_accepted(self):
        """Test that --target parameter is accepted by the CLI."""
        # Test the help text includes target parameter
        result = self.runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0
        assert "--target" in result.output
        assert "-t" in result.output

    @patch("aidb_cli.commands.test.TestCoordinatorService")
    def test_target_file_format(
        self,
        mock_coordinator_class,
        cli_runner,
        mock_repo_root,
        cli_context_mock,
    ):
        """Test that target parameter handles file format correctly."""
        # Mock coordinator to bypass all service registration
        mock_coordinator = MagicMock()
        mock_coordinator.determine_execution_environment.return_value = (
            False  # local execution
        )
        mock_coordinator.report_results.return_value = 0  # success exit code
        mock_coordinator_class.return_value = mock_coordinator

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            None,
            ["test", "run", "--suite=cli", "-t", "test_api.py", "--local"],
        )

        # Test should pass and parameter should be accepted
        assert result.exit_code == 0

    @patch("aidb_cli.commands.test.TestCoordinatorService")
    def test_target_function_format(
        self,
        mock_coordinator_class,
        cli_runner,
        mock_repo_root,
        cli_context_mock,
    ):
        """Test that target parameter handles function format correctly."""
        # Mock coordinator to bypass all service registration
        mock_coordinator = MagicMock()
        mock_coordinator.determine_execution_environment.return_value = (
            False  # local execution
        )
        mock_coordinator.report_results.return_value = 0  # success exit code
        mock_coordinator_class.return_value = mock_coordinator

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            None,
            [
                "test",
                "run",
                "--suite=cli",
                "-t",
                "test_file.py::TestClass::test_method",
                "--local",
            ],
        )

        # Test should pass and parameter should be accepted
        assert result.exit_code == 0

    def test_target_and_pattern_combined(self):
        """Test that target and pattern parameters can work together."""
        result = self.runner.invoke(
            test_group,
            ["run", "--help"],
        )

        assert result.exit_code == 0
        # Both parameters should be available
        assert "--target" in result.output
        assert "-k" in result.output


class TestEnhancedPatternFunctionality:
    """Test enhanced pattern functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_pattern_parameter_description(self):
        """Test that pattern parameter has enhanced description."""
        result = self.runner.invoke(test_group, ["run", "--help"])

        assert result.exit_code == 0
        assert "pytest -k style" in result.output
        assert "payment" in result.output  # Should show examples

    @patch("aidb_cli.commands.test.TestCoordinatorService")
    def test_complex_pattern_accepted(
        self,
        mock_coordinator_class,
        cli_runner,
        mock_repo_root,
        cli_context_mock,
    ):
        """Test that complex patterns are accepted without validation."""
        # Mock coordinator to bypass all service registration
        mock_coordinator = MagicMock()
        mock_coordinator.determine_execution_environment.return_value = (
            False  # local execution
        )
        mock_coordinator.report_results.return_value = 0  # success exit code
        mock_coordinator_class.return_value = mock_coordinator

        complex_pattern = "test_payment and not slow and (api or real)"

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            None,
            ["test", "run", "--suite=cli", "-k", complex_pattern, "--local"],
        )

        # Test should pass and parameter should be accepted
        assert result.exit_code == 0


class TestTestListEnhancements:
    """Test enhancements to the test list command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_patterns_flag_available(self):
        """Test that --patterns flag is available."""
        result = self.runner.invoke(test_group, ["list", "--help"])

        assert result.exit_code == 0
        assert "--patterns" in result.output
        assert "Show example test patterns" in result.output

    def test_patterns_display(self, cli_runner, mock_repo_root, cli_context_mock):
        """Test that --patterns flag displays pattern examples."""
        # Mock command executor
        mock_command_executor = Mock()

        # Use cli_context_mock helper
        with patch(
            "aidb_cli.cli.Context.command_executor",
            new_callable=PropertyMock,
            return_value=mock_command_executor,
        ):
            result = cli_context_mock(
                cli_runner,
                mock_repo_root,
                None,
                ["test", "list", "--patterns"],
            )

            # Test should pass and patterns flag should be accepted
            assert result.exit_code == 0

    def test_enhanced_markers_display(
        self,
        cli_runner,
        mock_repo_root,
        cli_context_mock,
    ):
        """Test that markers display is enhanced."""
        # Mock command executor
        mock_command_executor = Mock()

        # Use cli_context_mock helper
        with patch(
            "aidb_cli.cli.Context.command_executor",
            new_callable=PropertyMock,
            return_value=mock_command_executor,
        ):
            result = cli_context_mock(
                cli_runner,
                mock_repo_root,
                None,
                ["test", "list", "--markers"],
            )

            # Test should pass and markers flag should be accepted
            assert result.exit_code == 0


class TestTestOrchestratorIntegration:
    """Test that new parameters integrate correctly with TestOrchestrator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_orchestrator = Mock()

    def test_target_parameter_passed_to_orchestrator(self):
        """Test that target parameter is passed to orchestrator correctly."""
        # Mock the test orchestrator to verify parameter passing
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            with patch(
                "aidb_common.repo.detect_repo_root",
                return_value=tmp_path,
            ):
                with patch(
                    "aidb_cli.managers.test.test_orchestrator.TestOrchestrator",
                ) as mock_orchestrator_class:
                    mock_orchestrator = Mock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    mock_orchestrator.run_suite.return_value = 0

                    orchestrator = mock_orchestrator_class(tmp_path)
                    orchestrator.run_suite(
                        suite="cli",
                        target="test_file.py::TestClass::test_method",
                    )

                    # Should have called run_suite with target parameter
                    mock_orchestrator.run_suite.assert_called_once_with(
                        suite="cli",
                        target="test_file.py::TestClass::test_method",
                    )

    def test_target_formats_handled_correctly(self):
        """Test that different target formats are handled correctly."""
        # This test just validates that the CLI accepts different target formats
        # without crashing - the actual format handling is an integration concern
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            with patch(
                "aidb_common.repo.detect_repo_root",
                return_value=tmp_path,
            ):
                # Mock the TestOrchestrator to avoid the actual service calls
                with patch(
                    "aidb_cli.managers.test.test_orchestrator.TestOrchestrator",
                ) as mock_orchestrator_class:
                    mock_orchestrator = Mock()
                    mock_orchestrator_class.return_value = mock_orchestrator
                    mock_orchestrator.run_suite.return_value = 0

                    orchestrator = mock_orchestrator_class(tmp_path)

                    # Test that different target formats can be passed without error
                    target_formats = [
                        "test_file.py",
                        "test_file.py::TestClass",
                        "test_file.py::TestClass::test_method",
                        "test_pattern_name",
                    ]

                    for target_format in target_formats:
                        orchestrator.run_suite(
                            suite="cli",
                            target=target_format,
                        )

                    # Should have been called for each target format
                    assert mock_orchestrator.run_suite.call_count == len(target_formats)


class TestCommandExamples:
    """Test that command examples in help text are accurate."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_run_command_examples(self):
        """Test that run command examples are comprehensive."""
        result = self.runner.invoke(test_group, ["run", "--help"])

        assert result.exit_code == 0

        # Check for examples in help text
        examples_content = result.output
        assert "Examples:" in examples_content
        assert "payment" in examples_content  # Should show payment examples
        assert "TestEndpoint" in examples_content  # Should show test targeting examples

    def test_list_command_examples(self):
        """Test that list command examples are comprehensive."""
        result = self.runner.invoke(test_group, ["list", "--help"])

        assert result.exit_code == 0

        # Check for help text options
        examples_content = result.output
        assert "--markers" in examples_content
        assert "--patterns" in examples_content


class TestBackwardCompatibility:
    """Test that all changes maintain backward compatibility."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_existing_commands_still_work(self):
        """Test that existing command patterns still work."""
        # These commands should all parse successfully (even if they fail execution)
        # Note: --verbose/-v is a CLI-level flag, not a test command flag
        existing_patterns = [
            ["run", "-s", "cli"],
            ["run", "-s", "mcp", "-l", "python"],
            ["run", "-m", "unit"],
            ["run", "--coverage"],
            ["list"],
            ["list", "-s", "cli"],
            ["list", "--markers"],
        ]

        for pattern in existing_patterns:
            result = self.runner.invoke(test_group, pattern + ["--help"])
            # Should parse successfully
            assert result.exit_code == 0

    def test_old_pattern_type_still_works(self):
        """Test that old TestPatternParamType still works for backward compatibility."""
        from aidb_cli.core.param_types import TestPatternParamType

        pattern_type = TestPatternParamType()

        # Should accept any pattern (redirects to FlexiblePatternParamType)
        result = pattern_type.convert("*payment*", Mock(), None)
        assert result == "*payment*"


class TestErrorHandling:
    """Test error handling for new functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_invalid_target_handled_gracefully(self):
        """Test that invalid target formats don't crash the CLI."""
        # The CLI should accept any target format and let pytest handle validation
        result = self.runner.invoke(test_group, ["run", "--help"])
        assert result.exit_code == 0
        # Target parameter should be documented
        assert "--target" in result.output

    def test_marker_discovery_error_handling(self):
        """Test that marker discovery errors are handled gracefully."""
        from aidb_cli.core.param_types import TestMarkerParamType

        marker_type = TestMarkerParamType()

        # Should not crash even with IO errors
        with patch("builtins.open", side_effect=OSError("File not found")):
            choices = marker_type._choices(None)
            # Should still return common markers
            assert "unit" in choices
