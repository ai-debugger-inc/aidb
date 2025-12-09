"""CI/CD utilities for AIDB CLI."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import click

from aidb_cli.core.constants import (
    CIArtifactPatterns,
    CIFormatting,
    CIJobPatterns,
    CIJobStatus,
    ExitCode,
    ExternalURLs,
    Icons,
)
from aidb_cli.core.decorators import handle_exceptions

if TYPE_CHECKING:
    from aidb_cli.core.output import OutputStrategy


def _extract_job_name(raw_name: str) -> str:
    """Extract friendly job name from raw GitHub Actions job name.

    Parameters
    ----------
    raw_name : str
        Raw job name from GitHub Actions (e.g., "run-tests / test-cli / CLI Tests")

    Returns
    -------
    str
        Friendly job name (e.g., "cli / CLI Tests")
    """
    if CIJobPatterns.RUN_TESTS_TEST_PREFIX in raw_name:
        return raw_name.split(CIJobPatterns.RUN_TESTS_TEST_PREFIX, 1)[1]
    if CIJobPatterns.RUN_TESTS_PREFIX in raw_name:
        return raw_name.split(CIJobPatterns.RUN_TESTS_PREFIX, 1)[1]
    return raw_name


@click.group(name="ci")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Gitub Actions CI/CD utilities."""


@group.command(name="summary")
@click.argument("run_id")
@click.option(
    "--repo",
    default="ai-debugger-inc/aidb",
    help="Repository in owner/repo format",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Download and display detailed test summaries from artifacts",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all jobs including successful ones (default: only failed/cancelled)",
)
@click.option(
    "--flakes",
    is_flag=True,
    help="Show aggregated flaky tests report from CI run",
)
@click.pass_context
@handle_exceptions
def summary(  # noqa: C901
    ctx: click.Context,
    run_id: str,
    repo: str,
    detailed: bool,
    show_all: bool,
    flakes: bool,
) -> None:
    """Display aggregated test summary for a GitHub Actions workflow run.

    \b Fetches job data via gh CLI and formats it similar to the CI summary page. Useful
    for quickly identifying test failures without opening the browser.

    \b By default, only shows failed and cancelled jobs. Use --all to see all jobs.

    \b Examples:   ./dev-cli ci summary 19401533266   ./dev-cli ci summary 19401533266
    --all   ./dev-cli ci summary 19401533266 --detailed   ./dev-cli ci summary
    19401533266 --repo my-org/my-repo   ./dev-cli ci summary 19401533266 --flakes
    """  # noqa: W605
    output = ctx.obj.output

    # Handle --flakes option separately
    if flakes:
        _display_flakes_report(ctx, output, run_id, repo)
        return

    output.section(f"CI Summary for Run {run_id}", Icons.CHECK)

    # Check if gh CLI is available
    gh_check = subprocess.run(
        ["which", "gh"],  # noqa: S607
        capture_output=True,
        text=True,
    )

    if gh_check.returncode != 0:
        output.error("GitHub CLI (gh) is not installed or not in PATH")
        output.plain(ExternalURLs.GITHUB_CLI_INSTALL_MSG)
        ctx.exit(ExitCode.GENERAL_ERROR)

    # Fetch job data from GitHub
    try:
        result = subprocess.run(  # noqa: S603
            ["gh", "run", "view", run_id, "--repo", repo, "--json", "jobs"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        output.error(f"Failed to fetch workflow run data: {e.stderr.strip()}")
        output.plain(f"Make sure run ID {run_id} exists in {repo}")
        ctx.exit(ExitCode.GENERAL_ERROR)

    # Parse JSON response
    try:
        jobs_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        output.error(f"Failed to parse gh CLI response: {e}")
        ctx.exit(ExitCode.GENERAL_ERROR)

    # Filter to test jobs only
    all_jobs = jobs_data.get("jobs", [])
    test_jobs = [
        job
        for job in all_jobs
        if CIJobPatterns.TEST_PREFIX in job.get("name", "").lower()
        and CIJobPatterns.TEST_SUMMARY_JOB not in job.get("name", "").lower()
    ]

    if not test_jobs:
        output.warning("No test jobs found in this workflow run")
        ctx.exit(0)

    # Filter jobs based on --all flag (default: show only failed/cancelled)
    if not show_all:
        test_jobs = [
            job
            for job in test_jobs
            if job.get("conclusion") in CIJobStatus.NEEDS_ATTENTION
        ]

        if not test_jobs:
            output.success(
                "All test jobs passed! (Use --all to see details)",
            )
            ctx.exit(0)

    # Format and display results
    _display_summary_table(output, test_jobs)

    # Download and display detailed summaries if requested
    if detailed:
        _display_detailed_summaries(output, run_id, repo, test_jobs)

    # Count failures
    failed_jobs = [
        job for job in test_jobs if job.get("conclusion") == CIJobStatus.FAILURE
    ]
    cancelled_jobs = [
        job for job in test_jobs if job.get("conclusion") == CIJobStatus.CANCELLED
    ]

    output.plain("")
    if failed_jobs:
        output.error(
            f"{len(failed_jobs)} test job(s) failed. Check logs for details.",
        )
        if not detailed:
            output.plain("\nFor detailed test results:")
            output.plain(f"  ./dev-cli ci summary {run_id} --detailed")
        ctx.exit(ExitCode.GENERAL_ERROR)
    elif cancelled_jobs:
        output.warning(
            f"{len(cancelled_jobs)} test job(s) were cancelled",
        )
        ctx.exit(0)
    else:
        output.success("All test jobs passed!")
        ctx.exit(0)


def _display_summary_table(
    output: "OutputStrategy",
    test_jobs: list[dict],
) -> None:
    """Display formatted table of test job results.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    test_jobs : list[dict]
        List of test job dictionaries from gh CLI
    """
    # Parse job names and statuses
    results = []
    for job in test_jobs:
        raw_name = job.get("name", "")
        conclusion = job.get("conclusion", CIJobStatus.UNKNOWN)
        friendly_name = _extract_job_name(raw_name)
        results.append((friendly_name, conclusion))

    # Sort alphabetically by job name
    results.sort(key=lambda x: x[0].lower())

    # Display table header
    output.plain("\nTest Results:")
    output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.TABLE_WIDTH)

    # Display each job with appropriate icon
    for job_name, status in results:
        icon = _get_status_icon(status)
        status_display = _get_status_display(status)
        output.plain(f"{icon} {job_name:40s} {status_display}")

    output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.TABLE_WIDTH)


