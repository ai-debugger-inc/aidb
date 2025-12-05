"""Unified test orchestrator for AIDB CLI - refactored version.

This module provides advanced test orchestration capabilities beyond the basic
TestManager, including:
- Test discovery and metadata management
- Multi-suite coordination
- Test result aggregation
- Intelligent execution strategies
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import click

from aidb_cli.core.constants import (
    DEFAULT_LOG_LINES,
    Icons,
)
from aidb_cli.core.formatting import HeadingFormatter
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.docker import DockerOrchestrator
from aidb_cli.managers.test.test_manager import TestManager
from aidb_cli.services.test import (
    ParallelTestExecutionService,
    TestExecutionService,
    TestReportingService,
    TestSuites,
)
from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService
from aidb_cli.services.test.test_discovery_service import (
    TestDiscoveryService,
    TestSuiteMetadata,
)
from aidb_common.constants import Language
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestOrchestrator(TestManager):
    """Advanced test orchestration extending TestManager.

    Provides comprehensive test management including discovery, execution, and result
    aggregation across all test types. This refactored version extends TestManager,
    leveraging the services already registered there.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        command_executor: Optional["CommandExecutor"] = None,
        ctx: click.Context | None = None,
    ) -> None:
        """Initialize the test orchestrator.

        Parameters
        ----------
        repo_root : Path, optional
            Repository root directory. If not provided, will be auto-detected.
        command_executor : CommandExecutor, optional
            Command executor instance to use for running commands.
        ctx : click.Context, optional
            CLI context for accessing centralized environment.
        """
        super().__init__(repo_root, command_executor)

        # Store Click context when provided (initialize before using it)
        self.ctx: click.Context | None = ctx
        self._test_results: dict[str, Any] = {}
        self._docker_orchestrator: DockerOrchestrator | None = None
        self._coordinator: TestCoordinatorService | None = None
        self._discovery_service: TestDiscoveryService | None = None

        # Initialize orchestration services
        from aidb_cli.managers.test.orchestrator import TestProfileResolver

        self._profile_resolver = TestProfileResolver()

    @property
    def docker_orchestrator(self) -> DockerOrchestrator:
        """Get Docker orchestrator instance, creating if necessary.

        Returns
        -------
        DockerOrchestrator
            Docker orchestrator instance
        """
        if self._docker_orchestrator is None:
            self._docker_orchestrator = DockerOrchestrator(self.repo_root, ctx=self.ctx)
        return self._docker_orchestrator

    def _register_services(self) -> None:
        """Register services for test orchestration."""
        super()._register_services()  # Register parent services first

    @property
    def coordinator(self) -> TestCoordinatorService:
        """Get test coordinator service, creating if necessary."""
        if self._coordinator is None:
            self._coordinator = TestCoordinatorService(
                self.repo_root,
                self.command_executor,
                self,
            )
        return self._coordinator

    @property
    def discovery_service(self) -> TestDiscoveryService:
        """Get test discovery service, creating if necessary."""
        if self._discovery_service is None:
            self._discovery_service = TestDiscoveryService(
                self.repo_root,
                self.command_executor,
            )
        return self._discovery_service

    @property
    def current_session_id(self) -> str | None:
        """Get the current test session ID from the execution service.

        Returns
        -------
        str | None
            Current session ID, or None if no session has been started
        """
        execution_service = self.get_service(TestExecutionService)
        return execution_service.current_session_id

    def get_suite_metadata(self, suite: str) -> TestSuiteMetadata | None:
        """Get metadata for a specific test suite.

        Parameters
        ----------
        suite : str
            Name of the test suite

        Returns
        -------
        TestSuiteMetadata or None
            Metadata for the suite if found
        """
        return self.discovery_service.get_suite_metadata(suite)

    def validate_prerequisites(
        self,
        suite: str,
        languages: list[str] | None = None,
    ) -> bool:
        """Validate prerequisites for running a test suite.

        Parameters
        ----------
        suite : str
            Name of the test suite
        languages : list[str] | None
            Specific languages to validate adapters for.
            If None or ["all"], checks all supported languages.

        Returns
        -------
        bool
            True if all prerequisites are met
        """
        metadata = self.get_suite_metadata(suite)
        if not metadata:
            logger.debug("No metadata found for suite '%s'", suite)
            return True  # Allow running anyway

        if metadata.requires_docker and not self.check_prerequisites(
            check_adapters=False,
        ):
            return False

        if metadata.adapters_required:
            # Resolve "all" to None (checks all languages in check_adapters_* methods)
            langs_to_check = None
            if languages and languages != ["all"]:
                langs_to_check = languages

            # For Docker suites, check cache only (no source fallback).
            # Docker mounts .cache/adapters/ into containers.
            if metadata.requires_docker:
                built_adapters, missing_adapters = (
                    self.build_manager.check_adapters_in_cache(
                        languages=langs_to_check,
                    )
                )
            else:
                # Local suites can use installed adapters from ~/.aidb/adapters/
                built_adapters, missing_adapters = (
                    self.build_manager.check_adapters_built(
                        languages=langs_to_check,
                    )
                )

            if missing_adapters:
                adapter_list = ", ".join(missing_adapters)
                CliOutput.error(
                    f"{Icons.ERROR} Suite '{suite}' requires adapters: {adapter_list}",
                )
                CliOutput.info(
                    "Run './dev-cli adapters build' "
                    "or './dev-cli adapters install-all'",
                )
                return False

        return True

    @staticmethod
    def _normalize_suite(suite: str | None) -> str:
        """Normalize suite name, defaulting to BASE if None.

        Parameters
        ----------
        suite : str | None
            Suite name or None

        Returns
        -------
        str
            Normalized suite name
        """
        return TestSuites.BASE.name if suite is None else suite

    def run_suite(
        self,
        suite: str | None,
        profile: str | None = None,
        languages: list[str] | None = None,
        markers: list[str] | None = None,
        pattern: str | None = None,
        target: list[str] | None = None,
        parallel: int | None = None,
        coverage: bool = False,
        verbose: bool = False,
        failfast: bool = False,
        last_failed: bool = False,
        timeout: int | None = None,
        use_docker: bool | None = None,
        build: bool = False,
        no_cleanup: bool = False,
        **kwargs: Any,  # noqa: ARG002
    ) -> int:
        """Run a specific test suite with orchestration.

        Parameters
        ----------
        suite : str | None
            Test suite to run (defaults to base)
        profile : str | None
            Docker compose profile to use (overrides suite-based inference)
        languages : list[str] | None
            Language(s) to test (defaults to ["all"])
        markers : List[str], optional
            Pytest markers to filter by
        pattern : str, optional
            Test expression pattern (pytest -k style)
        target : list[str], optional
            Specific test targets (file, class, or function - can specify multiple)
        parallel : int, optional
            Number of parallel workers
        coverage : bool
            Enable coverage reporting
        verbose : bool
            Verbose output
        failfast : bool
            Stop on first failure
        last_failed : bool
            Only run tests that failed in the last run
        use_docker : bool, optional
            Force Docker usage (auto-detected if None)

        Returns
        -------
        int
            Exit code from test execution
        """
        # Default to all languages if not specified
        if languages is None:
            languages = ["all"]

        # Normalize suite (default to base if None)
        suite = self._normalize_suite(suite)

        # Handle "all" suite by running each suite individually
        if suite == "all":
            return self._run_all_suites(
                profile=profile,
                languages=languages,
                markers=markers,
                pattern=pattern,
                target=target,
                parallel=parallel,
                coverage=coverage,
                verbose=verbose,
                failfast=failfast,
                last_failed=last_failed,
                timeout=timeout,
                use_docker=use_docker,
                build=build,
                no_cleanup=no_cleanup,
            )

        if not self.validate_prerequisites(suite):
            return 1

        if use_docker is None:
            # Use first language for docker detection (backward compatibility)
            use_docker = self._should_use_docker(suite, languages[0], markers)

        self.get_service(TestExecutionService)

        if use_docker:
            return self._run_docker_tests(
                suite,
                languages,
                markers,
                pattern,
                target,
                parallel,
                coverage,
                verbose,
                failfast,
                last_failed,
                build,
                timeout,
                no_cleanup,
                profile=profile,
            )
        pytest_args = self.coordinator.build_pytest_args(
            suite=suite,
            markers=markers,
            pattern=pattern,
            target=target,
            parallel=parallel,
            coverage=coverage,
            verbose=verbose,
            failfast=failfast,
            last_failed=last_failed,
            timeout=timeout,
        )
        return self._run_local_tests(suite, pytest_args)

    def _run_all_suites(
        self,
        profile: str | None = None,
        languages: list[str] | None = None,
        markers: list[str] | None = None,
        pattern: str | None = None,
        target: list[str] | None = None,
        parallel: int | None = None,
        coverage: bool = False,
        verbose: bool = False,
        failfast: bool = False,
        last_failed: bool = False,
        timeout: int | None = None,
        use_docker: bool | None = None,
        build: bool = False,
        no_cleanup: bool = False,
    ) -> int:
        """Run all test suites sequentially.

        This method runs each defined suite individually, ensuring proper
        container deployment and dependencies for each suite.

        Parameters
        ----------
        profile : str | None
            Docker compose profile to use (overrides suite-based inference)
        languages : list[str] | None
            Language(s) to test
        markers : list[str] | None
            Pytest markers to filter by
        pattern : str | None
            Test expression pattern (pytest -k style)
        target : list[str] | None
            Specific test targets
        parallel : int | None
            Number of parallel workers
        coverage : bool
            Enable coverage reporting
        verbose : bool
            Verbose output
        failfast : bool
            Stop on first failure
        last_failed : bool
            Only run tests that failed in the last run
        timeout : int | None
            Timeout for tests
        use_docker : bool | None
            Force Docker usage (auto-detected if None)
        build : bool
            Build Docker images before running
        no_cleanup : bool
            Skip cleanup after tests

        Returns
        -------
        int
            Exit code (0 if all suites pass, 1 if any fail)
        """
        logger.info("Running all test suites")
        CliOutput.info(f"{Icons.PACKAGE} Running all test suites...")

        # Get all suites except "base" (which is a collection)
        all_suites = [s for s in TestSuites.all() if s.name != TestSuites.BASE.name]

        suite_results: dict[str, int] = {}
        failed_suites: list[str] = []

        for suite_def in all_suites:
            suite_name = suite_def.name
            logger.info("Running suite: %s", suite_name)
            CliOutput.info(f"\n{Icons.ARROW_RIGHT} Running {suite_name} suite...")

            # Run the suite
            exit_code = self.run_suite(
                suite=suite_name,
                profile=profile,
                languages=languages,
                markers=markers,
                pattern=pattern,
                target=target,
                parallel=parallel,
                coverage=coverage,
                verbose=verbose,
                failfast=failfast,
                last_failed=last_failed,
                timeout=timeout,
                use_docker=use_docker,
                build=build,
                no_cleanup=no_cleanup,
            )

            suite_results[suite_name] = exit_code

            if exit_code != 0:
                failed_suites.append(suite_name)
                logger.warning(
                    "Suite %s failed with exit code %s",
                    suite_name,
                    exit_code,
                )
                if failfast:
                    CliOutput.error(
                        f"Suite {suite_name} failed. Stopping due to --failfast",
                    )
                    break
            else:
                logger.info("Suite %s passed", suite_name)

        # Print summary
        CliOutput.info(f"\n{Icons.REPORT} Test Suite Summary:")
        for suite_name, exit_code in suite_results.items():
            status = f"{Icons.CHECK} PASSED" if exit_code == 0 else "FAILED"
            CliOutput.info(f"  {suite_name}: {status}")

        if failed_suites:
            CliOutput.error(
                f"\n{len(failed_suites)} suite(s) failed: {', '.join(failed_suites)}",
            )
            return 1

        CliOutput.success(f"\n{Icons.CHECK} All test suites passed!")
        return 0

    def _is_multilang_suite(self, suite: str) -> bool:
        """Check if suite requires multi-language execution.

        Parameters
        ----------
        suite : str
            Test suite name

        Returns
        -------
        bool
            True if suite has multi-language tests requiring parallel execution
        """
        suite_def = TestSuites.get(suite)
        return suite_def.is_multilang if suite_def else False

    def _should_use_docker(
        self,
        suite: str,
        language: str | None,
        markers: list[str] | None,
    ) -> bool:
        """Determine if tests should run in Docker.

        This ensures tests run in a consistent, isolated environment when needed.
        """
        # Check suite-specific rules first (before metadata check)
        if suite in ["adapters", TestSuites.FRAMEWORKS.name]:
            return True

        if suite == "mcp":
            if language and language != Language.PYTHON.value and language != "all":
                return True
            # MCP with Python can run locally unless multilang marker is present
            return bool(markers and "multilang" in markers)

        # Check metadata
        metadata = self.get_suite_metadata(suite)
        if not metadata:
            # No metadata: default to local for flexibility
            return False

        return metadata.requires_docker

    def _start_log_streaming_if_verbose(self, verbose: bool) -> None:
        """Start streaming compose logs if verbose mode is enabled.

        Parameters
        ----------
        verbose : bool
            Whether verbose mode is enabled

        Notes
        -----
        Logs are streamed via per-container tee used for test-runners.
        """
        if not verbose:
            return

        try:
            from aidb_cli.services.docker import DockerLoggingService

            self.docker_orchestrator.get_service(DockerLoggingService)
        except Exception as e:
            logger.debug("Failed to start log streaming: %s", e)

    def _process_test_target(
        self,
        target: list[str] | None,
        pattern: str | None,
    ) -> tuple[list[str] | None, str | None, list[str] | None]:
        """Process test target to extract test path and pattern.

        Parameters
        ----------
        target : list[str] | None
            Test target specifications (can be multiple)
        pattern : str | None
            Test pattern

        Returns
        -------
        tuple[list[str] | None, str | None, list[str] | None]
            (test_paths, updated_pattern, updated_targets)
        """
        if not target:
            return None, pattern, target

        # Process all targets
        processed_targets = [self.coordinator._process_target(t) for t in target]

        # Check if all targets are file paths (contain /, end with .py, or contain ::)
        all_paths = all(
            "/" in pt or pt.endswith(".py") or "::" in pt for pt in processed_targets
        )

        if all_paths:
            return processed_targets, pattern, None

        # If not all paths, treat as pattern filters
        target_pattern = " or ".join(target)
        if pattern:
            updated_pattern = f"({pattern}) and ({target_pattern})"
        else:
            updated_pattern = target_pattern
        return None, updated_pattern, None

    def _build_docker_test_environment(
        self,
        suite: str,
        language: str,
        markers: list[str] | None,
        pattern: str | None,
        target: list[str] | None,
        parallel: int | None,
        coverage: bool,
        verbose: bool,
        failfast: bool,
        last_failed: bool,
        timeout: int | None,
    ) -> tuple[str | None, dict[str, str]]:
        """Build pytest args and environment for Docker test execution.

        Parameters
        ----------
        suite : str
            Test suite name
        language : str
            Language being tested
        markers : list[str] | None
            Pytest markers
        pattern : str | None
            Test pattern
        target : list[str] | None
            Test targets (can specify multiple)
        parallel : int | None
            Number of parallel workers
        coverage : bool
            Enable coverage
        verbose : bool
            Verbose output
        failfast : bool
            Stop on first failure
        last_failed : bool
            Run only last failed tests
        timeout : int | None
            Test timeout

        Returns
        -------
        tuple[str | None, dict[str, str]]
            (pytest_args, env_vars)
        """
        test_paths, pattern, target = self._process_test_target(target, pattern)

        pytest_args_list = self.coordinator.build_pytest_args(
            suite=suite,
            markers=markers,
            pattern=pattern,
            target=target,
            parallel=parallel,
            coverage=coverage,
            verbose=verbose,
            failfast=failfast,
            last_failed=last_failed,
            timeout=timeout,
        )
        pytest_args = " ".join(pytest_args_list) if pytest_args_list else None

        execution_service = self.get_service(TestExecutionService)
        env_vars = execution_service.prepare_test_environment(
            suite=suite,
            language=language,
            markers=" ".join(markers) if markers else None,
            pattern=pattern,
            pytest_args=pytest_args,
            parallel=parallel,
        )

        if test_paths:
            env_vars["TEST_PATH"] = " ".join(test_paths)

        return pytest_args, env_vars

    def _get_centralized_env(self) -> dict[str, str]:
        """Get centralized environment from context.

        Returns
        -------
        dict[str, str]
            Centralized environment variables

        Raises
        ------
        RuntimeError
            If context is not properly initialized
        """
        if not (
            self.ctx
            and hasattr(self.ctx, "obj")
            and hasattr(self.ctx.obj, "resolved_env")
        ):
            msg = (
                "TestOrchestrator requires Click context with resolved_env. "
                "This is a bug in the CLI initialization."
            )
            raise RuntimeError(msg)

        return self.ctx.obj.resolved_env

    def _get_debug_services_for_suite(self, suite: str) -> list[str]:
        """Get list of service names to show logs for when debugging failures.

        Parameters
        ----------
        suite : str
            Test suite name

        Returns
        -------
        list[str]
            List of service names
        """
        from aidb_cli.services.docker import ServiceDependencyService

        dep_service = self.docker_orchestrator.get_service(ServiceDependencyService)
        return dep_service.get_services_by_profile(suite)

    def _print_debug_logs_on_failure(self, exit_code: int, suite: str) -> None:
        """Print recent container logs to aid debugging on test failure.

        Parameters
        ----------
        exit_code : int
            Test exit code
        suite : str
            Test suite name
        """
        if exit_code == 0:
            return

        from aidb_cli.services.docker import DockerLoggingService

        services = self._get_debug_services_for_suite(suite)
        if not services:
            return

        logging_service = self.docker_orchestrator.get_service(DockerLoggingService)
        HeadingFormatter.section("Recent Container Logs", Icons.INFO)
        for svc in services:
            HeadingFormatter.subsection(f"Service: {svc}")
            logs = logging_service.get_service_logs(svc, lines=DEFAULT_LOG_LINES)
            if logs:
                CliOutput.plain(logs)
            else:
                CliOutput.plain("<no logs>")

    def _run_parallel_language_containers(
        self,
        suite: str,
        languages: list[str] | None,
        markers: list[str] | None,
        pattern: str | None,
        target: list[str] | None,
        parallel: int | None,
        coverage: bool,
        verbose: bool,
        failfast: bool,
        last_failed: bool,
        timeout: int | None,
        centralized_env: dict[str, str],
        no_cleanup: bool = False,
    ) -> int:
        """Run tests in parallel across language-specific containers.

        Delegates to ParallelTestExecutionService for execution.

        Parameters
        ----------
        suite : str
            Test suite name
        markers : list[str] | None
            Pytest markers
        pattern : str | None
            Test pattern
        target : list[str] | None
            Test targets (can specify multiple)
        parallel : int | None
            Number of parallel workers
        coverage : bool
            Enable coverage
        verbose : bool
            Verbose output
        failfast : bool
            Stop on first failure
        last_failed : bool
            Run only last failed tests
        timeout : int | None
            Test timeout
        centralized_env : dict[str, str]
            Centralized environment variables
        no_cleanup : bool
            Skip Docker cleanup for postmortem inspection

        Returns
        -------
        int
            Aggregated exit code (0 if all pass, else first non-zero)
        """
        # Start log streaming if verbose
        self._start_log_streaming_if_verbose(verbose)

        # Get or create parallel execution service
        parallel_service = ParallelTestExecutionService(
            self.repo_root,
            self.command_executor,
            test_orchestrator=self,
        )

        # Execute tests in parallel
        return parallel_service.run_parallel_language_tests(
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
            timeout=timeout,
            centralized_env=centralized_env,
            docker_orchestrator=self.docker_orchestrator,
            coordinator=self.coordinator,
            execution_service=self.get_service(TestExecutionService),
            no_cleanup=no_cleanup,
        )

    def _cleanup_docker_environment(
        self,
        verbose: bool,
        no_cleanup: bool,
        suite: str,
    ) -> None:
        """Clean up Docker test environment after execution.

        Parameters
        ----------
        verbose : bool
            Whether verbose mode was enabled
        no_cleanup : bool
            Skip cleanup if True
        suite : str
            Test suite name
        """
        CliOutput.info("Cleaning up Docker services...")

        if verbose:
            try:
                from aidb_cli.services.docker import DockerLoggingService

                logging_service = self.docker_orchestrator.get_service(
                    DockerLoggingService,
                )
                logging_service.stop_log_streaming(
                    profile=suite,
                )
            except Exception as e:
                logger.debug("Failed to stop log streaming: %s", e)

        if not no_cleanup:
            self.docker_orchestrator.cleanup_services(
                profile=suite,
            )
        else:
            CliOutput.info("Skipping cleanup (--no-cleanup flag set)")

    def _run_docker_tests(
        self,
        suite: str | None,
        languages: list[str],
        markers: list[str] | None,
        pattern: str | None,
        target: list[str] | None,
        parallel: int | None,
        coverage: bool,
        verbose: bool,
        failfast: bool,
        last_failed: bool,
        build: bool,
        timeout: int | None = None,
        no_cleanup: bool = False,
        profile: str | None = None,
    ) -> int:
        """Run tests in Docker environment."""
        # Normalize suite (default to base if None)
        suite = self._normalize_suite(suite)

        CliOutput.info(f"Running {suite} tests in Docker...")

        centralized_env = self._get_centralized_env()

        # Check if this is a multi-language suite requiring parallel execution
        if self._is_multilang_suite(suite):
            # Determine if we're running all languages or a subset
            if "all" not in languages:
                # Specific language subset (e.g., ["java", "javascript"])
                return self._run_parallel_language_containers(
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
                    timeout=timeout,
                    centralized_env=centralized_env,
                    no_cleanup=no_cleanup,
                )
            # All languages (languages=["all"])
            return self._run_parallel_language_containers(
                suite=suite,
                languages=None,
                markers=markers,
                pattern=pattern,
                target=target,
                parallel=parallel,
                coverage=coverage,
                verbose=verbose,
                failfast=failfast,
                last_failed=last_failed,
                timeout=timeout,
                centralized_env=centralized_env,
                no_cleanup=no_cleanup,
            )

        # Single-language execution (original logic for non-multilang suites)
        # Use first language in list for python-only suites
        language = languages[0] if languages else "python"
        determined_profile = self._determine_docker_profile(suite, profile, target)

        # Use determined profile for starting containers
        started = self.docker_orchestrator.start_test_environment(
            determined_profile,
            language,
        )
        if not started:
            CliOutput.error("Failed to start Docker test environment")
            return 1

        try:
            self.get_service(TestExecutionService)
            self._start_log_streaming_if_verbose(verbose)

            pytest_args, env_vars = self._build_docker_test_environment(
                suite,
                language,
                markers,
                pattern,
                target,
                parallel,
                coverage,
                verbose,
                failfast,
                last_failed,
                timeout,
            )

            execution_service = self.get_service(TestExecutionService)
            exit_code = execution_service.run_tests(
                suite=suite,
                profile=determined_profile,
                env_vars=env_vars,
                centralized_env=centralized_env,
                build=build,
                verbose=verbose,
            )

            self._print_debug_logs_on_failure(exit_code, suite)
        finally:
            self._cleanup_docker_environment(verbose, no_cleanup, suite)

        return exit_code

    def _determine_docker_profile(
        self,
        suite: str | None,
        profile: str | None,
        target: list[str] | None,
    ) -> str:
        """Determine the appropriate Docker profile with clear priority.

        Priority order (highest to lowest):
        1. Explicit --profile flag
        2. Language detection from target path (frameworks/python/ → python)
        3. Suite mapping (mcp → mcp, frameworks → frameworks, etc.)
        4. Default to base profile (minimal profile)

        Parameters
        ----------
        suite : str | None
            Test suite name
        profile : str | None
            Explicitly requested profile
        target : list[str] | None
            Specific test target paths (uses first target for profile detection)

        Returns
        -------
        str
            Docker compose profile to use
        """
        return self._profile_resolver.determine_profile(suite, profile, target)

    def _run_local_tests(self, suite: str | None, pytest_args: list[str]) -> int:
        """Run tests locally using pytest.

        Parameters
        ----------
        suite : str | None
            Test suite to run
        pytest_args : List[str]
            Pytest arguments

        Returns
        -------
        int
            Exit code from pytest
        """
        # Normalize suite (default to base if None)
        suite = self._normalize_suite(suite)

        execution_service = self.get_service(TestExecutionService)
        # Run only the requested suite when metadata is available
        metadata = self.get_suite_metadata(suite)
        suite_path = metadata.path if metadata else self.repo_root / "src" / "tests"
        return execution_service.run_local_tests(suite_path, suite, pytest_args)

    def aggregate_results(self, suite_results: dict[str, int]) -> dict[str, Any]:
        """Aggregate test results from multiple suites.

        Parameters
        ----------
        suite_results : Dict[str, int]
            Dictionary mapping suite names to exit codes

        Returns
        -------
        Dict[str, Any]
            Aggregated test results with statistics
        """
        reporting_service = self.get_service(TestReportingService)
        return reporting_service.aggregate_results(suite_results, self.repo_root)

    def get_test_statistics(self) -> dict[str, Any]:
        """Get statistics about available tests.

        Returns
        -------
        Dict[str, Any]
            Test statistics including counts and coverage
        """
        reporting_service = self.get_service(TestReportingService)
        return reporting_service.generate_statistics(
            self.discovery_service.get_all_suites(),
        )


# Convenience function for getting the singleton instance
def get_test_orchestrator(repo_root: Path | None = None) -> TestOrchestrator:
    """Get the TestOrchestrator singleton instance.

    Parameters
    ----------
    repo_root : Path, optional
        Repository root directory

    Returns
    -------
    TestOrchestrator
        The singleton instance
    """
    return TestOrchestrator.get_instance(repo_root)
