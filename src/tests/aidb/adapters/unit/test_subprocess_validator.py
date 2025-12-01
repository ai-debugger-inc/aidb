"""Unit tests for SubprocessValidator utilities.

Tests subprocess execution, error extraction, binary detection, and file reading
utilities.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb.adapters.base.subprocess_validator import (
    SubprocessValidationResult,
    SubprocessValidator,
)

# =============================================================================
# TestSubprocessValidationResult
# =============================================================================


class TestSubprocessValidationResult:
    """Tests for SubprocessValidationResult class."""

    def test_init_success(self) -> None:
        """Test initialization for successful result."""
        result = SubprocessValidationResult(
            success=True,
            stdout="output",
            stderr="",
            returncode=0,
        )

        assert result.success is True
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.returncode == 0

    def test_init_failure(self) -> None:
        """Test initialization for failed result."""
        result = SubprocessValidationResult(
            success=False,
            stdout="",
            stderr="syntax error",
            returncode=1,
        )

        assert result.success is False
        assert result.stderr == "syntax error"
        assert result.returncode == 1


# =============================================================================
# TestSubprocessValidatorRunValidator
# =============================================================================


class TestSubprocessValidatorRunValidator:
    """Tests for run_validator static method."""

    def test_run_validator_success(self) -> None:
        """Test successful validation run."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = SubprocessValidator.run_validator(
                ["python", "-m", "py_compile", "test.py"],
            )

        assert result is not None
        assert result.success is True
        assert result.stdout == "success"
        assert result.returncode == 0

    def test_run_validator_failure(self) -> None:
        """Test failed validation run."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "syntax error at line 5"

        with patch("subprocess.run", return_value=mock_result):
            result = SubprocessValidator.run_validator(
                ["python", "-m", "py_compile", "bad.py"],
            )

        assert result is not None
        assert result.success is False
        assert result.returncode == 1

    def test_run_validator_not_found(self) -> None:
        """Test when validator command not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = SubprocessValidator.run_validator(
                ["nonexistent-validator", "test.py"],
            )

        assert result is None

    def test_run_validator_timeout(self) -> None:
        """Test timeout during validation."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 10),
        ):
            result = SubprocessValidator.run_validator(
                ["slow-validator", "test.py"],
                timeout=10,
                language="python",
            )

        assert result is not None
        assert result.success is False
        assert "timed out" in result.stderr
        assert result.returncode == -1

    def test_run_validator_generic_exception(self) -> None:
        """Test generic exception during validation."""
        with patch("subprocess.run", side_effect=OSError("IO error")):
            result = SubprocessValidator.run_validator(
                ["validator", "test.py"],
                language="python",
            )

        assert result is not None
        assert result.success is False
        assert "Error during python validation" in result.stderr
        assert result.returncode == -1


# =============================================================================
# TestSubprocessValidatorExtractErrorLines
# =============================================================================


class TestSubprocessValidatorExtractErrorLines:
    """Tests for extract_error_lines static method."""

    def test_extract_error_lines_matches_pattern(self) -> None:
        """Test extracting error line matching pattern."""
        output = "file.py:10: SyntaxError: invalid syntax\nother line"

        result = SubprocessValidator.extract_error_lines(
            output,
            ["SyntaxError", "TypeError"],
        )

        assert result == "file.py:10: SyntaxError: invalid syntax"

    def test_extract_error_lines_no_match(self) -> None:
        """Test when no pattern matches."""
        output = "success\nall tests passed"

        result = SubprocessValidator.extract_error_lines(
            output,
            ["Error", "Failed"],
        )

        assert result is None

    def test_extract_error_lines_empty_output(self) -> None:
        """Test with empty output."""
        result = SubprocessValidator.extract_error_lines(
            "",
            ["Error"],
        )

        assert result is None

    def test_extract_error_lines_none_output(self) -> None:
        """Test with None output."""
        result = SubprocessValidator.extract_error_lines(
            None,  # type: ignore[arg-type]
            ["Error"],
        )

        assert result is None

    def test_extract_error_lines_first_match_wins(self) -> None:
        """Test that first matching line is returned."""
        output = "line 1: TypeError\nline 2: SyntaxError"

        result = SubprocessValidator.extract_error_lines(
            output,
            ["TypeError", "SyntaxError"],
        )

        assert "TypeError" in result


# =============================================================================
# TestSubprocessValidatorFormatValidationError
# =============================================================================


class TestSubprocessValidatorFormatValidationError:
    """Tests for format_validation_error static method."""

    def test_format_success_result(self) -> None:
        """Test formatting successful result."""
        result = SubprocessValidationResult(
            success=True,
            stdout="",
            stderr="",
            returncode=0,
        )

        is_valid, error = SubprocessValidator.format_validation_error(
            result,
            "python",
            ["SyntaxError"],
        )

        assert is_valid is True
        assert error is None

    def test_format_failure_with_specific_error(self) -> None:
        """Test formatting failure with specific error."""
        result = SubprocessValidationResult(
            success=False,
            stdout="",
            stderr="file.py:10: SyntaxError: invalid syntax",
            returncode=1,
        )

        is_valid, error = SubprocessValidator.format_validation_error(
            result,
            "python",
            ["SyntaxError"],
        )

        assert is_valid is False
        assert "python syntax error" in error.lower()
        assert "SyntaxError" in error

    def test_format_failure_generic_error(self) -> None:
        """Test formatting failure without specific pattern match."""
        result = SubprocessValidationResult(
            success=False,
            stdout="",
            stderr="some generic error message",
            returncode=1,
        )

        is_valid, error = SubprocessValidator.format_validation_error(
            result,
            "python",
            ["SyntaxError"],
        )

        assert is_valid is False
        assert "python syntax error" in error.lower()
        assert "generic error" in error

    def test_format_failure_no_details(self) -> None:
        """Test formatting failure with no error details."""
        result = SubprocessValidationResult(
            success=False,
            stdout="",
            stderr="",
            returncode=1,
        )

        is_valid, error = SubprocessValidator.format_validation_error(
            result,
            "python",
            ["SyntaxError"],
        )

        assert is_valid is False
        assert "no details available" in error

    def test_format_uses_stdout_when_requested(self) -> None:
        """Test formatting uses stdout when use_stderr=False."""
        result = SubprocessValidationResult(
            success=False,
            stdout="error in stdout",
            stderr="",
            returncode=1,
        )

        is_valid, error = SubprocessValidator.format_validation_error(
            result,
            "java",
            ["error"],
            use_stderr=False,
        )

        assert is_valid is False
        assert "stdout" in error


# =============================================================================
# TestSubprocessValidatorIsBinaryExecutable
# =============================================================================


class TestSubprocessValidatorIsBinaryExecutable:
    """Tests for is_binary_executable static method."""

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Test non-existent file returns False."""
        result = SubprocessValidator.is_binary_executable(
            str(tmp_path / "nonexistent"),
        )

        assert result is False

    def test_directory_returns_false(self, tmp_path: Path) -> None:
        """Test directory returns False."""
        result = SubprocessValidator.is_binary_executable(str(tmp_path))

        assert result is False

    def test_text_file_returns_false(self, tmp_path: Path) -> None:
        """Test text file returns False."""
        text_file = tmp_path / "script.py"
        text_file.write_text("print('hello')")

        result = SubprocessValidator.is_binary_executable(str(text_file))

        assert result is False

    def test_elf_binary_returns_true(self, tmp_path: Path) -> None:
        """Test ELF binary returns True."""
        elf_file = tmp_path / "binary"
        elf_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        result = SubprocessValidator.is_binary_executable(str(elf_file))

        assert result is True

    def test_macho_binary_returns_true(self, tmp_path: Path) -> None:
        """Test Mach-O binary returns True."""
        macho_file = tmp_path / "binary"
        macho_file.write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 100)

        result = SubprocessValidator.is_binary_executable(str(macho_file))

        assert result is True

    def test_pe_binary_returns_true(self, tmp_path: Path) -> None:
        """Test PE binary (Windows) returns True."""
        pe_file = tmp_path / "binary.exe"
        pe_file.write_bytes(b"MZ" + b"\x00" * 100)

        result = SubprocessValidator.is_binary_executable(str(pe_file))

        assert result is True

    def test_shebang_script_returns_true(self, tmp_path: Path) -> None:
        """Test script with shebang returns True."""
        script_file = tmp_path / "script.sh"
        script_file.write_text("#!/bin/bash\necho hello")

        result = SubprocessValidator.is_binary_executable(str(script_file))

        assert result is True

    def test_short_file_returns_false(self, tmp_path: Path) -> None:
        """Test file shorter than 4 bytes returns False."""
        short_file = tmp_path / "short"
        short_file.write_bytes(b"AB")

        result = SubprocessValidator.is_binary_executable(str(short_file))

        assert result is False


