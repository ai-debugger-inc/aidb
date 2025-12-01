"""Global package version checker for pip and npm."""

from typing import Any

from ..sources.npm import NpmRegistrySource
from ..sources.pypi import PyPISource
from ..validators.version_utils import classify_version_update
from .base import BaseChecker


class PackageChecker(BaseChecker):
    """Checks for global package updates (pip and npm)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize checker.

        Parameters
        ----------
        config : dict[str, Any]
            Loaded configuration
        """
        super().__init__(config)
        self.pypi_source = PyPISource()
        self.npm_source = NpmRegistrySource()

    def check_pypi_updates(self) -> dict[str, dict[str, Any]]:
        """Check for pip package updates.

        Returns
        -------
        dict[str, dict[str, Any]]
            PyPI package updates found
        """
        pypi_updates = {}
        global_packages = self.config.get("global_packages", {})
        pip_packages = global_packages.get("pip", {})

        for package_name, package_info in pip_packages.items():
            current_version = package_info.get("version", "")
            if not current_version:
                continue

            latest_version = self.pypi_source.fetch_latest_version(package_name)

            if latest_version and latest_version != current_version:
                pypi_updates[package_name] = {
                    "current": current_version,
                    "latest": latest_version,
                    "update_type": classify_version_update(current_version, latest_version),
                }

        return pypi_updates

    def check_npm_updates(self) -> dict[str, dict[str, Any]]:
        """Check for npm package updates.

        Returns
        -------
        dict[str, dict[str, Any]]
            npm package updates found
        """
        npm_updates = {}
        global_packages = self.config.get("global_packages", {})
        npm_packages = global_packages.get("npm", {})

        for package_name, package_info in npm_packages.items():
            current_version = package_info.get("version", "")
            if not current_version:
                continue

            latest_version = self.npm_source.fetch_latest_version(package_name)

            if latest_version and latest_version != current_version:
                npm_updates[package_name] = {
                    "current": current_version,
                    "latest": latest_version,
                    "update_type": classify_version_update(current_version, latest_version),
                }

        return npm_updates
