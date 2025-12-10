"""Unit tests for MCP tool validation utilities.

Tests for validation.py functions:
- validate_required_params
- validate_session_id
- validate_file_path
- validate_breakpoint_location
- validate_expression
- validate_step_action
- validate_frame_id
- validate_timeout
- format_validation_error
- validate_language
- validate_required_param
- validate_session_active
- early_validate_handler_args
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from aidb_common.constants import SUPPORTED_LANGUAGES

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestValidateRequiredParams:
    """Tests for validate_required_params function."""

    def test_validate_required_params_all_present(self) -> None:
        """Test that validation passes when all required params present."""
        from aidb_mcp.tools.validation import validate_required_params

        args = {"name": "test", "value": 123}
        required = ["name", "value"]

        is_valid, error_msg = validate_required_params(args, required)

        assert is_valid is True
        assert error_msg is None

    def test_validate_required_params_missing_one(self) -> None:
        """Test that validation fails when one param missing."""
        from aidb_mcp.tools.validation import validate_required_params

        args = {"name": "test"}
        required = ["name", "value"]

        is_valid, error_msg = validate_required_params(args, required)

        assert is_valid is False
        assert error_msg is not None
        assert "value" in error_msg

    def test_validate_required_params_missing_all(self) -> None:
        """Test that validation fails when all params missing."""
        from aidb_mcp.tools.validation import validate_required_params

        args: dict = {}
        required = ["name", "value"]

        is_valid, error_msg = validate_required_params(args, required)

        assert is_valid is False
        assert error_msg is not None
        assert "name" in error_msg
        assert "value" in error_msg

    def test_validate_required_params_empty_string(self) -> None:
        """Test that empty string is treated as missing."""
        from aidb_mcp.tools.validation import validate_required_params

        args = {"name": "", "value": 123}
        required = ["name", "value"]

        is_valid, error_msg = validate_required_params(args, required)

        assert is_valid is False
        assert "name" in error_msg

    def test_validate_required_params_no_required(self) -> None:
        """Test that validation passes with no required params."""
        from aidb_mcp.tools.validation import validate_required_params

        args = {"name": "test"}
        required: list = []

        is_valid, error_msg = validate_required_params(args, required)

        assert is_valid is True
        assert error_msg is None


class TestValidateSessionId:
    """Tests for validate_session_id function."""

    def test_validate_session_id_valid_simple(self) -> None:
        """Test that simple alphanumeric session ID is valid."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id("abc123")

        assert is_valid is True
        assert error_msg is None

    def test_validate_session_id_valid_with_hyphens(self) -> None:
        """Test that session ID with hyphens is valid."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id("session-001-abc")

        assert is_valid is True
        assert error_msg is None

    def test_validate_session_id_valid_with_underscores(self) -> None:
        """Test that session ID with underscores is valid."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id("session_001_abc")

        assert is_valid is True
        assert error_msg is None

    def test_validate_session_id_none_is_valid(self) -> None:
        """Test that None session ID is valid (optional param)."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id(None)

        assert is_valid is True
        assert error_msg is None

    def test_validate_session_id_invalid_chars(self) -> None:
        """Test that session ID with invalid chars fails."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id("session@123")

        assert is_valid is False
        assert error_msg is not None
        assert "Invalid session ID" in error_msg

    def test_validate_session_id_spaces(self) -> None:
        """Test that session ID with spaces fails."""
        from aidb_mcp.tools.validation import validate_session_id

        is_valid, error_msg = validate_session_id("session 123")

        assert is_valid is False
        assert "Invalid session ID" in error_msg


class TestValidateFilePath:
    """Tests for validate_file_path function."""

    def test_validate_file_path_valid_path(self) -> None:
        """Test that valid path passes validation."""
        from aidb_mcp.tools.validation import validate_file_path

        is_valid, error_msg, resolved = validate_file_path("/tmp/test.py")

        assert is_valid is True
        assert error_msg is None
        assert resolved is not None

    def test_validate_file_path_existing_file(self) -> None:
        """Test that existing file passes validation with must_exist=True."""
        from aidb_mcp.tools.validation import validate_file_path

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            path = f.name

        is_valid, error_msg, resolved = validate_file_path(path, must_exist=True)

        assert is_valid is True
        assert error_msg is None
        assert resolved is not None

        Path(path).unlink()

    def test_validate_file_path_nonexistent_file(self) -> None:
        """Test that nonexistent file fails with must_exist=True."""
        from aidb_mcp.tools.validation import validate_file_path

        is_valid, error_msg, resolved = validate_file_path(
            "/nonexistent/path/file.py", must_exist=True
        )

        assert is_valid is False
        assert error_msg is not None
        assert "not found" in error_msg.lower()
        assert resolved is None

    def test_validate_file_path_directory_not_file(self) -> None:
        """Test that directory fails when expecting a file."""
        from aidb_mcp.tools.validation import validate_file_path

        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, error_msg, resolved = validate_file_path(tmpdir, must_exist=True)

        assert is_valid is False
        assert "Not a file" in error_msg