# =============================================================================
# TestSubprocessValidatorSafeFileRead
# =============================================================================


class TestSubprocessValidatorSafeFileRead:
    """Tests for safe_file_read static method."""

    def test_read_valid_file(self, tmp_path: Path) -> None:
        """Test reading valid UTF-8 file."""
        file_path = tmp_path / "test.py"
        file_path.write_text("print('hello')")

        success, content, error = SubprocessValidator.safe_file_read(str(file_path))

        assert success is True
        assert content == "print('hello')"
        assert error is None

    def test_read_nonexistent_file(self, tmp_path: Path) -> None:
        """Test reading non-existent file."""
        success, content, error = SubprocessValidator.safe_file_read(
            str(tmp_path / "nonexistent.py"),
        )

        assert success is False
        assert content is None
        assert "Error reading file" in error

    def test_read_binary_file_fails(self, tmp_path: Path) -> None:
        """Test reading binary file fails with decode error."""
        binary_file = tmp_path / "binary"
        binary_file.write_bytes(b"\x80\x81\x82\x83")

        success, content, error = SubprocessValidator.safe_file_read(str(binary_file))

        assert success is False
        assert content is None
        assert "Unable to decode" in error

    def test_read_unicode_file(self, tmp_path: Path) -> None:
        """Test reading file with unicode content."""
        unicode_file = tmp_path / "unicode.py"
        unicode_file.write_text("# 日本語コメント\nprint('こんにちは')")

        success, content, error = SubprocessValidator.safe_file_read(str(unicode_file))

        assert success is True
        assert "日本語" in content
        assert error is None
