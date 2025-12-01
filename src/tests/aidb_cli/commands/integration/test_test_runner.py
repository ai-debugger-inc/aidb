"""Integration tests for the CLI test runner capabilities.

Meta-testing: Tests the CLI's ability to run tests using the aidb_logging
test suite as lightweight, stable targets.
"""

import re
import subprocess
import time
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
    def test_run_specific_test_file(self, logging_test_path):
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
        assert "test_unified_logging.py" in result.output or "logging" in result.output

    @pytest.mark.integration
    def test_run_with_pattern_filter(self, logging_test_path):
        """Test running tests with pattern matching."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-p", "unified", "--local"],
            catch_exceptions=False,
        )

        # Integration test: verify CLI handles pattern filtering correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        assert "unified" in result.output.lower()

    @pytest.mark.integration
    def test_run_with_marker_filter(self):
        """Test running tests with marker filtering."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-m", "asyncio", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles marker filtering correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"

    @pytest.mark.integration
    def test_verbose_output_mode(self):
        """Test verbose output includes detailed information."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles verbose mode correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Should contain detailed test information in verbose mode
        assert (
            "test session starts" in result.output.lower()
            or "collected" in result.output.lower()
        )


class TestTestRunnerAdvanced:
    """Advanced test runner features."""

    @pytest.mark.integration
    def test_failfast_mode(self):
        """Test that failfast mode stops on first failure."""
        runner = CliRunner()

        # Note: Using actual logging tests which should pass
        # This tests the failfast mechanism works even if no failures occur
        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-x", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles failfast option correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Verify failfast option was passed
        assert (
            "-x" in result.output
            or "--tb=short" in result.output
            or "stop on first failure" in result.output.lower()
        )

    @pytest.mark.integration
    def test_parallel_execution_option(self):
        """Test parallel execution configuration."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-j", "2", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles parallel execution correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"

    @pytest.mark.integration
    def test_coverage_collection(self):
        """Test coverage collection functionality."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "-c", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles coverage collection correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"
        # Should mention coverage in output
        assert "coverage" in result.output.lower() or "cov" in result.output.lower()


class TestTestRunnerOrchestration:
    """Test orchestration and environment handling."""

    @pytest.mark.integration
    def test_local_execution_preference(self):
        """Test that local execution works when available."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI handles local execution correctly
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"

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
    def test_quick_execution_time(self):
        """Test that logging tests execute quickly (performance baseline)."""
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
        # Logging tests should complete reasonably quickly (< 30 seconds)
        assert execution_time < 30, (
            f"Test execution took too long: {execution_time:.2f}s"
        )

    @pytest.mark.integration
    def test_output_contains_timing_info(self):
        """Test that test output contains timing information."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["-v", "test", "run", "-s", "logging", "--local"],
            catch_exceptions=False,
        )
        # Integration test: verify CLI includes timing information
        assert result.exit_code == 0, f"CLI orchestration failed: {result.output}"

        # Look for timing patterns in pytest output
        timing_patterns = [
            r"\d+\.\d+s",  # Decimal seconds (e.g., "0.25s")
            r"in \d+",  # "in 2 seconds"
            r"\d+ passed",  # Test count
        ]

        output_lower = result.output.lower()
        has_timing = any(
            re.search(pattern, output_lower) for pattern in timing_patterns
        )
        assert has_timing, f"No timing information found in output: {result.output}"


class TestTestRunnerError:
    """Error handling and edge cases."""

    @pytest.mark.integration
    def test_invalid_test_pattern_handling(self):
        """Test handling of invalid test patterns."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "run", "-s", "logging", "-p", "nonexistent_pattern_xyz123"],
            catch_exceptions=False,
        )

        # Should complete successfully but with no tests collected/run
        assert result.exit_code == 0, f"Invalid pattern test failed: {result.output}"
        # Should indicate no tests were collected or run
        assert (
            "no tests ran" in result.output.lower()
            or "collected 0 items" in result.output.lower()
            or "0 passed" in result.output.lower()
            or "deselected" in result.output.lower()
        ), f"Expected indication of no tests, got: {result.output}"

    @pytest.mark.integration
    def test_invalid_marker_handling(self):
        """Test handling of non-existent markers."""
        runner = CliRunner()

        result = runner.invoke(
            cli,
            ["test", "run", "-s", "logging", "-m", "nonexistent_marker_xyz"],
            catch_exceptions=False,
        )

        # Should complete without error but with no tests
        assert result.exit_code == 0, f"Invalid marker test failed: {result.output}"
