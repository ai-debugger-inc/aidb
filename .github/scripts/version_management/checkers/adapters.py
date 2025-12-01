"""Debug adapter version checker."""

from typing import Any

from ..sources.github import GitHubReleasesSource
from .base import BaseChecker


class AdapterChecker(BaseChecker):
    """Checks for debug adapter version updates."""

    def __init__(self, config: dict[str, Any]):
        """Initialize checker.

        Parameters
        ----------
        config : dict[str, Any]
            Loaded configuration
        """
        super().__init__(config)
        self.source = GitHubReleasesSource()

    def check_updates(self) -> dict[str, dict[str, Any]]:
        """Check for adapter version updates.

        Returns
        -------
        dict[str, dict[str, Any]]
            Adapter updates found
        """
        adapter_updates = {}
        current_adapters = self.config.get("adapters", {})

        if "javascript" in current_adapters:
            current_version = current_adapters["javascript"].get("version", "").lstrip("v")
            latest_version = self.source.fetch_latest_version("microsoft/vscode-js-debug")

            if latest_version and latest_version != current_version:
                adapter_updates["javascript"] = {
                    "current": current_version,
                    "latest": latest_version,
                    "repo": "microsoft/vscode-js-debug",
                }

        if "java" in current_adapters:
            current_version = current_adapters["java"].get("version", "")
            latest_version = self.source.fetch_latest_version("microsoft/java-debug")

            if latest_version and latest_version != current_version:
                adapter_updates["java"] = {
                    "current": current_version,
                    "latest": latest_version,
                    "repo": "microsoft/java-debug",
                }

        return adapter_updates
