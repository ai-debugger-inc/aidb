"""Unit tests for format_test_summary.py script."""

from pathlib import Path

import pytest
from _script_loader import load_script_module

# Load the script module
format_test_summary = load_script_module("format_test_summary")


# Test fixtures for mock pytest logs


@pytest.fixture
def mock_log_all_pass_no_retries() -> str:
    """Mock pytest log: all tests pass, no retries."""
    return """
collected 220 items

src/tests/aidb/test_one.py::test_example_one PASSED                    [ 50%]
src/tests/aidb/test_two.py::test_example_two PASSED                    [100%]

======================== 220 passed in 32.19s =========================
"""


@pytest.fixture
def mock_log_pass_with_retries() -> str:
    """Mock pytest log: tests pass with 3 retries.

    Note: pytest-rerunfailures outputs RERUN on the same line as the test name,
    followed by another line with the final outcome (PASSED/FAILED).
    """
    return """
collected 220 items

src/tests/aidb/audit/unit/test_logger.py::TestAuditLoggerOperations::test_log_event RERUN [ 11%]
src/tests/aidb/audit/unit/test_logger.py::TestAuditLoggerOperations::test_log_event PASSED [ 11%]

src/tests/aidb/session/test_session.py::TestSession::test_start RERUN [ 30%]
src/tests/aidb/session/test_session.py::TestSession::test_start PASSED  [ 30%]

src/tests/aidb/service/test_service.py::TestService::test_connection RERUN [ 50%]
src/tests/aidb/service/test_service.py::TestService::test_connection PASSED        [ 50%]

======================== 220 passed, 3 rerun in 45.23s =======================
"""


@pytest.fixture
def mock_log_fail_with_retries() -> str:
    """Mock pytest log: 4 failures with 5 retries.

    Note: pytest-rerunfailures outputs RERUN on the same line as the test name.
    For tests that fail after max reruns, we see multiple RERUN lines followed by FAILED.
    """
    return """
collected 263 items

src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_list RERUN [ 10%]
src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_list RERUN [ 10%]
src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_list FAILED [ 10%]

src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_remove RERUN [ 20%]
src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_remove FAILED [ 20%]

src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_clear_all RERUN [ 30%]
src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_clear_all FAILED [ 30%]

src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_response_structure RERUN [ 40%]
src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_response_structure FAILED [ 40%]

=========================== short test summary info ============================
FAILED src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_list - asyncio.exceptions.CancelledError
FAILED src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_remove - asyncio.exceptions.CancelledError
FAILED src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_breakpoint_clear_all - asyncio.exceptions.CancelledError
FAILED src/tests/aidb_mcp/handlers/unit/test_breakpoint_handlers.py::TestBreakpointHandlers::test_response_structure - asyncio.exceptions.CancelledError
============== 4 failed, 259 passed, 5 rerun in 84.00s (0:01:23) ===============
"""


@pytest.fixture
def mock_log_with_ansi_codes() -> str:
    """Mock pytest log with ANSI color codes."""
    return """
collected 5 items

src/tests/test_example.py::test_one \x1b[32mPASSED\x1b[0m                 [ 50%]
src/tests/test_example.py::test_two \x1b[32mPASSED\x1b[0m                 [100%]

\x1b[32m=========================== 5 passed in 2.10s ===========================\x1b[0m
"""


@pytest.fixture
def mock_log_many_retries() -> str:
    """Mock pytest log with 25 retries (for testing capping).

    Note: pytest-rerunfailures outputs RERUN on the same line as the test name.
    """
    retries = []
    for i in range(25):
        retries.append(
            f"src/tests/test_file_{i}.py::TestClass::test_method_{i} RERUN [{i}%]\n"
            f"src/tests/test_file_{i}.py::TestClass::test_method_{i} PASSED  [{i}%]",
        )

    return (
        "collected 225 items\n\n"
        + "\n\n".join(retries)
        + "\n\n======================== 225 passed, 25 rerun in 120.45s =========================\n"
    )


# Test classes


