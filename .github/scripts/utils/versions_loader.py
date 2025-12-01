"""Shared utility for loading versions.yaml configuration."""

from pathlib import Path
from typing import Dict, Optional
import yaml


def load_versions(path: Optional[Path] = None) -> Dict:
    """Load and validate versions configuration.

    Args:
        path: Path to versions.yaml file. If None, uses root versions.yaml

    Returns:
        Dictionary containing versions configuration

    Raises:
        FileNotFoundError: If versions.yaml doesn't exist
        ValueError: If versions.yaml is malformed
    """
    if path is None:
        # Default to root versions.yaml
        root = Path(__file__).parent.parent.parent.parent
        path = root / "versions.yaml"

    if not path.exists():
        raise FileNotFoundError(f"versions.yaml not found at {path}")

    with open(path, 'r') as f:
        versions = yaml.safe_load(f)

    # Basic validation
    if not isinstance(versions, dict):
        raise ValueError(f"Invalid versions.yaml format at {path}")

    required_keys = ["version", "adapters"]
    missing = [k for k in required_keys if k not in versions]
    if missing:
        raise ValueError(f"Missing required keys in versions.yaml: {missing}")

    return versions


def get_adapter_version(adapter_name: str, path: Optional[Path] = None) -> str:
    """Get version for a specific adapter.

    Args:
        adapter_name: Name of the adapter (javascript, java, python)
        path: Optional path to versions.yaml

    Returns:
        Version string for the adapter

    Raises:
        KeyError: If adapter not found
    """
    versions = load_versions(path)

    if adapter_name not in versions.get("adapters", {}):
        raise KeyError(f"Adapter '{adapter_name}' not found in versions.yaml")

    adapter_config = versions["adapters"][adapter_name]
    return adapter_config.get("version", adapter_config.get("ref", "unknown"))


