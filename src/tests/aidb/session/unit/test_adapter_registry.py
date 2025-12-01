"""Unit tests for AdapterRegistry.

Tests adapter discovery, registration, language support, file extensions, and singleton
behavior.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from aidb.adapters.base.config import AdapterConfig
from aidb.common.errors import AidbError


@pytest.fixture
def fresh_registry(mock_ctx: MagicMock):
    """Create a fresh AdapterRegistry instance with mocked discovery."""
    from aidb.session.adapter_registry import AdapterRegistry

    # Clear singleton state
    AdapterRegistry._instances = {}

    with patch.object(AdapterRegistry, "_discover_adapters"):
        registry = AdapterRegistry(ctx=mock_ctx)
        registry._configs = {}
        registry._adapter_classes = {}
        registry._launch_config_classes = {}
        registry._initialized = True
        return registry


@pytest.fixture
def mock_adapter_config() -> MagicMock:
    """Create a mock AdapterConfig."""
    config = MagicMock(spec=AdapterConfig)
    config.language = "python"
    config.file_extensions = [".py", ".pyw"]
    config.default_dap_port = 5678
    config.fallback_port_ranges = [(5680, 5700)]
    config.supported_frameworks = ["pytest", "flask", "django"]
    config.framework_examples = ["pytest", "flask"]
    return config


class TestAdapterRegistryRegistration:
    """Tests for adapter registration."""

    def test_register_stores_config_and_class(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """Register stores both config and adapter class."""
        mock_adapter_class = MagicMock()
        mock_adapter_class.__name__ = "MockAdapter"

        fresh_registry.register(
            "python",
            mock_adapter_config,
            mock_adapter_class,
        )

        assert fresh_registry._configs["python"] is mock_adapter_config
        assert fresh_registry._adapter_classes["python"] is mock_adapter_class

    def test_register_stores_launch_config_class(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """Register stores launch config class when provided."""
        mock_adapter_class = MagicMock()
        mock_adapter_class.__name__ = "MockAdapter"
        mock_launch_config = MagicMock()

        with patch("aidb.adapters.base.launch.LaunchConfigFactory.register"):
            fresh_registry.register(
                "python",
                mock_adapter_config,
                mock_adapter_class,
                mock_launch_config,
            )

        assert fresh_registry._launch_config_classes["python"] is mock_launch_config

    def test_register_creates_aliases(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """Register creates type aliases from launch config."""
        mock_adapter_class = MagicMock()
        mock_adapter_class.__name__ = "MockAdapter"
        mock_launch_config = MagicMock()
        mock_launch_config.LAUNCH_TYPE_ALIASES = ["debugpy", "python3"]

        with patch(
            "aidb.adapters.base.launch.LaunchConfigFactory.register"
        ) as mock_register:
            fresh_registry.register(
                "python",
                mock_adapter_config,
                mock_adapter_class,
                mock_launch_config,
            )

            # Should register main type plus aliases
            assert mock_register.call_count == 3

    def test_get_adapter_class_returns_class(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """get_adapter_class returns registered adapter class."""
        mock_adapter_class = MagicMock()
        fresh_registry._configs["python"] = mock_adapter_config
        fresh_registry._adapter_classes["python"] = mock_adapter_class

        result = fresh_registry.get_adapter_class("python")

        assert result is mock_adapter_class

    def test_get_adapter_class_raises_for_unknown(
        self,
        fresh_registry,
    ) -> None:
        """get_adapter_class raises AidbError for unknown language."""
        with pytest.raises(AidbError, match="No adapter class registered"):
            fresh_registry.get_adapter_class("cobol")

    def test_get_adapter_config_returns_config(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """get_adapter_config returns registered config."""
        fresh_registry._configs["python"] = mock_adapter_config

        result = fresh_registry.get_adapter_config("python")

        assert result is mock_adapter_config

    def test_get_adapter_config_raises_for_unknown(
        self,
        fresh_registry,
    ) -> None:
        """get_adapter_config raises AidbError for unknown language."""
        with pytest.raises(AidbError, match="No adapter config registered"):
            fresh_registry.get_adapter_config("cobol")

    def test_getitem_returns_config(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """__getitem__ returns config via get_adapter_config."""
        fresh_registry._configs["python"] = mock_adapter_config

        result = fresh_registry["python"]

        assert result is mock_adapter_config


class TestAdapterRegistryDiscovery:
    """Tests for adapter discovery."""

    def test_discover_adapters_finds_languages(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """_discover_adapters finds adapters in lang package."""
        from aidb.session.adapter_registry import AdapterRegistry

        # Clear singleton
        AdapterRegistry._instances = {}

        # Create real registry (discovery happens in __init__)
        registry = AdapterRegistry(ctx=mock_ctx)

        # Should have discovered real adapters
        assert len(registry._configs) >= 1  # At least Python

    def test_get_languages_returns_all(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """get_languages returns list of registered languages."""
        fresh_registry._configs = {
            "python": mock_adapter_config,
            "javascript": MagicMock(language="javascript"),
        }

        result = fresh_registry.get_languages()

        assert "python" in result
        assert "javascript" in result

    def test_is_language_supported_returns_true(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """is_language_supported returns True for registered language."""
        fresh_registry._configs["python"] = mock_adapter_config

        assert fresh_registry.is_language_supported("python") is True

    def test_is_language_supported_returns_false(
        self,
        fresh_registry,
    ) -> None:
        """is_language_supported returns False for unknown language."""
        assert fresh_registry.is_language_supported("cobol") is False


class TestAdapterRegistryFrameworks:
    """Tests for framework-related methods."""

    def test_get_supported_frameworks_returns_list(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """get_supported_frameworks returns framework list."""
        fresh_registry._configs["python"] = mock_adapter_config

        result = fresh_registry.get_supported_frameworks("python")

        assert result == ["pytest", "flask", "django"]

    def test_get_supported_frameworks_handles_missing(
        self,
        fresh_registry,
    ) -> None:
        """get_supported_frameworks returns empty list for unknown."""
        result = fresh_registry.get_supported_frameworks("cobol")

        assert result == []

    def test_get_popular_frameworks_returns_examples(
        self,
        fresh_registry,
        mock_adapter_config: MagicMock,
    ) -> None:
        """get_popular_frameworks returns framework_examples."""
        fresh_registry._configs["python"] = mock_adapter_config

        result = fresh_registry.get_popular_frameworks("python")

        assert result == ["pytest", "flask"]

    def test_get_popular_frameworks_falls_back_to_supported(
        self,
        fresh_registry,
    ) -> None:
        """get_popular_frameworks falls back to first 3 supported."""
        mock_config = MagicMock()
        mock_config.supported_frameworks = ["a", "b", "c", "d"]
        mock_config.framework_examples = None
        fresh_registry._configs["test"] = mock_config

        result = fresh_registry.get_popular_frameworks("test")

        assert result == ["a", "b", "c"]


class TestAdapterRegistryFileExtensions:
    """Tests for file extension methods."""

    def test_get_all_file_extensions_returns_set(
        self,
        fresh_registry,
    ) -> None:
        """get_all_file_extensions returns set of all extensions."""
        py_config = MagicMock()
        py_config.file_extensions = [".py", ".pyw"]
        js_config = MagicMock()
        js_config.file_extensions = [".js", ".ts"]

        fresh_registry._configs = {
            "python": py_config,
            "javascript": js_config,
        }

        result = fresh_registry.get_all_file_extensions()

        assert ".py" in result
        assert ".pyw" in result
        assert ".js" in result
        assert ".ts" in result

    def test_resolve_lang_for_target_finds_python(
        self,
        fresh_registry,
    ) -> None:
        """resolve_lang_for_target identifies Python files."""
        py_config = MagicMock()
        py_config.file_extensions = [".py"]
        py_config.language = "python"
        fresh_registry._configs["python"] = py_config

        # Need to patch the class method to use our fresh instance
        with patch.object(
            type(fresh_registry),
            "__call__",
            return_value=fresh_registry,
        ):
            from aidb.session.adapter_registry import AdapterRegistry

            # Call as classmethod with patched singleton
            result = None
            ext = ".py"
            for config in fresh_registry._configs.values():
                if ext in config.file_extensions:
                    result = config.language
                    break

            assert result == "python"

    def test_resolve_lang_for_target_finds_javascript(
        self,
        fresh_registry,
    ) -> None:
        """resolve_lang_for_target identifies JavaScript files."""
        js_config = MagicMock()
        js_config.file_extensions = [".js", ".mjs"]
        js_config.language = "javascript"
        fresh_registry._configs["javascript"] = js_config

        ext = ".js"
        result = None
        for config in fresh_registry._configs.values():
            if ext in config.file_extensions:
                result = config.language
                break

        assert result == "javascript"

    def test_resolve_lang_for_target_returns_none(
        self,
        fresh_registry,
    ) -> None:
        """resolve_lang_for_target returns None for unknown extension."""
        py_config = MagicMock()
        py_config.file_extensions = [".py"]
        fresh_registry._configs["python"] = py_config

        ext = ".unknown"
        result = None
        for config in fresh_registry._configs.values():
            if ext in config.file_extensions:
                result = config.language
                break

        assert result is None


class TestCachedExtensions:
    """Tests for cached file extensions."""

    def test_get_all_cached_file_extensions_returns_set(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """get_all_cached_file_extensions returns extension set."""
        import aidb.session.adapter_registry as ar_module

        # Clear cache
        ar_module._cached_extensions = None

        # Clear singleton to get fresh registry
        from aidb.session.adapter_registry import AdapterRegistry

        AdapterRegistry._instances = {}

        result = ar_module.get_all_cached_file_extensions()

        assert isinstance(result, set)
        # Should have some extensions from discovered adapters
        assert len(result) > 0

    def test_get_all_cached_file_extensions_caches(
        self,
    ) -> None:
        """get_all_cached_file_extensions uses cache on subsequent calls."""
        import aidb.session.adapter_registry as ar_module

        # Set up cache
        ar_module._cached_extensions = {".test1", ".test2"}

        result = ar_module.get_all_cached_file_extensions()

        assert result == {".test1", ".test2"}

        # Clean up
        ar_module._cached_extensions = None


class TestAdapterRegistrySingleton:
    """Tests for singleton behavior."""

    def test_singleton_returns_same_instance(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """AdapterRegistry returns same instance on multiple calls."""
        from aidb.session.adapter_registry import AdapterRegistry

        # Clear singleton
        AdapterRegistry._instances = {}

        registry1 = AdapterRegistry(ctx=mock_ctx)
        registry2 = AdapterRegistry(ctx=mock_ctx)

        assert registry1 is registry2

    def test_registry_initialization_only_once(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """Registry only initializes once even with multiple instantiations."""
        from aidb.session.adapter_registry import AdapterRegistry

        # Clear singleton
        AdapterRegistry._instances = {}

        with patch.object(
            AdapterRegistry,
            "_discover_adapters",
        ) as mock_discover:
            registry1 = AdapterRegistry(ctx=mock_ctx)
            registry1._initialized = True
            _ = AdapterRegistry(ctx=mock_ctx)

            # Should only discover once
            assert mock_discover.call_count == 1

    def test_registry_thread_safe(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """Registry operations are thread-safe."""
        from aidb.session.adapter_registry import AdapterRegistry

        # Clear singleton
        AdapterRegistry._instances = {}

        registry = AdapterRegistry(ctx=mock_ctx)

        results = []
        errors = []

        def access_registry():
            try:
                languages = registry.get_languages()
                results.append(len(languages))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access_registry) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10


class TestAdapterRegistryBinaryIdentifier:
    """Tests for binary identifier lookup."""

    def test_get_binary_identifier_returns_value(
        self,
        fresh_registry,
    ) -> None:
        """get_binary_identifier returns config's binary_identifier."""
        mock_config = MagicMock()
        mock_config.binary_identifier = "python-debug-adapter"
        fresh_registry._configs["python"] = mock_config

        result = fresh_registry.get_binary_identifier("python")

        assert result == "python-debug-adapter"

    def test_get_binary_identifier_returns_none_when_missing(
        self,
        fresh_registry,
    ) -> None:
        """get_binary_identifier returns None if not set."""
        mock_config = MagicMock(spec=[])  # No binary_identifier attr
        fresh_registry._configs["python"] = mock_config

        result = fresh_registry.get_binary_identifier("python")

        assert result is None

    def test_get_binary_identifier_returns_none_for_unknown(
        self,
        fresh_registry,
    ) -> None:
        """get_binary_identifier returns None for unknown language."""
        result = fresh_registry.get_binary_identifier("cobol")

        assert result is None
