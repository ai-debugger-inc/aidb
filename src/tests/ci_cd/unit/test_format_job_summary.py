"""Unit tests for format_job_summary.py script."""

import json
import os
from pathlib import Path

import pytest
from _script_loader import load_script_module

format_job_summary = load_script_module("format_job_summary")


class TestParseResults:
    """Tests for parse_results function."""

    def test_parse_results_success(self, monkeypatch):
        """Test parsing valid JSON from environment variable."""
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
                "test-core": {"result": "failure"},
                "test-mcp": {"result": "skipped"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)

        results = format_job_summary.parse_results()

        assert results == {
            "test-cli": "success",
            "test-core": "failure",
            "test-mcp": "skipped",
        }

    def test_parse_results_missing_env_var(self, monkeypatch):
        """Test error when RESULTS_JSON is not set."""
        monkeypatch.delenv("RESULTS_JSON", raising=False)

        with pytest.raises(
            ValueError,
            match="RESULTS_JSON environment variable not set",
        ):
            format_job_summary.parse_results()

    def test_parse_results_invalid_json(self, monkeypatch):
        """Test error when RESULTS_JSON contains invalid JSON."""
        monkeypatch.setenv("RESULTS_JSON", "{invalid json")

        with pytest.raises(ValueError, match="Invalid JSON in RESULTS_JSON"):
            format_job_summary.parse_results()

    def test_parse_results_unknown_status(self, monkeypatch):
        """Test handling of jobs with missing result field."""
        results_json = json.dumps(
            {
                "test-cli": {},
                "test-core": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)

        results = format_job_summary.parse_results()

        assert results == {
            "test-cli": "unknown",
            "test-core": "success",
        }


class TestFormatJobName:
    """Tests for format_job_name function."""

    def test_format_job_name_removes_test_prefix(self):
        """Test that 'test-' prefix is removed."""
        assert format_job_summary.format_job_name("test-cli") == "CLI"
        assert format_job_summary.format_job_name("test-core") == "Core"

    def test_format_job_name_preserves_acronyms(self):
        """Test that acronyms are preserved in uppercase."""
        assert format_job_summary.format_job_name("test-cli") == "CLI"
        assert format_job_summary.format_job_name("test-mcp") == "MCP"
        assert format_job_summary.format_job_name("test-api") == "API"
        assert format_job_summary.format_job_name("test-dap") == "DAP"

    def test_format_job_name_special_cases(self):
        """Test special case handling."""
        assert format_job_summary.format_job_name("test-ci-cd") == "CI/CD"
        assert format_job_summary.format_job_name("test-shared-utils") == "Shared Utils"

    def test_format_job_name_title_case(self):
        """Test title case formatting for non-acronyms."""
        assert (
            format_job_summary.format_job_name("test-python-shared") == "Python Shared"
        )
        assert (
            format_job_summary.format_job_name("test-javascript-frameworks")
            == "Javascript Frameworks"
        )
        assert format_job_summary.format_job_name("test-java-launch") == "Java Launch"

    def test_format_job_name_mixed_acronyms(self):
        """Test formatting with mixed acronyms and regular words."""
        assert format_job_summary.format_job_name("test-mcp-handlers") == "MCP Handlers"


class TestGenerateSummaryTable:
    """Tests for generate_summary_table function."""

    def test_generate_summary_table_all_success(self):
        """Test summary table with all successful jobs."""
        results = {
            "test-cli": "success",
            "test-core": "success",
        }

        summary = format_job_summary.generate_summary_table(results)

        assert "## Test Results" in summary
        assert "| Job | Status |" in summary
        assert "| Core | ✅ Success |" in summary
        assert "| CLI | ✅ Success |" in summary

    def test_generate_summary_table_mixed_statuses(self):
        """Test summary table with mixed job statuses."""
        results = {
            "test-cli": "success",
            "test-core": "failure",
            "test-mcp": "skipped",
        }

        summary = format_job_summary.generate_summary_table(results)

        assert "| Core | ❌ Failed |" in summary
        assert "| CLI | ✅ Success |" in summary
        assert "| MCP | ⏭️ Skipped |" in summary

    def test_generate_summary_table_unknown_status(self):
        """Test summary table with unknown status."""
        results = {
            "test-cli": "unknown",
            "test-core": "cancelled",
        }

        summary = format_job_summary.generate_summary_table(results)

        assert "| CLI | ❓ Unknown |" in summary
        assert "| Core | ❓ Cancelled |" in summary

    def test_generate_summary_table_sorted_output(self):
        """Test that jobs are sorted alphabetically."""
        results = {
            "test-mcp": "success",
            "test-core": "success",
            "test-cli": "success",
        }

        summary = format_job_summary.generate_summary_table(results)
        lines = summary.split("\n")

        cli_idx = next(i for i, line in enumerate(lines) if "CLI" in line)
        core_idx = next(i for i, line in enumerate(lines) if "Core" in line)
        mcp_idx = next(i for i, line in enumerate(lines) if "MCP" in line)

        assert cli_idx < core_idx < mcp_idx


class TestCheckFailures:
    """Tests for check_failures function."""

    def test_check_failures_all_success(self, capsys):
        """Test check_failures with all successful jobs."""
        results = {
            "test-cli": "success",
            "test-core": "success",
        }

        result = format_job_summary.check_failures(results)

        assert result is True
        captured = capsys.readouterr()
        assert "✅ All tests passed!" in captured.out

    def test_check_failures_with_failures(self, capsys):
        """Test check_failures with failed jobs."""
        results = {
            "test-cli": "success",
            "test-core": "failure",
            "test-mcp": "failure",
        }

        result = format_job_summary.check_failures(results)

        assert result is False
        captured = capsys.readouterr()
        assert "❌ Some tests failed" in captured.out
        assert "test-core" in captured.out
        assert "test-mcp" in captured.out

    def test_check_failures_with_skipped(self, capsys):
        """Test check_failures treats skipped as non-failure."""
        results = {
            "test-cli": "success",
            "test-core": "skipped",
        }

        result = format_job_summary.check_failures(results)

        assert result is True
        captured = capsys.readouterr()
        assert "✅ All tests passed!" in captured.out


class TestMain:
    """Tests for main function."""

    def test_main_success_case(self, monkeypatch, capsys, tmp_path):
        """Test main function with successful jobs (no GITHUB_STEP_SUMMARY)."""
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
                "test-core": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        exit_code = format_job_summary.main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "## Test Results" in captured.out
        assert "✅ All tests passed!" in captured.out

    def test_main_failure_case(self, monkeypatch, capsys):
        """Test main function with failed jobs."""
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
                "test-core": {"result": "failure"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

        exit_code = format_job_summary.main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "❌ Some tests failed" in captured.out

    def test_main_writes_to_github_step_summary(self, monkeypatch, tmp_path):
        """Test main function writes to GITHUB_STEP_SUMMARY file."""
        summary_file = tmp_path / "summary.md"
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        exit_code = format_job_summary.main()

        assert exit_code == 0
        assert summary_file.exists()
        content = summary_file.read_text()
        assert "## Test Results" in content
        assert "| CLI | ✅ Success |" in content

    def test_main_appends_to_existing_file(self, monkeypatch, tmp_path):
        """Test main function appends to existing GITHUB_STEP_SUMMARY."""
        summary_file = tmp_path / "summary.md"
        summary_file.write_text("Existing content\n")

        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        exit_code = format_job_summary.main()

        assert exit_code == 0
        content = summary_file.read_text()
        assert "Existing content" in content
        assert "## Test Results" in content

    def test_main_handles_exceptions(self, monkeypatch, capsys):
        """Test main function handles exceptions gracefully."""
        monkeypatch.delenv("RESULTS_JSON", raising=False)

        exit_code = format_job_summary.main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error generating test summary" in captured.err


class TestIntegration:
    """Integration tests for full workflow."""

    def test_full_workflow_matrix_jobs(self, monkeypatch, tmp_path):
        """Test full workflow with matrix job results (GitHub Actions format)."""
        summary_file = tmp_path / "summary.md"
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
                "test-core": {"result": "success"},
                "test-shared": {"result": "success"},
                "test-frameworks": {"result": "success"},
                "test-launch": {"result": "success"},
                "test-ci-cd": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        exit_code = format_job_summary.main()

        assert exit_code == 0
        content = summary_file.read_text()

        assert "| Core | ✅ Success |" in content
        assert "| CLI | ✅ Success |" in content
        assert "| Shared | ✅ Success |" in content
        assert "| Frameworks | ✅ Success |" in content
        assert "| Launch | ✅ Success |" in content
        assert "| CI/CD | ✅ Success |" in content

    def test_full_workflow_with_failures(self, monkeypatch, tmp_path):
        """Test full workflow with some job failures."""
        summary_file = tmp_path / "summary.md"
        results_json = json.dumps(
            {
                "test-cli": {"result": "success"},
                "test-shared": {"result": "failure"},
                "test-frameworks": {"result": "skipped"},
                "test-launch": {"result": "success"},
            },
        )
        monkeypatch.setenv("RESULTS_JSON", results_json)
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

        exit_code = format_job_summary.main()

        assert exit_code == 1
        content = summary_file.read_text()

        assert "| Shared | ❌ Failed |" in content
        assert "| Frameworks | ⏭️ Skipped |" in content
