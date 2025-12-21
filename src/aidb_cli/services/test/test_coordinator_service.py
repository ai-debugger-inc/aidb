"""Service for coordinating test execution and orchestration."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import click

from aidb_cli.core.formatting import HeadingFormatter
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.managers.test import TestOrchestrator
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestCoordinatorService(BaseService):
    """Service for coordinating test execution.

    This service handles:
    - Test suite validation and prerequisite checking
    - Execution environment determination (Docker vs local)
    - Test argument building and validation
    - Result reporting and exit code handling
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        test_orchestrator: Optional["TestOrchestrator"] = None,
        ctx: click.Context | None = None,
    ) -> None:
        """Initialize the test coordinator service."""
        super().__init__(repo_root, command_executor)
        self.test_orchestrator = test_orchestrator
        self.ctx = ctx

    def determine_execution_environment(
        self,
        suite: str,
        docker_override: bool | None = None,
    ) -> bool:
        """Determine whether to use Docker or local execution.

        Args:
            suite: Test suite name
            docker_override: Explicit Docker preference

        Returns:
            True if Docker should be used, False otherwise
        """
        if docker_override is not None:
            return docker_override

        # Use metadata to determine Docker requirement
        if self.test_orchestrator:
            metadata = self.test_orchestrator.get_suite_metadata(suite)
            if metadata:
                return metadata.requires_docker

        # Fallback: default to Docker for safety if metadata unavailable
        # This should only happen for suite=None (pattern-based tests)
        logger.warning(
            "No metadata found for suite '%s', defaulting to Docker for isolation",
            suite if suite else "pattern-based",
        )
        return True

    def build_pytest_args(
        self,
        suite: str,  # noqa: ARG002
        markers: list[str] | None = None,
        pattern: str | None = None,
        target: list[str] | None = None,
        parallel: int | None = None,
        coverage: bool = False,
        verbose: bool = False,
        failfast: bool = False,
        last_failed: bool = False,
        failed_first: bool = False,
        timeout: int | None = None,
    ) -> list[str]:
        """Build pytest arguments from options.

        Args:
            suite: Test suite name
            markers: Pytest markers to filter tests
            pattern: Test pattern for filtering
            target: Direct test targets (can specify multiple)
            parallel: Number of parallel workers
            coverage: Enable coverage reporting
            verbose: Enable verbose output
            failfast: Stop on first failure
            last_failed: Only run tests that failed in the last run
            failed_first: Run failed tests first, then all other tests
            timeout: Per-test timeout in seconds

        Returns:
            List of pytest arguments
        """
        pytest_args = []

        if markers:
            marker_expr = " or ".join(markers)
            pytest_args.extend(["-m", marker_expr])

        if pattern:
            pytest_args.extend(["-k", pattern])

        if target:
            pytest_args.extend([self._process_target(t) for t in target])

        if parallel:
            pytest_args.extend(["-n", str(parallel)])
            # Use loadgroup distribution to respect xdist_group markers
            # This ensures @pytest.mark.serial tests run on a single worker
            # while other tests run in parallel on remaining workers
            pytest_args.extend(["--dist", "loadgroup"])

        if coverage:
            pytest_args.extend(self._build_coverage_args())
        else:
            # Disable coverage by default to prevent terminal UI conflicts
            # with streaming output (pytest-cov interferes with ANSI escape sequences)
            pytest_args.append("--no-cov")

        if verbose:
            pytest_args.append("-v")

        # Add failfast
        if failfast:
            pytest_args.append("-x")

        # Add last-failed
        if last_failed:
            pytest_args.append("--lf")

        # Add failed-first
        if failed_first:
            pytest_args.append("--ff")

        # Per-test timeout (pytest-timeout)
        if timeout:
            pytest_args.append(f"--timeout={timeout}")

        return pytest_args

    def _process_target(self, target: str) -> str:
        """Process test target specification.

        Args:
            target: Target specification

        Returns:
            Processed target for pytest
        """
        from aidb_cli.core.paths import ProjectPaths

        # Prepend test directory if target looks like a relative path
        tests_dir_str = str(ProjectPaths.TESTS_DIR)
        if (
            ("/" in target or target.endswith(".py") or "::" in target)
            and not target.startswith(f"{tests_dir_str}/")
            and not target.startswith("/")
        ):
            target = f"{tests_dir_str}/{target}"

        return target

    def _build_coverage_args(self) -> list[str]:
        """Build coverage-related arguments.

        Tracks all source modules to capture cross-module coverage.
        This ensures that when tests in one module call code in another
        module, that coverage is also recorded.

        Returns:
            List of coverage arguments for all source modules.
        """
        modules = ["aidb", "aidb_mcp", "aidb_cli", "aidb_common", "aidb_logging"]
        cov_args = [f"--cov={mod}" for mod in modules]
        cov_args.append("--cov-report=term-missing")
        return cov_args

    def validate_prerequisites(
        self,
        suite: str,
        languages: list[str] | None = None,
    ) -> bool:
        """Validate prerequisites for running a test suite.

        Parameters
        ----------
        suite : str
            Test suite name
        languages : list[str] | None
            Specific languages to validate adapters for.
            If None or ["all"], checks all supported languages.

        Returns
        -------
        bool
            True if prerequisites are met, False otherwise
        """
        if not self.test_orchestrator:
            # Without orchestrator, assume prerequisites are met
            return True

        return self.test_orchestrator.validate_prerequisites(suite, languages)

    def execute_tests(
        self,
        suite: str | None,
        languages: list[str] | None = None,
        use_docker: bool = False,
        **kwargs: Any,
    ) -> int:
        """Execute tests using the orchestrator.

        Args:
            suite: Test suite to run (defaults to base)
            languages: Language(s) to test (defaults to ["all"])
            use_docker: Whether to use Docker
            **kwargs: Additional test options

        Returns:
            Exit code from test execution
        """
        if not self.test_orchestrator:
            logger.error("Test orchestrator not configured")
            return 1

        # Default to all languages if not specified
        if languages is None:
            languages = ["all"]

        # Extract and validate known parameters from kwargs
        markers = kwargs.pop("markers", None)
        pattern = kwargs.pop("pattern", None)
        target = kwargs.pop("target", None)
        parallel = kwargs.pop("parallel", None)
        coverage = kwargs.pop("coverage", False)
        verbose = kwargs.pop("verbose", False)
        failfast = kwargs.pop("failfast", False)
        last_failed = kwargs.pop("last_failed", False)
        failed_first = kwargs.pop("failed_first", False)
        timeout = kwargs.pop("timeout", None)
        no_cache = kwargs.pop("no_cache", False)
        build = kwargs.pop("build", False)
        no_cleanup = kwargs.pop("no_cleanup", False)

        return self.test_orchestrator.run_suite(
            suite=suite,
            languages=languages,
            markers=markers,
            pattern=pattern,
            target=target,
            parallel=parallel,
            coverage=coverage,
            verbose=verbose,
            failfast=failfast,
            last_failed=last_failed,
            failed_first=failed_first,
            timeout=timeout,
            use_docker=use_docker,
            no_cache=no_cache,
            build=build,
            no_cleanup=no_cleanup,
        )

    def report_results(
        self,
        exit_code: int,
        session_id: str | None = None,
        use_docker: bool = False,
        container_data_dir: Path | None = None,
        pytest_logs_dir: Path | None = None,
        app_log_dir: Path | None = None,
    ) -> int:
        """Report test execution results with comprehensive log location summary.

        Args:
            exit_code: Exit code from test execution
            session_id: Test session ID for log tracking
            use_docker: Whether tests ran in Docker container
            container_data_dir: Path to container data directory (for Docker runs)
            pytest_logs_dir: Path to pytest logs directory (for local runs)
            app_log_dir: Path to application log directory

        Returns:
            Normalized exit code (0 for success, non-zero for failure)
        """
        # Determine status icon and message
        if exit_code == 5:
            # Normalize pytest exit code 5 (NO_TESTS_COLLECTED) to success
            status_icon = "⚠️"
            status_title = "NO TESTS RAN"
            exit_code = 0  # Normalize to success
        elif exit_code == 0:
            status_icon = "✅"
            status_title = "TESTS PASSED"
        else:
            status_icon = "❌"
            status_title = f"TESTS FAILED (exit code: {exit_code})"

        # Show status banner
        HeadingFormatter.section(status_title, icon=status_icon)

        # Show session ID
        if session_id:
            CliOutput.plain("")
            CliOutput.plain(f"Session:  {session_id}")

        # Show log locations
        CliOutput.plain("")
        CliOutput.plain("Logs:")

        if use_docker and container_data_dir:
            # Docker mode: show container data directory (relative to repo)
            rel_path = self._make_relative_if_possible(container_data_dir)
            CliOutput.plain(f"  Container: {rel_path}")
        elif pytest_logs_dir and session_id:
            # Local mode: show pytest logs and CLI logs
            test_log_path = pytest_logs_dir / session_id
            rel_test_path = self._make_relative_if_possible(test_log_path)
            CliOutput.plain(f"  Test: {rel_test_path}")

            if app_log_dir:
                # App logs are in home directory, show with ~
                app_log_str = str(app_log_dir).replace(str(Path.home()), "~")
                CliOutput.plain(f"  CLI:  {app_log_str}")

        return exit_code

    def _make_relative_if_possible(self, path: Path) -> str:
        """Convert path to relative if under repo root, otherwise return as-is.

        Parameters
        ----------
        path : Path
            Path to potentially make relative

        Returns
        -------
        str
            Relative path if under repo root, otherwise absolute path
        """
        try:
            return str(path.relative_to(self.repo_root))
        except ValueError:
            # Not under repo root, return as-is
            return str(path)
