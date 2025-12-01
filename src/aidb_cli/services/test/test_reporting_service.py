"""Service for test result aggregation and reporting."""

import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import Icons
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.io import safe_write_json
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


@dataclass
class TestResult:
    """Result from a test execution."""

    suite: str
    exit_code: int
    duration: float
    test_count: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    output: str | None = None


@dataclass
class TestReport:
    """Aggregated test report."""

    total_suites: int
    total_tests: int
    total_passed: int
    total_failed: int
    total_skipped: int
    total_duration: float
    suite_results: dict[str, TestResult]
    overall_success: bool


class TestReportingService(BaseService):
    """Service for test result aggregation and reporting.

    This service handles:
    - Collecting test results from multiple suites
    - Aggregating statistics across test runs
    - Generating test reports
    - Parsing test output for metrics
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the test reporting service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        """
        super().__init__(repo_root, command_executor)
        self.results: dict[str, TestResult] = {}
        self.start_times: dict[str, float] = {}

    def start_suite(self, suite: str) -> None:
        """Mark the start of a test suite execution.

        Parameters
        ----------
        suite : str
            Name of the test suite
        """
        self.start_times[suite] = time.time()
        logger.debug("Started tracking suite: %s", suite)

    def record_result(
        self,
        suite: str,
        exit_code: int,
        output: str | None = None,
        test_count: int | None = None,
        passed: int | None = None,
        failed: int | None = None,
        skipped: int | None = None,
    ) -> TestResult:
        """Record the result of a test suite execution.

        Parameters
        ----------
        suite : str
            Name of the test suite
        exit_code : int
            Exit code from test execution
        output : str, optional
            Test output to parse
        test_count : int, optional
            Total number of tests
        passed : int, optional
            Number of passed tests
        failed : int, optional
            Number of failed tests
        skipped : int, optional
            Number of skipped tests

        Returns
        -------
        TestResult
            The recorded test result
        """
        # Calculate duration
        duration = 0.0
        if suite in self.start_times:
            duration = time.time() - self.start_times[suite]
            del self.start_times[suite]

        # Parse output if counts not provided
        if output and test_count is None:
            metrics = self._parse_test_output(output)
            test_count = metrics.get("total", 0)
            passed = metrics.get("passed", 0)
            failed = metrics.get("failed", 0)
            skipped = metrics.get("skipped", 0)

        # Create result
        result = TestResult(
            suite=suite,
            exit_code=exit_code,
            duration=duration,
            test_count=test_count or 0,
            passed=passed or 0,
            failed=failed or 0,
            skipped=skipped or 0,
            output=output,
        )

        # Extract errors if failed
        if exit_code != 0 and output:
            result.errors = self._extract_errors(output)

        self.results[suite] = result
        logger.debug("Recorded result for %s: exit_code=%s", suite, exit_code)

        return result

    def _parse_test_output(self, output: str) -> dict[str, int]:
        """Parse test output for metrics.

        Parameters
        ----------
        output : str
            Test output to parse

        Returns
        -------
        dict[str, int]
            Parsed test metrics
        """
        metrics = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

        # Look for pytest-style output
        lines = output.split("\n")
        for line in lines:
            # Common pytest summary formats
            if "passed" in line or "failed" in line or "skipped" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        with contextlib.suppress(ValueError, IndexError):
                            metrics["passed"] = int(parts[i - 1])
                    elif part == "failed" and i > 0:
                        with contextlib.suppress(ValueError, IndexError):
                            metrics["failed"] = int(parts[i - 1])
                    elif part == "skipped" and i > 0:
                        with contextlib.suppress(ValueError, IndexError):
                            metrics["skipped"] = int(parts[i - 1])

        metrics["total"] = metrics["passed"] + metrics["failed"] + metrics["skipped"]
        return metrics

    def _extract_errors(self, output: str) -> list[str]:
        """Extract error messages from test output.

        Parameters
        ----------
        output : str
            Test output to parse

        Returns
        -------
        list[str]
            List of error messages
        """
        errors = []
        lines = output.split("\n")

        # Look for common error patterns
        in_error = False
        current_error = []

        for line in lines:
            if "FAILED" in line or "ERROR" in line:
                in_error = True
                current_error = [line]
            elif in_error:
                if line.startswith(("=", "-")):
                    # End of error section
                    if current_error:
                        errors.append("\n".join(current_error))
                    in_error = False
                    current_error = []
                else:
                    current_error.append(line)

        # Add any remaining error
        if current_error:
            errors.append("\n".join(current_error))

        return errors[:10]  # Limit to first 10 errors

    def aggregate_results(
        self,
        suite_filter: list[str] | None = None,
    ) -> TestReport:
        """Aggregate results across multiple test suites.

        Parameters
        ----------
        suite_filter : list[str], optional
            Only include these suites in aggregation

        Returns
        -------
        TestReport
            Aggregated test report
        """
        # Filter results if needed
        results_to_aggregate = self.results
        if suite_filter:
            results_to_aggregate = {
                k: v for k, v in self.results.items() if k in suite_filter
            }

        # Calculate totals
        total_tests = sum(r.test_count for r in results_to_aggregate.values())
        total_passed = sum(r.passed for r in results_to_aggregate.values())
        total_failed = sum(r.failed for r in results_to_aggregate.values())
        total_skipped = sum(r.skipped for r in results_to_aggregate.values())
        total_duration = sum(r.duration for r in results_to_aggregate.values())

        # Determine overall success
        overall_success = all(r.exit_code == 0 for r in results_to_aggregate.values())

        return TestReport(
            total_suites=len(results_to_aggregate),
            total_tests=total_tests,
            total_passed=total_passed,
            total_failed=total_failed,
            total_skipped=total_skipped,
            total_duration=total_duration,
            suite_results=results_to_aggregate,
            overall_success=overall_success,
        )

    def print_report(self, report: TestReport) -> None:
        """Print a formatted test report.

        Parameters
        ----------
        report : TestReport
            Report to print
        """
        from aidb_cli.core.formatting import HeadingFormatter

        CliOutput.plain("")
        HeadingFormatter.section("Test Results Summary", Icons.REPORT)

        # Overall status
        if report.overall_success:
            CliOutput.success("All tests passed!")
        else:
            CliOutput.error("Some tests failed")

        # Statistics
        CliOutput.plain(f"Suites run: {report.total_suites}")
        CliOutput.plain(f"Total tests: {report.total_tests}")
        CliOutput.plain(f"  Passed: {report.total_passed}")
        CliOutput.plain(f"  Failed: {report.total_failed}")
        CliOutput.plain(f"  Skipped: {report.total_skipped}")
        CliOutput.plain(f"Duration: {report.total_duration:.2f}s")

        # Per-suite results
        if report.suite_results:
            CliOutput.plain("\nPer-suite results:")
            for suite_name, result in report.suite_results.items():
                status_icon = Icons.SUCCESS if result.exit_code == 0 else Icons.ERROR
                CliOutput.plain(
                    f"  {status_icon} {suite_name}: "
                    f"{result.passed}/{result.test_count} passed "
                    f"({result.duration:.2f}s)",
                )

                # Show first error if any
                if result.errors and result.errors[0]:
                    error_preview = result.errors[0].split("\n")[0][:80]
                    CliOutput.plain(f"      Error: {error_preview}...")

        HeadingFormatter.table_separator()

    def save_report(self, report: TestReport, filepath: Path) -> None:
        """Save test report to file.

        Parameters
        ----------
        report : TestReport
            Report to save
        filepath : Path
            Path to save report to
        """
        report_data = {
            "total_suites": report.total_suites,
            "total_tests": report.total_tests,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "total_skipped": report.total_skipped,
            "total_duration": report.total_duration,
            "overall_success": report.overall_success,
            "suite_results": {
                suite: {
                    "exit_code": result.exit_code,
                    "duration": result.duration,
                    "test_count": result.test_count,
                    "passed": result.passed,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "errors": result.errors[:5] if result.errors else [],
                }
                for suite, result in report.suite_results.items()
            },
        }

        safe_write_json(filepath, report_data)

        logger.info("Saved test report to %s", filepath)

    def clear_results(self) -> None:
        """Clear all stored test results."""
        self.results.clear()
        self.start_times.clear()
        logger.debug("Cleared all test results")