def _get_status_icon(status: str) -> str:
    """Get display icon for job status.

    Parameters
    ----------
    status : str
        Job conclusion status

    Returns
    -------
    str
        Icon to display
    """
    if status == CIJobStatus.SUCCESS:
        return Icons.SUCCESS
    if status == CIJobStatus.FAILURE:
        return Icons.ERROR
    if status == CIJobStatus.SKIPPED:
        return Icons.SKIPPED
    if status == CIJobStatus.CANCELLED:
        return Icons.WARNING
    return Icons.UNKNOWN


def _get_status_display(status: str) -> str:
    """Get display string for job status.

    Parameters
    ----------
    status : str
        Job conclusion status

    Returns
    -------
    str
        Status display string
    """
    status_map = {
        CIJobStatus.SUCCESS: "Success",
        CIJobStatus.FAILURE: "Failed",
        CIJobStatus.SKIPPED: "Skipped",
        CIJobStatus.CANCELLED: "Cancelled",
        CIJobStatus.UNKNOWN: "Unknown",
    }
    return status_map.get(status, status.capitalize())


def _display_detailed_summaries(
    output: "OutputStrategy",
    run_id: str,
    repo: str,
    test_jobs: list[dict],
) -> None:
    """Download and display detailed test summaries from artifacts.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    run_id : str
        GitHub Actions run ID
    repo : str
        Repository in owner/repo format
    test_jobs : list[dict]
        List of test job dictionaries
    """
    output.plain(
        "\n" + CIFormatting.SECTION_SEPARATOR * CIFormatting.SECTION_WIDTH,
    )
    output.plain("DETAILED TEST SUMMARIES")
    output.plain(
        CIFormatting.SECTION_SEPARATOR * CIFormatting.SECTION_WIDTH + "\n",
    )

    # Create temp directory for downloads
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        for job in test_jobs:
            raw_name = job.get("name", "")
            suite_part = _extract_job_name(raw_name)

            # Determine artifact name from job name
            # Matrix jobs: "shared (python) / Shared Tests (python)"
            #              -> test-summary-shared-python
            if " / " in suite_part:
                first_part = suite_part.split(" / ")[0]
                # Check if it's a matrix job like "shared (python)"
                if "(" in first_part and ")" in first_part:
                    suite_name = first_part.split("(")[0].strip()
                    language = first_part.split("(")[1].split(")")[0].strip()
                    artifact_name = (
                        f"{CIArtifactPatterns.SUMMARY_PREFIX}{suite_name}-{language}"
                    )
                else:
                    artifact_name = f"{CIArtifactPatterns.SUMMARY_PREFIX}{first_part}"
            else:
                suite_first = suite_part.split()[0].lower()
                artifact_name = f"{CIArtifactPatterns.SUMMARY_PREFIX}{suite_first}"

            # Download artifact
            try:
                subprocess.run(  # noqa: S603
                    [  # noqa: S607
                        "gh",
                        "run",
                        "download",
                        run_id,
                        "--repo",
                        repo,
                        "--name",
                        artifact_name,
                        "--dir",
                        str(tmppath / artifact_name),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Read and display summary
                summary_file = tmppath / artifact_name / CIArtifactPatterns.SUMMARY_FILE
                if summary_file.exists():
                    summary_content = summary_file.read_text()
                    output.plain(summary_content)
                    output.plain(
                        "\n"
                        + CIFormatting.SUBSECTION_SEPARATOR * CIFormatting.SECTION_WIDTH
                        + "\n",
                    )
                else:
                    output.warning(
                        f"Summary file not found in artifact: {artifact_name}",
                    )

            except subprocess.CalledProcessError:
                # Artifact might not exist (e.g., cancelled jobs)
                continue


def _display_flakes_report(
    ctx: click.Context,
    output: "OutputStrategy",
    run_id: str,
    repo: str,
) -> None:
    """Download and display aggregated flaky tests report.

    Parameters
    ----------
    ctx : click.Context
        Click context for exit handling
    output : OutputStrategy
        Output strategy for CLI messages
    run_id : str
        GitHub Actions run ID
    repo : str
        Repository in owner/repo format
    """
    output.section(f"Flaky Tests Report for Run {run_id}", Icons.WARNING)

    # Check if gh CLI is available
    gh_check = subprocess.run(
        ["which", "gh"],  # noqa: S607
        capture_output=True,
        text=True,
    )

    if gh_check.returncode != 0:
        output.error("GitHub CLI (gh) is not installed or not in PATH")
        output.plain(ExternalURLs.GITHUB_CLI_INSTALL_MSG)
        ctx.exit(ExitCode.GENERAL_ERROR)

    # Download the flaky-tests-report artifact
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        artifact_name = CIArtifactPatterns.FLAKES_REPORT_ARTIFACT

        try:
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "gh",
                    "run",
                    "download",
                    run_id,
                    "--repo",
                    repo,
                    "--name",
                    artifact_name,
                    "--dir",
                    str(tmppath / artifact_name),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else "unknown error"
            output.error(f"Failed to download flaky tests report: {err_msg}")
            output.plain(
                f"Make sure run ID {run_id} has a '{artifact_name}' artifact.",
            )
            output.plain(
                "This artifact is generated by test runs with flaky test detection.",
            )
            ctx.exit(ExitCode.GENERAL_ERROR)

        # Read and parse the report
        report_file = tmppath / artifact_name / CIArtifactPatterns.FLAKES_REPORT_FILE
        if not report_file.exists():
            output.error(f"Report file not found in artifact: {report_file.name}")
            ctx.exit(ExitCode.GENERAL_ERROR)

        try:
            report = json.loads(report_file.read_text())
        except json.JSONDecodeError as e:
            output.error(f"Failed to parse flaky tests report: {e}")
            ctx.exit(ExitCode.GENERAL_ERROR)

        # Display the report
        _format_flakes_output(output, report)

        ctx.exit(0)


def _format_flakes_output(  # noqa: C901
    output: "OutputStrategy",
    report: dict,
) -> None:
    """Format and display flaky tests report.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    report : dict
        Parsed flaky-tests-report.json data
    """
    by_test = report.get("by_test", {})
    by_suite = report.get("by_suite", {})
    total_flaky = report.get("total_flaky_tests", 0)
    total_failing = report.get("total_consistently_failing", 0)

    # No flakes case
    if not by_test:
        output.success("No flaky or retried tests detected in this run.")
        return

    # Summary stats
    output.plain("")
    suites_with_flakes = sum(
        1 for s in by_suite.values() if s.get("flaky_count", 0) > 0
    )
    output.warning(
        f"{total_flaky} flaky test(s) detected across {suites_with_flakes} suite(s)",
    )
    if total_failing > 0:
        output.error(
            f"{total_failing} test(s) failed even after retry",
        )

    # By-test table (flaky tests)
    flaky_tests = {t: d for t, d in by_test.items() if d.get("type") == "flaky"}
    if flaky_tests:
        output.plain("")
        output.plain("Flaky Tests (passed on retry):")
        output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)

        # Sort by flake count descending
        sorted_tests = sorted(
            flaky_tests.items(),
            key=lambda x: (-x[1].get("flake_count", 0), x[0]),
        )

        max_display = CIFormatting.MAX_FLAKY_TESTS_DISPLAY
        for test_name, data in sorted_tests[:max_display]:
            # Truncate long test names
            display_name = test_name
            if len(display_name) > CIFormatting.TEST_NAME_MAX_LENGTH:
                truncate_len = CIFormatting.TEST_NAME_TRUNCATE_LENGTH
                display_name = "..." + display_name[-truncate_len:]
            suites = ", ".join(sorted(data.get("suites", [])))
            count = data.get("flake_count", 0)
            output.plain(f"  {display_name}")
            output.plain(f"    Suites: {suites}  Count: {count}")

        if len(sorted_tests) > max_display:
            remaining = len(sorted_tests) - max_display
            output.plain(f"  ... and {remaining} more")

        output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)

    # Consistently failing tests
    failing_tests = {
        t: d for t, d in by_test.items() if d.get("type") in ("failing", "mixed")
    }
    if failing_tests:
        output.plain("")
        output.plain("Consistently Failing (not flaky - investigate root cause):")
        output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)

        max_failing = CIFormatting.MAX_FAILING_TESTS_DISPLAY
        for test_name, data in sorted(failing_tests.items())[:max_failing]:
            display_name = test_name
            if len(display_name) > CIFormatting.TEST_NAME_MAX_LENGTH:
                truncate_len = CIFormatting.TEST_NAME_TRUNCATE_LENGTH
                display_name = "..." + display_name[-truncate_len:]
            suites = ", ".join(sorted(data.get("suites", [])))
            output.plain(f"  {display_name}")
            output.plain(f"    Suites: {suites}")

        output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)

    # By-suite summary
    output.plain("")
    output.plain("By Suite:")
    output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)
    output.plain(f"  {'Suite':<25s} {'Flaky':>8s} {'Failing':>10s}")
    output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)

    for suite_name in sorted(by_suite.keys()):
        data = by_suite[suite_name]
        flaky_count = data.get("flaky_count", 0)
        failing_count = data.get("failing_count", 0)
        if flaky_count > 0 or failing_count > 0:
            output.plain(
                f"  {suite_name:<25s} {flaky_count:>8d} {failing_count:>10d}",
            )

    output.plain(CIFormatting.TABLE_SEPARATOR * CIFormatting.SECTION_WIDTH)
