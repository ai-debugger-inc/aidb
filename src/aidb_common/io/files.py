"""Safe file operations for AIDB common."""

import contextlib
import json
import tempfile
from pathlib import Path
from typing import Any

import yaml


class FileOperationError(Exception):
    """Raised when file operations fail."""


def safe_read_yaml(path: Path) -> dict[str, Any]:
    """Safely read YAML file with error handling.

    Parameters
    ----------
    path : Path
        Path to YAML file

    Returns
    -------
    dict[str, Any]
        Parsed YAML data

    Raises
    ------
    FileOperationError
        If file cannot be read or parsed
    """
    try:
        if not path.exists():
            msg = f"YAML file does not exist: {path}"
            raise FileOperationError(msg)

        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data is not None else {}

    except yaml.YAMLError as e:
        msg = f"Invalid YAML in {path}: {e}"
        raise FileOperationError(msg) from e
    except OSError as e:
        msg = f"Cannot read YAML file {path}: {e}"
        raise FileOperationError(msg) from e


def safe_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Safely write YAML file with atomic operation.

    Parameters
    ----------
    path : Path
        Path to YAML file
    data : dict[str, Any]
        Data to write

    Raises
    ------
    FileOperationError
        If file cannot be written
    """
    temp_path = None
    try:
        ensure_dir(path.parent)

        # Use atomic write to prevent corruption
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".yaml",
            dir=path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            yaml.safe_dump(data, temp_file, default_flow_style=False, sort_keys=True)

        # Atomic move
        temp_path.replace(path)

    except (OSError, yaml.YAMLError) as e:
        # Clean up temp file if it exists
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
        msg = f"Cannot write YAML file {path}: {e}"
        raise FileOperationError(msg) from e


def safe_read_json(path: Path) -> dict[str, Any]:
    """Safely read JSON file with error handling.

    Parameters
    ----------
    path : Path
        Path to JSON file

    Returns
    -------
    dict[str, Any]
        Parsed JSON data

    Raises
    ------
    FileOperationError
        If file cannot be read or parsed
    """
    try:
        if not path.exists():
            msg = f"JSON file does not exist: {path}"
            raise FileOperationError(msg)

        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        msg = f"Invalid JSON in {path}: {e}"
        raise FileOperationError(msg) from e
    except OSError as e:
        msg = f"Cannot read JSON file {path}: {e}"
        raise FileOperationError(msg) from e


def safe_write_json(path: Path, data: dict[str, Any]) -> None:
    """Safely write JSON file with atomic operation.

    Parameters
    ----------
    path : Path
        Path to JSON file
    data : dict[str, Any]
        Data to write

    Raises
    ------
    FileOperationError
        If file cannot be written
    """
    temp_path = None
    try:
        ensure_dir(path.parent)

        # Use atomic write to prevent corruption
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, indent=2, sort_keys=True)

        # Atomic move
        temp_path.replace(path)

    except (OSError, TypeError, ValueError) as e:
        # Clean up temp file if it exists
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
        msg = f"Cannot write JSON file {path}: {e}"
        raise FileOperationError(msg) from e


def atomic_write(path: Path, content: str) -> None:
    """Atomically write content to a file.

    Parameters
    ----------
    path : Path
        Path to write to
    content : str
        Content to write

    Raises
    ------
    FileOperationError
        If file cannot be written
    """
    temp_path = None
    try:
        ensure_dir(path.parent)

        # Write to temporary file first
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=path.suffix,
            dir=path.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)

        # Atomic move
        temp_path.replace(path)

    except OSError as e:
        # Clean up temp file if it exists
        if temp_path is not None:
            with contextlib.suppress(OSError):
                temp_path.unlink(missing_ok=True)
        msg = f"Cannot write file {path}: {e}"
        raise FileOperationError(msg) from e


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, creating it if necessary.

    Parameters
    ----------
    path : Path
        Directory path to ensure

    Returns
    -------
    Path
        The directory path

    Raises
    ------
    FileOperationError
        If directory cannot be created
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as e:
        msg = f"Cannot create directory {path}: {e}"
        raise FileOperationError(msg) from e


def read_cache_file(path: Path) -> str | None:
    """Safely read a cache file.

    Parameters
    ----------
    path : Path
        Path to cache file

    Returns
    -------
    str | None
        Cache file contents (stripped of whitespace) or None if file doesn't exist

    Notes
    -----
    This function is designed for simple cache files containing hash values
    or other single-line data. Returns None (not an error) if the file doesn't
    exist, which simplifies cache miss handling.
    """
    try:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        # Treat read errors as cache miss
        return None


def write_cache_file(path: Path, content: str) -> None:
    """Safely write content to a cache file with atomic operation.

    Parameters
    ----------
    path : Path
        Path to cache file
    content : str
        Content to write (will be written with trailing newline)

    Raises
    ------
    FileOperationError
        If file cannot be written

    Notes
    -----
    This uses atomic write to prevent corruption if the process is interrupted.
    The parent directory is created if it doesn't exist.
    """
    atomic_write(path, content.strip() + "\n")
