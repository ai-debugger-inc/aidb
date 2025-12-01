"""Configuration loader for versions.yaml."""

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Loads and parses versions.yaml configuration."""

    @staticmethod
    def load(config_path: Path) -> dict[str, Any]:
        """Load versions.yaml configuration.

        Parameters
        ----------
        config_path : Path
            Path to versions.yaml

        Returns
        -------
        dict[str, Any]
            Loaded configuration
        """
        with config_path.open() as f:
            return yaml.safe_load(f)

    @staticmethod
    def save(config_path: Path, config: dict[str, Any]) -> None:
        """Save configuration to versions.yaml atomically.

        Uses temp file + atomic rename to prevent corruption.

        Parameters
        ----------
        config_path : Path
            Path to versions.yaml
        config : dict[str, Any]
            Configuration to save

        Raises
        ------
        yaml.YAMLError
            If YAML serialization fails
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
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

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