class TestStripAnsi:
    """Test ANSI color code removal."""

    def test_strip_simple_color_codes(self):
        """Test stripping basic color codes."""
        text = "\x1b[32mPASSED\x1b[0m"
        result = format_test_summary.strip_ansi(text)
        assert result == "PASSED"
        assert "\x1b[" not in result

    def test_strip_multiple_color_codes(self):
        """Test stripping multiple color codes in one line."""
        text = "\x1b[32mgreen\x1b[0m and \x1b[31mred\x1b[0m"
        result = format_test_summary.strip_ansi(text)
        assert result == "green and red"

    def test_strip_complex_codes(self):
        """Test stripping complex ANSI codes."""
        text = "\x1b[1;32;40mCOMPLEX\x1b[0m"
        result = format_test_summary.strip_ansi(text)
        assert result == "COMPLEX"

    def test_no_codes_unchanged(self):
        """Test that text without codes is unchanged."""
        text = "plain text"
        result = format_test_summary.strip_ansi(text)
        assert result == text


class TestExtractFinalSummary:
    """Test final summary line extraction."""

    def test_extract_pass_summary(self, mock_log_all_pass_no_retries):
        """Test extracting summary from passing tests."""
        result = format_test_summary.extract_final_summary(mock_log_all_pass_no_retries)
        assert "220 passed" in result
        assert "32.19s" in result

    def test_extract_summary_with_retries(self, mock_log_pass_with_retries):
        """Test extracting summary with retries."""
        result = format_test_summary.extract_final_summary(mock_log_pass_with_retries)
        assert "220 passed" in result
        assert "3 rerun" in result

    def test_extract_fail_summary(self, mock_log_fail_with_retries):
        """Test extracting summary from failed tests."""
        result = format_test_summary.extract_final_summary(mock_log_fail_with_retries)
        assert "4 failed" in result
        assert "259 passed" in result
        assert "5 rerun" in result

    def test_extract_with_ansi(self, mock_log_with_ansi_codes):
        """Test that ANSI codes are stripped from summary."""
        result = format_test_summary.extract_final_summary(mock_log_with_ansi_codes)
        assert "5 passed" in result
        assert "\x1b[" not in result

    def test_no_summary_returns_empty(self):
        """Test that missing summary returns empty string."""
        log = "Some log content without summary line"
        result = format_test_summary.extract_final_summary(log)
        assert result == ""


class TestExtractRerunTests:
    """Test rerun test extraction."""

    def test_extract_single_rerun(self):
        """Test extracting single rerun test."""
        log = """
src/tests/test_example.py::test_one RERUN [ 50%]
src/tests/test_example.py::test_one PASSED              [ 50%]
"""
        flaky, failing = format_test_summary.extract_rerun_tests(log)
        assert len(flaky) == 1
        assert len(failing) == 0
        assert "src/tests/test_example.py::test_one" in flaky

    def test_extract_multiple_reruns(self, mock_log_pass_with_retries):
        """Test extracting multiple rerun tests."""
        flaky, failing = format_test_summary.extract_rerun_tests(
            mock_log_pass_with_retries,
        )
        assert len(flaky) == 3
        assert len(failing) == 0
        assert any("test_logger.py" in test for test in flaky)
        assert any("test_session.py" in test for test in flaky)
        assert any("test_service.py" in test for test in flaky)

    def test_extract_with_ansi_codes(self):
        """Test extracting reruns with ANSI codes."""
        log = """
\x1b[32msrc/tests/test_example.py::test_one\x1b[0m \x1b[33mRERUN\x1b[0m [ 50%]
\x1b[32msrc/tests/test_example.py::test_one PASSED\x1b[0m    [ 50%]
"""
        flaky, failing = format_test_summary.extract_rerun_tests(log)
        assert len(flaky) == 1
        assert len(failing) == 0
        assert "\x1b[" not in flaky[0]

    def test_no_reruns_returns_empty(self, mock_log_all_pass_no_retries):
        """Test that no reruns returns empty lists."""
        flaky, failing = format_test_summary.extract_rerun_tests(
            mock_log_all_pass_no_retries,
        )
        assert flaky == []
        assert failing == []


