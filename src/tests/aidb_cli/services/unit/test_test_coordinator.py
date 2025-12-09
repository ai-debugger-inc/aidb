"""Unit tests for TestCoordinatorService (pytest args building)."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService


class TestBuildPytestArgs:
    """Test the build_pytest_args method in TestCoordinatorService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_executor = Mock()
        self.mock_orchestrator = Mock()
        self.service = TestCoordinatorService(
            repo_root=self.temp_dir,
            command_executor=self.mock_executor,
            test_orchestrator=self.mock_orchestrator,
        )

    def test_build_pytest_args_basic(self):
        """Test basic pytest args building."""
        result = self.service.build_pytest_args(suite="test")

        assert result == ["--no-cov"]

    def test_build_pytest_args_with_markers(self):
        """Test pytest args with markers."""
        result = self.service.build_pytest_args(
            suite="test",
            markers=("unit", "integration"),
        )

        assert result == ["-m", "unit or integration", "--no-cov"]

    def test_build_pytest_args_with_pattern(self):
        """Test pytest args with pattern."""
        result = self.service.build_pytest_args(
            suite="test",
            pattern="*database*",
        )

        assert result == ["-k", "*database*", "--no-cov"]

    def test_build_pytest_args_with_target(self):
        """Test pytest args with single target."""
        result = self.service.build_pytest_args(
            suite="test",
            target=["test_file.py::TestClass::test_method"],
        )

        assert result == ["src/tests/test_file.py::TestClass::test_method", "--no-cov"]

    def test_build_pytest_args_with_multiple_targets(self):
        """Test pytest args with multiple targets."""
        result = self.service.build_pytest_args(
            suite="test",
            target=[
                "test_file.py::TestClass::test_method1",
                "test_file.py::TestClass::test_method2",
            ],
        )

        assert result == [
            "src/tests/test_file.py::TestClass::test_method1",
            "src/tests/test_file.py::TestClass::test_method2",
            "--no-cov",
        ]

    def test_build_pytest_args_with_parallel(self):
        """Test pytest args with parallel workers."""
        result = self.service.build_pytest_args(
            suite="test",
            parallel=2,
        )

        assert result == ["-n", "2", "--dist", "loadgroup", "--no-cov"]

    def test_build_pytest_args_with_coverage(self):
        """Test pytest args with coverage."""
        result = self.service.build_pytest_args(
            suite="cli",
            coverage=True,
        )

        assert result == ["--cov=aidb_cli", "--cov-report=term-missing"]

    def test_build_pytest_args_with_verbose(self):
        """Test pytest args with verbose output."""
        result = self.service.build_pytest_args(
            suite="test",
            verbose=True,
        )

        assert result == ["--no-cov", "-v"]

    def test_build_pytest_args_with_failfast(self):
        """Test pytest args with failfast."""
        result = self.service.build_pytest_args(
            suite="test",
            failfast=True,
        )

        assert result == ["--no-cov", "-x"]

    def test_build_pytest_args_with_last_failed(self):
        """Test pytest args with last-failed."""
        result = self.service.build_pytest_args(
            suite="test",
            last_failed=True,
        )

        assert result == ["--no-cov", "--lf"]

    def test_build_pytest_args_with_failed_first(self):
        """Test pytest args with failed-first."""
        result = self.service.build_pytest_args(
            suite="test",
            failed_first=True,
        )

        assert result == ["--no-cov", "--ff"]

    def test_build_pytest_args_with_last_failed_and_failed_first(self):
        """Test pytest args with both last-failed and failed-first."""
        result = self.service.build_pytest_args(
            suite="test",
            last_failed=True,
            failed_first=True,
        )

        assert result == ["--no-cov", "--lf", "--ff"]

    def test_build_pytest_args_with_timeout(self):
        """Test pytest args with per-test timeout option."""
        result = self.service.build_pytest_args(
            suite="test",
            timeout=120,
        )

        assert result == ["--no-cov", "--timeout=120"]

    def test_build_pytest_args_combined_options(self):
        """Test pytest args with multiple options combined."""
        result = self.service.build_pytest_args(
            suite="mcp",
            markers=("unit", "integration"),
            pattern="*session*",
            parallel=2,
            coverage=True,
            verbose=True,
            failfast=True,
        )

        expected = [
            "-m",
            "unit or integration",
            "-k",
            "*session*",
            "-n",
            "2",
            "--dist",
            "loadgroup",
            "--cov=aidb_mcp",
            "--cov-report=term-missing",
            "-v",
            "-x",
        ]
        assert result == expected

    def test_build_pytest_args_first_param_is_suite(self):
        """Test that first parameter is suite (not keyword-only)."""
        # This should work since suite is the first parameter
        result = self.service.build_pytest_args("test")
        assert result == ["--no-cov"]


