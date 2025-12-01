"""Infrastructure version checker for Python, Node, Java."""

from typing import Any

from ..sources.endoflife import EndOfLifeSource
from .base import BaseChecker


class InfrastructureChecker(BaseChecker):
    """Checks for infrastructure version updates (Python, Node, Java)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize checker.

        Parameters
        ----------
        config : dict[str, Any]
            Loaded configuration
        """
        super().__init__(config)
        self.source = EndOfLifeSource()

    def check_updates(self) -> dict[str, dict[str, str]]:
        """Check for infrastructure version updates.

        Returns
        -------
        dict[str, dict[str, str]]
            Updates found with metadata
        """
        infrastructure_updates = {}
        current_infrastructure = self.config.get("infrastructure", {})

        languages = ["python", "node", "java"]

        for lang in languages:
            current_version = None

            if lang in current_infrastructure and isinstance(current_infrastructure[lang], dict):
                current_version = current_infrastructure[lang].get("version")
            elif f"{lang}_version" in current_infrastructure:
                current_version = current_infrastructure[f"{lang}_version"]

            if current_version:
                new_info = self.source.get_version_info(lang)

                if new_info and new_info["version"] != current_version:
                    infrastructure_updates[lang] = {
                        "old_version": current_version,
                        "new_version": new_info["version"],
                        "type": new_info.get("type", "stable"),
                        "end_of_life": new_info.get("end_of_life"),
                        "notes": new_info.get(
                            "notes", f"Latest {new_info.get('type', 'stable')} version",
                        ),
                    }

        return infrastructure_updates
