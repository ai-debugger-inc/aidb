"""Safe YAML file operations for AIDB CLI.

This module provides YAML read/write utilities for CLI-only use cases. The core aidb
package does not depend on PyYAML.
"""

import contextlib
import tempfile
from pathlib import Path
from typing import Any

import yaml


class YamlOperationError(Exception):
    """Raised when YAML file operations fail."""


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
    YamlOperationError
        If file cannot be read or parsed
    """
    try:
        if not path.exists():
            msg = f"YAML file does not exist: {path}"
            raise YamlOperationError(msg)

        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data is not None else {}

    except yaml.YAMLError as e:
        msg = f"Invalid YAML in {path}: {e}"
        raise YamlOperationError(msg) from e
    except OSError as e:
        msg = f"Cannot read YAML file {path}: {e}"
        raise YamlOperationError(msg) from e


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
    YamlOperationError
        If file cannot be written
    """
    temp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

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
        raise YamlOperationError(msg) from e