class TestValidateBreakpointLocation:
    """Tests for validate_breakpoint_location function."""

    def test_validate_breakpoint_location_file_line(self) -> None:
        """Test that file:line format is valid."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location(
            "/path/to/file.py:42"
        )

        assert is_valid is True
        assert error_msg is None
        assert parsed == {"file": "/path/to/file.py", "line": 42}

    def test_validate_breakpoint_location_line_only(self) -> None:
        """Test that line-only format is valid."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("42")

        assert is_valid is True
        assert error_msg is None
        assert parsed == {"line": 42}

    def test_validate_breakpoint_location_function_name(self) -> None:
        """Test that function name format is valid."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("my_function")

        assert is_valid is True
        assert error_msg is None
        assert parsed == {"function": "my_function"}

    def test_validate_breakpoint_location_negative_line(self) -> None:
        """Test that negative line number fails."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("file.py:-1")

        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_validate_breakpoint_location_zero_line(self) -> None:
        """Test that zero line number fails."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("file.py:0")

        assert is_valid is False
        assert "positive" in error_msg.lower()

    def test_validate_breakpoint_location_invalid_line(self) -> None:
        """Test that invalid line number fails."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("file.py:abc")

        assert is_valid is False
        assert "Invalid line number" in error_msg

    def test_validate_breakpoint_location_invalid_format(self) -> None:
        """Test that invalid format fails."""
        from aidb_mcp.tools.validation import validate_breakpoint_location

        is_valid, error_msg, parsed = validate_breakpoint_location("invalid@location")

        assert is_valid is False
        assert "Invalid breakpoint location" in error_msg


class TestValidateExpression:
    """Tests for validate_expression function."""

    def test_validate_expression_valid_simple(self) -> None:
        """Test that simple expression is valid."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("x + y")

        assert is_valid is True
        assert error_msg is None

    def test_validate_expression_valid_attribute_access(self) -> None:
        """Test that attribute access expression is valid."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("obj.attr.value")

        assert is_valid is True
        assert error_msg is None

    def test_validate_expression_empty(self) -> None:
        """Test that empty expression fails."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("")

        assert is_valid is False
        assert "empty" in error_msg.lower()

    def test_validate_expression_whitespace_only(self) -> None:
        """Test that whitespace-only expression fails."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("   ")

        assert is_valid is False
        assert "empty" in error_msg.lower()

    def test_validate_expression_dangerous_import(self) -> None:
        """Test that __import__ is blocked."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("__import__('os')")

        assert is_valid is False
        assert "dangerous" in error_msg.lower()

    def test_validate_expression_dangerous_exec(self) -> None:
        """Test that exec is blocked."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("exec('print(1)')")

        assert is_valid is False
        assert "dangerous" in error_msg.lower()

    def test_validate_expression_dangerous_eval(self) -> None:
        """Test that eval is blocked."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("eval('1+1')")

        assert is_valid is False
        assert "dangerous" in error_msg.lower()

    def test_validate_expression_dangerous_subprocess(self) -> None:
        """Test that subprocess is blocked."""
        from aidb_mcp.tools.validation import validate_expression

        is_valid, error_msg = validate_expression("subprocess.run(['ls'])")

        assert is_valid is False
        assert "dangerous" in error_msg.lower()


class TestValidateStepAction:
    """Tests for validate_step_action function."""

    def test_validate_step_action_into(self) -> None:
        """Test that 'into' action is valid."""
        from aidb_mcp.tools.validation import validate_step_action

        is_valid, error_msg = validate_step_action("into")

        assert is_valid is True
        assert error_msg is None

    def test_validate_step_action_over(self) -> None:
        """Test that 'over' action is valid."""
        from aidb_mcp.tools.validation import validate_step_action

        is_valid, error_msg = validate_step_action("over")

        assert is_valid is True
        assert error_msg is None

    def test_validate_step_action_out(self) -> None:
        """Test that 'out' action is valid."""
        from aidb_mcp.tools.validation import validate_step_action

        is_valid, error_msg = validate_step_action("out")

        assert is_valid is True
        assert error_msg is None

    def test_validate_step_action_case_insensitive(self) -> None:
        """Test that action validation is case-insensitive."""
        from aidb_mcp.tools.validation import validate_step_action

        is_valid, error_msg = validate_step_action("INTO")

        assert is_valid is True
        assert error_msg is None

    def test_validate_step_action_invalid(self) -> None:
        """Test that invalid action fails."""
        from aidb_mcp.tools.validation import validate_step_action

        is_valid, error_msg = validate_step_action("jump")

        assert is_valid is False
        assert "Invalid step action" in error_msg


class TestValidateFrameId:
    """Tests for validate_frame_id function."""

    def test_validate_frame_id_valid(self) -> None:
        """Test that positive frame ID is valid."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id(5)

        assert is_valid is True
        assert error_msg is None
        assert parsed == 5

    def test_validate_frame_id_zero(self) -> None:
        """Test that zero frame ID is valid."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id(0)

        assert is_valid is True
        assert error_msg is None
        assert parsed == 0

    def test_validate_frame_id_none(self) -> None:
        """Test that None frame ID is valid (optional)."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id(None)

        assert is_valid is True
        assert error_msg is None
        assert parsed is None

    def test_validate_frame_id_string_number(self) -> None:
        """Test that string number is converted."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id("10")

        assert is_valid is True
        assert parsed == 10

    def test_validate_frame_id_negative(self) -> None:
        """Test that negative frame ID fails."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id(-1)

        assert is_valid is False
        assert "non-negative" in error_msg

    def test_validate_frame_id_invalid(self) -> None:
        """Test that invalid frame ID fails."""
        from aidb_mcp.tools.validation import validate_frame_id

        is_valid, error_msg, parsed = validate_frame_id("abc")

        assert is_valid is False
        assert "Invalid frame ID" in error_msg