class TestCountReruns:
    """Test rerun counting from summary."""

    def test_count_single_rerun(self):
        """Test counting single rerun."""
        summary = "=== 220 passed, 1 rerun in 32.19s ==="
        result = format_test_summary.count_reruns_from_summary(summary)
        assert result == 1

    def test_count_multiple_reruns(self):
        """Test counting multiple reruns."""
        summary = "=== 220 passed, 5 rerun in 45.23s ==="
        result = format_test_summary.count_reruns_from_summary(summary)
        assert result == 5

    def test_count_no_reruns(self):
        """Test counting when no reruns."""
        summary = "=== 220 passed in 32.19s ==="
        result = format_test_summary.count_reruns_from_summary(summary)
        assert result == 0

    def test_count_from_empty_summary(self):
        """Test counting from empty summary."""
        result = format_test_summary.count_reruns_from_summary("")
        assert result == 0


class TestExtractRerunTestsDetailed:
    """Test categorized rerun extraction with mixed outcomes."""

    def test_extract_flaky_tests(self, mock_log_pass_with_retries):
        """Test extracting tests that passed on retry (flaky)."""
        flaky, failing = format_test_summary.extract_rerun_tests(
            mock_log_pass_with_retries,
        )
        assert len(flaky) == 3
        assert len(failing) == 0
        assert any("test_logger.py" in test for test in flaky)
        assert any("test_session.py" in test for test in flaky)
        assert any("test_service.py" in test for test in flaky)

    def test_extract_consistently_failing_tests(self, mock_log_fail_with_retries):
        """Test extracting tests that failed despite retry."""
        flaky, failing = format_test_summary.extract_rerun_tests(
            mock_log_fail_with_retries,
        )
        assert len(flaky) == 0
        assert len(failing) == 4
        assert any("test_breakpoint_list" in test for test in failing)
        assert any("test_breakpoint_remove" in test for test in failing)

    def test_extract_mixed_outcomes(self):
        """Test extracting tests with mixed outcomes (some flaky, some failing)."""
        log = """
src/tests/test_one.py::test_flaky RERUN [ 25%]
src/tests/test_one.py::test_flaky PASSED                 [ 25%]

src/tests/test_two.py::test_consistent_fail RERUN [ 50%]
src/tests/test_two.py::test_consistent_fail FAILED       [ 50%]

src/tests/test_three.py::test_also_flaky RERUN [ 75%]
src/tests/test_three.py::test_also_flaky PASSED          [ 75%]
"""
        flaky, failing = format_test_summary.extract_rerun_tests(log)
        assert len(flaky) == 2
        assert len(failing) == 1
        assert "src/tests/test_one.py::test_flaky" in flaky
        assert "src/tests/test_three.py::test_also_flaky" in flaky
        assert "src/tests/test_two.py::test_consistent_fail" in failing


class TestFormatRetrySummary:
    """Test retry summary formatting."""

    def test_format_flaky_only(self):
        """Test formatting with only flaky tests (passed on retry)."""
        flaky = [
            "src/tests/test_one.py::test_a",
            "src/tests/test_two.py::test_b",
        ]
        result = format_test_summary.format_retry_summary(flaky, [], 2)
        assert "⚠️ Flaky Tests (passed on retry)" in result
        assert "failed initially but passed on retry" in result
        assert "test_one.py" in result
        assert "test_two.py" in result
        assert "Retried But Still Failing" not in result

    def test_format_consistently_failing_only(self):
        """Test formatting with only consistently failing tests."""
        failing = [
            "src/tests/test_one.py::test_a",
            "src/tests/test_two.py::test_b",
        ]
        result = format_test_summary.format_retry_summary([], failing, 2)
        assert "❌ Retried But Still Failing" in result
        assert "not flaky - investigate root cause" in result
        assert "test_one.py" in result
        assert "test_two.py" in result
        assert "Flaky Tests (passed on retry)" not in result

    def test_format_mixed_categories(self):
        """Test formatting with both flaky and consistently failing tests."""
        flaky = ["src/tests/test_one.py::test_a"]
        failing = ["src/tests/test_two.py::test_b"]
        result = format_test_summary.format_retry_summary(flaky, failing, 2)
        assert "⚠️ Flaky Tests (passed on retry)" in result
        assert "❌ Retried But Still Failing" in result
        assert "test_one.py" in result
        assert "test_two.py" in result

    def test_format_with_many_flaky_retries(self):
        """Test formatting with many flaky retries (over cap)."""
        flaky = [f"src/tests/test_{i}.py::test_method" for i in range(25)]
        result = format_test_summary.format_retry_summary(flaky, [], 25, max_display=20)
        assert "⚠️ Flaky Tests (passed on retry)" in result
        assert "test_0.py" in result
        assert "test_19.py" in result
        assert "... and 5 more" in result

    def test_format_with_empty_lists_but_count(self):
        """Test formatting when both lists are empty but count is provided."""
        result = format_test_summary.format_retry_summary([], [], 5)
        assert "⚠️ Retried Tests" in result
        assert "5 tests were retried" in result
        assert "Check test-output.log" in result


