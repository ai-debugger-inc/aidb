"""Registry for language-specific debugging starters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from .java import JavaStarter
from .javascript import JavaScriptStarter
from .python import PythonStarter

if TYPE_CHECKING:
    from .base import BaseStarter

logger = get_logger(__name__)


class StarterRegistry:
    """Registry for managing language-specific starter implementations.

    This class bridges the MCP layer with the aidb core adapter registry, providing
    access to adapter configurations and language-specific starters without requiring
    session initialization.
    """

    _starters: dict[str, type[BaseStarter]] = {}
    _adapter_configs: dict[str, Any] = {}

    # Register built-in starters at module load
    @classmethod
    def _register_builtin_starters(cls) -> None:
        """Register all built-in language starters."""
        logger.debug("Registering built-in language starters")
        cls.register(Language.PYTHON.value, PythonStarter)
        cls.register(Language.JAVASCRIPT.value, JavaScriptStarter)
        cls.register(Language.JAVA.value, JavaStarter)
        logger.info(
            "Built-in starters registered",
            extra={
                "starter_count": len(cls._starters),
                "languages": list(cls._starters.keys()),
            },
        )

    @classmethod
    def register(cls, language: str, starter_class: type[BaseStarter]) -> None:
        """Register a starter for a language.

        Parameters
        ----------
        language : str
            The programming language identifier
        starter_class : Type[BaseStarter]
            The starter class implementation for this language
        """
        normalized = language.lower()
        cls._starters[normalized] = starter_class
        logger.debug(
            "Registered starter",
            extra={"language": normalized, "starter_class": starter_class.__name__},
        )

    @classmethod
    def get_starter(cls, language: str) -> BaseStarter | None:
        """Get a starter instance for the specified language.

        Parameters
        ----------
        language : str
            The programming language identifier

        Returns
        -------
        Optional[BaseStarter]
            Starter instance if available, None otherwise
        """
        language = language.lower()
        logger.debug("Getting starter for language %s", extra={"language": language})

        # Check if we have a registered starter
        starter_class = cls._starters.get(language)
        if not starter_class:
            logger.warning(
                "No starter registered for language",
                extra={"language": language, "available": list(cls._starters.keys())},
            )
            return None

        # Get adapter config if available
        adapter_config = cls.get_adapter_config(language)

        # Create and return starter instance
        instance = starter_class(language, adapter_config)
        logger.info(
            "Created starter instance",
            extra={
                "language": language,
                "starter_class": starter_class.__name__,
                "has_config": adapter_config is not None,
            },
        )
        return instance

    @classmethod
    def get_adapter_config(cls, language: str) -> Any | None:
        """Get adapter configuration for a language without creating a session.

        This method attempts to get the adapter configuration from the aidb
        core adapter registry without initializing an adapter instance.

        Parameters
        ----------
        language : str
            The programming language identifier

        Returns
        -------
        Optional[Any]
            Adapter configuration if available, None otherwise
        """
        language = language.lower()

        # Check cache first
        if language in cls._adapter_configs:
            logger.debug("Using cached adapter config %s", extra={"language": language})
            return cls._adapter_configs[language]

        try:
            # Import here to avoid circular dependencies
            from aidb_common.discovery.adapters import get_adapter_class

            # Get the adapter class without creating an instance
            adapter_class = get_adapter_class(language)
            if not adapter_class:
                logger.debug("No adapter class found %s", extra={"language": language})
                return None

            # Get the config from the adapter class
            # Most adapters have a config class attribute or default config
            if hasattr(adapter_class, "config"):
                config = adapter_class.config
            elif hasattr(adapter_class, "get_default_config"):
                config = adapter_class.get_default_config()
            else:
                # Try to instantiate the config class directly
                # This assumes naming convention: PythonAdapter -> PythonAdapterConfig
                config_module = adapter_class.__module__.replace(".adapter", ".config")
                config_class_name = f"{language.capitalize()}AdapterConfig"

                try:
                    import importlib

                    module = importlib.import_module(config_module)
                    config_class = getattr(module, config_class_name, None)
                    config = config_class() if config_class else None
                except (ImportError, AttributeError):
                    config = None

            # Cache the config
            if config:
                cls._adapter_configs[language] = config
                logger.info(
                    "Adapter config loaded and cached",
                    extra={"language": language, "config_type": type(config).__name__},
                )
            else:
                logger.warning(
                    "Could not load adapter config",
                    extra={"language": language},
                )

            return config

        except ImportError:
            # aidb core not available or adapter registry not found
            logger.debug(
                "AdapterRegistry not available %s",
                extra={"language": language},
            )
            return None
        except Exception as e:
            # Any other error getting adapter config
            logger.exception(
                "Failed to get adapter config",
                extra={"language": language, "error": str(e)},
            )
            return None

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """Get list of languages with registered starters.

        Returns
        -------
        list[str]
            List of supported language identifiers
        """
        languages = list(cls._starters.keys())
        logger.debug(
            "Retrieved supported languages",
            extra={"language_count": len(languages), "languages": languages},
        )
        return languages

    @classmethod
    def discover_adapter_capabilities(cls, language: str) -> dict[str, Any]:
        """Discover capabilities for a language adapter.

        This provides static capabilities from the adapter configuration
        without requiring adapter initialization.

        Parameters
        ----------
        language : str
            The programming language identifier

        Returns
        -------
        Dict[str, Any]
            Dictionary of discovered capabilities:
            - supported_frameworks: List of framework names
            - file_extensions: List of file extensions
            - default_port: Default debugging port
            - features: Other adapter-specific features
        """
        capabilities: dict[str, Any] = {
            "supported_frameworks": [],
            "file_extensions": [],
            "default_port": None,
            "features": {},
        }

        logger.debug(
            "Discovering adapter capabilities %s",
            extra={"language": language},
        )

        # Get adapter config
        config = cls.get_adapter_config(language)
        if not config:
            logger.debug(
                "No config available for capability discovery",
                extra={"language": language},
            )
            return capabilities

        # Extract capabilities from config
        if hasattr(config, "supported_frameworks"):
            capabilities["supported_frameworks"] = config.supported_frameworks

        if hasattr(config, "file_extensions"):
            capabilities["file_extensions"] = config.file_extensions

        if hasattr(config, "adapter_port"):
            capabilities["default_port"] = config.adapter_port
        elif hasattr(config, "default_dap_port"):
            capabilities["default_port"] = config.default_dap_port

        # Add language-specific features
        features_dict = capabilities["features"]

        # Python-specific features
        if language == Language.PYTHON and hasattr(config, "justMyCode"):
            features_dict["justMyCode"] = config.justMyCode
            features_dict["django"] = getattr(config, "django", False)
            features_dict["flask"] = getattr(config, "flask", False)

        # JavaScript-specific features
        if language == Language.JAVASCRIPT and hasattr(config, "enable_source_maps"):
            features_dict["source_maps"] = config.enable_source_maps

        logger.info(
            "Discovered adapter capabilities",
            extra={
                "language": language,
                "framework_count": len(capabilities["supported_frameworks"]),
                "extension_count": len(capabilities["file_extensions"]),
                "default_port": capabilities["default_port"],
                "feature_count": len(capabilities["features"]),
            },
        )

        return capabilities

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the adapter configuration cache.

        Useful for testing or when adapter configurations may have changed.
        """
        cache_size = len(cls._adapter_configs)
        cls._adapter_configs.clear()
        logger.info(
            "Cleared adapter config cache %s",
            extra={"cleared_count": cache_size},
        )


# Register built-in starters when module loads
StarterRegistry._register_builtin_starters()