class TestValidateTimeout:
    """Tests for validate_timeout function."""

    def test_validate_timeout_valid(self) -> None:
        """Test that valid timeout passes."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout(5000)

        assert is_valid is True
        assert error_msg is None
        assert parsed == 5000

    def test_validate_timeout_zero(self) -> None:
        """Test that zero timeout is valid."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout(0)

        assert is_valid is True
        assert parsed == 0

    def test_validate_timeout_none(self) -> None:
        """Test that None timeout is valid (optional)."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout(None)

        assert is_valid is True
        assert parsed is None

    def test_validate_timeout_negative(self) -> None:
        """Test that negative timeout fails."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout(-1000)

        assert is_valid is False
        assert "non-negative" in error_msg

    def test_validate_timeout_exceeds_max(self) -> None:
        """Test that timeout exceeding max fails."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout(400000)

        assert is_valid is False
        assert "exceed" in error_msg.lower()

    def test_validate_timeout_invalid(self) -> None:
        """Test that invalid timeout fails."""
        from aidb_mcp.tools.validation import validate_timeout

        is_valid, error_msg, parsed = validate_timeout("fast")

        assert is_valid is False
        assert "Invalid timeout" in error_msg


class TestFormatValidationError:
    """Tests for format_validation_error function."""

    def test_format_validation_error_basic(self) -> None:
        """Test basic error formatting."""
        from aidb_mcp.tools.validation import format_validation_error

        result = format_validation_error(
            param_name="timeout",
            expected_format="positive integer (ms)",
            provided_value="abc",
        )

        assert "timeout" in result
        assert "positive integer" in result
        assert "abc" in result

    def test_format_validation_error_with_examples(self) -> None:
        """Test error formatting with examples."""
        from aidb_mcp.tools.validation import format_validation_error

        result = format_validation_error(
            param_name="language",
            expected_format="supported language",
            provided_value="ruby",
            examples=SUPPORTED_LANGUAGES,
        )

        assert "language" in result
        assert "ruby" in result
        assert "python" in result
        assert "javascript" in result


class TestValidateLanguage:
    """Tests for validate_language function."""

    def test_validate_language_python(self) -> None:
        """Test that python is valid."""
        from aidb_mcp.tools.validation import validate_language

        with patch(
            "aidb_mcp.utils.get_supported_languages",
            return_value=SUPPORTED_LANGUAGES,
        ):
            is_valid, error_msg = validate_language("python")

        assert is_valid is True
        assert error_msg is None

    def test_validate_language_case_insensitive(self) -> None:
        """Test that language validation is case-insensitive."""
        from aidb_mcp.tools.validation import validate_language

        with patch(
            "aidb_mcp.utils.get_supported_languages",
            return_value=SUPPORTED_LANGUAGES,
        ):
            is_valid, error_msg = validate_language("PYTHON")

        assert is_valid is True
        assert error_msg is None

    def test_validate_language_unsupported(self) -> None:
        """Test that unsupported language fails."""
        from aidb_mcp.tools.validation import validate_language

        with patch(
            "aidb_mcp.utils.get_supported_languages",
            return_value=SUPPORTED_LANGUAGES,
        ):
            is_valid, error_msg = validate_language("ruby")

        assert is_valid is False
        assert "Unsupported language" in error_msg


class TestValidateRequiredParam:
    """Tests for validate_required_param function."""

    def test_validate_required_param_present(self) -> None:
        """Test that present value passes."""
        from aidb_mcp.tools.validation import validate_required_param

        is_valid, error_msg = validate_required_param("value", "test_param")

        assert is_valid is True
        assert error_msg is None

    def test_validate_required_param_none(self) -> None:
        """Test that None value fails."""
        from aidb_mcp.tools.validation import validate_required_param

        is_valid, error_msg = validate_required_param(None, "test_param")

        assert is_valid is False
        assert "test_param" in error_msg
        assert "missing" in error_msg.lower()

    def test_validate_required_param_empty_string(self) -> None:
        """Test that empty string fails."""
        from aidb_mcp.tools.validation import validate_required_param

        is_valid, error_msg = validate_required_param("", "test_param")

        assert is_valid is False
        assert "empty" in error_msg.lower()


class TestValidateSessionActive:
    """Tests for validate_session_active function."""

    def test_validate_session_active_valid(self) -> None:
        """Test that active session passes."""
        from aidb_mcp.tools.validation import validate_session_active

        session = MagicMock()
        session.started = True
        session.terminated = False

        is_valid, error_msg = validate_session_active(session)

        assert is_valid is True
        assert error_msg is None

    def test_validate_session_active_none(self) -> None:
        """Test that None session fails."""
        from aidb_mcp.tools.validation import validate_session_active

        is_valid, error_msg = validate_session_active(None)

        assert is_valid is False
        assert "No active" in error_msg

    def test_validate_session_active_not_started(self) -> None:
        """Test that not-started session fails."""
        from aidb_mcp.tools.validation import validate_session_active

        session = MagicMock()
        session.started = False

        is_valid, error_msg = validate_session_active(session)

        assert is_valid is False
        assert "not started" in error_msg

    def test_validate_session_active_terminated(self) -> None:
        """Test that terminated session fails."""
        from aidb_mcp.tools.validation import validate_session_active

        session = MagicMock()
        session.started = True
        session.terminated = True

        is_valid, error_msg = validate_session_active(session)

        assert is_valid is False
        assert "terminated" in error_msg


class TestEarlyValidateHandlerArgs:
    """Tests for early_validate_handler_args function."""

    def test_early_validate_handler_args_valid(self) -> None:
        """Test that valid args pass early validation."""
        from aidb_mcp.tools.validation import early_validate_handler_args

        args = {"action": "get", "session_id": "test-123"}

        result = early_validate_handler_args("aidb_variable", args)

        assert result is None  # No error

    def test_early_validate_handler_args_missing_required(self) -> None:
        """Test that missing required param returns error."""
        from aidb_mcp.tools.validation import early_validate_handler_args

        args = {"session_id": "test-123"}

        result = early_validate_handler_args("aidb_breakpoint", args)

        assert result is not None
        assert "error" in str(result).lower() or "isError" in str(result)

    def test_early_validate_handler_args_invalid_session_id(self) -> None:
        """Test that invalid session_id returns error."""
        from aidb_mcp.tools.validation import early_validate_handler_args

        args = {"action": "get", "session_id": "invalid@session"}

        result = early_validate_handler_args("aidb_variable", args)

        assert result is not None

    def test_early_validate_handler_args_invalid_frame_id(self) -> None:
        """Test that invalid frame_id returns error."""
        from aidb_mcp.tools.validation import early_validate_handler_args

        args = {"action": "get", "frame": -1}

        result = early_validate_handler_args("aidb_variable", args)

        assert result is not None

    def test_early_validate_handler_args_no_rules(self) -> None:
        """Test that unknown handler passes validation."""
        from aidb_mcp.tools.validation import early_validate_handler_args

        args = {"some": "arg"}

        result = early_validate_handler_args("unknown_handler", args)

        assert result is None  # No rules = pass
