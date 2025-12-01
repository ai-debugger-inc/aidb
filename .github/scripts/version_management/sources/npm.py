"""npm registry API source for Node packages."""

import requests

from .base import VersionSource


class NpmRegistrySource(VersionSource):
    """Fetch latest package versions from npm registry."""

    NPM_API = "https://registry.npmjs.org/{}/latest"

    PACKAGE_NAME_MAP = {
        "ts_node": "ts-node",
    }

    def fetch_latest_version(self, package: str) -> str | None:
        """Fetch latest version from npm registry.

        Parameters
        ----------
        package : str
            Package name (from versions.yaml, may use underscores)

        Returns
        -------
        str | None
            Latest version string
        """
        npm_package = self.PACKAGE_NAME_MAP.get(package, package)

        try:
            url = self.NPM_API.format(npm_package)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            return data.get("version")

        except Exception as e:
            self._handle_error(npm_package, e)
            return None
