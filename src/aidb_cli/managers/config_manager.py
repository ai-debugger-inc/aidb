"""Centralized configuration manager for AIDB CLI.

This module provides a singleton ConfigManager that consolidates functionality from
VersionManager, configuration validation, and settings management.
"""

import json
from pathlib import Path
from typing import Any, Optional

from aidb_cli.core.constants import Icons, LogLevel
from aidb_cli.core.utils import CliOutput
from aidb_common.config import VersionManager, load_merged_config
from aidb_common.constants import Language
from aidb_common.io import safe_read_yaml, safe_write_yaml
from aidb_common.io.files import FileOperationError
from aidb_common.repo import detect_repo_root
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class ConfigManager:
    """Centralized singleton manager for all configuration operations.

    Consolidates functionality from VersionManager and other config-related operations
    into a single, reusable interface.
    """

    _instance: Optional["ConfigManager"] = None
    _initialized: bool = False

    def __new__(
        cls,
        repo_root: Path | None = None,  # noqa: ARG004
    ) -> "ConfigManager":
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, repo_root: Path | None = None) -> None:
        if self._initialized:
            return

        if repo_root is None:
            repo_root = detect_repo_root()

        from aidb_cli.core.paths import ProjectPaths

        self.repo_root = repo_root
        self.versions_file = repo_root / ProjectPaths.VERSIONS_YAML

        self.project_config = repo_root / ProjectPaths.AIDB_CONFIG
        self.user_config = Path.home() / ".config" / "aidb" / "config.yaml"

        self.version_manager = VersionManager(self.versions_file)

        self._config_cache: dict[str, Any] | None = None

        self._initialized = True
        logger.debug("ConfigManager initialized with repo_root: %s", self.repo_root)

    @property
    def config(self) -> dict[str, Any]:
        """Get merged configuration dictionary."""
        if self._config_cache is None:
            self._load_configs()
        return self._config_cache or {}

    def _load_configs(self) -> None:
        """Load and merge configuration files using shared loader."""
        self._config_cache = load_merged_config(self.repo_root)

    def get_versions(self, format_type: str = "text") -> str:
        """Get version information in specified format.

        Parameters
        ----------
        format_type : str
            Output format: 'text', 'json', 'yaml', 'env'

        Returns
        -------
        str
            Formatted version information
        """
        return self.version_manager.format_versions_output(format_type)

    def get_infrastructure_versions(self) -> dict[str, str]:
        """Get infrastructure versions for Docker builds.

        Returns
        -------
        Dict[str, str]
            Infrastructure versions (python, node, java)
        """
        return self.version_manager.get_infrastructure_versions()

    def get_adapter_version(self, language: str) -> str | None:
        """Get adapter version for a specific language.

        Parameters
        ----------
        language : str
            Language name (javascript, java, python)

        Returns
        -------
        str | None
            Adapter version or None if not found
        """
        return self.version_manager.get_adapter_version(language)

    def get_docker_build_args(self) -> dict[str, str]:
        """Generate Docker build arguments from versions.json.

        Returns
        -------
        Dict[str, str]
            Build arguments for Docker
        """
        return self.version_manager.get_docker_build_args()

    def validate_versions(self) -> dict[str, bool]:
        """Validate that all required version fields are present.

        Returns
        -------
        Dict[str, bool]
            Validation results for each section
        """
        return self.version_manager.validate_versions()

    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Parameters
        ----------
        key_path : str
            Dot-separated path to config value (e.g., 'adapters.auto_build')
        default : Any
            Default value if key not found

        Returns
        -------
        Any
            Configuration value
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set_config_value(
        self,
        key_path: str,
        value: Any,
        save_to: str = "user",
    ) -> bool:
        """Set configuration value using dot notation.

        Parameters
        ----------
        key_path : str
            Dot-separated path to config value
        value : Any
            Value to set
        save_to : str
            Where to save ('user' or 'project')

        Returns
        -------
        bool
            True if successful
        """
        try:
            config_file = self.user_config if save_to == "user" else self.project_config

            if config_file.exists():
                try:
                    file_config = safe_read_yaml(config_file)
                except FileOperationError as read_error:
                    logger.error(
                        "Failed to read config %s: %s",
                        config_file,
                        read_error,
                    )
                    return False
            else:
                file_config = {}

            keys = key_path.split(".")
            current = file_config

            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            current[keys[-1]] = value

            try:
                safe_write_yaml(config_file, file_config)
            except FileOperationError as write_error:
                logger.error(
                    "Failed to write config %s: %s",
                    config_file,
                    write_error,
                )
                return False

            self._config_cache = None

            logger.debug("Set config %s = %s in %s", key_path, value, config_file)
            return True

        except (KeyError, TypeError, AttributeError) as e:
            logger.error("Failed to set config %s: %s", key_path, e)
            return False

    def create_default_config(self, save_to: str = "user") -> bool:
        """Create a default configuration file.

        Parameters
        ----------
        save_to : str
            Where to save ('user' or 'project')

        Returns
        -------
        bool
            True if successful
        """
        try:
            config_file = self.user_config if save_to == "user" else self.project_config

            if config_file.exists():
                CliOutput.plain(f"Configuration file already exists: {config_file}")
                return False

            default_config = {
                "defaults": {
                    "verbose": False,
                    "log_level": LogLevel.INFO.value,
                },
                "adapters": {
                    "auto_build": True,
                    "languages": {
                        Language.PYTHON.value: {"enabled": True},
                        Language.JAVASCRIPT.value: {"enabled": True},
                        Language.JAVA.value: {"enabled": True},
                    },
                },
                "test": {
                    "auto_install_deps": True,
                    "pytest_args": "-v --tb=short",
                },
            }

            try:
                safe_write_yaml(config_file, default_config)
            except FileOperationError as write_error:
                logger.error("Failed to create default config: %s", write_error)
                CliOutput.plain(
                    f"{Icons.ERROR} Failed to create config: {write_error}",
                    err=True,
                )
                return False

            CliOutput.plain(
                f"{Icons.SUCCESS} Created default configuration: {config_file}",
            )
            return True

        except (OSError, FileOperationError) as e:
            logger.error("Failed to create default config: %s", e)
            CliOutput.plain(f"{Icons.ERROR} Failed to create config: {e}", err=True)
            return False

    def show_config(
        self,
        format_type: str = "yaml",
        config_type: str = "merged",
    ) -> None:
        """Display current configuration.

        Parameters
        ----------
        format_type : str
            Output format: 'yaml', 'json', 'text'
        config_type : str
            Which config to show: 'merged', 'user', 'project', 'versions'
        """
        try:
            config = self._load_config_by_type(config_type)
            output = self._format_output(config, format_type, config_type)
            CliOutput.plain(output)

        except (OSError, FileOperationError) as e:
            logger.error("Failed to show config: %s", e)
            CliOutput.plain(f"{Icons.ERROR} Failed to show config: {e}", err=True)

    def _format_config_text(self, config: dict[str, Any], indent: int = 0) -> str:
        """Format configuration as readable text.

        Parameters
        ----------
        config : Dict[str, Any]
            Configuration to format
        indent : int
            Current indentation level

        Returns
        -------
        str
            Formatted text
        """
        lines = []
        prefix = "  " * indent

        for key, value in config.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_config_text(value, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {value}")

        return "\n".join(lines)

    def _load_config_by_type(self, config_type: str) -> dict[str, Any] | None:
        """Load configuration based on type.

        Parameters
        ----------
        config_type : str
            Type of config to load ('merged', 'user', 'project', 'versions')

        Returns
        -------
        dict[str, Any] | None
            Loaded configuration or None for versions type
        """
        if config_type == "versions":
            return None  # Handled separately

        if config_type == "user":
            if self.user_config.exists():
                try:
                    return safe_read_yaml(self.user_config)
                except FileOperationError as read_error:
                    logger.error("Failed to read user config: %s", read_error)
            return {}

        if config_type == "project":
            if self.project_config.exists():
                try:
                    return safe_read_yaml(self.project_config)
                except FileOperationError as read_error:
                    logger.error("Failed to read project config: %s", read_error)
            return {}

        return self.config

    def _format_output(
        self,
        config: dict[str, Any] | None,
        format_type: str,
        config_type: str,
    ) -> str:
        """Format configuration output.

        Parameters
        ----------
        config : dict[str, Any] | None
            Configuration to format
        format_type : str
            Output format ('yaml', 'json', 'text')
        config_type : str
            Type of config being formatted

        Returns
        -------
        str
            Formatted output
        """
        if config_type == "versions":
            return self.get_versions(format_type)

        if format_type == "json":
            return json.dumps(config, indent=2)

        if format_type == "yaml":
            import yaml

            return yaml.dump(config, default_flow_style=False)

        return self._format_config_text(config or {})


# Convenience function for getting the singleton instance
def get_config_manager(repo_root: Path | None = None) -> ConfigManager:
    """Get the ConfigManager singleton instance.

    Parameters
    ----------
    repo_root : Path, optional
        Repository root directory

    Returns
    -------
    ConfigManager
        The singleton instance
    """
    return ConfigManager(repo_root)
