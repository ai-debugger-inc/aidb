"""Tests for aidb_common.discovery.adapters module."""

from unittest.mock import Mock, patch

from aidb_common.discovery.adapters import (
    get_adapter_capabilities,
    get_adapter_class,
    get_adapter_config,
    get_adapter_for_validation,
    get_default_language,
    get_file_extensions_for_language,
    get_hit_condition_examples,
    get_language_description,
    get_language_enum,
    get_language_from_file,
    get_popular_frameworks,
    get_supported_frameworks,
    get_supported_hit_conditions,
    get_supported_languages,
    is_language_supported,
    supports_hit_condition,
)


class TestGetSupportedLanguages:
    """Tests for get_supported_languages function."""

    def test_returns_languages_from_registry(self, mock_adapter_registry):
        """Test that languages are returned from registry."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            languages = get_supported_languages()
            assert set(languages) == {"python", "javascript"}

    def test_returns_empty_list_when_no_configs(self):
        """Test that empty list is returned when registry has no _configs."""
        mock_registry = Mock()
        mock_registry._configs = None
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_registry,
        ):
            languages = get_supported_languages()
            assert languages == []

    def test_returns_empty_list_on_import_error(self):
        """Test that empty list is returned on ImportError."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=ImportError,
        ):
            languages = get_supported_languages()
            assert languages == []

    def test_returns_empty_list_on_exception(self):
        """Test that empty list is returned on general exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            languages = get_supported_languages()
            assert languages == []

    def test_normalizes_language_names_to_lowercase(self):
        """Test that language names are normalized to lowercase."""
        mock_registry = Mock()
        mock_registry._configs = {"Python": Mock(), "JavaScript": Mock()}
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_registry,
        ):
            languages = get_supported_languages()
            assert all(lang.islower() for lang in languages)


class TestGetLanguageDescription:
    """Tests for get_language_description function."""

    def test_returns_description_with_languages(self, mock_adapter_registry):
        """Test description with available languages."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            desc = get_language_description()
            assert "python" in desc
            assert "javascript" in desc
            assert "Programming language" in desc

    def test_returns_generic_description_when_no_languages(self):
        """Test generic description when no languages available."""
        with patch(
            "aidb_common.discovery.adapters.get_supported_languages",
            return_value=[],
        ):
            desc = get_language_description()
            assert desc == "Programming language"


class TestGetLanguageEnum:
    """Tests for get_language_enum function."""

    def test_returns_language_list_when_available(self, mock_adapter_registry):
        """Test that language list is returned when available."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            enum = get_language_enum()
            assert enum is not None
            assert set(enum) == {"python", "javascript"}

    def test_returns_none_when_no_languages(self):
        """Test that None is returned when no languages available."""
        with patch(
            "aidb_common.discovery.adapters.get_supported_languages",
            return_value=[],
        ):
            enum = get_language_enum()
            assert enum is None


class TestIsLanguageSupported:
    """Tests for is_language_supported function."""

    def test_returns_true_for_supported_language(self, mock_adapter_registry):
        """Test that True is returned for supported languages."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            assert is_language_supported("python") is True
            assert is_language_supported("javascript") is True

    def test_returns_false_for_unsupported_language(self, mock_adapter_registry):
        """Test that False is returned for unsupported languages."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            assert is_language_supported("ruby") is False
            assert is_language_supported("go") is False

    def test_normalizes_language_name_to_lowercase(self, mock_adapter_registry):
        """Test that language name is normalized to lowercase."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            assert is_language_supported("Python") is True
            assert is_language_supported("JAVASCRIPT") is True


class TestGetLanguageFromFile:
    """Tests for get_language_from_file function."""

    def test_resolves_language_from_file_extension(self):
        """Test language resolution from file extension."""
        mock_registry_class = Mock()
        mock_registry_class.resolve_lang_for_target = Mock(return_value="Python")
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            mock_registry_class,
        ):
            lang = get_language_from_file("test.py")
            assert lang == "python"

    def test_returns_none_for_unknown_extension(self):
        """Test that None is returned for unknown extensions."""
        mock_registry_class = Mock()
        mock_registry_class.resolve_lang_for_target = Mock(return_value=None)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            mock_registry_class,
        ):
            lang = get_language_from_file("test.unknown")
            assert lang is None

    def test_returns_none_on_import_error(self):
        """Test that None is returned on ImportError."""
        with patch.dict("sys.modules", {"aidb.session.adapter_registry": None}):
            lang = get_language_from_file("test.py")
            assert lang is None

    def test_returns_none_on_exception(self):
        """Test that None is returned on exception."""
        mock_registry_class = Mock()
        mock_registry_class.resolve_lang_for_target = Mock(
            side_effect=Exception("Test error"),
        )
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            mock_registry_class,
        ):
            lang = get_language_from_file("test.py")
            assert lang is None


