"""PyPI API source for Python packages."""

import requests

from .base import VersionSource


class PyPISource(VersionSource):
    """Fetch latest package versions from PyPI."""

    PYPI_API = "https://pypi.org/pypi/{}/json"

    def fetch_latest_version(self, package: str) -> str | None:
        """Fetch latest version from PyPI.

        Parameters
        ----------
        package : str
            Package name

        Returns
        -------
        str | None
            Latest version string
        """
        try:
            url = self.PYPI_API.format(package)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            return data.get("info", {}).get("version")

        except Exception as e:
            self._handle_error(package, e)
            return None
