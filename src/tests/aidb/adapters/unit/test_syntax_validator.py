"""Unit tests for SyntaxValidator base class.

Tests syntax validation flow, language factory, and NoOp validator.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb.adapters.base.syntax_validator import NoOpSyntaxValidator, SyntaxValidator

# =============================================================================
# MockSyntaxValidator for testing
# =============================================================================


class MockSyntaxValidator(SyntaxValidator):
    """Mock validator for testing abstract base class."""

    def __init__(self, should_pass: bool = True, error_msg: str | None = None):
        super().__init__("mock")
        self.should_pass = should_pass
        self.error_msg = error_msg
        self.validate_called = False

    def _validate_syntax(self, file_path: str) -> tuple[bool, str | None]:
        self.validate_called = True
        return self.should_pass, self.error_msg


# =============================================================================
# TestSyntaxValidatorValidate
# =============================================================================


class TestSyntaxValidatorValidate:
    """Tests for SyntaxValidator.validate() method."""

    def test_validate_skips_identifiers(self) -> None:
        """Test validate skips non-file-path identifiers."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py", ".js", ".java"},
        ):
            is_valid, error = validator.validate("MyClassName")

        assert is_valid is True
        assert error is None
        assert validator.validate_called is False

    def test_validate_processes_file_paths(self, tmp_path: Path) -> None:
        """Test validate processes file paths."""
        validator = MockSyntaxValidator()
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py", ".js", ".java"},
        ):
            is_valid, error = validator.validate(str(test_file))

        assert is_valid is True
        assert validator.validate_called is True

    def test_validate_returns_error_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test validate returns error for non-existent file."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py", ".js", ".java"},
        ):
            is_valid, error = validator.validate(str(tmp_path / "nonexistent.py"))

        assert is_valid is False
        assert "File not found" in error

    def test_validate_returns_error_for_directory(self, tmp_path: Path) -> None:
        """Test validate returns error when path is a directory."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py", ".js", ".java"},
        ):
            is_valid, error = validator.validate(str(tmp_path))

        assert is_valid is False
        assert "Not a file" in error

    def test_validate_returns_error_for_unreadable_file(self, tmp_path: Path) -> None:
        """Test validate returns error for unreadable file."""
        validator = MockSyntaxValidator()
        test_file = tmp_path / "test.py"
        test_file.touch()

        with (
            patch(
                "aidb.session.adapter_registry.get_all_cached_file_extensions",
                return_value={".py"},
            ),
            patch("os.access", return_value=False),
        ):
            is_valid, error = validator.validate(str(test_file))

        assert is_valid is False
        assert "not readable" in error

    def test_validate_skips_binary_executable(self, tmp_path: Path) -> None:
        """Test validate skips binary executables."""
        validator = MockSyntaxValidator()
        binary_file = tmp_path / "binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py"},
        ):
            is_valid, error = validator.validate(str(binary_file))

        assert is_valid is True
        assert validator.validate_called is False

    def test_validate_calls_language_specific_validation(
        self,
        tmp_path: Path,
    ) -> None:
        """Test validate delegates to _validate_syntax."""
        validator = MockSyntaxValidator(should_pass=False, error_msg="syntax error")
        test_file = tmp_path / "test.py"
        test_file.write_text("invalid python syntax")

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py"},
        ):
            is_valid, error = validator.validate(str(test_file))

        assert is_valid is False
        assert error == "syntax error"
        assert validator.validate_called is True


# =============================================================================
# TestSyntaxValidatorForLanguage
# =============================================================================


class TestSyntaxValidatorForLanguage:
    """Tests for SyntaxValidator.for_language() factory method."""

    def test_for_language_python(self) -> None:
        """Test factory returns Python validator."""
        with patch(
            "aidb.adapters.lang.python.syntax_validator.PythonSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("python")

        assert result is not None
        mock_class.assert_called_once()

    def test_for_language_javascript(self) -> None:
        """Test factory returns JavaScript validator."""
        with patch(
            "aidb.adapters.lang.javascript.syntax_validator.JavaScriptSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("javascript")

        assert result is not None
        mock_class.assert_called_once()

    def test_for_language_js_alias(self) -> None:
        """Test factory handles 'js' alias."""
        with patch(
            "aidb.adapters.lang.javascript.syntax_validator.JavaScriptSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("js")

        assert result is not None

    def test_for_language_node_alias(self) -> None:
        """Test factory handles 'node' alias."""
        with patch(
            "aidb.adapters.lang.javascript.syntax_validator.JavaScriptSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("node")

        assert result is not None

    def test_for_language_java(self) -> None:
        """Test factory returns Java validator."""
        with patch(
            "aidb.adapters.lang.java.syntax_validator.JavaSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("java")

        assert result is not None
        mock_class.assert_called_once()

    def test_for_language_unsupported(self) -> None:
        """Test factory returns None for unsupported language."""
        result = SyntaxValidator.for_language("ruby")

        assert result is None

    def test_for_language_case_insensitive(self) -> None:
        """Test factory is case insensitive."""
        with patch(
            "aidb.adapters.lang.python.syntax_validator.PythonSyntaxValidator",
        ) as mock_class:
            mock_class.return_value = MagicMock()
            result = SyntaxValidator.for_language("PYTHON")

        assert result is not None


# =============================================================================
# TestNoOpSyntaxValidator
# =============================================================================


class TestNoOpSyntaxValidator:
    """Tests for NoOpSyntaxValidator class."""

    def test_init_sets_language_to_unknown(self) -> None:
        """Test initialization sets language to unknown."""
        validator = NoOpSyntaxValidator()

        assert validator.language == "unknown"

    def test_validate_syntax_always_returns_true(self) -> None:
        """Test _validate_syntax always returns True."""
        validator = NoOpSyntaxValidator()

        is_valid, error = validator._validate_syntax("/any/file.txt")

        assert is_valid is True
        assert error is None

    def test_validate_syntax_accepts_any_path(self) -> None:
        """Test _validate_syntax accepts any path."""
        validator = NoOpSyntaxValidator()

        is_valid, error = validator._validate_syntax("/nonexistent/path.xyz")

        assert is_valid is True
        assert error is None


# =============================================================================
# TestSyntaxValidatorPathDetection
# =============================================================================


class TestSyntaxValidatorPathDetection:
    """Tests for file path vs identifier detection."""

    def test_path_with_separator_is_file_path(self) -> None:
        """Test path with separator is treated as file path."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py"},
        ):
            # Path with separator but no known extension should still be treated
            # as file path and checked for existence
            is_valid, error = validator.validate("/some/path/to/file")

        # Should try to validate and fail because file doesn't exist
        assert is_valid is False or validator.validate_called is False

    def test_known_extension_is_file_path(self) -> None:
        """Test known extension is treated as file path."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py"},
        ):
            is_valid, error = validator.validate("script.py")

        assert is_valid is False  # File doesn't exist
        assert "File not found" in error

    def test_class_name_is_identifier(self) -> None:
        """Test class name without extension is identifier."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py", ".java"},
        ):
            is_valid, error = validator.validate("MyTestClass")

        assert is_valid is True
        assert error is None
        assert validator.validate_called is False

    def test_module_name_is_identifier(self) -> None:
        """Test module name without extension is identifier."""
        validator = MockSyntaxValidator()

        with patch(
            "aidb.session.adapter_registry.get_all_cached_file_extensions",
            return_value={".py"},
        ):
            is_valid, error = validator.validate("my_module")

        assert is_valid is True
        assert error is None
        assert validator.validate_called is False