class TestGetFileExtensionsForLanguage:
    """Tests for get_file_extensions_for_language function."""

    def test_returns_extensions_for_language(self, mock_adapter_registry):
        """Test that file extensions are returned for language."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(
                return_value=mock_adapter_registry._configs["python"],
            )
            extensions = get_file_extensions_for_language("python")
            assert extensions == [".py", ".pyw"]

    def test_returns_empty_list_for_missing_config(self, mock_adapter_registry):
        """Test that empty list is returned for missing config."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=None)
            extensions = get_file_extensions_for_language("unknown")
            assert extensions == []

    def test_returns_empty_list_on_exception(self, mock_adapter_registry):
        """Test that empty list is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            extensions = get_file_extensions_for_language("python")
            assert extensions == []


class TestGetDefaultLanguage:
    """Tests for get_default_language function."""

    def test_returns_python_as_default(self):
        """Test that python is returned as default language."""
        assert get_default_language() == "python"


class TestGetSupportedHitConditions:
    """Tests for get_supported_hit_conditions function."""

    def test_returns_hit_condition_modes(
        self,
        mock_adapter_registry,
        mock_hit_condition_modes,
    ):
        """Test that hit condition modes are returned."""
        config = mock_adapter_registry._configs["python"]
        config.supported_hit_conditions = mock_hit_condition_modes
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=config)
            modes = get_supported_hit_conditions("python")
            assert modes == {"EXACT", "MODULO", "GREATER_THAN", "GREATER_EQUAL"}

    def test_returns_empty_set_for_missing_config(self, mock_adapter_registry):
        """Test that empty set is returned for missing config."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=None)
            modes = get_supported_hit_conditions("unknown")
            assert modes == set()

    def test_returns_empty_set_on_exception(self):
        """Test that empty set is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            modes = get_supported_hit_conditions("python")
            assert modes == set()


class TestSupportsHitCondition:
    """Tests for supports_hit_condition function."""

    def test_returns_true_for_supported_expression(self, mock_adapter_registry):
        """Test that True is returned for supported expressions."""
        config = mock_adapter_registry._configs["python"]
        config.supports_hit_condition = Mock(return_value=True)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=config)
            assert supports_hit_condition("python", ">5") is True

    def test_returns_false_for_unsupported_expression(self, mock_adapter_registry):
        """Test that False is returned for unsupported expressions."""
        config = mock_adapter_registry._configs["python"]
        config.supports_hit_condition = Mock(return_value=False)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=config)
            assert supports_hit_condition("python", "invalid") is False

    def test_returns_false_for_missing_config(self, mock_adapter_registry):
        """Test that False is returned for missing config."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=None)
            assert supports_hit_condition("unknown", ">5") is False


class TestGetHitConditionExamples:
    """Tests for get_hit_condition_examples function."""

    def test_returns_examples_for_supported_modes(
        self,
        mock_adapter_registry,
        mock_hit_condition_modes,
    ):
        """Test that examples are returned for supported modes."""
        config = mock_adapter_registry._configs["python"]
        config.supported_hit_conditions = mock_hit_condition_modes

        with (
            patch(
                "aidb.session.adapter_registry.AdapterRegistry",
                return_value=mock_adapter_registry,
            ),
            patch("aidb.models.entities.breakpoint.HitConditionMode") as mock_mode_enum,
        ):
            mock_mode_enum.EXACT = mock_hit_condition_modes[0]
            mock_mode_enum.MODULO = mock_hit_condition_modes[1]
            mock_mode_enum.GREATER_THAN = mock_hit_condition_modes[2]
            mock_mode_enum.GREATER_EQUAL = mock_hit_condition_modes[3]

            mock_adapter_registry.get_adapter_config = Mock(return_value=config)
            examples = get_hit_condition_examples("python")

            assert any("5th hit" in ex for ex in examples)
            assert any("every 10th hit" in ex for ex in examples)

    def test_returns_default_example_for_no_support(self, mock_adapter_registry):
        """Test that default example is returned when no support."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=None)
            examples = get_hit_condition_examples("unknown")
            assert examples == ["'5' - exact hit count only"]


class TestGetAdapterCapabilities:
    """Tests for get_adapter_capabilities function."""

    def test_returns_full_capabilities(self, mock_adapter_registry):
        """Test that full capabilities are returned from config."""
        # The mock_adapter_registry fixture provides configs with capabilities
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            caps = get_adapter_capabilities("python")

            assert caps["supported"] is True
            assert caps["language"] == "python"
            # Verify capability fields are present
            assert "supports_conditional_breakpoints" in caps
            assert "supports_logpoints" in caps
            assert "file_extensions" in caps

    def test_returns_unsupported_for_missing_config(self, mock_adapter_registry):
        """Test that unsupported is returned when config is missing."""
        mock_adapter_registry.get_adapter_config = Mock(return_value=None)

        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            caps = get_adapter_capabilities("unknown")

            assert caps["supported"] is False
            assert caps["language"] == "unknown"

    def test_returns_unsupported_on_exception(self):
        """Test that unsupported is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            caps = get_adapter_capabilities("python")
            assert caps["supported"] is False


