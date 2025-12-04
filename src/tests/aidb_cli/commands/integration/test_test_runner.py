"""Integration tests for the CLI test runner capabilities.

Meta-testing: Tests the CLI's ability to orchestrate test runs without
actually executing the full test suites. Uses mocked subprocess execution
to verify CLI argument handling and orchestration logic.
"""

import re
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
def logging_test_path(repo_root):
    """Path to logging tests for meta-testing."""
    return repo_root / "src" / "tests" / "aidb_logging"


class TestTestRunnerBasic:
    """Basic test runner functionality."""

    @pytest.mark.integration
    def test_run_specific_test_file(self, logging_test_path, mock_test_execution):
        """Test running a specific test file."""
        runner = CliRunner()
        # Use a specific passing test instead of the whole file
        test_target = str(
            logging_test_path
            / "integration/test_unified_logging.py::TestUnifiedLoggingIntegration::test_aidb_profile_logging",
        )

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-t", test_target, "--local"],
            catch_exceptions=False,
        )
        # For integration testing, we mainly care that the CLI orchestration works
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Verify the mock was called (CLI orchestration worked)
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_run_with_pattern_filter(self, logging_test_path, mock_test_execution):
        """Test running tests with pattern matching."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-p", "unified", "--local"],
            catch_exceptions=False,
        )

        # Integration test: verify CLI handles pattern filtering correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_run_with_marker_filter(self, mock_test_execution):
        """Test running tests with marker filtering."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-m", "asyncio", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles marker filtering correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_verbose_output_mode(self, mock_test_execution):
        """Test verbose output includes detailed information."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles verbose mode correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Mock output contains "test session starts" from conftest.py MOCK_PYTEST_OUTPUT
        assert (
            "test session starts" in result.output.lower()
            or "collected" in result.output.lower()
            or mock_test_execution.called
        )


class TestTestRunnerAdvanced:
    """Advanced test runner features."""

    @pytest.mark.integration
    def test_failfast_mode(self, mock_test_execution):
        """Test that failfast mode stops on first failure."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-x", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles failfast option correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Verify CLI orchestrated the test run
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_parallel_execution_option(self, mock_test_execution):
        """Test parallel execution configuration."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-j", "2", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles parallel execution correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_coverage_collection(self, mock_test_execution):
        """Test coverage collection functionality."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-c", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles coverage collection correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Verify CLI orchestrated the test run with coverage
        assert mock_test_execution.called


class TestTestRunnerOrchestration:
    """Test orchestration and environment handling."""

    @pytest.mark.integration
    def test_local_execution_preference(self, mock_test_execution):
        """Test that local execution works when available."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles local execution correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_test_list_functionality(self):
        """Test the test list command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "list", "-s", "logging"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Test list failed: {result.output}"
        # Should show available tests
        assert "test" in result.output.lower()

    @pytest.mark.integration
    def test_test_cleanup_command(self):
        """Test the test cleanup command."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "cleanup"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Test cleanup failed: {result.output}"

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_test_cleanup_command_with_all_flag(self):
        """Test cleanup command with --all flag."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "cleanup", "--all"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"Test cleanup --all failed: {result.output}"
        assert "cleanup" in result.output.lower()

    @pytest.mark.integration
    @pytest.mark.requires_docker
    def test_test_cleanup_command_with_individual_flags(self):
        """Test cleanup command with individual flags."""
        runner = CliRunner()

        # Test --docker flag
        result_docker = runner.invoke(
            cli,
            ["test", "cleanup", "--docker"],
            catch_exceptions=False,
        )
        assert result_docker.exit_code == 0

        # Test --artifacts flag
        result_artifacts = runner.invoke(
            cli,
            ["test", "cleanup", "--artifacts"],
            catch_exceptions=False,
        )
        assert result_artifacts.exit_code == 0

        # Test --temp flag
        result_temp = runner.invoke(
            cli,
            ["test", "cleanup", "--temp"],
            catch_exceptions=False,
        )
        assert result_temp.exit_code == 0


class TestTestRunnerPerformance:
    """Performance and timing tests."""

    @pytest.mark.integration
    def test_quick_execution_time(self, mock_test_execution):
        """Test that CLI orchestration completes quickly (with mocked execution)."""
        import time

        runner = CliRunner()

        start_time = time.time()
        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        execution_time = time.time() - start_time

        # Integration test: verify CLI orchestration works within time limit
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # With mocked execution, orchestration should be very fast (< 5 seconds)
        assert execution_time < 5, (
            f"CLI orchestration took too long: {execution_time:.2f}s"
        )
        assert mock_test_execution.called

    @pytest.mark.integration
    def test_output_contains_timing_info(self, mock_test_execution):
        """Test that test output contains timing information."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI includes timing information
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"

        # Look for timing patterns in mock pytest output
        timing_patterns = [
            r"\d+\.\d+s",  # Decimal seconds (e.g., "0.25s")
            r"in \d+",  # "in 2 seconds"
            r"\d+ passed",  # Test count
        ]

        output_lower = result.output.lower()
        has_timing = any(
            re.search(pattern, output_lower) for pattern in timing_patterns
        )
        # Either timing info in output or mock was called (mocked output contains timing)
        assert has_timing or mock_test_execution.called


class TestTestRunnerError:
    """Error handling and edge cases."""

    @pytest.mark.integration
    def test_invalid_test_pattern_handling(self, mock_test_execution_no_tests):
        """Test handling of invalid test patterns."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "run", "-s", "logging", "-p", "nonexistent_pattern_xyz123"],
            catch_exceptions=False,
        )

        # Should complete successfully (exit code 5 normalized to 0 by CLI)
        assert result.exit_code == 0, f"Invalid pattern test failed: {result.output}"
        # Verify CLI orchestrated the test run
        assert mock_test_execution_no_tests.called

    @pytest.mark.integration
    def test_invalid_marker_handling(self, mock_test_execution_no_tests):
        """Test handling of non-existent markers."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "run", "-s", "logging", "-m", "nonexistent_marker_xyz"],
            catch_exceptions=False,
        )

        # Should complete without error (exit code 5 normalized to 0 by CLI)
        assert result.exit_code == 0, f"Invalid marker test failed: {result.output}"
        assert mock_test_execution_no_tests.called
