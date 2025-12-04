"""Adapter download utilities.

This package provides utilities for downloading and installing debug adapters, including
version management and GitHub release integration.
"""

from .download import AdapterDownloader
from .result import AdapterDownloaderResult
from .version import find_project_root, get_project_version

__all__ = [
    "AdapterDownloader",
    "AdapterDownloaderResult",
    "find_project_root",
    "get_project_version",
]
