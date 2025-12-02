"""Unit tests for CI CLI commands."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli
from aidb_cli.commands.ci import (
    _extract_job_name,
    _format_flakes_output,
    _get_status_display,
    _get_status_icon,
)


@pytest.mark.unit
class TestCiSummaryCommand:
    """Unit tests for ci summary command."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_gh_installed(self):
        """Mock gh CLI being installed."""
        with patch("subprocess.run") as mock_run:
            # First call checks if gh is installed
            mock_run.return_value = subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            )
            yield mock_run

    def test_gh_not_installed(self, runner):
        """Test error when gh CLI is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=1,
                stdout="",
                stderr="",
            )

            result = runner.invoke(cli, ["ci", "summary", "12345"])

            assert result.exit_code != 0
            assert "GitHub CLI (gh) is not installed" in result.output

    def test_gh_fetch_failure(self, runner, mock_gh_installed):
        """Test error when gh run view fails."""
        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh run view fails
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["gh", "run", "view"],
                stderr="HTTP 404: Not Found",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "99999"])

        assert result.exit_code != 0
        assert "Failed to fetch workflow run data" in result.output

    def test_invalid_json_response(self, runner, mock_gh_installed):
        """Test error when gh returns invalid JSON."""
        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns invalid JSON
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout="{ invalid json",
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        assert result.exit_code != 0
        assert "Failed to parse gh CLI response" in result.output

    def test_no_test_jobs_found(self, runner, mock_gh_installed):
        """Test behavior when no test jobs are found."""
        jobs_response = {
            "jobs": [
                {"name": "build", "conclusion": "success"},
                {"name": "lint", "conclusion": "success"},
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns jobs without test jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        assert result.exit_code == 0
        assert "No test jobs found" in result.output

    def test_all_tests_passed(self, runner, mock_gh_installed):
        """Test display when all test jobs pass (with --all flag)."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-mcp / MCP Server Tests",
                    "conclusion": "success",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns test jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345", "--all"])

        assert result.exit_code == 0
        assert "All test jobs passed" in result.output
        assert "CLI Tests" in result.output
        assert "Core Tests" in result.output
        assert "MCP Server Tests" in result.output

    def test_some_tests_failed(self, runner, mock_gh_installed):
        """Test display when some test jobs fail."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "failure",
                },
                {
                    "name": "run-tests / test-mcp / MCP Server Tests",
                    "conclusion": "failure",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns test jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        assert result.exit_code != 0
        assert "2 test job(s) failed" in result.output
        assert "--detailed" in result.output

    def test_cancelled_jobs(self, runner, mock_gh_installed):
        """Test display when jobs are cancelled."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "cancelled",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns test jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        assert result.exit_code == 0
        assert "1 test job(s) were cancelled" in result.output

    def test_matrix_job_formatting(self, runner, mock_gh_installed):
        """Test formatting of matrix job names."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-shared (python) / Shared Tests (python)",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-shared (javascript) / Shared Tests (javascript)",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-shared (java) / Shared Tests (java)",
                    "conclusion": "failure",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns matrix jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345", "--all"])

        assert result.exit_code != 0
        # With --all flag, should show all jobs including successful ones
        assert "Shared Tests (python)" in result.output
        assert "Shared Tests (javascript)" in result.output
        assert "Shared Tests (java)" in result.output

    def test_custom_repo_option(self, runner, mock_gh_installed):
        """Test --repo option is passed to gh CLI."""
        jobs_response: dict[str, list] = {"jobs": []}

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh run view with custom repo
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        runner.invoke(
            cli,
            ["ci", "summary", "12345", "--repo", "my-org/my-repo"],
        )

        # Verify gh was called with correct repo
        calls = mock_gh_installed.call_args_list
        assert len(calls) == 2
        gh_call_args = calls[1][0][0]
        assert "--repo" in gh_call_args
        assert "my-org/my-repo" in gh_call_args

    def test_excludes_test_summary_job(self, runner, mock_gh_installed):
        """Test that Test Summary job itself is excluded from results."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / Test Summary",
                    "conclusion": "success",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            # First call: gh is installed
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            # Second call: gh returns jobs
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345", "--all"])

        assert result.exit_code == 0
        assert "CLI Tests" in result.output
        assert "Test Summary" not in result.output


