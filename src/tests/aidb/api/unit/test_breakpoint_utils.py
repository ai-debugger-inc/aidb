"""Unit tests for breakpoint_utils.

Tests breakpoint validation, conversion, and DAP request creation.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aidb.api.breakpoint_utils import (
    _group_breakpoints_by_source,
    _validate_column_number,
    _validate_hit_condition,
    _validate_line_number,
    _validate_required_fields,
    convert_breakpoints,
    process_breakpoint_inputs,
    validate_breakpoint_line,
    validate_breakpoint_spec,
)
from aidb.common.errors import AidbError


class TestValidateBreakpointLine:
    """Tests for validate_breakpoint_line function."""

    def test_validate_line_out_of_range_returns_invalid(self, tmp_path):
        """Line out of file range returns invalid."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\nline3\n")

        is_valid, reason = validate_breakpoint_line(str(test_file), 10)

        assert is_valid is False
        assert "out of range" in reason
        assert "3 lines" in reason

    def test_validate_line_zero_returns_invalid(self, tmp_path):
        """Line 0 is out of range (1-based indexing)."""
        test_file = tmp_path / "test.py"
        test_file.write_text("line1\nline2\n")

        is_valid, reason = validate_breakpoint_line(str(test_file), 0)

        assert is_valid is False
        assert "out of range" in reason

    def test_validate_blank_line_returns_invalid(self, tmp_path):
        """Blank line cannot have a breakpoint."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n\nx = 2\n")

        is_valid, reason = validate_breakpoint_line(str(test_file), 2)

        assert is_valid is False
        assert "blank" in reason

    def test_validate_whitespace_only_line_returns_invalid(self, tmp_path):
        """Whitespace-only line returns invalid."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n    \nx = 2\n")

        is_valid, reason = validate_breakpoint_line(str(test_file), 2)

        assert is_valid is False
        assert "blank" in reason

    def test_validate_valid_line_returns_valid(self, tmp_path):
        """Valid code line returns valid."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\ny = 2\nprint(x + y)\n")

        is_valid, reason = validate_breakpoint_line(str(test_file), 2)

        assert is_valid is True
        assert reason == "OK"

    def test_validate_file_not_found_returns_invalid(self):
        """Non-existent file returns invalid."""
        is_valid, reason = validate_breakpoint_line("/nonexistent/file.py", 1)

        assert is_valid is False
        assert "File not found" in reason

    def test_validate_with_adapter_checks_patterns(self, tmp_path):
        """Adapter patterns are checked for non-executable lines."""
        test_file = tmp_path / "test.py"
        test_file.write_text("# comment\nx = 1\n")

        mock_adapter = MagicMock()
        mock_adapter.config.non_executable_patterns = ["#"]

        is_valid, reason = validate_breakpoint_line(str(test_file), 1, mock_adapter)

        assert is_valid is False
        assert "not executable" in reason.lower() or "pattern" in reason


class TestValidateRequiredFields:
    """Tests for _validate_required_fields function."""

    def test_validate_missing_file_raises(self):
        """Spec without 'file' raises AidbError."""
        with pytest.raises(AidbError, match="must include 'file'"):
            _validate_required_fields({"line": 10})

    def test_validate_missing_line_raises(self):
        """Spec without 'line' raises AidbError."""
        with pytest.raises(AidbError, match="must include 'line'"):
            _validate_required_fields({"file": "/path/to/test.py"})

    def test_validate_with_both_fields_passes(self):
        """Spec with both fields passes validation."""
        _validate_required_fields({"file": "/path/to/test.py", "line": 10})


class TestValidateLineNumber:
    """Tests for _validate_line_number function."""

    def test_validate_invalid_line_type_raises(self):
        """Non-integer line raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_line_number({"line": "10"})

    def test_validate_zero_line_raises(self):
        """Line 0 raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_line_number({"line": 0})

    def test_validate_negative_line_raises(self):
        """Negative line raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_line_number({"line": -5})

    def test_validate_positive_line_passes(self):
        """Positive integer line passes validation."""
        _validate_line_number({"line": 10})


class TestValidateColumnNumber:
    """Tests for _validate_column_number function."""

    def test_validate_invalid_column_type_raises(self):
        """Non-integer column raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_column_number({"column": "5"})

    def test_validate_zero_column_raises(self):
        """Column 0 raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_column_number({"column": 0})

    def test_validate_negative_column_raises(self):
        """Negative column raises AidbError."""
        with pytest.raises(AidbError, match="positive integer"):
            _validate_column_number({"column": -1})

    def test_validate_positive_column_passes(self):
        """Positive integer column passes validation."""
        _validate_column_number({"column": 5})

    def test_validate_missing_column_passes(self):
        """Missing column passes validation (optional field)."""
        _validate_column_number({})

    def test_validate_none_column_passes(self):
        """None column passes validation."""
        _validate_column_number({"column": None})


class TestValidateHitCondition:
    """Tests for _validate_hit_condition function."""

    def test_validate_invalid_hit_condition_raises(self):
        """Invalid hit condition format raises AidbError."""
        with pytest.raises(AidbError, match="Invalid hit condition"):
            _validate_hit_condition({"hit_condition": "invalid"})

    def test_validate_valid_hit_condition_passes(self):
        """Valid hit condition passes (e.g., '>5', '>=10', '%3')."""
        _validate_hit_condition({"hit_condition": ">5"})

    def test_validate_missing_hit_condition_passes(self):
        """Missing hit_condition passes validation."""
        _validate_hit_condition({})

    def test_validate_empty_hit_condition_passes(self):
        """Empty hit_condition passes validation."""
        _validate_hit_condition({"hit_condition": ""})


