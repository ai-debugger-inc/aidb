#!/usr/bin/env python3
"""Format pytest test summary for GitHub Actions.

Generates GitHub-flavored markdown summaries from pytest output logs.
Handles three scenarios:
1. All tests pass, no retries → Simple summary
2. Tests pass with retries → Summary + retry list
3. Tests fail with/without retries → Failure summary + retry list (if any)

Strips ANSI color codes and caps retry lists at configurable limit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Constants
MAX_RETRY_DISPLAY = 20
MAX_SUMMARY_LINES = 100
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI color codes from text.

    Parameters
    ----------
    text : str
        Text potentially containing ANSI escape sequences

    Returns
    -------
    str
        Text with all ANSI escape sequences removed
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


def extract_final_summary(log_content: str) -> str:
    """Extract final pytest summary line from log.

    Searches for lines like:
    "=== 220 passed, 1 rerun in 32.19s ==="

    Parameters
    ----------
    log_content : str
        Full pytest log content

    Returns
    -------
    str
        Final summary line with ANSI codes stripped, or empty string if not found
    """
    # Match summary lines: "=== ... (passed|failed|error) ... ==="
    pattern = r"^=+\s+.*\s+(passed|failed|error).*\s+=+$"

    for line in reversed(log_content.splitlines()):
        # Strip ANSI codes before matching to handle color-coded output
        clean_line = strip_ansi(line.strip())
        if re.match(pattern, clean_line):
            return clean_line

    return ""


def extract_rerun_tests(log_content: str) -> tuple[list[str], list[str]]:
    """Extract names of tests that were rerun, categorized by final outcome.

    Distinguishes between:
    - Flaky tests: Failed initially but passed on retry
    - Consistently failing: Failed even after retry

    Parameters
    ----------
    log_content : str
        Full pytest log content

    Returns
    -------
    tuple[list[str], list[str]]
        (flaky_tests, consistently_failing_tests) - both sorted lists
    """
    flaky_tests = set()
    consistently_failing = set()
    lines = log_content.splitlines()

    for i, line in enumerate(lines):
        # Look for test lines that have RERUN on the SAME line
        # Format: "src/tests/.../test_foo.py::TestClass::test_method RERUN [ 50%]"
        stripped = strip_ansi(line.strip())
        if (
            stripped.startswith("src/tests/")
            and "::" in stripped
            and "RERUN" in stripped
        ):
            test_name = stripped.split()[0]

            # Look ahead for the final outcome of this same test
            for next_line in lines[i + 1 : i + 10]:
                clean_next = strip_ansi(next_line.strip())
                if clean_next.startswith(test_name):
                    if "PASSED" in clean_next:
                        flaky_tests.add(test_name)
                    elif "FAILED" in clean_next:
                        consistently_failing.add(test_name)
                    break

    return sorted(list(flaky_tests)), sorted(list(consistently_failing))


def count_reruns_from_summary(summary: str) -> int:
    """Extract rerun count from final summary line.

    Parameters
    ----------
    summary : str
        Final pytest summary line (e.g., "=== 220 passed, 1 rerun in 32.19s ===")

    Returns
    -------
    int
        Number of reruns, or 0 if not found
    """
    # Match patterns like "5 rerun" or "1 rerun"
    match = re.search(r"(\d+)\s+rerun", summary)
    if match:
        return int(match.group(1))
    return 0


def format_retry_summary(
    flaky_tests: list[str],
    consistently_failing: list[str],
    rerun_count: int,
    max_display: int = MAX_RETRY_DISPLAY,
) -> str:
    """Format retry summary section.

    Parameters
    ----------
    flaky_tests : list[str]
        Tests that passed on retry (genuinely flaky)
    consistently_failing : list[str]
        Tests that failed even after retry (deterministic failures)
    rerun_count : int
        Total number of reruns from summary
    max_display : int, optional
        Maximum number of tests to display (default: 20)

    Returns
    -------
    str
        Formatted markdown section for retried tests
    """
    lines = []

    # Section 1: Flaky tests (passed on retry)
    if flaky_tests:
        lines.extend([
            "",
            "### ⚠️ Flaky Tests (passed on retry)",
            "",
            "The following tests failed initially but passed on retry:",
            "",
            "```",
        ])
        _append_test_list(lines, flaky_tests, max_display)
        lines.append("```")

    # Section 2: Consistently failing tests
    if consistently_failing:
        lines.extend([
            "",
            "### ❌ Retried But Still Failing",
            "",
            "The following tests failed even after retry (not flaky - investigate root cause):",
            "",
            "```",
        ])
        _append_test_list(lines, consistently_failing, max_display)
        lines.append("```")

    # If neither list populated but we have a count, fall back to generic
    if not flaky_tests and not consistently_failing and rerun_count > 0:
        lines.extend([
            "",
            "### ⚠️ Retried Tests",
            "",
            f"_Check test-output.log for details ({rerun_count} tests were retried)_",
        ])

    return "\n".join(lines)


def _append_test_list(lines: list[str], tests: list[str], max_display: int) -> None:
    """Append test list to lines, capping at max_display."""
    if len(tests) <= max_display:
        lines.extend(tests)
    else:
        lines.extend(tests[:max_display])
        remaining = len(tests) - max_display
        lines.append("")
        lines.append(f"... and {remaining} more (see test-output.log)")


def format_failure_summary(
    log_content: str,
    suite_name: str,
    max_lines: int = MAX_SUMMARY_LINES,
    final_summary: str | None = None,
) -> str:
    """Format pytest failure summary section.

    Parameters
    ----------
    log_content : str
        Full pytest log content
    suite_name : str
        Name of test suite (for artifact reference)
    max_lines : int, optional
        Maximum lines to show from failure summary (default: 100)
    final_summary : str, optional
        Final pytest summary line (e.g., "1 failed, 640 passed, 24 skipped")

    Returns
    -------
    str
        Formatted markdown section for failures
    """
    lines = []

    # Check if detailed failure summary exists
    if "short test summary info" in log_content:
        lines.append(f"### Pytest Summary (capped at {max_lines} lines)")
        lines.append("")
        lines.append("```")

        # Extract from "short test summary info" to end
        summary_start = log_content.find("short test summary info")
        if summary_start != -1:
            summary_section = log_content[summary_start:]
            summary_lines = summary_section.splitlines()

            # Take up to max_lines and strip ANSI
            for line in summary_lines[:max_lines]:
                lines.append(strip_ansi(line))

        lines.append("```")

        # Check if truncated
        if summary_start != -1:
            total_lines = len(log_content[summary_start:].splitlines())
            if total_lines > max_lines:
                lines.append("")
                lines.append(
                    f"_Note: Output truncated at {max_lines} lines. "
                    f"Download test-logs-{suite_name} artifact for full details._",
                )

                # Append final pytest summary if available
                if final_summary:
                    lines.append("")
                    lines.append("**Final pytest summary:**")
                    lines.append("")
                    lines.append("```")
                    lines.append(final_summary)
                    lines.append("```")
    else:
        # No detailed summary - show last 50 lines
        lines.append("### Pytest Summary")
        lines.append("")
        lines.append("**Tests failed or timed out** - no pytest summary available.")
        lines.append("")
        lines.append("Check the artifact logs for details. Last 50 lines of output:")
        lines.append("")
        lines.append("```")

        log_lines = log_content.splitlines()
        for line in log_lines[-50:]:
            lines.append(strip_ansi(line))

        lines.append("```")

    return "\n".join(lines)


def export_flakes_json(
    suite_name: str,
    artifact_suffix: str,
    flaky_tests: list[str],
    consistently_failing: list[str],
    rerun_count: int,
    output_dir: Path,
) -> Path:
    """Export flaky test data as JSON for aggregation.

    Parameters
    ----------
    suite_name : str
        Name of test suite
    artifact_suffix : str
        Optional suffix for matrix jobs (e.g., "python", "java")
    flaky_tests : list[str]
        Tests that passed on retry (genuinely flaky)
    consistently_failing : list[str]
        Tests that failed even after retry
    rerun_count : int
        Total number of reruns from summary
    output_dir : Path
        Directory to write flakes.json

    Returns
    -------
    Path
        Path to the written flakes.json file
    """
    # Build full suite identifier (e.g., "shared-python" for matrix jobs)
    full_suite = suite_name
    if artifact_suffix:
        full_suite = f"{suite_name}-{artifact_suffix}"

    flakes_data = {
        "suite": full_suite,
        "flaky_tests": flaky_tests,
        "consistently_failing": consistently_failing,
        "rerun_count": rerun_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    output_path = output_dir / "flakes.json"
    output_path.write_text(json.dumps(flakes_data, indent=2))

    return output_path


def format_summary(
    log_file: Path,
    exit_code: int,
    suite_name: str,
    run_id: str,
    artifact_suffix: str = "",
) -> tuple[str, list[str], list[str], int]:
    """Generate formatted test summary markdown.

    Parameters
    ----------
    log_file : Path
        Path to pytest output log file
    exit_code : int
        Exit code from test run (0 = pass, non-zero = fail)
    suite_name : str
        Name of test suite for display and artifact references
    run_id : str
        GitHub Actions run ID for artifact download commands
    artifact_suffix : str, optional
        Suffix to append to artifact names (e.g., "java" for matrix jobs)

    Returns
    -------
    tuple[str, list[str], list[str], int]
        Tuple of (markdown_summary, flaky_tests, consistently_failing, rerun_count)

    Raises
    ------
    FileNotFoundError
        If log file does not exist
    """
    if not log_file.exists():
        msg = f"Log file not found: {log_file}"
        raise FileNotFoundError(msg)

    # Read log content
    log_content = log_file.read_text()

    # Extract data
    final_summary = extract_final_summary(log_content)
    flaky_tests, consistently_failing = extract_rerun_tests(log_content)
    rerun_count = count_reruns_from_summary(final_summary)

    # Build artifact name with optional suffix (e.g., "shared-java" for matrix jobs)
    artifact_name = f"test-logs-{suite_name}"
    if artifact_suffix:
        artifact_name = f"{artifact_name}-{artifact_suffix}"

    # Build markdown
    lines = [
        f"## Test Results: {suite_name}",
        "",
    ]

    # Status indicator
    if exit_code == 0:
        lines.append("**Status**: ✅ Passed")
    else:
        lines.append("**Status**: ❌ Failed")

    lines.extend([
        "",
        f"**Logs**: Uploaded to `{artifact_name}` artifact",
        "",
        "```bash",
        f"gh run download {run_id} -n {artifact_name}",
        "```",
        "",
    ])

    # Scenario-based content
    if exit_code == 0:
        if rerun_count == 0:
            # Scenario 1: All green, no retries - simple summary
            lines.append("### Pytest Summary")
            lines.append("")
            if final_summary:
                lines.append("```")
                lines.append(final_summary)
                lines.append("```")
            else:
                lines.append("✅ All tests passed")
        else:
            # Scenario 2: Green with retries - summary + retry list
            lines.append("### Pytest Summary")
            lines.append("")
            lines.append("```")
            lines.append(final_summary)
            lines.append("```")

            lines.append(format_retry_summary(
                flaky_tests, consistently_failing, rerun_count,
            ))
    else:
        # Scenario 3: Red - failure summary + retry list if any
        lines.append(format_failure_summary(log_content, suite_name, final_summary=final_summary))

        if rerun_count > 0:
            lines.append(format_retry_summary(
                flaky_tests, consistently_failing, rerun_count,
            ))

    # Footer
    lines.extend([
        "",
        "---",
    ])

    return "\n".join(lines), flaky_tests, consistently_failing, rerun_count


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Format pytest test summary for GitHub Actions",
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to pytest output log file",
    )
    parser.add_argument(
        "exit_code",
        type=int,
        help="Exit code from test run (0 = pass, non-zero = fail)",
    )
    parser.add_argument(
        "suite_name",
        type=str,
        help="Name of test suite for display",
    )
    parser.add_argument(
        "run_id",
        type=str,
        help="GitHub Actions run ID",
    )
    parser.add_argument(
        "artifact_suffix",
        type=str,
        nargs="?",
        default="",
        help="Optional suffix for artifact names (e.g., 'java' for matrix jobs)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(),
        help="Directory to write flakes.json (default: current directory)",
    )

    args = parser.parse_args()

    try:
        summary, flaky_tests, consistently_failing, rerun_count = format_summary(
            args.log_file,
            args.exit_code,
            args.suite_name,
            args.run_id,
            args.artifact_suffix,
        )
        print(summary)

        # Export flakes data for aggregation
        export_flakes_json(
            args.suite_name,
            args.artifact_suffix,
            flaky_tests,
            consistently_failing,
            rerun_count,
            args.output_dir,
        )

        sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error generating summary: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