class TestFormatFailureSummary:
    """Test failure summary formatting."""

    def test_format_with_short_summary(self, mock_log_fail_with_retries):
        """Test formatting when short test summary info exists."""
        result = format_test_summary.format_failure_summary(
            mock_log_fail_with_retries,
            "mcp",
        )
        assert "Pytest Summary (capped at 100 lines)" in result
        assert "short test summary info" in result
        assert "FAILED" in result
        assert "test_breakpoint_list" in result

    def test_format_without_summary(self):
        """Test formatting when no short summary info exists."""
        log = """
Some test output
No summary section
"""
        result = format_test_summary.format_failure_summary(log, "core")
        assert "Tests failed or timed out" in result
        assert "Last 50 lines" in result

    def test_ansi_codes_stripped(self):
        """Test that ANSI codes are stripped from failure summary."""
        log = """
=========================== short test summary info ============================
\x1b[31mFAILED\x1b[0m src/tests/test.py::test_one
"""
        result = format_test_summary.format_failure_summary(log, "test")
        assert "\x1b[" not in result
        assert "FAILED" in result


class TestFormatSummary:
    """Test complete summary formatting."""

    def test_scenario_all_pass_no_retries(self, tmp_path, mock_log_all_pass_no_retries):
        """Test scenario 1: All tests pass, no retries."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_all_pass_no_retries)

        result, flaky, failing, rerun_count = format_test_summary.format_summary(
            log_file,
            0,
            "core",
            "12345678",
        )

        assert "## Test Results: core" in result
        assert "✅ Passed" in result
        assert "220 passed" in result
        assert "⚠️ Flaky Tests" not in result
        assert flaky == []
        assert failing == []
        assert rerun_count == 0

    def test_scenario_pass_with_retries(self, tmp_path, mock_log_pass_with_retries):
        """Test scenario 2: Tests pass with retries (flaky tests)."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_pass_with_retries)

        result, flaky, failing, rerun_count = format_test_summary.format_summary(
            log_file,
            0,
            "core",
            "12345678",
        )

        assert "## Test Results: core" in result
        assert "✅ Passed" in result
        assert "220 passed, 3 rerun" in result
        # Should show "Flaky Tests (passed on retry)" since these tests passed
        assert "⚠️ Flaky Tests (passed on retry)" in result
        assert "test_logger.py" in result
        assert len(flaky) == 3
        assert len(failing) == 0
        assert rerun_count == 3

    def test_scenario_fail_with_retries(self, tmp_path, mock_log_fail_with_retries):
        """Test scenario 3: Tests fail with retries (consistently failing)."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_fail_with_retries)

        result, flaky, failing, rerun_count = format_test_summary.format_summary(
            log_file,
            1,
            "mcp",
            "12345678",
        )

        assert "## Test Results: mcp" in result
        assert "❌ Failed" in result
        assert "short test summary info" in result
        # Should show "Retried But Still Failing" since these tests failed even after retry
        assert "❌ Retried But Still Failing" in result
        assert "test_breakpoint_handlers.py" in result
        assert len(flaky) == 0
        assert len(failing) == 4
        assert rerun_count == 5

    def test_missing_file_raises_error(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        log_file = tmp_path / "nonexistent.log"

        with pytest.raises(FileNotFoundError, match="Log file not found"):
            format_test_summary.format_summary(log_file, 0, "core", "12345678")

    def test_ansi_codes_stripped_from_output(self, tmp_path, mock_log_with_ansi_codes):
        """Test that all ANSI codes are stripped from final output."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_with_ansi_codes)

        result, _, _, _ = format_test_summary.format_summary(
            log_file,
            0,
            "test",
            "12345678",
        )

        assert "\x1b[" not in result
        assert "5 passed" in result

    def test_retry_list_capping(self, tmp_path, mock_log_many_retries):
        """Test that retry list is capped at 20 with overflow message."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_many_retries)

        result, flaky, failing, rerun_count = format_test_summary.format_summary(
            log_file,
            0,
            "test",
            "12345678",
        )

        # All 25 tests passed on retry, so they should be in the flaky section
        assert "⚠️ Flaky Tests (passed on retry)" in result
        assert "test_file_0.py" in result
        assert "test_file_19.py" in result
        assert "... and 5 more" in result
        assert len(flaky) == 25
        assert rerun_count == 25

    def test_github_run_id_placeholder(self, tmp_path, mock_log_all_pass_no_retries):
        """Test that actual run_id is included (not template variable)."""
        log_file = tmp_path / "test-output.log"
        log_file.write_text(mock_log_all_pass_no_retries)

        result, _, _, _ = format_test_summary.format_summary(
            log_file,
            0,
            "core",
            "12345678",
        )

        assert "gh run download 12345678 -n test-logs-core" in result
        assert "${{ github.run_id }}" not in result  # Template should NOT appear


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_log_file(self, tmp_path):
        """Test handling of empty log file."""
        log_file = tmp_path / "empty.log"
        log_file.write_text("")

        result, _, _, _ = format_test_summary.format_summary(
            log_file,
            0,
            "empty",
            "12345678",
        )

        assert "## Test Results: empty" in result
        assert "✅ Passed" in result

    def test_malformed_log(self, tmp_path):
        """Test handling of malformed log content."""
        log_file = tmp_path / "malformed.log"
        log_file.write_text("Random content with no pytest structure")

        result, _, _, _ = format_test_summary.format_summary(
            log_file,
            1,
            "test",
            "12345678",
        )

        # Should still generate a summary, even if incomplete
        assert "## Test Results: test" in result
        assert "❌ Failed" in result

    def test_unicode_in_log(self, tmp_path):
        """Test handling of Unicode characters in log."""
        log = """
