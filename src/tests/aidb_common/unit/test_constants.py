"""Tests for shared constants module."""

import pytest

from aidb_common.constants import SUPPORTED_LANGUAGES, Language


class TestLanguageEnum:
    """Test Language enum."""

    def test_language_enum_values(self) -> None:
        """Test that Language enum has expected values."""
        assert Language.PYTHON.value == "python"
        assert Language.JAVASCRIPT.value == "javascript"
        assert Language.JAVA.value == "java"

    def test_language_enum_is_string(self) -> None:
        """Test that Language enum inherits from str."""
        assert isinstance(Language.PYTHON, str)
        assert isinstance(Language.JAVASCRIPT, str)
        assert isinstance(Language.JAVA, str)

    def test_language_enum_string_operations(self) -> None:
        """Test that Language enum supports string operations."""
        assert Language.PYTHON == "python"
        assert Language.PYTHON.upper() == "PYTHON"
        assert Language.PYTHON.value == "python"

    def test_all_languages_present(self) -> None:
        """Test that all expected languages are in the enum."""
        languages = [lang.value for lang in Language]
        assert "python" in languages
        assert "javascript" in languages
        assert "java" in languages


class TestLanguageFileExtension:
    """Test Language.file_extension property."""

    def test_python_extension(self) -> None:
        """Test Python file extension."""
        assert Language.PYTHON.file_extension == ".py"

    def test_javascript_extension(self) -> None:
        """Test JavaScript file extension."""
        assert Language.JAVASCRIPT.file_extension == ".js"

    def test_java_extension(self) -> None:
        """Test Java file extension."""
        assert Language.JAVA.file_extension == ".java"

    def test_all_extensions_start_with_dot(self) -> None:
        """Test that all extensions start with a dot."""
        for lang in Language:
            assert lang.file_extension.startswith(".")


class TestLanguageCommentPrefix:
    """Test Language.comment_prefix property."""

    def test_python_comment_prefix(self) -> None:
        """Test Python comment prefix."""
        assert Language.PYTHON.comment_prefix == "#"

    def test_javascript_comment_prefix(self) -> None:
        """Test JavaScript comment prefix."""
        assert Language.JAVASCRIPT.comment_prefix == "//"

    def test_java_comment_prefix(self) -> None:
        """Test Java comment prefix."""
        assert Language.JAVA.comment_prefix == "//"

    def test_all_comment_prefixes_non_empty(self) -> None:
        """Test that all comment prefixes are non-empty."""
        for lang in Language:
            assert len(lang.comment_prefix) > 0


class TestSupportedLanguages:
    """Test SUPPORTED_LANGUAGES constant."""

    def test_supported_languages_type(self) -> None:
        """Test that SUPPORTED_LANGUAGES is a list."""
        assert isinstance(SUPPORTED_LANGUAGES, list)

    def test_supported_languages_contents(self) -> None:
        """Test that SUPPORTED_LANGUAGES contains expected values."""
        assert "python" in SUPPORTED_LANGUAGES
        assert "javascript" in SUPPORTED_LANGUAGES
        assert "java" in SUPPORTED_LANGUAGES

    def test_supported_languages_matches_enum(self) -> None:
        """Test that SUPPORTED_LANGUAGES matches Language enum values."""
        enum_values = [lang.value for lang in Language]
        assert set(SUPPORTED_LANGUAGES) == set(enum_values)

    def test_supported_languages_all_strings(self) -> None:
        """Test that all items in SUPPORTED_LANGUAGES are strings."""
        assert all(isinstance(lang, str) for lang in SUPPORTED_LANGUAGES)


class TestLanguageEnumEdgeCases:
    """Test Language enum edge cases."""

    def test_language_enum_iteration(self) -> None:
        """Test that Language enum can be iterated."""
        languages = list(Language)
        assert len(languages) == 3
        assert Language.PYTHON in languages
        assert Language.JAVASCRIPT in languages
        assert Language.JAVA in languages

    def test_language_enum_membership(self) -> None:
        """Test membership testing with Language enum."""
        assert Language.PYTHON == "python"
        assert Language.JAVASCRIPT == "javascript"
        assert Language.JAVA == "java"

    def test_language_enum_unique_values(self) -> None:
        """Test that all Language enum values are unique."""
        values = [lang.value for lang in Language]
        assert len(values) == len(set(values))

    def test_language_enum_comparison(self) -> None:
        """Test Language enum comparison operations."""
        assert Language.PYTHON != Language.JAVASCRIPT
        assert Language.PYTHON == Language.PYTHON
        assert Language.PYTHON.value == "python"