@pytest.mark.unit
class TestStatusHelpers:
    """Unit tests for status helper functions."""

    def test_get_status_icon_success(self):
        """Test success icon."""
        from aidb_cli.core.constants import CIJobStatus, Icons

        assert _get_status_icon(CIJobStatus.SUCCESS) == Icons.SUCCESS

    def test_get_status_icon_failure(self):
        """Test failure icon."""
        from aidb_cli.core.constants import CIJobStatus, Icons

        assert _get_status_icon(CIJobStatus.FAILURE) == Icons.ERROR

    def test_get_status_icon_skipped(self):
        """Test skipped icon."""
        from aidb_cli.core.constants import CIJobStatus, Icons

        assert _get_status_icon(CIJobStatus.SKIPPED) == Icons.SKIPPED

    def test_get_status_icon_cancelled(self):
        """Test cancelled icon."""
        from aidb_cli.core.constants import CIJobStatus, Icons

        assert _get_status_icon(CIJobStatus.CANCELLED) == Icons.WARNING

    def test_get_status_icon_unknown(self):
        """Test unknown status icon."""
        from aidb_cli.core.constants import CIJobStatus, Icons

        assert _get_status_icon(CIJobStatus.UNKNOWN) == Icons.UNKNOWN
        assert _get_status_icon("weird_status") == Icons.UNKNOWN

    def test_get_status_display_success(self):
        """Test success display."""
        assert _get_status_display("success") == "Success"

    def test_get_status_display_failure(self):
        """Test failure display."""
        assert _get_status_display("failure") == "Failed"

    def test_get_status_display_skipped(self):
        """Test skipped display."""
        assert _get_status_display("skipped") == "Skipped"

    def test_get_status_display_cancelled(self):
        """Test cancelled display."""
        assert _get_status_display("cancelled") == "Cancelled"

    def test_get_status_display_unknown(self):
        """Test unknown status display."""
        assert _get_status_display("unknown") == "Unknown"

    def test_get_status_display_capitalize_fallback(self):
        """Test capitalization fallback for unexpected status."""
        assert _get_status_display("pending") == "Pending"
        assert _get_status_display("queued") == "Queued"


@pytest.mark.unit
class TestExtractJobName:
    """Unit tests for _extract_job_name helper function."""

    def test_extract_with_test_prefix(self):
        """Test extraction with 'run-tests / test-' prefix."""
        assert (
            _extract_job_name("run-tests / test-cli / CLI Tests") == "cli / CLI Tests"
        )

    def test_extract_with_run_tests_prefix(self):
        """Test extraction with 'run-tests /' prefix only."""
        assert _extract_job_name("run-tests / Test Summary") == "Test Summary"

    def test_extract_without_prefix(self):
        """Test extraction without recognized prefix."""
        assert _extract_job_name("some-random-job") == "some-random-job"

    def test_extract_matrix_job(self):
        """Test extraction of matrix job name."""
        result = _extract_job_name(
            "run-tests / test-shared (python) / Shared Tests (python)",
        )
        assert result == "shared (python) / Shared Tests (python)"