class TestValidateBreakpointSpec:
    """Tests for validate_breakpoint_spec function."""

    def test_validate_minimal_spec(self):
        """Minimal valid spec returns normalized spec."""
        result = validate_breakpoint_spec(
            {
                "file": "/path/to/test.py",
                "line": 10,
            }
        )

        assert result["file"] is not None
        assert result["line"] == 10

    def test_validate_spec_with_optional_fields(self):
        """Spec with optional fields includes them in result."""
        result = validate_breakpoint_spec(
            {
                "file": "/path/to/test.py",
                "line": 10,
                "column": 5,
                "condition": "x > 0",
                "log_message": "Value of x: {x}",
            }
        )

        assert result["line"] == 10
        assert result["column"] == 5
        assert result["condition"] == "x > 0"
        assert result["log_message"] == "Value of x: {x}"

    def test_validate_spec_normalizes_path(self):
        """File path is normalized in result."""
        result = validate_breakpoint_spec(
            {
                "file": "/path//to/../to/test.py",
                "line": 10,
            }
        )

        assert "//" not in result["file"]


class TestProcessBreakpointInputs:
    """Tests for process_breakpoint_inputs function."""

    def test_process_single_breakpoint_wraps_in_list(self):
        """Single breakpoint dict is wrapped in list."""
        spec = {"file": "/path/to/test.py", "line": 10}

        result = process_breakpoint_inputs(spec)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["line"] == 10

    def test_process_list_validates_each(self):
        """Each breakpoint in list is validated."""
        specs = [
            {"file": "/path/to/test.py", "line": 10},
            {"file": "/path/to/other.py", "line": 20},
        ]

        result = process_breakpoint_inputs(specs)

        assert len(result) == 2
        assert result[0]["line"] == 10
        assert result[1]["line"] == 20

    def test_process_non_dict_raises(self):
        """Non-dict breakpoint raises AidbError."""
        with pytest.raises(AidbError, match="must be a dict"):
            process_breakpoint_inputs(["not a dict"])

    def test_process_empty_list_returns_empty(self):
        """Empty list returns empty list."""
        result = process_breakpoint_inputs([])

        assert result == []


class TestGroupBreakpointsBySource:
    """Tests for _group_breakpoints_by_source function."""

    def test_group_single_file(self):
        """Breakpoints for single file are grouped together."""
        breakpoints = [
            {"file": "/path/to/test.py", "line": 10},
            {"file": "/path/to/test.py", "line": 20},
        ]

        result = _group_breakpoints_by_source(breakpoints)

        assert len(result) == 1
        assert "/path/to/test.py" in result
        assert len(result["/path/to/test.py"]) == 2

    def test_group_multiple_files(self):
        """Breakpoints are grouped by source file."""
        breakpoints = [
            {"file": "/path/to/test.py", "line": 10},
            {"file": "/path/to/other.py", "line": 5},
            {"file": "/path/to/test.py", "line": 20},
        ]

        result = _group_breakpoints_by_source(breakpoints)

        assert len(result) == 2
        assert len(result["/path/to/test.py"]) == 2
        assert len(result["/path/to/other.py"]) == 1

    def test_group_empty_returns_empty(self):
        """Empty breakpoints returns empty dict."""
        result = _group_breakpoints_by_source([])

        assert result == {}


class TestConvertBreakpoints:
    """Tests for convert_breakpoints function."""

    def test_convert_empty_returns_empty(self):
        """Empty breakpoints returns empty list."""
        result = convert_breakpoints([])

        assert result == []

    def test_convert_creates_dap_requests(self, tmp_path, monkeypatch):
        """Breakpoints are converted to DAP SetBreakpointsRequest."""
        # Disable validation to test conversion without real files
        monkeypatch.setenv("AIDB_VALIDATE_BREAKPOINTS", "false")

        breakpoints = [
            {"file": "/path/to/test.py", "line": 10},
            {"file": "/path/to/test.py", "line": 20},
        ]

        result = convert_breakpoints(breakpoints)

        assert len(result) == 1
        assert result[0].command == "setBreakpoints"
        assert result[0].arguments.source.path == "/path/to/test.py"
        assert len(result[0].arguments.breakpoints) == 2

    def test_convert_groups_by_source(self, monkeypatch):
        """Multiple files create multiple requests."""
        monkeypatch.setenv("AIDB_VALIDATE_BREAKPOINTS", "false")

        breakpoints = [
            {"file": "/path/to/test.py", "line": 10},
            {"file": "/path/to/other.py", "line": 5},
        ]

        result = convert_breakpoints(breakpoints)

        assert len(result) == 2

    def test_convert_includes_optional_fields(self, monkeypatch):
        """Optional fields are included in DAP request."""
        monkeypatch.setenv("AIDB_VALIDATE_BREAKPOINTS", "false")

        breakpoints = [
            {
                "file": "/path/to/test.py",
                "line": 10,
                "column": 5,
                "condition": "x > 0",
                "hit_condition": ">5",
                "log_message": "x = {x}",
            },
        ]

        result = convert_breakpoints(breakpoints)

        bp = result[0].arguments.breakpoints[0]
        assert bp.line == 10
        assert bp.column == 5
        assert bp.condition == "x > 0"
        assert bp.hitCondition == ">5"
        assert bp.logMessage == "x = {x}"

    def test_convert_with_real_files(self, tmp_path):
        """Breakpoints with real files pass validation."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\ny = 2\nprint(x + y)\n")

        breakpoints = [
            {"file": str(test_file), "line": 1},
            {"file": str(test_file), "line": 2},
        ]

        result = convert_breakpoints(breakpoints)

        assert len(result) == 1
        assert len(result[0].arguments.breakpoints) == 2
