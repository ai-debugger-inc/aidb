"""Unit tests for TestReportingService."""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.test.test_reporting_service import (
    TestReport,
    TestReportingService,
    TestResult,
)


class TestTestReportingService:
    """Test the TestReportingService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create service instance with mocks."""
        return TestReportingService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_start_suite_records_start_time(self, service):
        """Test that start_suite records the start time."""
        before = time.time()
        service.start_suite("test-suite")
        after = time.time()

        assert "test-suite" in service.start_times
        assert before <= service.start_times["test-suite"] <= after

    def test_record_result_without_start_suite(self, service):
        """Test recording result without prior start_suite call."""
        result = service.record_result(
            suite="test-suite",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        assert result.suite == "test-suite"
        assert result.exit_code == 0
        assert result.duration == 0.0
        assert result.test_count == 10
        assert result.passed == 10
        assert result.failed == 0
        assert result.skipped == 0

    def test_record_result_with_start_suite(self, service):
        """Test recording result with prior start_suite call."""
        service.start_suite("test-suite")
        time.sleep(0.1)  # Small delay to ensure duration > 0

        result = service.record_result(
            suite="test-suite",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        assert result.duration > 0.0
        assert "test-suite" not in service.start_times

    def test_record_result_with_output_parsing(self, service):
        """Test recording result that parses output."""
        output = """
        ============================= test session starts ==============================
        collected 15 items

        test_foo.py::test_one PASSED
        test_foo.py::test_two PASSED

        12 passed 3 failed in 2.5s
        """

        result = service.record_result(
            suite="test-suite",
            exit_code=1,
            output=output,
        )

        assert result.test_count == 15
        assert result.passed == 12
        assert result.failed == 3
        assert result.skipped == 0

    def test_record_result_manual_counts_override_parsing(self, service):
        """Test that manual counts override output parsing."""
        output = "12 passed, 3 failed"

        result = service.record_result(
            suite="test-suite",
            exit_code=0,
            output=output,
            test_count=20,
            passed=15,
            failed=5,
            skipped=0,
        )

        assert result.test_count == 20
        assert result.passed == 15
        assert result.failed == 5

    def test_record_result_extracts_errors_on_failure(self, service):
        """Test that errors are extracted from failed test output."""
        output = """FAILED test_foo.py::test_one - AssertionError: expected 1 got 2
Some traceback here
===========================
ERROR test_bar.py::test_two - ValueError: invalid value
More traceback
==========================="""

        result = service.record_result(
            suite="test-suite",
            exit_code=1,
            output=output,
            test_count=2,
            passed=0,
            failed=2,
            skipped=0,
        )

        assert len(result.errors) == 2
        assert "FAILED" in result.errors[0]
        assert "ERROR" in result.errors[1]

    def test_record_result_stores_in_results_dict(self, service):
        """Test that record_result stores result in results dict."""
        result = service.record_result(
            suite="test-suite",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        assert "test-suite" in service.results
        assert service.results["test-suite"] == result

    def test_parse_test_output_with_pytest_format(self, service):
        """Test parsing pytest-style output."""
        output = "25 passed 3 failed 2 skipped in 5.2s"

        metrics = service._parse_test_output(output)

        assert metrics["passed"] == 25
        assert metrics["failed"] == 3
        assert metrics["skipped"] == 2
        assert metrics["total"] == 30

    def test_parse_test_output_with_partial_info(self, service):
        """Test parsing output with only some metrics."""
        output = "15 passed in 2.1s"

        metrics = service._parse_test_output(output)

        assert metrics["passed"] == 15
        assert metrics["failed"] == 0
        assert metrics["skipped"] == 0
        assert metrics["total"] == 15

    def test_parse_test_output_with_no_matches(self, service):
        """Test parsing output with no recognizable metrics."""
        output = "Some random output without test metrics"

        metrics = service._parse_test_output(output)

        assert metrics["total"] == 0
        assert metrics["passed"] == 0
        assert metrics["failed"] == 0
        assert metrics["skipped"] == 0

    def test_extract_errors_finds_multiple_errors(self, service):
        """Test extracting multiple error messages."""
        output = """FAILED test_one - Error message 1
Line 2
Line 3
===========================
FAILED test_two - Error message 2
Line 2
==========================="""

        errors = service._extract_errors(output)

        assert len(errors) == 2
        assert "Error message 1" in errors[0]
        assert "Error message 2" in errors[1]

    def test_extract_errors_limits_to_ten(self, service):
        """Test that error extraction limits to 10 errors."""
        # Create output with 15 errors
        lines = []
        for i in range(15):
            lines.append(f"FAILED test_{i} - Error {i}")
            lines.append("===")

        output = "\n".join(lines)
        errors = service._extract_errors(output)

        assert len(errors) == 10

    def test_aggregate_results_with_single_suite(self, service):
        """Test aggregating results from a single suite."""
        service.record_result(
            suite="test-suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        report = service.aggregate_results()

        assert report.total_suites == 1
        assert report.total_tests == 10
        assert report.total_passed == 10
        assert report.total_failed == 0
        assert report.total_skipped == 0
        assert report.overall_success is True

    def test_aggregate_results_with_multiple_suites(self, service):
        """Test aggregating results from multiple suites."""
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )
        service.record_result(
            suite="suite-2",
            exit_code=0,
            test_count=15,
            passed=14,
            failed=0,
            skipped=1,
        )

        report = service.aggregate_results()

        assert report.total_suites == 2
        assert report.total_tests == 25
        assert report.total_passed == 24
        assert report.total_failed == 0
        assert report.total_skipped == 1
        assert report.overall_success is True

    def test_aggregate_results_with_failures(self, service):
        """Test aggregate results marks overall failure."""
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )
        service.record_result(
            suite="suite-2",
            exit_code=1,
            test_count=10,
            passed=8,
            failed=2,
            skipped=0,
        )

        report = service.aggregate_results()

        assert report.total_tests == 20
        assert report.total_passed == 18
        assert report.total_failed == 2
        assert report.overall_success is False

    def test_aggregate_results_with_suite_filter(self, service):
        """Test aggregating with suite filter."""
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )
        service.record_result(
            suite="suite-2",
            exit_code=0,
            test_count=15,
            passed=15,
            failed=0,
            skipped=0,
        )

        report = service.aggregate_results(suite_filter=["suite-1"])

        assert report.total_suites == 1
        assert report.total_tests == 10
        assert report.total_passed == 10

    def test_aggregate_results_empty(self, service):
        """Test aggregating with no results."""
        report = service.aggregate_results()

        assert report.total_suites == 0
        assert report.total_tests == 0
        assert report.overall_success is True

    def test_print_report_success(self, service, capsys):
        """Test printing successful report."""
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        report = service.aggregate_results()
        service.print_report(report)

        captured = capsys.readouterr()
        assert "All tests passed" in captured.out
        assert "Suites run: 1" in captured.out
        assert "Total tests: 10" in captured.out
        assert "Passed: 10" in captured.out

    def test_print_report_failure(self, service, capsys):
        """Test printing failed report."""
        service.record_result(
            suite="suite-1",
            exit_code=1,
            test_count=10,
            passed=8,
            failed=2,
            skipped=0,
        )

        report = service.aggregate_results()
        service.print_report(report)

        captured = capsys.readouterr()
        # Failure message goes to stderr
        assert "Some tests failed" in captured.err
        assert "Failed: 2" in captured.out

    def test_print_report_with_errors(self, service, capsys):
        """Test printing report with error messages."""
        output = "FAILED test_foo - AssertionError: test failed"
        service.record_result(
            suite="suite-1",
            exit_code=1,
            output=output,
            test_count=1,
            passed=0,
            failed=1,
            skipped=0,
        )

        report = service.aggregate_results()
        service.print_report(report)

        captured = capsys.readouterr()
        assert "Error:" in captured.out

    def test_save_report_creates_json_file(self, service, tmp_path):
        """Test saving report to JSON file."""
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        report = service.aggregate_results()
        filepath = tmp_path / "test_report.json"

        service.save_report(report, filepath)

        assert filepath.exists()

        # Verify content
        import json

        with filepath.open() as f:
            data = json.load(f)

        assert data["total_suites"] == 1
        assert data["total_tests"] == 10
        assert data["overall_success"] is True

    def test_save_report_limits_errors(self, service, tmp_path):
        """Test that save_report limits errors to 5 per suite."""
        # Create 10 errors
        [f"Error {i}" for i in range(10)]
        output = "\n".join([f"FAILED test_{i}\n===" for i in range(10)])

        service.record_result(
            suite="suite-1",
            exit_code=1,
            output=output,
            test_count=10,
            passed=0,
            failed=10,
            skipped=0,
        )

        report = service.aggregate_results()
        filepath = tmp_path / "test_report.json"

        service.save_report(report, filepath)

        # Verify errors are limited to 5
        import json

        with filepath.open() as f:
            data = json.load(f)

        assert len(data["suite_results"]["suite-1"]["errors"]) <= 5

    def test_clear_results_empties_dictionaries(self, service):
        """Test that clear_results empties all dictionaries."""
        service.start_suite("suite-1")
        service.record_result(
            suite="suite-1",
            exit_code=0,
            test_count=10,
            passed=10,
            failed=0,
            skipped=0,
        )

        assert len(service.results) > 0

        service.clear_results()

        assert len(service.results) == 0
        assert len(service.start_times) == 0
