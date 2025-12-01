"""Unified test command for AIDB CLI."""

from pathlib import Path

import click

from aidb_cli.core.cleanup import ResourceCleaner
from aidb_cli.core.constants import Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.param_types import (
    DockerProfileParamType,
    LanguageParamType,
    TestMarkerParamType,
    TestPatternParamType,
    TestSuiteParamType,
)
from aidb_cli.core.paths import CachePaths
from aidb_cli.services.test.test_coordinator_service import TestCoordinatorService
from aidb_cli.services.test.test_coverage_service import TestCoverageService
from aidb_cli.services.test.test_suite_service import TestSuiteService
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


@click.group(name="test")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Unified test orchestration for all AIDB tests."""


@group.command()
@click.option(
    "--suite",
    "-s",
    type=TestSuiteParamType(),
    required=True,
    help="Test suite to run (required)",
)
@click.option(
    "--profile",
    type=DockerProfileParamType(),
    default=None,
    help="Docker compose profile to use (overrides suite-based inference)",
)
@click.option(
    "--language",
    "-l",
    type=LanguageParamType(include_all=True),
    multiple=True,
    default=None,
    help="Language(s) to test (can specify multiple)",
)
@click.option(
    "--marker",
    "-m",
    type=str,
    multiple=True,
    help="Pytest markers to filter tests",
)
@click.option(
    "--pattern",
    "-p",
    type=TestPatternParamType(),
    help="Test expression to match (pytest -k style)",
)
@click.option(
    "--target",
    "-t",
    multiple=True,
    help="Specific test target (can specify multiple)",
)
@click.option("--local", is_flag=True, help="Run tests locally instead of in Docker")
@click.option("--parallel", "-j", type=int, help="Number of parallel test workers")
@click.option("--coverage", "-c", is_flag=True, help="Run with coverage reporting")
@click.option("--failfast", "-x", is_flag=True, help="Stop on first failure")
@click.option(
    "--last-failed",
    "--lf",
    is_flag=True,
    help="Only run tests that failed in the last run",
)
@click.option(
    "--failed-first",
    "--ff",
    is_flag=True,
    help="Run failed tests first, then all other tests",
)
@click.option(
    "--timeout",
    type=int,
    help="Per-test timeout in seconds (pytest-timeout)",
)
@click.option(
    "--build",
    "-b",
    is_flag=True,
    help="Rebuild Docker images before testing",
)
@click.option("--no-cache", is_flag=True, help="Build without Docker cache")
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Skip Docker cleanup for postmortem inspection",
)
@click.pass_context
@handle_exceptions
def run(
    ctx: click.Context,
    suite: str,
    profile: str | None,
    language: tuple[str, ...],
    marker: tuple[str, ...],
    pattern: str | None,
    target: tuple[str, ...],
    local: bool,
    parallel: int | None,
    coverage: bool,
    failfast: bool,
    last_failed: bool,
    failed_first: bool,
    timeout: int | None,
    build: bool,
    no_cache: bool,
    no_cleanup: bool,
) -> None:
    """Run tests with intelligent orchestration.

    \b
    Examples:
        ./dev-cli test run -p "*payment*"  # Runs in Docker by default
        ./dev-cli test run -t "test_api.py::TestEndpoint" --local
        ./dev-cli test run --suite shared --language python
        ./dev-cli test run --suite shared --language java --language javascript
    """  # noqa: W605
    # Normalize languages: None → ["all"], ("python",) → ["python"]
    languages = list(language) if language else ["all"]

    # Pass the context to the test orchestrator so it has access to resolved_env
    if ctx.obj.test_orchestrator:
        ctx.obj.test_orchestrator.ctx = ctx

    coordinator = TestCoordinatorService(
        ctx.obj.repo_root,
        ctx.obj.command_executor,
        ctx.obj.test_orchestrator,
        ctx=ctx,
    )

    # Determine execution environment based on suite metadata
    # Only override if --local is explicitly set, otherwise respect metadata
    # If profile is specified, that implies Docker
    docker_override = False if local else (True if profile else None)
    use_docker = coordinator.determine_execution_environment(suite, docker_override)

    # Prepare suite display name
    if suite:
        suite_display = suite
    elif profile:
        suite_display = f"profile={profile}"
    else:
        suite_display = "pattern-based"

    # Show clean test initiation banner
    mode = "docker" if use_docker else "local"
    output = ctx.obj.output

    output.plain("")
    output.section("TESTS STARTING")
    output.plain(f"Suite:  {suite_display}")
    output.plain(f"Mode:   {mode}")

    # Store no_cleanup flag in context for exception handler
    ctx.obj.no_cleanup = no_cleanup

    # Set up cleanup handlers for docker resources if using docker (unless --no-cleanup)
    if use_docker and not no_cleanup:
        cleaner = ResourceCleaner(
            ctx.obj.repo_root,
            ctx.obj.command_executor,
            ctx=ctx,
        )
        cleaner.register_cleanup_handler()
        logger.debug("Registered docker cleanup handlers for ctrl+c and signals")

    # Update environment with test-specific variables early
    # This ensures they're available throughout the test execution
    # Build pytest args to get the full command line
    coord_service = TestCoordinatorService(
        ctx.obj.repo_root,
        ctx.obj.command_executor,
        ctx.obj.test_orchestrator,
    )
    pytest_args_list = coord_service.build_pytest_args(
        suite=suite,
        markers=list(marker) if marker else None,
        pattern=pattern,
        target=list(target) if target else None,
        parallel=parallel,
        coverage=coverage,
        verbose=ctx.obj.verbose,
        failfast=failfast,
        last_failed=last_failed,
        failed_first=failed_first,
        timeout=timeout,
    )
    pytest_args_str = " ".join(pytest_args_list) if pytest_args_list else ""

    # Update environment via the centralized manager
    # Use first language for env var (backward compatibility)
    test_env_updates = {
        "TEST_SUITE": suite or "default",
        "TEST_LANGUAGE": languages[0] if languages else "all",
    }

    # Always set TEST_PATTERN and PYTEST_ADDOPTS, even if empty
    # This prevents Docker defaults from overriding
    test_env_updates["TEST_PATTERN"] = pattern or ""
    test_env_updates["PYTEST_ADDOPTS"] = (
        pytest_args_str or "-v"
    )  # Default to -v if no args

    if parallel:
        test_env_updates["PYTEST_PARALLEL"] = str(parallel)

    # Apply updates through the environment manager
    ctx.obj.env_manager.update(test_env_updates, source="test_command")

    # Log what we're setting for debugging
    logger.debug("Test environment updates: %s", test_env_updates)

    # Validate prerequisites
    if not coordinator.validate_prerequisites(suite):
        ctx.exit(1)

    # Execute tests
    exit_code = coordinator.execute_tests(
        suite=suite,
        profile=profile,
        languages=languages,
        markers=list(marker) if marker else None,
        pattern=pattern,
        target=list(target) if target else None,
        parallel=parallel,
        coverage=coverage,
        verbose=ctx.obj.verbose,
        failfast=failfast,
        last_failed=last_failed,
        failed_first=failed_first,
        timeout=timeout,
        use_docker=use_docker,
        no_cache=no_cache,
        build=build,
        no_cleanup=no_cleanup,
    )

    # Report results (normalize exit codes) with log location summary
    orchestrator = ctx.obj.test_orchestrator
    session_id = orchestrator.current_session_id if orchestrator else None

    # Prepare paths based on execution mode
    if use_docker:
        container_data_path = CachePaths.container_data_dir(ctx.obj.repo_root)
        pytest_logs_path = None
        app_log_path = None
    else:
        container_data_path = None
        pytest_logs_path = ctx.obj.repo_root / "pytest-logs"
        app_log_path = CachePaths.log_dir()

    normalized_exit_code = coordinator.report_results(
        exit_code,
        session_id=session_id,
        use_docker=use_docker,
        container_data_dir=container_data_path,
        pytest_logs_dir=pytest_logs_path,
        app_log_dir=app_log_path,
    )
    if normalized_exit_code != 0:
        ctx.exit(normalized_exit_code)


@group.command(name="list")
@click.option(
    "--suite",
    "-s",
    type=TestSuiteParamType(),
    default=None,
    help="Filter by test suite (optional)",
)
@click.option("--marker", "-m", type=TestMarkerParamType(), help="Filter by marker")
@click.option("--pattern", "-p", type=TestPatternParamType(), help="Filter by pattern")
@click.option("--markers", is_flag=True, help="Show all available pytest markers")
@click.option("--patterns", is_flag=True, help="Show example test patterns")
@click.pass_context
@handle_exceptions
def list_tests(
    ctx: click.Context,
    suite: str | None,
    marker: str | None,
    pattern: str | None,
    markers: bool,
    patterns: bool,
) -> None:
    """List available tests, suites, and markers."""
    output = ctx.obj.output
    verbose = ctx.obj.verbose

    output.section("Available Test Suites", Icons.LIST)

    # Initialize suite service
    suite_service = TestSuiteService(ctx.obj.repo_root, ctx.obj.command_executor)

    output.info("Discovering tests...")

    # Determine what to show
    show_suites = not (
        (markers or patterns) and not verbose and not suite and not pattern
    )

    # List test suites
    if show_suites:
        suites = suite_service.list_suites(suite, verbose)
        suite_service.display_suites(suites, verbose)

    # List markers if requested
    if marker or verbose or markers:
        markers_dict = suite_service.list_markers(marker)
        suite_service.display_markers(markers_dict)

    # Show pattern examples if requested
    if patterns or verbose:
        suite_service.display_pattern_examples()

    # List matching files if requested
    if pattern or (verbose and not patterns):
        pattern_to_use = pattern or "test_*.py"
        files = suite_service.find_matching_files(pattern_to_use, suite)
        # Get total count
        all_files = suite_service.find_matching_files(pattern_to_use, suite, limit=999)
        suite_service.display_matching_files(pattern_to_use, files, len(all_files))


@group.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["terminal", "html", "xml", "json"]),
    default="terminal",
    help="Report format",
)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
@click.option("--coverage", "-c", is_flag=True, help="Include coverage report")
@click.pass_context
@handle_exceptions
def report(
    ctx: click.Context,
    fmt: str,
    output_path: Path | None,
    coverage: bool,
) -> None:
    """Generate test reports and coverage analysis."""
    cli_output = ctx.obj.output
    cli_output.section("Test Report Generation", Icons.REPORT)

    # Initialize coverage service
    coverage_service = TestCoverageService(ctx.obj.repo_root, ctx.obj.command_executor)

    # Generate report
    if not coverage_service.generate_report(fmt, output_path, coverage):
        ctx.exit(1)


@group.command()
@click.option("--docker", "-d", is_flag=True, help="Clean up Docker resources")
@click.option("--artifacts", "-a", is_flag=True, help="Clean up test artifacts")
@click.option("--temp", "-t", is_flag=True, help="Clean up temporary files")
@click.option("--all", "clean_all", is_flag=True, help="Clean up everything")
@click.option("--force", "-f", is_flag=True, help="Force cleanup")
@click.pass_context
@handle_exceptions
def cleanup(
    ctx: click.Context,
    docker: bool,
    artifacts: bool,
    temp: bool,
    clean_all: bool,
    force: bool,
) -> None:
    """Clean up test resources and artifacts."""
    output = ctx.obj.output
    output.section("Cleaning Test Resources", Icons.CLEAN)

    cleaner = ResourceCleaner(ctx.obj.repo_root, ctx.obj.command_executor, ctx=ctx)

    if clean_all:
        # Full cleanup
        if not cleaner.full_cleanup(force=force):
            ctx.exit(1)
    else:
        # Selective cleanup
        if not any([docker, artifacts, temp]):
            output.warning("No cleanup options specified. Use --help for options.")
            return

        success = True

        if docker and not cleaner.cleanup_docker_resources():
            success = False

        if artifacts and not cleaner.cleanup_test_artifacts(
            clean_cache=True,
            clean_coverage=True,
            clean_logs=True,
        ):
            success = False

        if temp and not cleaner.cleanup_temp_files():
            success = False

        if not success:
            output.error("Some cleanup operations failed")
            ctx.exit(1)

    output.success("Cleanup complete!")
