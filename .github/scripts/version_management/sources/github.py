"""GitHub Releases API source for debug adapters."""

from typing import Any

import requests

from ..validators.version_utils import is_stable_version
from .base import VersionSource


class GitHubReleasesSource(VersionSource):
    """Fetch latest release versions from GitHub."""

    GITHUB_API = "https://api.github.com/repos/{}/releases"

    def fetch_latest_version(self, repo: str) -> str | None:
        """Fetch latest stable release version from GitHub.

        Parameters
        ----------
        repo : str
            Repository in format "owner/name"

        Returns
        -------
        str | None
            Latest release version (without 'v' prefix)
        """
        try:
            url = self.GITHUB_API.format(repo)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            for release in data:
                if release.get("prerelease", False):
                    continue
                if release.get("draft", False):
                    continue

                tag_name = release.get("tag_name", "")
                version_str = tag_name.lstrip("v")

                if is_stable_version(version_str):
                    return version_str

        except Exception as e:
            self._handle_error(repo, e)

        return None

    def fetch_releases(self, repo: str) -> list[dict[str, Any]] | None:
        """Fetch all releases from GitHub.

        Parameters
        ----------
        repo : str
            Repository name in format "owner/name"

        Returns
        -------
        list[dict[str, Any]] | None
            List of releases or None on error
        """
        try:
            url = self.GITHUB_API.format(repo)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._handle_error(repo, e)
            return None

    def find_latest_stable_release(self, releases: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Find the latest stable release from a list.

        Parameters
        ----------
        releases : list[dict[str, Any]]
            List of release objects

        Returns
        -------
        dict[str, Any] | None
            Latest stable release or None
        """
        for release in releases:
            if release.get("prerelease", False) or release.get("draft", False):
                continue

            tag_name = release.get("tag_name", "")
            version_str = tag_name.lstrip("v")

            if is_stable_version(version_str):
                return release

        return None
