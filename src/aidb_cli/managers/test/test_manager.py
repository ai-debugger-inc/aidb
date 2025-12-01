"""Refactored test manager using orchestrator pattern."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.orchestrator import BaseOrchestrator
from aidb_cli.managers.build import BuildManager
from aidb_cli.services.test import (
    TestDiscoveryService,
    TestExecutionService,
    TestReportingService,
)
from aidb_common.constants import Language
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class TestManager(BaseOrchestrator):
    """Centralized orchestrator for all test operations.

    This refactored version uses the orchestrator pattern to coordinate multiple
    services for test operations.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the test manager orchestrator.

        Parameters
        ----------
        repo_root : Path | None, optional
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        """
        super().__init__(repo_root, command_executor)

        self.build_manager = BuildManager(repo_root)

    def _register_services(self) -> None:
        """Register services for test operations."""
        self.register_service(TestDiscoveryService)
        self.register_service(TestExecutionService)
        self.register_service(TestReportingService)

    def check_prerequisites(self, check_adapters: bool = True) -> bool:  # noqa: ARG002
        """Check if Docker and required files are available.

        Parameters
        ----------
        check_adapters : bool
            Whether to check for adapter availability

        Returns
        -------
        bool
            True if all prerequisites are met
        """
        try:
            self.command_executor.execute(
                ["docker", "--version"],
                capture_output=True,
                check=True,
            )
        except (AidbError, FileNotFoundError):
            CliOutput.plain(
                f"{Icons.ERROR} Docker is not installed or not available",
                err=True,
            )
            return False

        execution_service = self.get_service(TestExecutionService)
        if not execution_service.compose_file.exists():
            CliOutput.plain(
                f"{Icons.ERROR} Docker compose file not found: "
                f"{execution_service.compose_file}",
                err=True,
            )
            return False

        return True

    def check_adapters(self, languages: list[str]) -> dict[str, bool]:
        """Check which adapters are available.

        Parameters
        ----------
        languages : list[str]
            Languages to check

        Returns
        -------
        dict[str, bool]
            Status of each adapter
        """
        if not languages or languages == ["all"]:
            languages = self.build_manager.get_supported_languages()

        status = {}
        for lang in languages:
            adapter_path = self.build_manager.find_adapter_source(lang)
            status[lang] = adapter_path is not None

        return status

    def build_docker_command(
        self,
        profile: str,
        service: str | None = None,
        command: str | None = None,
        env_vars: dict[str, str] | None = None,
        build: bool = False,
        detach: bool = False,
    ) -> list[str]:
        """Build the docker compose command."""
        execution_service = self.get_service(TestExecutionService)
        return execution_service.build_docker_command(
            profile=profile,
            service=service,
            command=command,
            env_vars=env_vars,
            build=build,
            detach=detach,
        )

    def run_tests(
        self,
        suite: str,
        language: str = "all",
        profile: str = "auto",
        markers: str | None = None,
        pattern: str | None = None,
        pytest_args: str | None = None,
        build: bool = False,
        parallel: int | None = None,
        verbose: bool = False,
    ) -> int:
        """Run tests with specified configuration.

        Parameters
        ----------
        suite : str
            Test suite to run (mcp, backend, adapters, etc.)
        language : str
            Language to test (python, javascript, java, all)
        profile : str
            Docker profile to use
        markers : str, optional
            Pytest markers to filter tests
        pattern : str, optional
            Test pattern to match
        pytest_args : str, optional
            Additional pytest arguments
        build : bool
            Whether to rebuild images
        parallel : int, optional
            Number of parallel workers
        verbose : bool
            Enable verbose output

        Returns
        -------
        int
            Exit code from test execution
        """
        if not self.check_prerequisites(check_adapters=False):
            return 1

        if suite in ["mcp", "adapters"]:
            adapter_status = self.check_adapters([language])
            missing = [k for k, v in adapter_status.items() if not v]
            if missing:
                CliOutput.plain(
                    f"{Icons.WARNING}  Missing adapters: {', '.join(missing)}",
                )
                CliOutput.plain("   Run './dev-cli adapters build' to build them")
                response = click.confirm("Continue anyway?", default=False)
                if not response:
                    return 1

        execution_service = self.get_service(TestExecutionService)
        reporting_service = self.get_service(TestReportingService)

        env_vars = execution_service.prepare_test_environment(
            suite=suite,
            language=language,
            markers=markers,
            pattern=pattern,
            pytest_args=pytest_args,
            parallel=parallel,
        )

        if profile == "auto":
            # Convention: suite names match profile names
            # Special cases: suites without docker profiles use "base"
            profile = suite if suite not in ("shared", "cli") else "base"

        reporting_service.start_suite(suite)

        exit_code = execution_service.run_tests(
            suite=suite,
            profile=profile,
            env_vars=env_vars,
            build=build,
            verbose=verbose,
        )

        reporting_service.record_result(
            suite=suite,
            exit_code=exit_code,
        )

        return exit_code

    def run_shell(self, profile: str = "shell") -> int:
        """Open an interactive shell in the test container."""
        execution_service = self.get_service(TestExecutionService)
        return execution_service.run_shell(profile)

    def clean(self) -> int:
        """Clean up Docker test environment."""
        execution_service = self.get_service(TestExecutionService)
        return execution_service.clean_test_environment()

    def build_images(
        self,
        profile: str = "base",
        verbose: bool = False,
    ) -> int:
        """Build Docker images for testing.

        Parameters
        ----------
        profile : str
            Docker profile to build
        verbose : bool
            Enable verbose output

        Returns
        -------
        int
            Exit code from build
        """
        execution_service = self.get_service(TestExecutionService)
        return execution_service.build_docker_images(profile, verbose)

    def get_test_status(self) -> dict[str, Any]:
        """Get current Docker/test environment status and statistics.

        Returns
        -------
        dict[str, Any]
            Status information including Docker availability, compose file,
            adapter build status, repo root, and basic test statistics.
        """
        discovery_service = self.get_service(TestDiscoveryService)
        reporting_service = self.get_service(TestReportingService)

        # Base statistics about discovered tests
        stats = discovery_service.get_test_statistics()

        # Docker availability and version
        docker_available = False
        docker_version = None
        try:
            result = self.command_executor.execute(
                ["docker", "--version"],
                capture_output=True,
                check=True,
            )
            docker_available = result.returncode == 0
            if docker_available and result.stdout:
                docker_version = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            docker_available = False

        # Compose file existence
        execution_service = self.get_service(TestExecutionService)
        compose_file_exists = execution_service.compose_file.exists()

        # Adapter build status as a mapping of language -> bool
        try:
            languages = self.build_manager.get_supported_languages()
        except Exception:  # Fallback to default languages if retrieval fails
            languages = [lang.value for lang in Language]

        adapters_built_map: dict[str, bool] = {}
        try:
            # BuildManager.check_adapters_built returns (built_list, missing_list)
            built_list, missing_list = self.build_manager.check_adapters_built(
                languages,
                verbose=False,
            )
            for lang in languages:
                adapters_built_map[lang] = lang in built_list
        except (OSError, AttributeError, RuntimeError):
            # Fall back to assuming none are built
            adapters_built_map = {lang: False for lang in languages}

        env_status: dict[str, Any] = {
            "docker_available": docker_available,
            "docker_version": docker_version or "",
            "compose_file_exists": compose_file_exists,
            "adapters_built": adapters_built_map,
            "repo_root": str(self.repo_root),
        }

        # Include last run summary if available
        if reporting_service.results:
            report = reporting_service.aggregate_results()
            env_status["last_run"] = {
                "total_suites": report.total_suites,
                "total_tests": report.total_tests,
                "total_passed": report.total_passed,
                "total_failed": report.total_failed,
                "overall_success": report.overall_success,
            }

        # Merge basic stats under a dedicated key to avoid key conflicts
        env_status["test_stats"] = stats

        return env_status
