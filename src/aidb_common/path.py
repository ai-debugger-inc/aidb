"""Path utilities for consistent path handling across AIDB."""

from __future__ import annotations

from pathlib import Path
from typing import overload

from aidb_common.constants import ADAPTERS_SUBDIR, AIDB_HOME_DIR, LOG_SUBDIR

# Cache directory constants
_CACHE_DIR = ".cache"
_CACHE_AIDB_SUBDIR = "aidb"


def get_aidb_home() -> Path:
    """Get the AIDB home directory (~/.aidb).

    Returns
    -------
    Path
        The AIDB home directory path
    """
    return Path.home() / AIDB_HOME_DIR


def get_aidb_adapters_dir() -> Path:
    """Get the AIDB adapters directory (~/.aidb/adapters).

    Returns
    -------
    Path
        The AIDB adapters directory path
    """
    return Path.home() / AIDB_HOME_DIR / ADAPTERS_SUBDIR


def get_aidb_log_dir() -> Path:
    """Get the AIDB log directory (~/.aidb/log).

    Returns
    -------
    Path
        The AIDB log directory path
    """
    return Path.home() / AIDB_HOME_DIR / LOG_SUBDIR


def get_aidb_cache_dir() -> Path:
    """Get the AIDB cache directory (~/.cache/aidb/adapters).

    Returns
    -------
    Path
        The AIDB cache directory path
    """
    return Path.home() / _CACHE_DIR / _CACHE_AIDB_SUBDIR / ADAPTERS_SUBDIR


@overload
def normalize_path(
    path: str,
    *,
    strict: bool = False,
    return_path: bool = False,
) -> str: ...


@overload
def normalize_path(
    path: Path,
    *,
    strict: bool = False,
    return_path: bool = True,
) -> Path: ...


def normalize_path(
    path: str | Path,
    *,
    strict: bool = False,
    return_path: bool | None = None,
) -> str | Path:
    """Normalize file paths to ensure consistent comparison and logging.

    The helper resolves ``~`` (user home), collapses redundant separators, and
    resolves symlinks when appropriate. It tolerates non-existent paths by
    default to preserve virtual locations (e.g., synthetic files created by
    debuggers). Set ``strict=True`` to force normalization even when the path
    does not yet exist.

    Parameters
    ----------
    path : str | Path
        The path to normalize.
    strict : bool, optional
        When True, resolve symlinks regardless of whether the path currently
        exists (uses ``Path.resolve(strict=False)``). Defaults to False which
        preserves the original value for missing paths.
    return_path : bool | None, optional
        Controls the return type. ``True`` returns a ``Path`` object, ``False``
        returns ``str``. When ``None`` (default) the return type matches the
        input type.

    Returns
    -------
    str | Path
        Normalized path with symlinks resolved when available.
    """
    if path is None or path == "":
        return path

    input_was_str = isinstance(path, str)
    path_obj = Path(path).expanduser()

    should_resolve = strict or path_obj.exists()
    if should_resolve:
        # ``strict=False`` avoids raising for missing intermediates while still
        # collapsing redundant segments and normalizing case on case-insensitive
        # filesystems.
        path_obj = path_obj.resolve(strict=False)

    if return_path is None:
        return_path = not input_was_str

    return path_obj if return_path else str(path_obj)
