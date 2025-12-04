"""Version discovery utilities for adapter downloads."""

from pathlib import Path

from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError


def find_project_root() -> Path:
    """Find the project root directory containing versions.json.

    Returns
    -------
    Path
        Path to the project root directory

    Raises
    ------
    FileNotFoundError
        If versions.json cannot be found
    """
    current = Path(__file__)

    # Walk up the directory tree looking for versions.json
    for parent in current.parents:
        versions_file = parent / "versions.json"
        if versions_file.exists():
            return parent

    # Fallback: check some common locations relative to this file
    common_locations = [
        # From src/aidb/adapters/downloads/
        Path(__file__).parent.parent.parent.parent.parent,
        Path(__file__).parent.parent.parent.parent,  # One level up
    ]

    for location in common_locations:
        versions_file = location / "versions.json"
        if versions_file.exists():
            return location

    msg = "Could not locate project root with versions.json"
    raise FileNotFoundError(msg)


def get_project_version() -> str:
    """Get the current project version from versions.json.

    Returns
    -------
    str
        Project version string
    """
    try:
        project_root = find_project_root()
        versions_file = project_root / "versions.json"

        versions = safe_read_json(versions_file)
        return versions.get("version", "latest")
    except (FileOperationError, FileNotFoundError):
        return "latest"
