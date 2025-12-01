"""Service for test coverage and report generation."""

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestCoverageService(BaseService):
    """Service for handling test coverage and reports.

    This service handles:
    - Coverage report generation in various formats
    - Test result analysis and reporting
    - Failed test tracking
    - Coverage data management
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the test coverage service."""
        super().__init__(repo_root, command_executor)
        self.pytest_cache = repo_root / ".pytest_cache"
        self.coverage_file = repo_root / ".coverage"

    def check_test_results_exist(self) -> bool:
        """Check if test results exist.

        Returns:
            True if test results are available
        """
        return self.pytest_cache.exists()

    def generate_report(
        self,
        format: str = "terminal",
        output: Path | None = None,
        coverage: bool = False,
    ) -> bool:
        """Generate test report in specified format.

        Args:
            format: Report format (terminal, html, xml, json)
            output: Optional output file path
            coverage: Include coverage information

        Returns:
            True if report was generated successfully
        """
        if not self.check_test_results_exist():
            CliOutput.warning("No test results found. Run tests first.")
            return False

        if format == "terminal":
            return self._generate_terminal_report(coverage)
        if format == "html":
            return self._generate_html_report(output, coverage)
        if format in ["xml", "json"]:
            CliOutput.warning(f"{format.upper()} format not yet implemented")
            CliOutput.info("Coming soon!")
            return False

        return True

    def _generate_terminal_report(self, coverage: bool) -> bool:
        """Generate terminal-based test report.

        Args:
            coverage: Include coverage information

        Returns:
            True if report was generated successfully
        """
        from aidb_cli.core.constants import Icons
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Test Report", Icons.REPORT)

        self._show_failed_tests()

        if coverage:
            self._show_coverage_report()

        CliOutput.info("\nReport generation complete!")
        return True

    def _generate_html_report(
        self,
        output: Path | None,
        coverage: bool,
    ) -> bool:
        """Generate HTML test report.

        Args:
            output: Optional output directory
            coverage: Include coverage information

        Returns:
            True if report was generated successfully
        """
        if not coverage:
            CliOutput.warning("HTML format currently only supports coverage reports")
            CliOutput.info("Run with --coverage flag")
            return False

        if not self.coverage_file.exists():
            CliOutput.warning("No coverage data found. Run tests with --coverage flag.")
            return False

        cmd = [
            str(self.repo_root / "venv" / "bin" / "coverage"),
            "html",
        ]

        if output:
            cmd.extend(["-d", str(output)])

        result = self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            output_dir = output or self.repo_root / "htmlcov"
            CliOutput.success(f"HTML report generated: {output_dir}/index.html")
            return True
        CliOutput.error("Failed to generate HTML report")
        if result.stderr:
            CliOutput.error(result.stderr)
        return False

    def _show_failed_tests(self) -> None:
        """Show information about failed tests from last run."""
        lastfailed = self.pytest_cache / "v" / "cache" / "lastfailed"
        if not lastfailed.exists():
            return

        try:
            failed_tests = safe_read_json(lastfailed) or {}

            if failed_tests:
                CliOutput.error(f"Failed Tests: {len(failed_tests)}")
                for test in list(failed_tests.keys())[:10]:
                    CliOutput.info(f"  - {test}")
                if len(failed_tests) > 10:
                    CliOutput.info(f"  ... and {len(failed_tests) - 10} more")
            else:
                CliOutput.success("\nAll tests passed in last run!")
        except FileOperationError as e:
            logger.debug("Could not read failed tests: %s", e)

    def _show_coverage_report(self) -> None:
        """Show coverage report in terminal."""
        from aidb_cli.core.constants import Icons
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.subsection("Coverage Report", Icons.TARGET)

        if not self.coverage_file.exists():
            CliOutput.warning(
                "No coverage data found. Run tests with --coverage flag.",
            )
            return

        cmd = [
            str(self.repo_root / "venv" / "bin" / "coverage"),
            "report",
        ]

        self.command_executor.execute(
            cmd,
            cwd=self.repo_root,
            check=False,
        )

    def get_test_statistics(self) -> dict[str, int | float | None]:
        """Get test statistics from last run.

        Returns:
            Dictionary with test statistics
        """
        stats: dict[str, int | float | None] = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "coverage_percentage": None,
        }

        lastfailed = self.pytest_cache / "v" / "cache" / "lastfailed"
        if lastfailed.exists():
            try:
                failed_tests = safe_read_json(lastfailed) or {}
                stats["failed"] = len(failed_tests)
            except FileOperationError:
                pass

        if self.coverage_file.exists():
            cmd = [
                str(self.repo_root / "venv" / "bin" / "coverage"),
                "report",
                "--format=total",
            ]
            result = self.command_executor.execute(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                with contextlib.suppress(ValueError):
                    stats["coverage_percentage"] = float(result.stdout.strip())

        return stats
