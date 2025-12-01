"""Configuration loader for versions.json."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class ConfigLoader:
    """Loads and parses versions.json configuration."""

    @staticmethod
    def load(config_path: Path) -> dict[str, Any]:
        """Load versions.json configuration.

        Parameters
        ----------
        config_path : Path
            Path to versions.json

        Returns
        -------
        dict[str, Any]
            Loaded configuration
        """
        with config_path.open() as f:
            return json.load(f)

    @staticmethod
    def save(config_path: Path, config: dict[str, Any]) -> None:
        """Save configuration to versions.json atomically.

        Uses temp file + atomic rename to prevent corruption.

        Parameters
        ----------
        config_path : Path
            Path to versions.json
        config : dict[str, Any]
            Configuration to save

        Raises
        ------
        json.JSONDecodeError
            If JSON serialization fails
        OSError
            If file write or rename fails
        """
        config_path = Path(config_path)
        temp_fd = None
        temp_path = None

        try:
            temp_fd, temp_path_str = tempfile.mkstemp(
                dir=config_path.parent,
                prefix=f".{config_path.name}.",
                suffix=".tmp",
            )
            temp_path = Path(temp_path_str)

            with os.fdopen(temp_fd, "w") as f:
                temp_fd = None
                json.dump(config, f, indent=2)

            Path(temp_path).replace(config_path)
            temp_path = None

        finally:
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
