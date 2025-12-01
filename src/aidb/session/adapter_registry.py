"""Registry for language adapters and their configurations."""

import importlib
import inspect
import pkgutil
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.adapters.base.config import AdapterConfig
from aidb.common import acquire_lock
from aidb.common.errors import AidbError
from aidb.patterns import Obj
from aidb_common.patterns import Singleton

if TYPE_CHECKING:
    from aidb.adapters.base.adapter import DebugAdapter
    from aidb.interfaces import IContext


# Module-level cache for hot-path optimization
_cached_extensions: set[str] | None = None


def get_all_cached_file_extensions() -> set[str]:
    """Get all file extensions with module-level caching.

    This avoids Singleton + lock overhead on hot paths (e.g., during
    DAP request handling). Uses same pattern as get_global_validator().

    Returns
    -------
    set[str]
        All file extensions across all registered adapters
    """
    global _cached_extensions
    if _cached_extensions is None:
        _cached_extensions = AdapterRegistry().get_all_file_extensions()
    return _cached_extensions


class AdapterRegistry(Singleton["AdapterRegistry"], Obj):
    """Registry for all implemented DebugAdapter classes.

    This class is implemented as a singleton to ensure that there is only one registry
    of debug adapters in the application context.
    """

    _initialized: bool

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the adapter registry.

        Parameters
        ----------
        ctx : object, optional
            Application context
        """
        super().__init__(ctx)
        self.lock = threading.RLock()
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._configs: dict[str, AdapterConfig] = {}
        self._adapter_classes: dict[str, type[DebugAdapter]] = {}
        self._launch_config_classes: dict[str, type] = {}
        self._registration_logged = False  # Track if we've logged registration
        self._discover_adapters()
        self._initialized = True

    @acquire_lock
    def register(
        self,
        language: str,
        config: AdapterConfig,
        adapter_class: type["DebugAdapter"],
        launch_config_class: type | None = None,
    ) -> None:
        """Register an adapter configuration and class.

        Parameters
        ----------
        language : str
            The language identifier
        config : AdapterConfig
            The adapter configuration
        adapter_class : Type[DebugAdapter]
            The adapter class
        launch_config_class : Type, optional
            The launch configuration class for VS Code launch.json support
        """
        self._configs[language] = config
        self._adapter_classes[language] = adapter_class
        if launch_config_class:
            self._launch_config_classes[language] = launch_config_class
            # Register in LaunchConfigFactory to enable VS Code launch.json parsing
            from aidb.adapters.base.launch import LaunchConfigFactory

            # Register the main language type
            LaunchConfigFactory.register(language, launch_config_class)

            # Register any aliases defined by the launch config class
            # This allows each language to define its own VS Code type aliases
            if hasattr(launch_config_class, "LAUNCH_TYPE_ALIASES"):
                for alias in launch_config_class.LAUNCH_TYPE_ALIASES:
                    LaunchConfigFactory.register(alias, launch_config_class)
                    # Only log alias registration once per process
                    if not self._registration_logged:
                        self.ctx.info(
                            f"Registered launch config alias '{alias}' for {language}",
                        )
        # Only log adapter registration once per process
        if not self._registration_logged:
            self.ctx.info(
                f"Registered adapter for {language}: {adapter_class.__name__}",
            )
        self._registration_logged = True

    @acquire_lock
    def get_adapter_class(self, language: str) -> type["DebugAdapter"]:
        """Get the adapter class for a language.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        Type[DebugAdapter]
            The adapter class

        Raises
        ------
        AidbError
            If language is not registered or has no adapter class
        """
        if language not in self._adapter_classes:
            self.ctx.debug(
                f"Adapter class for {language} not found, attempting discovery",
            )
            self._discover_adapters()
        if language not in self._adapter_classes:
            msg = f"No adapter class registered for language: {language}"
            raise AidbError(msg)
        return self._adapter_classes[language]

    @acquire_lock
    def get_adapter_config(self, language: str) -> AdapterConfig:
        """Get the adapter configuration for a language.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        AdapterConfig
            The adapter configuration

        Raises
        ------
        AidbError
            If language is not registered
        """
        if language not in self._configs:
            self.ctx.debug(
                f"Adapter config for {language} not found, attempting discovery",
            )
            self._discover_adapters()
        if language not in self._configs:
            msg = f"No adapter config registered for language: {language}"
            raise AidbError(msg)
        return self._configs[language]

    @classmethod
    def resolve_lang_for_target(cls, target: str) -> str | None:
        """Determine the lang string for a target file based on its extension.

        Parameters
        ----------
        target : str
            The path to the target file.

        Returns
        -------
        Optional[str]
            The language string if found, else `None`.
        """
        ext = Path(target).suffix
        registry = cls()
        for config in registry._configs.values():
            if ext in config.file_extensions:
                return config.language
        return None

    @acquire_lock
    def get_supported_frameworks(self, language: str) -> list[str]:
        """Get list of frameworks supported by a language adapter.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        List[str]
            List of supported framework names
        """
        try:
            config = self.get_adapter_config(language)
            if hasattr(config, "supported_frameworks"):
                return config.supported_frameworks
        except Exception as e:
            msg = f"Failed to get supported frameworks for {language}: {e}"
            self.ctx.debug(msg)
        return []

    @acquire_lock
    def get_popular_frameworks(self, language: str) -> list[str]:
        """Get list of popular frameworks for a language.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        List[str]
            List of popular framework names (2-3 max)
        """
        try:
            config = self.get_adapter_config(language)
            if hasattr(config, "framework_examples") and config.framework_examples:
                return config.framework_examples
        except Exception as e:
            msg = f"Failed to get popular frameworks for {language}: {e}"
            self.ctx.debug(msg)
        # Fallback to first 3 supported frameworks
        return self.get_supported_frameworks(language)[:3]

    def _find_config_class(
        self,
        module,
        module_name: str,
    ) -> type[AdapterConfig] | None:
        """Find AdapterConfig subclass in a module.

        Parameters
        ----------
        module : Module
            The module to search
        module_name : str
            The module name for filtering

        Returns
        -------
        type[AdapterConfig] | None
            Found config class or None
        """
        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and obj.__module__ == module_name
                and issubclass(obj, AdapterConfig)
                and obj is not AdapterConfig
            ):
                return obj
        return None

    def _find_adapter_class(
        self,
        module,
        module_name: str,
    ) -> type["DebugAdapter"] | None:
        """Find DebugAdapter subclass in a module.

        Parameters
        ----------
        module : Module
            The module to search
        module_name : str
            The module name for filtering

        Returns
        -------
        type[DebugAdapter] | None
            Found adapter class or None
        """
        # Import DebugAdapter here to avoid circular import
        from aidb.adapters.base.adapter import DebugAdapter

        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and obj.__module__ == module_name
                and issubclass(obj, DebugAdapter)
                and obj is not DebugAdapter
            ):
                return obj
        return None

    def _process_adapter_package(self, name: str) -> None:
        """Process a single adapter package.

        Parameters
        ----------
        name : str
            Package name to process
        """
        try:
            # Import modules
            adapter_module_name = f"aidb.adapters.lang.{name}.{name}"
            config_module_name = f"aidb.adapters.lang.{name}.config"

            adapter_module = importlib.import_module(adapter_module_name)
            config_module = importlib.import_module(config_module_name)

            # Find classes
            config_class = self._find_config_class(config_module, config_module_name)
            adapter_class = self._find_adapter_class(
                adapter_module,
                adapter_module_name,
            )

            # Find launch config class (e.g., PythonLaunchConfig,
            # JavaScriptLaunchConfig)
            launch_config_class = None
            for item_name in dir(config_module):
                item = getattr(config_module, item_name)
                if (
                    inspect.isclass(item)
                    and item.__module__ == config_module_name
                    and "LaunchConfig" in item_name
                ):
                    launch_config_class = item
                    break

            # Register if both found
            if config_class and adapter_class:
                config = config_class()
                language = config.language
                self.register(language, config, adapter_class, launch_config_class)
            elif config_class:
                self.ctx.warning(
                    f"Found config class {config_class.__name__} in {name} "
                    "but no corresponding DebugAdapter subclass",
                )
            elif adapter_class:
                self.ctx.warning(
                    f"Found adapter class {adapter_class.__name__} in {name} "
                    "but no corresponding AdapterConfig subclass",
                )

        except (ImportError, AttributeError) as e:
            self.ctx.warning(f"Failed to load adapter for {name}: {e}")

    @acquire_lock
    def _discover_adapters(self) -> None:
        """Discover and register adapter configs and classes."""
        import aidb.adapters.lang as lang_pkg

        # Discover adapters in the lang subpackage (now they are in subpackages)
        for _, name, is_pkg in pkgutil.iter_modules(lang_pkg.__path__):
            # Now we want packages, not modules
            if not is_pkg or name == "__init__":
                continue

            self._process_adapter_package(name)

    @acquire_lock
    def __getitem__(self, language: str) -> AdapterConfig:
        """Get adapter configuration for a language.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        AdapterConfig
            The adapter configuration
        """
        return self.get_adapter_config(language)

    @acquire_lock
    def get_languages(self) -> list[str]:
        """Get list of all supported languages.

        Returns
        -------
        list[str]
            List of supported language identifiers
        """
        return list(self._configs.keys())

    @acquire_lock
    def get_all_file_extensions(self) -> set[str]:
        """Get all file extensions across all registered adapters.

        This method collects file extensions from all registered adapter
        configurations, providing a unified set of all supported file types.
        Useful for file type detection and validation across languages.

        Returns
        -------
        set[str]
            Set of all file extensions (e.g., {".py", ".js", ".java"})

        Examples
        --------
        >>> registry = AdapterRegistry()
        >>> extensions = registry.get_all_file_extensions()
        >>> ".py" in extensions
        True
        """
        extensions = set()
        for config in self._configs.values():
            extensions.update(config.file_extensions)
        return extensions

    @acquire_lock
    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        bool
            True if the language is supported
        """
        return language in self._configs

    @acquire_lock
    def get_binary_identifier(self, language: str) -> str | None:
        """Get the binary identifier for a language's adapter.

        Parameters
        ----------
        language : str
            The language identifier

        Returns
        -------
        str | None
            The binary identifier from the adapter config, or None if not found
        """
        try:
            config = self.get_adapter_config(language)
            if hasattr(config, "binary_identifier"):
                return config.binary_identifier
            return None
        except AidbError:
            return None
