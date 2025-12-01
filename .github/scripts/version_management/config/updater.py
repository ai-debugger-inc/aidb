"""Configuration updater for applying version updates to versions.yaml."""

from datetime import datetime
from pathlib import Path
from typing import Any

from .loader import ConfigLoader


class ConfigUpdater:
    """Applies version updates to versions.yaml configuration."""

    def __init__(self, config_path: Path):
        """Initialize updater.

        Parameters
        ----------
        config_path : Path
            Path to versions.yaml
        """
        self.config_path = config_path
        self.config = ConfigLoader.load(config_path)

    def apply_updates(self, all_updates: dict[str, Any]) -> None:
        """Apply all updates to configuration.

        Parameters
        ----------
        all_updates : dict[str, Any]
            Dictionary of updates from checkers
        """
        if "infrastructure" in all_updates:
            self._apply_infrastructure_updates(all_updates["infrastructure"])

        if "adapters" in all_updates:
            self._apply_adapter_updates(all_updates["adapters"])

        if "global_packages_pip" in all_updates:
            self._apply_pip_package_updates(all_updates["global_packages_pip"])

        if "global_packages_npm" in all_updates:
            self._apply_npm_package_updates(all_updates["global_packages_npm"])

    def save(self) -> None:
        """Save updated configuration."""
        ConfigLoader.save(self.config_path, self.config)

    def _apply_infrastructure_updates(self, updates: dict[str, dict[str, Any]]) -> None:
        """Apply infrastructure version updates.

        Parameters
        ----------
        updates : dict[str, dict[str, Any]]
            Infrastructure updates
        """
        if "infrastructure" not in self.config:
            self.config["infrastructure"] = {}

        for lang, update_info in updates.items():
            new_version = update_info.get("new_version")
            if new_version:
                if lang in self.config["infrastructure"] and isinstance(
                    self.config["infrastructure"][lang], dict,
                ):
                    self.config["infrastructure"][lang]["version"] = new_version
                else:
                    self.config["infrastructure"][lang] = {"version": new_version}

        if "_metadata" not in self.config["infrastructure"]:
            self.config["infrastructure"]["_metadata"] = {}

        self.config["infrastructure"]["_metadata"]["last_updated"] = datetime.now().strftime(
            "%Y-%m-%d",
        )

    def _apply_adapter_updates(self, updates: dict[str, dict[str, Any]]) -> None:
        """Apply adapter version updates.

        Parameters
        ----------
        updates : dict[str, dict[str, Any]]
            Adapter updates
        """
        for adapter_name, update_info in updates.items():
            latest_version = update_info.get("latest")
            if latest_version and adapter_name in self.config.get("adapters", {}):
                if (
                    adapter_name == "javascript"
                    and self.config["adapters"]["javascript"].get("version", "").startswith("v")
                ):
                    latest_version = f"v{latest_version}"

                self.config["adapters"][adapter_name]["version"] = latest_version

    def _apply_pip_package_updates(self, updates: dict[str, dict[str, Any]]) -> None:
        """Apply pip package updates.

        Parameters
        ----------
        updates : dict[str, dict[str, Any]]
            Pip package updates
        """
        if "global_packages" not in self.config:
            self.config["global_packages"] = {}
        if "pip" not in self.config["global_packages"]:
            self.config["global_packages"]["pip"] = {}

        for package_name, update_info in updates.items():
            latest_version = update_info.get("latest")
            if latest_version and package_name in self.config["global_packages"]["pip"]:
                self.config["global_packages"]["pip"][package_name]["version"] = latest_version

    def _apply_npm_package_updates(self, updates: dict[str, dict[str, Any]]) -> None:
        """Apply npm package updates.

        Parameters
        ----------
        updates : dict[str, dict[str, Any]]
            npm package updates
        """
        if "global_packages" not in self.config:
            self.config["global_packages"] = {}
        if "npm" not in self.config["global_packages"]:
            self.config["global_packages"]["npm"] = {}

        for package_name, update_info in updates.items():
            latest_version = update_info.get("latest")
            if latest_version and package_name in self.config["global_packages"]["npm"]:
                self.config["global_packages"]["npm"][package_name]["version"] = latest_version
