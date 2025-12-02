"""Repository detection utilities for AIDB."""

from pathlib import Path


def detect_repo_root(start_path: Path | None = None) -> Path:
    """Auto-detect repository root directory.

    Parameters
    ----------
    start_path : Path, optional
        Starting path for detection. If not provided, uses current file location.

    Returns
    -------
    Path
        Repository root directory
    """
    if start_path is None:
        # Default: start from this file's location and go up
        start_path = Path(__file__).resolve().parent
    else:
        start_path = Path(start_path).resolve()

    # Walk up the directory tree looking for repo markers
    current = start_path
    while current != current.parent:
        if (current / "versions.json").exists() and (
            current / "pyproject.toml"
        ).exists():
            return current
        current = current.parent

    # Fallback: assume repo root is 4 levels up from src/aidb_common/
    return Path(__file__).parent.parent.parent
