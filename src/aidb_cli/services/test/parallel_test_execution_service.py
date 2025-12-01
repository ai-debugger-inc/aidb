"""Service for parallel multi-language test execution."""

import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.managers.docker import DockerOrchestrator
    from aidb_cli.managers.test.test_orchestrator import TestOrchestrator
    from aidb_cli.services import CommandExecutor
    from aidb_cli.services.docker.docker_logging_service import DockerLoggingService
    from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService
    from aidb_cli.services.test.test_execution_service import TestExecutionService

logger = get_cli_logger(__name__)


class ParallelTestExecutionService(BaseService):
    """Service for executing tests in parallel across language-specific containers.

    This service handles:
    - Starting multiple language-specific test containers in parallel
    - Running tests with language marker filters
    - Aggregating results from parallel executions
    - Cleanup of parallel test environments
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
        test_orchestrator: Optional["TestOrchestrator"] = None,
    ) -> None:
        """Initialize the parallel test execution service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        test_orchestrator : TestOrchestrator | None, optional
            Test orchestrator instance for accessing services
        """
        super().__init__(repo_root, command_executor)
        self.test_orchestrator = test_orchestrator

    def run_parallel_language_tests(
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
        docker_orchestrator: "DockerOrchestrator",
        coordinator: "TestCoordinatorService",
        execution_service: "TestExecutionService",
        logging_service: Optional["DockerLoggingService"] = None,
        no_cleanup: bool = False,
    ) -> int:
        """Run tests in parallel across language-specific containers.

        Parameters
        ----------
        suite : str
            Test suite name
        languages : list[str] | None
            Specific languages to test (None = all supported languages)
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
        docker_orchestrator : DockerOrchestrator
            Docker orchestrator for managing containers
        coordinator : TestCoordinatorService
            Test coordinator for building pytest args
        execution_service : TestExecutionService
            Execution service for running tests
        logging_service : DockerLoggingService | None, optional
            Logging service for streaming container logs
        no_cleanup : bool
            Skip Docker cleanup for postmortem inspection

        Returns
        -------
        int
            Aggregated exit code (0 if all pass, else first non-zero)
        """
        from aidb_cli.core.constants import SUPPORTED_LANGUAGES

        # Determine which languages to run
        langs_to_run = languages if languages else SUPPORTED_LANGUAGES

        CliOutput.info(
            f"Running {suite} tests in parallel across "
            f"{len(langs_to_run)} containers...",
        )

        # In CI (IS_GITHUB=true), images are pre-pulled from GHCR.
        # Skip checksum-based rebuild detection - trust the pulled images.
        import os

        if os.environ.get("IS_GITHUB") != "true":
            # Check if images need rebuilding BEFORE starting containers
            from aidb_cli.services.docker.docker_build_service import DockerBuildService
            from aidb_cli.services.docker.docker_image_checksum_service import (
                DockerImageChecksumService,
            )

            build_service = DockerBuildService(
                self.repo_root,
                self.command_executor,
                self.resolved_env,
            )
            checksum_service = DockerImageChecksumService(
                self.repo_root,
                self.command_executor,
            )

            rebuild_status = checksum_service.check_all_images()
            needs_rebuild = any(needs for needs, _ in rebuild_status.values())

            if needs_rebuild:
                CliOutput.info("Detected changes requiring image rebuild")
                if verbose:
                    for image_type, (needs, reason) in rebuild_status.items():
                        if needs:
                            CliOutput.plain(f"  {image_type}: {reason}")

                # Build all framework images at once
                rc = build_service.build_images(
                    profile="frameworks",
                    no_cache=False,
                    verbose=verbose,
                )
                if rc != 0:
                    CliOutput.error("Image rebuild failed")
                    return rc

                CliOutput.success("Images rebuilt successfully")
        elif verbose:
            CliOutput.info("CI detected: using pre-pulled images")

        # Prepare environment variables for each language container
        env_vars_per_language = self._prepare_language_env_vars(
            languages=langs_to_run,
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
            coordinator=coordinator,
            execution_service=execution_service,
        )

        # Start all containers with their respective environment variables
        if not self._start_all_language_containers(
            langs_to_run,
            docker_orchestrator,
            env_vars_per_language,
        ):
            return 1

        # Avoid compose log streaming for language test profiles to prevent
        # duplication with the per-container tee that prints live pytest output.
        # Compose log streaming remains enabled for infra suites via orchestrator.
        log_processes: dict[str, Any] = {}

        try:
            # Execute tests in parallel
            results = self._execute_parallel_tests(
                languages=langs_to_run,
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
                centralized_env=centralized_env,
                coordinator=coordinator,
                execution_service=execution_service,
            )

            # Aggregate and report results
            return self._aggregate_results(results)

        finally:
            # Stop log streaming
            if logging_service and log_processes:
                logging_service.stop_all_profile_streams(langs_to_run)

            # Cleanup all language containers (unless --no-cleanup flag set)
            if not no_cleanup:
                self._cleanup_language_containers(langs_to_run, docker_orchestrator)
            else:
                CliOutput.info(
                    "Skipping language container cleanup (--no-cleanup flag set)",
                )

    def _prepare_language_env_vars(
        self,
        languages: list[str],
        suite: str,
        markers: list[str] | None,
        pattern: str | None,
        target: list[str] | None,
        parallel: int | None,
        coverage: bool,
        verbose: bool,
        failfast: bool,
        last_failed: bool,
        timeout: int | None,
        coordinator: "TestCoordinatorService",
        execution_service: "TestExecutionService",
    ) -> dict[str, dict[str, str]]:
        """Prepare environment variables for each language container.

        Parameters
        ----------
        languages : list[str]
            List of languages to prepare env_vars for
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
        coordinator : TestCoordinatorService
            Test coordinator service
        execution_service : TestExecutionService
            Test execution service

        Returns
        -------
        dict[str, dict[str, str]]
            Mapping of language to environment variables
        """
        env_vars_per_language = {}

        # Generate timestamp once for all languages to ensure consistent session ID
        shared_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        for lang in languages:
            # Add language marker filter
            lang_markers = markers.copy() if markers else []
            lang_markers.append(f"language_{lang}")

            # Process target to extract test path
            test_paths, updated_pattern, updated_target = (
                self._process_test_target(target, pattern)
                if self.test_orchestrator
                else (None, pattern, target)
            )

            # Build pytest arguments
            pytest_args_list = coordinator.build_pytest_args(
                suite=suite,
                markers=lang_markers,
                pattern=updated_pattern,
                target=updated_target,
                parallel=parallel,
                coverage=coverage,
                verbose=verbose,
                failfast=failfast,
                last_failed=last_failed,
                timeout=timeout,
            )
            # Quote arguments that need quoting for shell safety
            if pytest_args_list:
                pytest_args = " ".join(shlex.quote(arg) for arg in pytest_args_list)
            else:
                pytest_args = None

            # Prepare test environment (shared timestamp for consistent session ID)
            env_vars = execution_service.prepare_test_environment(
                suite=suite,
                language=lang,
                markers=" ".join(lang_markers),
                pattern=updated_pattern,
                pytest_args=pytest_args,
                parallel=parallel,
                timestamp=shared_timestamp,
            )

            # Map suite to correct test path
            if not test_paths:
                from aidb_cli.services.test import TestSuites

                suite_def = TestSuites.get(suite)
                if suite_def:
                    if suite_def.is_multilang:
                        # Only frameworks suite has language subdirectories
                        if suite == "frameworks":
                            test_path = f"src/tests/{suite_def.path}{lang}/"
                        else:
                            # shared, mcp, launch use parametrization (no lang dirs)
                            test_path = f"src/tests/{suite_def.path}"
                    else:
                        test_path = f"src/tests/{suite_def.path}"
                else:
                    # Fallback for unknown suites
                    test_path = f"src/tests/frameworks/{lang}/"
                env_vars["TEST_PATH"] = test_path
            else:
                # Multiple test paths - join with space
                env_vars["TEST_PATH"] = " ".join(test_paths)
            env_vars_per_language[lang] = env_vars

        return env_vars_per_language

    def _start_all_language_containers(
        self,
        languages: list[str],
        docker_orchestrator: "DockerOrchestrator",
        env_vars_per_language: dict[str, dict[str, str]] | None = None,
    ) -> bool:
        """Start all language-specific test containers.

        Parameters
        ----------
        languages : list[str]
            List of languages to start containers for
        docker_orchestrator : DockerOrchestrator
            Docker orchestrator instance
        env_vars_per_language : dict[str, dict[str, str]] | None, optional
            Environment variables for each language container

        Returns
        -------
        bool
            True if all containers started successfully
        """
        for lang in languages:
            profile = lang  # Use language as profile name
            extra_env = (
                env_vars_per_language.get(lang) if env_vars_per_language else None
            )
            started = docker_orchestrator.start_test_environment(
                profile,
                lang,
                extra_env=extra_env,
            )
            if not started:
                CliOutput.error(f"Failed to start {lang} test environment")
                return False
        return True

    def _execute_parallel_tests(
        self,
        languages: list[str],
        suite: str,
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
        coordinator: "TestCoordinatorService",
        execution_service: "TestExecutionService",
    ) -> dict[str, int]:
        """Execute tests in parallel for all languages.

        Parameters
        ----------
        languages : list[str]
            List of languages to test
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
        coordinator : TestCoordinatorService
            Test coordinator service
        execution_service : TestExecutionService
            Test execution service

        Returns
        -------
        dict[str, int]
            Mapping of language to exit code
        """
        # Generate timestamp once for all languages to ensure consistent session ID
        shared_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

        def run_language_tests(lang: str) -> tuple[str, int]:
            """Run tests for a specific language."""
            # Add language marker filter to existing markers
            lang_markers = markers.copy() if markers else []
            lang_markers.append(f"language_{lang}")

            # Process target to extract test path
            test_paths, updated_pattern, updated_target = (
                self._process_test_target(target, pattern)
                if self.test_orchestrator
                else (None, pattern, target)
            )

            # Build pytest arguments
            pytest_args_list = coordinator.build_pytest_args(
                suite=suite,
                markers=lang_markers,
                pattern=updated_pattern,
                target=updated_target,
                parallel=parallel,
                coverage=coverage,
                verbose=verbose,
                failfast=failfast,
                last_failed=last_failed,
                timeout=timeout,
            )
            # Quote arguments that need quoting for shell safety
            if pytest_args_list:
                pytest_args = " ".join(shlex.quote(arg) for arg in pytest_args_list)
            else:
                pytest_args = None

            # Prepare test environment (shared timestamp for consistent session ID)
            env_vars = execution_service.prepare_test_environment(
                suite=suite,
                language=lang,
                markers=" ".join(lang_markers),
                pattern=updated_pattern,
                pytest_args=pytest_args,
                parallel=parallel,
                timestamp=shared_timestamp,
            )

            # Map suite to correct test path for multi-language execution
            # If test_paths not already set from target, use suite definition
            if not test_paths:
                from aidb_cli.services.test import TestSuites

                suite_def = TestSuites.get(suite)
                if suite_def:
                    if suite_def.is_multilang:
                        # Only frameworks suite has language subdirectories
                        if suite == "frameworks":
                            test_path = f"src/tests/{suite_def.path}{lang}/"
                        else:
                            # shared, mcp, launch use parametrization (no lang dirs)
                            test_path = f"src/tests/{suite_def.path}"
                    else:
                        test_path = f"src/tests/{suite_def.path}"
                else:
                    # Fallback for unknown suites
                    test_path = f"src/tests/frameworks/{lang}/"
                env_vars["TEST_PATH"] = test_path
            else:
                # Multiple test paths - join with space
                env_vars["TEST_PATH"] = " ".join(test_paths)

            # Run tests (quiet mode - individual results shown below)
            profile = lang
            exit_code = execution_service.run_tests(
                suite=suite,
                profile=profile,
                env_vars=env_vars,
                centralized_env=centralized_env,
                build=False,
                verbose=verbose,
                quiet=True,
            )

            return lang, exit_code

        # Execute in parallel using ThreadPoolExecutor
        results = {}
        with ThreadPoolExecutor(max_workers=len(languages)) as executor:
            futures = {
                executor.submit(run_language_tests, lang): lang for lang in languages
            }

            for future in as_completed(futures):
                lang, exit_code = future.result()
                results[lang] = exit_code
                status = "✓" if exit_code == 0 else "✗"
                CliOutput.info(
                    f"{status} {lang} tests completed (exit: {exit_code})",
                )

        return results

    def _process_test_target(
        self,
        target: list[str] | None,
        pattern: str | None,
    ) -> tuple[list[str] | None, str | None, list[str] | None]:
        """Process test target to extract test path and pattern.

        Delegates to test orchestrator if available.

        Parameters
        ----------
        target : list[str] | None
            Test target specifications (can specify multiple)
        pattern : str | None
            Test pattern

        Returns
        -------
        tuple[list[str] | None, str | None, list[str] | None]
            (test_paths, updated_pattern, updated_target)
        """
        if not self.test_orchestrator or not target:
            return None, pattern, target

        return self.test_orchestrator._process_test_target(target, pattern)

    def _aggregate_results(self, results: dict[str, int]) -> int:
        """Aggregate results from parallel test executions.

        Parameters
        ----------
        results : dict[str, int]
            Mapping of language to exit code

        Returns
        -------
        int
            Aggregated exit code (0 if all pass, else first non-zero)
        """
        all_passed = all(code == 0 for code in results.values())

        if all_passed:
            CliOutput.success("All language tests passed!")
            return 0

        # Prefer real failures over 'no tests collected' (pytest exit code 5)
        real_failures = {
            lang: code for lang, code in results.items() if code not in (0, 5)
        }
        no_tests = {lang: code for lang, code in results.items() if code == 5}

        if real_failures:
            failed_langs = list(real_failures.keys())
            CliOutput.error(f"Tests failed in: {', '.join(failed_langs)}")
            # Return the first real failure code deterministically (sorted by lang)
            first_lang = sorted(real_failures.keys())[0]
            return real_failures[first_lang]

        if no_tests and not real_failures:
            # All non-zero results are 'no tests collected' → aggregate as 5
            CliOutput.warning("No tests ran - collected 0 items")
            return 5

        # Fallback: unexpected mix (shouldn't happen), return first non-zero
        failed_langs = [lang for lang, code in results.items() if code != 0]
        CliOutput.error(f"Tests failed in: {', '.join(failed_langs)}")
        first_lang = sorted(failed_langs)[0]
        return results[first_lang]

    def _cleanup_language_containers(
        self,
        languages: list[str],
        docker_orchestrator: "DockerOrchestrator",
    ) -> None:
        """Clean up all language-specific test containers.

        Parameters
        ----------
        languages : list[str]
            List of languages to cleanup
        docker_orchestrator : DockerOrchestrator
            Docker orchestrator instance
        """
        from aidb_cli.core.utils import CliOutput

        if languages:
            CliOutput.info(
                f"Cleaning up {len(languages)} language container(s): "
                f"{', '.join(languages)}...",
            )

        for lang in languages:
            try:
                docker_orchestrator.cleanup_services(profile=lang, quiet=True)
            except Exception as e:
                logger.debug("Failed to cleanup %s environment: %s", lang, e)

        if languages:
            CliOutput.success("Language containers cleaned up")