class TestProcessTarget:
    """Test the _process_target helper method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_executor = Mock()
        self.mock_orchestrator = Mock()
        self.service = TestCoordinatorService(
            repo_root=self.temp_dir,
            command_executor=self.mock_executor,
            test_orchestrator=self.mock_orchestrator,
        )

    def test_process_target_specific_test_function(self):
        """Test processing specific test function target."""
        target = "test_file.py::TestClass::test_method"
        result = self.service._process_target(target)

        assert result == f"src/tests/{target}"

    def test_process_target_test_file(self):
        """Test processing test file target."""
        target = "test_example.py"
        result = self.service._process_target(target)

        assert result == f"src/tests/{target}"

    def test_process_target_path_like(self):
        """Test processing path-like target."""
        target = "src/tests/test_example.py"
        result = self.service._process_target(target)

        assert result == target

    def test_process_target_test_function_name(self):
        """Test processing test function name target."""
        target = "test_function_name"
        result = self.service._process_target(target)

        assert result == target

    def test_process_target_generic_pattern(self):
        """Test processing generic pattern target."""
        target = "example_pattern"
        result = self.service._process_target(target)

        assert result == target


class TestBuildCoverageArgs:
    """Test the _build_coverage_args helper method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_executor = Mock()
        self.mock_orchestrator = Mock()
        self.service = TestCoordinatorService(
            repo_root=self.temp_dir,
            command_executor=self.mock_executor,
            test_orchestrator=self.mock_orchestrator,
        )

    def test_build_coverage_args_specific_suite(self):
        """Test coverage args for specific suite."""
        result = self.service._build_coverage_args("mcp")

        assert result == ["--cov=aidb_mcp", "--cov-report=term-missing"]

    def test_build_coverage_args_cli_suite(self):
        """Test coverage args for CLI suite."""
        result = self.service._build_coverage_args("cli")

        assert result == ["--cov=aidb_cli", "--cov-report=term-missing"]

    def test_build_coverage_args_mcp_suite(self):
        """Test coverage args for MCP suite."""
        result = self.service._build_coverage_args("mcp")

        assert result == ["--cov=aidb_mcp", "--cov-report=term-missing"]

    def test_build_coverage_args_custom_suite(self):
        """Test coverage args for custom suite name."""
        result = self.service._build_coverage_args("custom")

        assert result == ["--cov=aidb_custom", "--cov-report=term-missing"]


