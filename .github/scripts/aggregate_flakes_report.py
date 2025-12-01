#!/usr/bin/env python3
"""Aggregate flaky test data from all suite artifacts.

Collects flakes.json files from test-summary-* artifacts and produces:
1. A consolidated JSON report (flaky-tests-report.json)
2. A markdown summary for GITHUB_STEP_SUMMARY
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Constants
MAX_TESTS_IN_SUMMARY = 50  # Cap tests shown in GitHub summary


def load_flakes_files(summaries_dir: Path) -> list[dict]:
    """Load all flakes.json files from the summaries directory.

    Parameters
    ----------
    summaries_dir : Path
        Directory containing downloaded test-summary-* artifact directories

    Returns
    -------
    list[dict]
        List of parsed flakes.json data from each suite
    """
    flakes_data = []

    # Each artifact downloads to its own subdirectory: summaries/test-summary-cli/flakes.json
    for artifact_dir in summaries_dir.iterdir():
        if not artifact_dir.is_dir():
            continue

        flakes_file = artifact_dir / "flakes.json"
        if flakes_file.exists():
            try:
                data = json.loads(flakes_file.read_text())
                flakes_data.append(data)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse {flakes_file}: {e}", file=sys.stderr)
                continue

    return flakes_data


def aggregate_flakes(flakes_data: list[dict]) -> dict:
    """Aggregate flakes data from multiple suites.

    Parameters
    ----------
    flakes_data : list[dict]
        List of flakes.json data from each suite

    Returns
    -------
    dict
        Aggregated data with by_test and by_suite views
    """
    by_test: dict[str, dict] = {}
    by_suite: dict[str, dict] = {}
    total_flaky = 0
    total_failing = 0

    for suite_data in flakes_data:
        suite_name = suite_data.get("suite", "unknown")
        flaky_tests = suite_data.get("flaky_tests", [])
        consistently_failing = suite_data.get("consistently_failing", [])

        # Track by suite
        by_suite[suite_name] = {
            "flaky": flaky_tests,
            "failing": consistently_failing,
            "flaky_count": len(flaky_tests),
            "failing_count": len(consistently_failing),
        }

        # Track by test (aggregate across suites)
        for test in flaky_tests:
            if test not in by_test:
                by_test[test] = {
                    "suites": [],
                    "flake_count": 0,
                    "type": "flaky",
                }
            by_test[test]["suites"].append(suite_name)
            by_test[test]["flake_count"] += 1
            total_flaky += 1

        for test in consistently_failing:
            if test not in by_test:
                by_test[test] = {
                    "suites": [],
                    "flake_count": 0,
                    "type": "failing",
                }
            # A test that's consistently failing in one suite is more severe
            if by_test[test]["type"] == "flaky":
                by_test[test]["type"] = "mixed"  # Flaky in some, failing in others
            by_test[test]["suites"].append(suite_name)
            total_failing += 1

    return {
        "by_test": by_test,
        "by_suite": by_suite,
        "total_flaky_tests": len(
            [t for t, d in by_test.items() if d["type"] == "flaky"],
        ),
        "total_consistently_failing": len(
            [t for t, d in by_test.items() if d["type"] in ("failing", "mixed")],
        ),
        "total_flake_occurrences": total_flaky,
        "total_failing_occurrences": total_failing,
    }


def format_github_summary(aggregated: dict, run_id: str) -> str:  # noqa: C901
    """Generate markdown summary for GITHUB_STEP_SUMMARY.

    Parameters
    ----------
    aggregated : dict
        Aggregated flakes data
    run_id : str
        GitHub Actions run ID

    Returns
    -------
    str
        Markdown-formatted summary
    """
    by_test = aggregated["by_test"]
    by_suite = aggregated["by_suite"]
    total_flaky = aggregated["total_flaky_tests"]
    total_failing = aggregated["total_consistently_failing"]

    lines = []

    # Header section
    lines.extend([
        "## Flaky Tests Report",
        "",
    ])

    # No flakes case
    if not by_test:
        lines.extend([
            "No flaky or retried tests detected in this run.",
            "",
        ])
        return "\n".join(lines)

    # Summary stats
    lines.extend([
        f"**{total_flaky} flaky test(s)** detected across **{len(by_suite)} suite(s)**",
    ])
    if total_failing > 0:
        lines.append(f"**{total_failing} test(s)** failed even after retry")
    lines.append("")

    # By-test table (most valuable view)
    flaky_tests = {t: d for t, d in by_test.items() if d["type"] == "flaky"}
    if flaky_tests:
        lines.extend([
            "### Flaky Tests (passed on retry)",
            "",
            "| Test | Suites | Count |",
            "|------|--------|-------|",
        ])

        # Sort by flake count descending, then by name
        sorted_tests = sorted(
            flaky_tests.items(),
            key=lambda x: (-x[1]["flake_count"], x[0]),
        )

        for test_name, data in sorted_tests[:MAX_TESTS_IN_SUMMARY]:
            # Truncate long test names for display
            display_name = test_name
            if len(display_name) > 60:
                display_name = "..." + display_name[-57:]
            suites = ", ".join(sorted(data["suites"]))
            lines.append(f"| `{display_name}` | {suites} | {data['flake_count']} |")

        if len(sorted_tests) > MAX_TESTS_IN_SUMMARY:
            remaining = len(sorted_tests) - MAX_TESTS_IN_SUMMARY
            lines.append(f"| ... | _+{remaining} more_ | |")

        lines.append("")

    # Consistently failing tests
    failing_tests = {t: d for t, d in by_test.items() if d["type"] in ("failing", "mixed")}
    if failing_tests:
        lines.extend([
            "### Consistently Failing (not flaky)",
            "",
            "| Test | Suites |",
            "|------|--------|",
        ])

        for test_name, data in sorted(failing_tests.items())[:MAX_TESTS_IN_SUMMARY]:
            display_name = test_name
            if len(display_name) > 60:
                display_name = "..." + display_name[-57:]
            suites = ", ".join(sorted(data["suites"]))
            lines.append(f"| `{display_name}` | {suites} |")

        lines.append("")

    # By-suite summary table
    lines.extend([
        "### By Suite",
        "",
        "| Suite | Flaky | Failing |",
        "|-------|-------|---------|",
    ])

    for suite_name in sorted(by_suite.keys()):
        data = by_suite[suite_name]
        flaky_count = data["flaky_count"]
        failing_count = data["failing_count"]
        if flaky_count > 0 or failing_count > 0:
            lines.append(f"| {suite_name} | {flaky_count} | {failing_count} |")

    lines.extend([
        "",
        f"**Download report**: `gh run download {run_id} -n flaky-tests-report`",
        "",
        "---",
        "",
    ])

    return "\n".join(lines)


def export_report(aggregated: dict, run_id: str, output_path: Path) -> None:
    """Write JSON report for artifact/dev-cli consumption.

    Parameters
    ----------
    aggregated : dict
        Aggregated flakes data
    run_id : str
        GitHub Actions run ID
    output_path : Path
        Path to write the report
    """
    report = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **aggregated,
    }

    output_path.write_text(json.dumps(report, indent=2))


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate flaky test data from all suite artifacts",
    )
    parser.add_argument(
        "--summaries-dir",
        type=Path,
        required=True,
        help="Directory containing downloaded test-summary-* artifact directories",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="GitHub Actions run ID",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("flaky-tests-report.json"),
        help="Output path for JSON report (default: flaky-tests-report.json)",
    )

    args = parser.parse_args()

    if not args.summaries_dir.exists():
        print(f"Error: Summaries directory not found: {args.summaries_dir}", file=sys.stderr)
        sys.exit(1)

    # Load and aggregate
    flakes_data = load_flakes_files(args.summaries_dir)

    if not flakes_data:
        print("No flakes.json files found in summaries directory", file=sys.stderr)
        # Still generate empty report
        aggregated = {
            "by_test": {},
            "by_suite": {},
            "total_flaky_tests": 0,
            "total_consistently_failing": 0,
            "total_flake_occurrences": 0,
            "total_failing_occurrences": 0,
        }
    else:
        aggregated = aggregate_flakes(flakes_data)

    # Output markdown to stdout (for >> $GITHUB_STEP_SUMMARY)
    summary = format_github_summary(aggregated, args.run_id)
    print(summary)

    # Write JSON report
    export_report(aggregated, args.run_id, args.output)


if __name__ == "__main__":
    main()