src/tests/test_unicode.py::test_emoji RERUN [ 50%]
src/tests/test_unicode.py::test_emoji PASSED             [ 50%]

======================== 1 passed, 1 rerun in 2.10s =========================
"""
        log_file = tmp_path / "unicode.log"
        log_file.write_text(log)

        result, flaky, _, rerun_count = format_test_summary.format_summary(
            log_file,
            0,
            "test",
            "12345678",
        )

        assert "## Test Results: test" in result
        assert "1 passed, 1 rerun" in result
        assert len(flaky) == 1
        assert rerun_count == 1


class TestExportFlakesJson:
    """Test flakes.json export functionality."""

    def test_export_creates_file(self, tmp_path):
        """Test that export_flakes_json creates the file."""
        result_path = format_test_summary.export_flakes_json(
            suite_name="cli",
            artifact_suffix="",
            flaky_tests=["src/tests/test.py::test_one"],
            consistently_failing=[],
            rerun_count=1,
            output_dir=tmp_path,
        )

        assert result_path.exists()
        assert result_path.name == "flakes.json"

    def test_export_json_structure(self, tmp_path):
        """Test that exported JSON has correct structure."""
        import json

        format_test_summary.export_flakes_json(
            suite_name="shared",
            artifact_suffix="python",
            flaky_tests=[
                "src/tests/test_a.py::test_one",
                "src/tests/test_b.py::test_two",
            ],
            consistently_failing=["src/tests/test_c.py::test_three"],
            rerun_count=3,
            output_dir=tmp_path,
        )

        flakes_file = tmp_path / "flakes.json"
        data = json.loads(flakes_file.read_text())

        assert data["suite"] == "shared-python"
        assert len(data["flaky_tests"]) == 2
        assert len(data["consistently_failing"]) == 1
        assert data["rerun_count"] == 3
        assert "timestamp" in data

    def test_export_without_suffix(self, tmp_path):
        """Test export without artifact suffix."""
        import json

        format_test_summary.export_flakes_json(
            suite_name="core",
            artifact_suffix="",
            flaky_tests=[],
            consistently_failing=[],
            rerun_count=0,
            output_dir=tmp_path,
        )

        flakes_file = tmp_path / "flakes.json"
        data = json.loads(flakes_file.read_text())

        assert data["suite"] == "core"
        assert data["flaky_tests"] == []
        assert data["consistently_failing"] == []
        assert data["rerun_count"] == 0
