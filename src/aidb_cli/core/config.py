"""Configuration management for AIDB CLI."""

from pathlib import Path
from typing import Any

from aidb_cli.core.constants import LogLevel
from aidb_common.config import ConfigManager as BaseConfigManager
from aidb_common.config import load_merged_config
from aidb_common.repo import detect_repo_root


class CliConfig:
    """Configuration class for AIDB CLI."""

    def __init__(self, config_file: Path | None = None) -> None:
        """Initialize CLI configuration.

        Parameters
        ----------
        config_file : Path, optional
            Path to .aidb.yaml configuration file
        """
        self.config_file = config_file
        self.repo_root: Path | None = None
        self._config_data: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file and environment variables."""
        repo_root = None

        if self.config_file and self.config_file.exists():
            repo_root = self.config_file.parent
        else:
            from aidb_cli.core.paths import ProjectPaths

            repo_root = detect_repo_root()
            inferred_config = repo_root / ProjectPaths.AIDB_CONFIG
            if inferred_config.exists():
                self.config_file = inferred_config
            elif self.config_file is None:
                # Record default path even if it does not yet exist
                self.config_file = inferred_config

        self.repo_root = repo_root
        self._config_data = load_merged_config(repo_root)

    @property
    def verbose(self) -> bool:
        """Get verbose mode setting."""
        return self._config_data.get("defaults", {}).get("verbose", False)

    @property
    def debug(self) -> bool:
        """Get debug mode setting."""
        return self._config_data.get("defaults", {}).get("debug", False)

    @property
    def log_level(self) -> LogLevel:
        """Get log level setting."""
        level = self._config_data.get("defaults", {}).get(
            "log_level",
            LogLevel.INFO.value,
        )
        return LogLevel(level.upper())

    @property
    def env(self) -> str:
        """Get environment setting."""
        return self._config_data.get("defaults", {}).get("env", "dev")

    @property
    def adapter_auto_build(self) -> bool:
        """Get adapter auto-build setting."""
        return self._config_data.get("adapters", {}).get("auto_build", True)

    @property
    def adapter_cache_dir(self) -> Path:
        """Get adapter cache directory."""
        from aidb_cli.core.paths import CachePaths

        cache_dir = self._config_data.get("adapters", {}).get(
            "cache_dir",
            str(CachePaths.user_aidb()),
        )
        return Path(cache_dir)

    @property
    def enabled_languages(self) -> list[str]:
        """Get list of enabled languages."""
        from aidb_cli.core.constants import SUPPORTED_LANGUAGES

        languages = self._config_data.get("adapters", {}).get("languages", {})
        enabled = []
        for lang, config in languages.items():
            if config.get("enabled", True):
                enabled.append(lang)
        return enabled or SUPPORTED_LANGUAGES

    @property
    def docker_auto_build(self) -> bool:
        """Get Docker auto-build setting."""
        return self._config_data.get("docker", {}).get("auto_build", True)

    @property
    def docker_compose_file(self) -> Path:
        """Get Docker Compose file path."""
        from aidb_cli.core.paths import ProjectPaths

        compose_file = self._config_data.get("docker", {}).get(
            "compose_file",
            str(ProjectPaths.TEST_DOCKER_COMPOSE),
        )
        return Path(compose_file)

    @property
    def test_auto_install_deps(self) -> bool:
        """Get test auto-install dependencies setting."""
        return self._config_data.get("test", {}).get("auto_install_deps", True)

    @property
    def pytest_args(self) -> str:
        """Get default pytest arguments."""
        return self._config_data.get("test", {}).get("pytest_args", "-v --tb=short")

    def get_section(self, section: str) -> dict[str, Any]:
        """Get entire configuration section.

        Parameters
        ----------
        section : str
            Section name

        Returns
        -------
        dict[str, Any]
            Section configuration
        """
        return self._config_data.get(section, {})


def get_cli_config(config_file: Path | None = None) -> CliConfig:
    """Get CLI configuration instance.

    Parameters
    ----------
    config_file : Path, optional
        Path to configuration file

    Returns
    -------
    CliConfig
        Configuration instance
    """
    return CliConfig(config_file)


def get_base_config() -> BaseConfigManager:
    """Get base AIDB configuration manager.

    Returns
    -------
    BaseConfigManager
        Base configuration manager instance
    """
    return BaseConfigManager()