class TestGetAdapterForValidation:
    """Tests for get_adapter_for_validation function."""

    def test_returns_adapter_wrapper(self, mock_adapter_registry):
        """Test that adapter wrapper is returned."""
        config = mock_adapter_registry._configs["python"]
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=config)
            adapter = get_adapter_for_validation("python")

            assert adapter is not None
            assert hasattr(adapter, "config")
            assert hasattr(adapter, "validate_syntax")

    def test_returns_none_for_missing_config(self, mock_adapter_registry):
        """Test that None is returned for missing config."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            mock_adapter_registry.get_adapter_config = Mock(return_value=None)
            adapter = get_adapter_for_validation("unknown")
            assert adapter is None

    def test_returns_none_on_exception(self):
        """Test that None is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            adapter = get_adapter_for_validation("python")
            assert adapter is None


class TestGetSupportedFrameworks:
    """Tests for get_supported_frameworks function."""

    def test_returns_frameworks_for_language(self, mock_adapter_registry):
        """Test that frameworks are returned for language."""
        mock_adapter_registry.get_supported_frameworks = Mock(
            return_value=["pytest", "unittest", "django"],
        )
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            frameworks = get_supported_frameworks("python")
            assert frameworks == ["pytest", "unittest", "django"]

    def test_returns_empty_list_on_exception(self):
        """Test that empty list is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            frameworks = get_supported_frameworks("python")
            assert frameworks == []


class TestGetPopularFrameworks:
    """Tests for get_popular_frameworks function."""

    def test_returns_popular_frameworks_for_language(self, mock_adapter_registry):
        """Test that popular frameworks are returned for language."""
        mock_adapter_registry.get_popular_frameworks = Mock(
            return_value=["pytest", "django"],
        )
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            frameworks = get_popular_frameworks("python")
            assert frameworks == ["pytest", "django"]

    def test_returns_empty_list_on_exception(self):
        """Test that empty list is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            frameworks = get_popular_frameworks("python")
            assert frameworks == []


class TestGetAdapterConfig:
    """Tests for get_adapter_config function."""

    def test_returns_config_for_language(self, mock_adapter_registry):
        """Test that config is returned for language."""
        config = mock_adapter_registry._configs["python"]
        mock_adapter_registry.get_adapter_config = Mock(return_value=config)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            result = get_adapter_config("python")
            assert result is not None
            assert result.language == "python"

    def test_returns_none_for_unknown_language(self, mock_adapter_registry):
        """Test that None is returned for unknown language."""
        mock_adapter_registry.get_adapter_config = Mock(return_value=None)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            result = get_adapter_config("unknown")
            assert result is None

    def test_returns_none_on_exception(self):
        """Test that None is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            result = get_adapter_config("python")
            assert result is None


class TestGetAdapterClass:
    """Tests for get_adapter_class function."""

    def test_returns_adapter_class_for_language(self, mock_adapter_registry):
        """Test that adapter class is returned for language."""
        mock_class = Mock()
        mock_class.__name__ = "PythonAdapter"
        mock_adapter_registry.get_adapter_class = Mock(return_value=mock_class)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            result = get_adapter_class("python")
            assert result is not None
            assert result.__name__ == "PythonAdapter"

    def test_returns_none_for_unknown_language(self, mock_adapter_registry):
        """Test that None is returned for unknown language."""
        mock_adapter_registry.get_adapter_class = Mock(return_value=None)
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            return_value=mock_adapter_registry,
        ):
            result = get_adapter_class("unknown")
            assert result is None

    def test_returns_none_on_exception(self):
        """Test that None is returned on exception."""
        with patch(
            "aidb.session.adapter_registry.AdapterRegistry",
            side_effect=Exception("Test error"),
        ):
            result = get_adapter_class("python")
            assert result is None