@pytest.mark.unit
class TestAllFlag:
    """Unit tests for --all flag functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_gh_installed(self):
        """Mock gh CLI being installed."""
        with patch("subprocess.run") as mock_run:
            yield mock_run

    def test_default_behavior_hides_successful_jobs(self, runner, mock_gh_installed):
        """Test that successful jobs are hidden by default."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "failure",
                },
                {
                    "name": "run-tests / test-mcp / MCP Tests",
                    "conclusion": "success",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        # Should show failure but not successes
        assert "Core Tests" in result.output
        assert "CLI Tests" not in result.output
        assert "MCP Tests" not in result.output

    def test_all_flag_shows_all_jobs(self, runner, mock_gh_installed):
        """Test that --all shows all jobs including successful."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "failure",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345", "--all"])

        # Should show both success and failure
        assert "CLI Tests" in result.output
        assert "Core Tests" in result.output

    def test_all_tests_passed_with_default_filter(self, runner, mock_gh_installed):
        """Test message when all tests pass (default filter)."""
        jobs_response = {
            "jobs": [
                {
                    "name": "run-tests / test-cli / CLI Tests",
                    "conclusion": "success",
                },
                {
                    "name": "run-tests / test-core / Core Tests",
                    "conclusion": "success",
                },
            ],
        }

        mock_gh_installed.side_effect = [
            subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=0,
                stdout="/usr/local/bin/gh\n",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=["gh", "run", "view"],
                returncode=0,
                stdout=json.dumps(jobs_response),
                stderr="",
            ),
        ]

        result = runner.invoke(cli, ["ci", "summary", "12345"])

        assert result.exit_code == 0
        assert "All test jobs passed" in result.output
        assert "--all" in result.output  # Suggests using --all flag


@pytest.mark.unit
class TestFlakesFlag:
    """Unit tests for --flakes flag functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_flakes_report(self) -> dict:
        """Mock flaky-tests-report.json data."""
        return {
            "run_id": "12345678",
            "timestamp": "2024-01-15T10:45:00Z",
            "total_flaky_tests": 3,
            "total_consistently_failing": 1,
            "by_test": {
                "src/tests/test_a.py::test_flaky_one": {
                    "suites": ["shared-python", "core"],
                    "flake_count": 2,
                    "type": "flaky",
                },
                "src/tests/test_b.py::test_flaky_two": {
                    "suites": ["mcp"],
                    "flake_count": 1,
                    "type": "flaky",
                },
                "src/tests/test_c.py::test_flaky_three": {
                    "suites": ["shared-java"],
                    "flake_count": 1,
                    "type": "flaky",
                },
                "src/tests/test_d.py::test_consistent_fail": {
                    "suites": ["core"],
                    "flake_count": 0,
                    "type": "failing",
                },
            },
            "by_suite": {
                "shared-python": {"flaky_count": 1, "failing_count": 0},
                "core": {"flaky_count": 1, "failing_count": 1},
                "mcp": {"flaky_count": 1, "failing_count": 0},
                "shared-java": {"flaky_count": 1, "failing_count": 0},
            },
        }

    def test_flakes_flag_gh_not_installed(self, runner):
        """Test error when gh CLI is not installed with --flakes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["which", "gh"],
                returncode=1,
                stdout="",
                stderr="",
            )

            result = runner.invoke(cli, ["ci", "summary", "12345", "--flakes"])

            assert result.exit_code != 0
            assert "GitHub CLI (gh) is not installed" in result.output

    def test_flakes_flag_artifact_not_found(self, runner):
        """Test error when flaky-tests-report artifact is not found."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                # First call: gh is installed
                subprocess.CompletedProcess(
                    args=["which", "gh"],
                    returncode=0,
                    stdout="/usr/local/bin/gh\n",
                    stderr="",
                ),
                # Second call: artifact download fails
                subprocess.CalledProcessError(
                    returncode=1,
                    cmd=["gh", "run", "download"],
                    stderr="no artifact found",
                ),
            ]

            result = runner.invoke(cli, ["ci", "summary", "12345", "--flakes"])

            assert result.exit_code != 0
            assert "Failed to download flaky tests report" in result.output

    def test_flakes_flag_success(self, runner, mock_flakes_report, tmp_path):
        """Test successful --flakes flag output."""
        # Create mock artifact directory structure
        artifact_dir = tmp_path / "flaky-tests-report"
        artifact_dir.mkdir()
        (artifact_dir / "flaky-tests-report.json").write_text(
            json.dumps(mock_flakes_report),
        )

        with (
            patch("subprocess.run") as mock_run,
            patch(
                "tempfile.TemporaryDirectory",
            ) as mock_tmpdir,
        ):
            # Mock the context manager to return our tmp_path
            mock_tmpdir.return_value.__enter__ = Mock(return_value=str(tmp_path))
            mock_tmpdir.return_value.__exit__ = Mock(return_value=False)

            mock_run.side_effect = [
                # First call: gh is installed
                subprocess.CompletedProcess(
                    args=["which", "gh"],
                    returncode=0,
                    stdout="/usr/local/bin/gh\n",
                    stderr="",
                ),
                # Second call: artifact download succeeds
                subprocess.CompletedProcess(
                    args=["gh", "run", "download"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ]

            result = runner.invoke(cli, ["ci", "summary", "12345", "--flakes"])

            assert result.exit_code == 0
            assert "Flaky Tests Report" in result.output
            assert "3 flaky test(s)" in result.output


@pytest.mark.unit
class TestFormatFlakesOutput:
    """Unit tests for _format_flakes_output helper function."""

    def test_format_no_flakes(self, mock_output, capsys):
        """Test formatting when no flakes detected."""
        report = {
            "by_test": {},
            "by_suite": {},
            "total_flaky_tests": 0,
            "total_consistently_failing": 0,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        assert "No flaky or retried tests detected" in captured.out

    def test_format_with_flaky_tests(self, mock_output, capsys):
        """Test formatting with flaky tests."""
        report = {
            "by_test": {
                "src/tests/test_a.py::test_one": {
                    "suites": ["shared-python"],
                    "flake_count": 1,
                    "type": "flaky",
                },
            },
            "by_suite": {
                "shared-python": {"flaky_count": 1, "failing_count": 0},
            },
            "total_flaky_tests": 1,
            "total_consistently_failing": 0,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        assert "1 flaky test(s) detected" in captured.out
        assert "Flaky Tests (passed on retry)" in captured.out
        assert "test_a.py" in captured.out
        assert "By Suite" in captured.out

    def test_format_with_consistently_failing(self, mock_output, capsys):
        """Test formatting with consistently failing tests."""
        report = {
            "by_test": {
                "src/tests/test_a.py::test_fail": {
                    "suites": ["core"],
                    "flake_count": 0,
                    "type": "failing",
                },
            },
            "by_suite": {
                "core": {"flaky_count": 0, "failing_count": 1},
            },
            "total_flaky_tests": 0,
            "total_consistently_failing": 1,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        # Error message goes to stderr
        assert "1 test(s) failed even after retry" in captured.err
        assert "Consistently Failing" in captured.out

    def test_format_mixed_results(self, mock_output, capsys):
        """Test formatting with both flaky and failing tests."""
        report = {
            "by_test": {
                "src/tests/test_a.py::test_flaky": {
                    "suites": ["shared-python", "core"],
                    "flake_count": 2,
                    "type": "flaky",
                },
                "src/tests/test_b.py::test_fail": {
                    "suites": ["core"],
                    "flake_count": 0,
                    "type": "failing",
                },
            },
            "by_suite": {
                "shared-python": {"flaky_count": 1, "failing_count": 0},
                "core": {"flaky_count": 1, "failing_count": 1},
            },
            "total_flaky_tests": 1,
            "total_consistently_failing": 1,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        assert "1 flaky test(s) detected" in captured.out
        # Error message goes to stderr
        assert "1 test(s) failed even after retry" in captured.err
        assert "Flaky Tests (passed on retry)" in captured.out
        assert "Consistently Failing" in captured.out
        assert "By Suite" in captured.out

    def test_format_long_test_names_truncated(self, mock_output, capsys):
        """Test that long test names are truncated."""
        long_test_name = "src/tests/" + "x" * 100 + ".py::test_very_long_name"
        report = {
            "by_test": {
                long_test_name: {
                    "suites": ["core"],
                    "flake_count": 1,
                    "type": "flaky",
                },
            },
            "by_suite": {
                "core": {"flaky_count": 1, "failing_count": 0},
            },
            "total_flaky_tests": 1,
            "total_consistently_failing": 0,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        # Long names should be truncated with "..."
        assert "..." in captured.out

    def test_format_by_suite_table(self, mock_output, capsys):
        """Test that by-suite table shows correct counts."""
        report = {
            "by_test": {
                "src/tests/test_a.py::test_one": {
                    "suites": ["shared-python"],
                    "flake_count": 1,
                    "type": "flaky",
                },
                "src/tests/test_b.py::test_two": {
                    "suites": ["shared-python"],
                    "flake_count": 1,
                    "type": "flaky",
                },
            },
            "by_suite": {
                "shared-python": {"flaky_count": 2, "failing_count": 0},
                "core": {"flaky_count": 0, "failing_count": 0},  # Should not show
            },
            "total_flaky_tests": 2,
            "total_consistently_failing": 0,
        }

        _format_flakes_output(mock_output, report)

        captured = capsys.readouterr()
        assert "By Suite" in captured.out
        assert "shared-python" in captured.out
        # core has 0 flakes so shouldn't be shown
        lines = captured.out.split("\n")
        suite_lines = [line for line in lines if "core" in line and "0" in line]
        assert len(suite_lines) == 0  # core with 0 counts should not appear
