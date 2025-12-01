"""End of Life API source for infrastructure versions (Python, Node, Java)."""

from typing import Any

import requests

from ..validators.version_utils import is_stable_version
from .base import VersionSource


class EndOfLifeSource(VersionSource):
    """Fetch infrastructure versions from endoflife.date API."""

    VERSION_APIS = {
        "python": "https://endoflife.date/api/python.json",
        "node": "https://endoflife.date/api/nodejs.json",
        "nodejs": "https://endoflife.date/api/nodejs.json",
        "java": "https://endoflife.date/api/oracle-jdk.json",
        "go": "https://endoflife.date/api/go.json",
        "rust": "https://endoflife.date/api/rust.json",
        "ruby": "https://endoflife.date/api/ruby.json",
        "php": "https://endoflife.date/api/php.json",
        "dotnet": "https://endoflife.date/api/dotnet.json",
    }

    def fetch_latest_version(self, language: str) -> str | None:
        """Fetch latest stable/LTS version for infrastructure language.

        Parameters
        ----------
        language : str
            Language name (python, nodejs, java, etc.)

        Returns
        -------
        str | None
            Latest version string
        """
        info = self.get_version_info(language)
        return info["version"] if info else None

    def get_version_info(self, language: str) -> dict[str, Any] | None:
        """Get detailed version info including EOL metadata.

        Parameters
        ----------
        language : str
            Language name

        Returns
        -------
        dict[str, Any] | None
            Version info with metadata (version, type, end_of_life, notes)
        """
        if language not in self.VERSION_APIS:
            return None

        try:
            response = requests.get(self.VERSION_APIS[language], timeout=30)
            response.raise_for_status()
            data = response.json()

            return self._parse_latest_version(language, data)

        except Exception as e:
            self._handle_error(language, e)
            return None

    def _parse_latest_version(self, language: str, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Parse latest version from endoflife.date response.

        Parameters
        ----------
        language : str
            Language name
        data : list[dict[str, Any]]
            API response data

        Returns
        -------
        dict[str, Any] | None
            Parsed version info
        """
        if language == "python":
            return self._parse_python_version(data)
        if language in ("nodejs", "node"):
            return self._parse_nodejs_version(data)
        if language == "java":
            return self._parse_java_version(data)

        return self._parse_generic_version(data)

    def _parse_python_version(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Parse Python version info."""
        for item in data:
            version_str = str(item.get("cycle", ""))
            eol = item.get("eol")

            if eol and eol:
                continue
            if not is_stable_version(version_str):
                continue

            return {
                "version": version_str,
                "type": "stable",
                "end_of_life": item.get("eol") or f"{int(version_str.split('.')[0]) + 5}-10",
                "notes": "Stable production version",
            }
        return None

    def _parse_nodejs_version(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Parse Node.js LTS version info."""
        for item in data:
            version_str = str(item.get("cycle", ""))
            lts = item.get("lts")
            eol = item.get("eol")

            if not lts or (eol and eol):
                continue

            return {
                "version": version_str,
                "type": "lts",
                "end_of_life": item.get("eol") or f"{int(version_str) + 2:02d}-04-30",
                "notes": f"Latest LTS ({lts})",
            }
        return None

    def _parse_java_version(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Parse Java LTS version info."""
        for item in data:
            version_str = str(item.get("cycle", ""))
            lts = item.get("lts")
            eol = item.get("eol")

            if not lts or (eol and eol):
                continue

            return {
                "version": version_str,
                "type": "lts",
                "end_of_life": item.get("eol") or f"{int(version_str) + 10}-09",
                "notes": "Latest stable LTS",
            }
        return None

    def _parse_generic_version(self, data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Parse generic version info (for other languages)."""
        for item in data:
            version_str = str(item.get("cycle", ""))
            eol = item.get("eol")

            if eol and eol:
                continue
            if not is_stable_version(version_str):
                continue

            return {
                "version": version_str,
                "type": "stable",
                "end_of_life": item.get("eol"),
                "notes": "Latest stable version",
            }
        return None
