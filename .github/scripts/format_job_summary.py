#!/usr/bin/env python3
"""Generate GitHub Actions test summary from job results JSON.

This script parses the results of all test jobs and generates a markdown
summary table, then checks if any jobs failed and exits with appropriate code.

Usage
-----
RESULTS_JSON='{"job1": {"result": "success"}, ...}' python3 format_job_summary.py

Environment Variables
---------------------
RESULTS_JSON : str
    JSON object mapping job names to their result objects
    (from ${{ toJson(needs) }} in GitHub Actions)
"""

import json
import os
import sys
from pathlib import Path

# Status values (from GitHub Actions job results)
STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_UNKNOWN = "unknown"

# Status display strings
STATUS_DISPLAY_SUCCESS = "✅ Success"
STATUS_DISPLAY_FAILED = "❌ Failed"
STATUS_DISPLAY_SKIPPED = "⏭️ Skipped"
STATUS_DISPLAY_UNKNOWN = "❓"

# Environment variables
ENV_RESULTS_JSON = "RESULTS_JSON"
ENV_GITHUB_STEP_SUMMARY = "GITHUB_STEP_SUMMARY"

# Job name parsing
JOB_NAME_PREFIX = "test-"
SPECIAL_CASE_CICD = "ci-cd"
SPECIAL_CASE_SHARED_UTILS = "shared-utils"
DISPLAY_NAME_CICD = "CI/CD"
DISPLAY_NAME_SHARED_UTILS = "Shared Utils"
ACRONYMS = frozenset(["CLI", "MCP", "API", "DAP"])

# Table formatting
TABLE_HEADER = "## Test Results"
TABLE_SEPARATOR = "|-----|--------|"
TABLE_HEADER_ROW = "| Job | Status |"


def parse_results() -> dict[str, str]:
    """Parse job results from RESULTS_JSON environment variable.

    Returns
    -------
    dict[str, str]
        Dict mapping job names to their result status (success/failure/skipped)

    Raises
    ------
    ValueError
        If RESULTS_JSON is missing or invalid
    """
    results_json = os.getenv(ENV_RESULTS_JSON)
    if not results_json:
        msg = f"{ENV_RESULTS_JSON} environment variable not set"
        raise ValueError(msg)

    try:
        results = json.loads(results_json)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {ENV_RESULTS_JSON}: {e}"
        raise ValueError(msg) from e

    return {
        job_name: job_data.get("result", STATUS_UNKNOWN)
        for job_name, job_data in results.items()
    }


def format_job_name(job_name: str) -> str:
    """Format job name for display in summary table.

    Converts hyphenated job names to human-readable format:
    - test-python-shared → Python Shared
    - test-cli → CLI

    Parameters
    ----------
    job_name : str
        Raw job name from workflow

    Returns
    -------
    str
        Formatted display name
    """
    name = job_name.replace(JOB_NAME_PREFIX, "")

    if name == SPECIAL_CASE_CICD:
        return DISPLAY_NAME_CICD

    if name == SPECIAL_CASE_SHARED_UTILS:
        return DISPLAY_NAME_SHARED_UTILS

    parts = name.split("-")
    formatted_parts = []

    for part in parts:
        if part.upper() in ACRONYMS:
            formatted_parts.append(part.upper())
        else:
            formatted_parts.append(part.capitalize())

    return " ".join(formatted_parts)


def generate_summary_table(results: dict[str, str]) -> str:
    """Generate markdown summary table from job results.

    Parameters
    ----------
    results : dict[str, str]
        Dict mapping job names to result statuses

    Returns
    -------
    str
        Markdown table as string
    """
    lines = [
        TABLE_HEADER,
        "",
        TABLE_HEADER_ROW,
        TABLE_SEPARATOR,
    ]

    for job_name in sorted(results.keys()):
        status = results[job_name]
        display_name = format_job_name(job_name)

        if status == STATUS_SUCCESS:
            status_display = STATUS_DISPLAY_SUCCESS
        elif status == STATUS_FAILURE:
            status_display = STATUS_DISPLAY_FAILED
        elif status == STATUS_SKIPPED:
            status_display = STATUS_DISPLAY_SKIPPED
        else:
            status_display = f"{STATUS_DISPLAY_UNKNOWN} {status.capitalize()}"

        lines.append(f"| {display_name} | {status_display} |")

    lines.append("")
    return "\n".join(lines)


def check_failures(results: dict[str, str]) -> bool:
    """Check if any jobs failed.

    Parameters
    ----------
    results : dict[str, str]
        Dict mapping job names to result statuses

    Returns
    -------
    bool
        True if all jobs passed or were skipped, False if any failed
    """
    failures = [job for job, status in results.items() if status == STATUS_FAILURE]

    if failures:
        print("\n❌ Some tests failed. Check individual job logs for details.")
        print(f"\nFailed jobs: {', '.join(failures)}")
        return False

    print("\n✅ All tests passed!")
    return True


def main() -> int:
    """Main entry point.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failures)
    """
    try:
        results = parse_results()
        summary = generate_summary_table(results)

        github_step_summary = os.getenv(ENV_GITHUB_STEP_SUMMARY)
        if github_step_summary:
            with Path(github_step_summary).open("a") as f:
                f.write(summary)
        else:
            print(summary)

        if check_failures(results):
            return 0

        return 1

    except Exception as e:
        print(f"Error generating test summary: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
