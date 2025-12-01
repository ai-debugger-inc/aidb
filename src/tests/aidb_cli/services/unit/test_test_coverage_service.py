"""Unit tests for TestCoverageService."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.test.test_coverage_service import TestCoverageService
from aidb_common.io.files import FileOperationError


class TestTestCoverageService:
    """Test the TestCoverageService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create a TestCoverageService instance."""
        return TestCoverageService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization."""
        service = TestCoverageService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.repo_root == tmp_path
        assert service.pytest_cache == tmp_path / ".pytest_cache"
        assert service.coverage_file == tmp_path / ".coverage"

    def test_check_test_results_exist_true(self, service):
        """Test checking test results when they exist."""
        service.pytest_cache.mkdir()
        result = service.check_test_results_exist()
        assert result is True

    def test_check_test_results_exist_false(self, service):
        """Test checking test results when they don't exist."""
        result = service.check_test_results_exist()
        assert result is False

    def test_generate_report_no_results(self, service):
        """Test generate_report when no test results exist."""
        result = service.generate_report()
        assert result is False

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_generate_report_terminal_success(
        self,
        mock_heading,
        service,
        mock_command_executor,
    ):
        """Test generating terminal report successfully."""
        service.pytest_cache.mkdir(parents=True)

        result = service.generate_report(format="terminal")

        assert result is True
        mock_heading.section.assert_called_once()

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_generate_report_terminal_with_coverage(
        self,
        mock_heading,
        service,
        mock_command_executor,
    ):
        """Test generating terminal report with coverage."""
        service.pytest_cache.mkdir(parents=True)
        service.coverage_file.write_text("coverage data")

        mock_command_executor.execute.return_value = Mock(returncode=0)

        result = service.generate_report(format="terminal", coverage=True)

        assert result is True
        mock_command_executor.execute.assert_called_once()
        cmd = mock_command_executor.execute.call_args[0][0]
        assert "coverage" in cmd[0]
        assert "report" in cmd

    def test_generate_report_html_no_coverage(self, service):
        """Test generating HTML report without coverage flag."""
        service.pytest_cache.mkdir(parents=True)

        result = service.generate_report(format="html")

        assert result is False

    def test_generate_report_html_no_coverage_file(self, service):
        """Test generating HTML report when coverage file missing."""
        service.pytest_cache.mkdir(parents=True)

        result = service.generate_report(format="html", coverage=True)

        assert result is False

    def test_generate_report_html_success(self, service, mock_command_executor):
        """Test generating HTML report successfully."""
        service.pytest_cache.mkdir(parents=True)
        service.coverage_file.write_text("coverage data")

        mock_command_executor.execute.return_value = Mock(returncode=0)

        result = service.generate_report(format="html", coverage=True)

        assert result is True
        cmd = mock_command_executor.execute.call_args[0][0]
        assert "coverage" in cmd[0]
        assert "html" in cmd

    def test_generate_report_html_custom_output(self, service, mock_command_executor):
        """Test generating HTML report with custom output directory."""
        service.pytest_cache.mkdir(parents=True)
        service.coverage_file.write_text("coverage data")
        output_dir = service.repo_root / "custom-htmlcov"

        mock_command_executor.execute.return_value = Mock(returncode=0)

        result = service.generate_report(
            format="html",
            output=output_dir,
            coverage=True,
        )

        assert result is True
        cmd = mock_command_executor.execute.call_args[0][0]
        assert "-d" in cmd
        assert str(output_dir) in cmd

    def test_generate_report_html_failure(self, service, mock_command_executor):
        """Test generating HTML report when command fails."""
        service.pytest_cache.mkdir(parents=True)
        service.coverage_file.write_text("coverage data")

        mock_command_executor.execute.return_value = Mock(
            returncode=1,
            stderr="Coverage error",
        )

        result = service.generate_report(format="html", coverage=True)

        assert result is False

    def test_generate_report_xml_not_implemented(self, service):
        """Test generating XML report (not yet implemented)."""
        service.pytest_cache.mkdir(parents=True)

        result = service.generate_report(format="xml")

        assert result is False

    def test_generate_report_json_not_implemented(self, service):
        """Test generating JSON report (not yet implemented)."""
        service.pytest_cache.mkdir(parents=True)

        result = service.generate_report(format="json")

        assert result is False

    def test_show_failed_tests_with_failures(self, service):
        """Test showing failed tests when failures exist."""
        lastfailed = service.pytest_cache / "v" / "cache" / "lastfailed"
        lastfailed.parent.mkdir(parents=True)
        lastfailed.write_text(
            '{"test1.py::test_foo": true, "test2.py::test_bar": true}',
        )

        # Should not raise error
        service._show_failed_tests()

    def test_show_failed_tests_no_failures(self, service):
        """Test showing failed tests when no failures."""
        lastfailed = service.pytest_cache / "v" / "cache" / "lastfailed"
        lastfailed.parent.mkdir(parents=True)
        lastfailed.write_text("{}")

        # Should not raise error
        service._show_failed_tests()

    def test_show_failed_tests_many_failures(self, service):
        """Test showing failed tests truncates when many failures."""
        lastfailed = service.pytest_cache / "v" / "cache" / "lastfailed"
        lastfailed.parent.mkdir(parents=True)

        # Create 15 failures
        failures = {f"test{i}.py::test_func": True for i in range(15)}
        lastfailed.write_text(json.dumps(failures))

        # Should not raise error (will show only first 10)
        service._show_failed_tests()

    @patch("aidb_common.io.safe_read_json")
    def test_show_failed_tests_file_not_exists(self, mock_read_json, service):
        """Test showing failed tests when file doesn't exist."""
        service._show_failed_tests()

        # Should handle gracefully when file doesn't exist
        mock_read_json.assert_not_called()

    @patch("aidb_common.io.safe_read_json")
    def test_show_failed_tests_read_error(self, mock_read_json, service):
        """Test showing failed tests when read fails."""
        lastfailed = service.pytest_cache / "v" / "cache" / "lastfailed"
        lastfailed.parent.mkdir(parents=True)
        lastfailed.write_text("{}")

        mock_read_json.side_effect = FileOperationError("Read error")

        # Should handle error gracefully
        service._show_failed_tests()

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_show_coverage_report_success(
        self,
        mock_heading,
        service,
        mock_command_executor,
    ):
        """Test showing coverage report successfully."""
        service.coverage_file.write_text("coverage data")

        mock_command_executor.execute.return_value = Mock(returncode=0)

        service._show_coverage_report()

        mock_command_executor.execute.assert_called_once()
        cmd = mock_command_executor.execute.call_args[0][0]
        assert "coverage" in cmd[0]
        assert "report" in cmd

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_show_coverage_report_no_file(self, mock_heading, service):
        """Test showing coverage report when file missing."""
        service._show_coverage_report()

        # Should warn about missing file
        mock_heading.subsection.assert_called_once()

    def test_get_test_statistics_with_failures(self, service):
        """Test getting test statistics with failures."""
        lastfailed = service.pytest_cache / "v" / "cache" / "lastfailed"
        lastfailed.parent.mkdir(parents=True)
        lastfailed.write_text('{"test1.py::test_foo": true}')

        stats = service.get_test_statistics()

        assert stats["failed"] == 1
        assert stats["coverage_percentage"] is None

    @patch("aidb_common.io.safe_read_json")
    def test_get_test_statistics_with_coverage(
        self,
        mock_read_json,
        service,
        mock_command_executor,
    ):
        """Test getting test statistics with coverage."""
        service.coverage_file.write_text("coverage data")
        mock_read_json.return_value = {}

        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="85.5",
        )

        stats = service.get_test_statistics()

        assert stats["failed"] == 0
        assert stats["coverage_percentage"] == 85.5

    @patch("aidb_common.io.safe_read_json")
    def test_get_test_statistics_coverage_error(
        self,
        mock_read_json,
        service,
        mock_command_executor,
    ):
        """Test getting test statistics when coverage command fails."""
        service.coverage_file.write_text("coverage data")
        mock_read_json.return_value = {}

        mock_command_executor.execute.return_value = Mock(returncode=1)

        stats = service.get_test_statistics()

        assert stats["coverage_percentage"] is None

    @patch("aidb_common.io.safe_read_json")
    def test_get_test_statistics_invalid_coverage(
        self,
        mock_read_json,
        service,
        mock_command_executor,
    ):
        """Test getting test statistics with invalid coverage value."""
        service.coverage_file.write_text("coverage data")
        mock_read_json.return_value = {}

        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="invalid",
        )

        stats = service.get_test_statistics()

        # Should handle ValueError gracefully
        assert stats["coverage_percentage"] is None

    def test_initialization_without_command_executor(self, tmp_path):
        """Test initialization without explicit command executor."""
        service = TestCoverageService(repo_root=tmp_path)
        assert service.repo_root == tmp_path
        assert service.command_executor is not None
