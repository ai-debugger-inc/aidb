"""Service for test suite management and discovery."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb_cli.core.constants import Icons
from aidb_cli.core.formatting import HeadingFormatter
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.test.markers import get_marker_descriptions
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestSuiteService(BaseService):
    """Service for managing test suites and their metadata.

    This service handles:
    - Test suite enumeration and discovery
    - Suite metadata management
    - Test file listing within suites
    - Marker discovery and descriptions
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the test suite service."""
        super().__init__(repo_root, command_executor)
        self.test_root = repo_root / "src" / "tests"

    def list_suites(
        self,
        suite_filter: str | None = None,
        verbose: bool = False,
    ) -> dict[str, dict]:
        """List available test suites.

        Args:
            suite_filter: Optional filter for specific suite
            verbose: Include detailed information

        Returns:
            Dictionary of suite information
        """
        from aidb_cli.services.test import TestSuites

        suites = {}

        for suite_def in TestSuites.all():
            suite_name = suite_def.name

            # Skip special aggregate suites (unit, integration, base)
            if suite_name in ("unit", "integration", "base"):
                continue

            # Apply suite filter
            if suite_filter and suite_name != suite_filter:
                continue

            # Determine the actual path
            suite_path = self.test_root / suite_def.path
            if not suite_path.exists():
                logger.debug("Suite path does not exist: %s", suite_path)
                continue

            # Count test files
            test_files = list(suite_path.rglob("test_*.py"))

            suite_info = {
                "path": str(suite_path),
                "test_count": len(test_files),
                "test_files": [],
            }

            if verbose:
                # Include sample test files
                suite_info["test_files"] = [
                    str(f.relative_to(suite_path)) for f in test_files[:5]
                ]

            suites[suite_name] = suite_info

        return suites

    def list_markers(
        self,
        marker_filter: str | None = None,
    ) -> dict[str, str]:
        """List available pytest markers with descriptions.

        Args:
            marker_filter: Optional filter for specific marker

        Returns:
            Dictionary of marker names to descriptions
        """
        from aidb_cli.core.param_types import TestMarkerParamType

        # Get available markers
        marker_type = TestMarkerParamType()
        available_markers = marker_type._choices(None)
        marker_descriptions = get_marker_descriptions()

        markers = {}
        for marker_name in available_markers:
            if marker_filter and marker_filter != marker_name:
                continue

            description = marker_descriptions.get(marker_name, "Custom marker")
            markers[marker_name] = description

        return markers

    def get_pattern_examples(self) -> list[tuple[str, str]]:
        """Get example test patterns for filtering.

        Returns:
            List of (pattern, description) tuples
        """
        return [
            ("test_payment*", "Tests starting with 'test_payment'"),
            ("*_integration*", "Integration tests"),
            ("*_multilang*", "Multi-language tests"),
            ("test_*_real*", "Tests with 'real' in the middle of name"),
            ("*slow* and not unit", "Slow tests but not unit tests"),
            ("not flaky", "All tests except flaky ones"),
            ("TestAPI* or test_api*", "API test classes or functions"),
        ]

    def find_matching_files(
        self,
        pattern: str,
        suite: str | None = None,
        limit: int = 10,
    ) -> list[Path]:
        """Find test files matching a pattern.

        Args:
            pattern: File pattern to match
            suite: Optional suite to search within
            limit: Maximum number of results to return

        Returns:
            List of matching file paths
        """
        # Determine search path
        search_path = self.test_root / f"aidb_{suite}" if suite else self.test_root

        if not search_path.exists():
            return []

        # Find matching files using Path.rglob
        matches = [str(p) for p in search_path.rglob(pattern)]

        # Convert to Path objects and limit results
        return [Path(m) for m in matches[:limit]]

    def display_suites(
        self,
        suites: dict[str, dict],
        verbose: bool = False,
    ) -> None:
        """Display test suite information.

        Args:
            suites: Dictionary of suite information
            verbose: Show detailed information
        """
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Test Suites", Icons.LIST)

        for suite_name, info in suites.items():
            CliOutput.success(
                f"  {suite_name:<15} {info['test_count']:>3} test files",
            )

            if verbose and info.get("test_files"):
                for test_file in info["test_files"]:
                    CliOutput.info(f"    - {test_file}")

                remaining = info["test_count"] - len(info["test_files"])
                if remaining > 0:
                    CliOutput.info(f"    ... and {remaining} more")

        CliOutput.info(f"Total: {len(suites)} test suites")

    def display_markers(self, markers: dict[str, str]) -> None:
        """Display pytest markers with descriptions.

        Args:
            markers: Dictionary of marker names to descriptions
        """

        from aidb_cli.core.constants import Icons
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Pytest Markers", Icons.MARKERS)

        for marker_name, description in markers.items():
            CliOutput.plain(f"  {marker_name:<15} {description}")

        CliOutput.info(f"Total: {len(markers)} markers available")

    def display_pattern_examples(self) -> None:
        """Display example test patterns."""
        HeadingFormatter.section("Pattern Examples")

        patterns = self.get_pattern_examples()
        CliOutput.info("Common patterns for -p/--pattern option:")

        for pattern, description in patterns:
            CliOutput.info(f"  {pattern:<30} {description}")

        CliOutput.info(
            "\nNote: Patterns use pytest -k syntax and support "
            "'and', 'or', 'not' operators",
        )

    def display_matching_files(
        self,
        pattern: str,
        files: list[Path],
        total: int | None = None,
    ) -> None:
        """Display files matching a pattern.

        Args:
            pattern: The pattern that was searched
            files: List of matching files
            total: Total count if more than displayed
        """
        HeadingFormatter.section("Matching Files")

        if files:
            CliOutput.info(f"Files matching '{pattern}':")
            for file_path in files:
                rel_path = file_path.relative_to(self.test_root)
                CliOutput.info(f"  - {rel_path}")

            if total and total > len(files):
                CliOutput.info(f"  ... and {total - len(files)} more")
        else:
            CliOutput.warning(f"No files matching '{pattern}'")
