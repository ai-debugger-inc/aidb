"""Version data sources for external APIs."""

from .base import VersionSource
from .docker_hub import DockerHubSource
from .endoflife import EndOfLifeSource
from .github import GitHubReleasesSource
from .npm import NpmRegistrySource
from .pypi import PyPISource

__all__ = [
    "VersionSource",
    "EndOfLifeSource",
    "GitHubReleasesSource",
    "DockerHubSource",
    "PyPISource",
    "NpmRegistrySource",
]
