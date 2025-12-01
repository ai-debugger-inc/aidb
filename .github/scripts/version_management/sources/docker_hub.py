"""Docker Hub API source for container images."""

import requests
from packaging import version

from ..validators.version_utils import is_semver
from .base import VersionSource


class DockerHubSource(VersionSource):
    """Fetch latest Docker image tags from Docker Hub."""

    DOCKER_HUB_API = "https://hub.docker.com/v2/repositories/{}/tags"

    def fetch_latest_version(self, image: str, current_tag: str | None = None) -> str | None:
        """Fetch latest semantic version tag from Docker Hub.

        Parameters
        ----------
        image : str
            Docker image name (e.g., 'redis')
        current_tag : str | None
            Current tag to compare against (optional)

        Returns
        -------
        str | None
            Latest semantic version tag
        """
        try:
            url = self.DOCKER_HUB_API.format(image)
            response = requests.get(url, params={"page_size": 100}, timeout=30)
            response.raise_for_status()
            data = response.json()

            tags = [t["name"] for t in data.get("results", [])]

            semver_tags = [tag for tag in tags if is_semver(tag)]

            if not semver_tags:
                return None

            try:
                return max(semver_tags, key=lambda t: version.parse(t.lstrip("v")))
            except Exception:
                return None

        except Exception as e:
            self._handle_error(image, e)
            return None