class TestTestCoordinatorServiceIntegration:
    """Integration tests for TestCoordinatorService methods working together."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_executor = Mock()
        self.mock_orchestrator = Mock()
        self.service = TestCoordinatorService(
            repo_root=self.temp_dir,
            command_executor=self.mock_executor,
            test_orchestrator=self.mock_orchestrator,
        )

    def test_realistic_pytest_args_scenario(self):
        """Test a realistic scenario with multiple pytest options."""
        # Simulate running integration tests with coverage for the MCP suite
        result = self.service.build_pytest_args(
            suite="mcp",
            markers=("integration",),
            pattern="*debug*",
            parallel=2,
            coverage=True,
            verbose=True,
        )

        expected = [
            "-m",
            "integration",
            "-k",
            "*debug*",
            "-n",
            "2",
            "--dist",
            "loadgroup",
            "--cov=aidb_mcp",
            "--cov-report=term-missing",
            "-v",
        ]
        assert result == expected

    def test_simple_unit_test_scenario(self):
        """Test a simple unit test scenario."""
        result = self.service.build_pytest_args(
            suite="cli",
            markers=("unit",),
            verbose=True,
            failfast=True,
        )

        expected = [
            "-m",
            "unit",
            "--no-cov",
            "-v",
            "-x",
        ]
        assert result == expected

    def test_specific_test_target_scenario(self):
        """Test running a specific test target."""
        result = self.service.build_pytest_args(
            suite="mcp",
            target=[
                "src/tests/aidb_mcp/test_handlers.py::TestHandlers::test_init",
            ],
            verbose=True,
        )

        expected = [
            "src/tests/aidb_mcp/test_handlers.py::TestHandlers::test_init",
            "--no-cov",
            "-v",
        ]
        assert result == expected


class TestReportResults:
    """Test the report_results method in TestCoordinatorService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_executor = Mock()
        self.mock_orchestrator = Mock()
        self.service = TestCoordinatorService(
            repo_root=self.temp_dir,
            command_executor=self.mock_executor,
            test_orchestrator=self.mock_orchestrator,
        )

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_success(self, mock_output, mock_heading):
        """Test report_results with successful exit code."""
        result = self.service.report_results(exit_code=0)

        assert result == 0
        mock_heading.section.assert_called_once_with("TESTS PASSED", icon="✅")

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_failure(self, mock_output, mock_heading):
        """Test report_results with failure exit code."""
        result = self.service.report_results(exit_code=1)

        assert result == 1
        mock_heading.section.assert_called_once_with(
            "TESTS FAILED (exit code: 1)",
            icon="❌",
        )

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_no_tests_collected(self, mock_output, mock_heading):
        """Test report_results normalizes pytest exit code 5 to success."""
        result = self.service.report_results(exit_code=5)

        assert result == 0
        mock_heading.section.assert_called_once_with("NO TESTS RAN", icon="⚠️")

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_docker_mode_with_session(
        self,
        mock_output,
        mock_heading,
    ):
        """Test report_results displays Docker container paths."""
        container_dir = self.temp_dir / ".cache" / "container-data"
        session_id = "mcp-20251109-123456"

        result = self.service.report_results(
            exit_code=0,
            session_id=session_id,
            use_docker=True,
            container_data_dir=container_dir,
        )

        assert result == 0

        # Verify session ID shown
        assert any(
            call[0][0] == f"Session:  {session_id}"
            for call in mock_output.plain.call_args_list
        )

        # Verify container logs path shown (relative path)
        assert any(
            "Container:" in call[0][0] for call in mock_output.plain.call_args_list
        )

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_local_mode_with_session(
        self,
        mock_output,
        mock_heading,
    ):
        """Test report_results displays local pytest and app log paths."""
        pytest_logs_dir = self.temp_dir / "pytest-logs"
        app_log_dir = self.temp_dir / ".cache" / "aidb" / "logs"
        session_id = "cli-20251109-123456"

        result = self.service.report_results(
            exit_code=0,
            session_id=session_id,
            use_docker=False,
            pytest_logs_dir=pytest_logs_dir,
            app_log_dir=app_log_dir,
        )

        assert result == 0

        # Verify session ID shown
        assert any(
            call[0][0] == f"Session:  {session_id}"
            for call in mock_output.plain.call_args_list
        )

        # Verify pytest logs path shown (with Test: prefix and relative path)
        assert any(
            "Test:" in call[0][0] and session_id in call[0][0]
            for call in mock_output.plain.call_args_list
        )

        # Verify application logs path shown (with CLI: prefix and ~ shorthand)
        assert any("CLI:" in call[0][0] for call in mock_output.plain.call_args_list)

    @patch("aidb_cli.services.test.test_coordinator_service.HeadingFormatter")
    @patch("aidb_cli.services.test.test_coordinator_service.CliOutput")
    def test_report_results_without_session_id(self, mock_output, mock_heading):
        """Test report_results handles None session_id gracefully."""
        result = self.service.report_results(
            exit_code=0,
            session_id=None,
            use_docker=False,
        )

        assert result == 0

        # Verify no session ID logging occurred
        for call in mock_output.plain.call_args_list:
            assert "Session:" not in str(call)
