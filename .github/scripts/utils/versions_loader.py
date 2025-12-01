"""Shared utility for loading versions.json configuration."""

import json
from pathlib import Path
from typing import Dict, Optional


def load_versions(path: Optional[Path] = None) -> Dict:
    """Load and validate versions configuration.

    Args:
        path: Path to versions.json file. If None, uses root versions.json

    Returns:
        Dictionary containing versions configuration

    Raises:
        FileNotFoundError: If versions.json doesn't exist
        ValueError: If versions.json is malformed
    """
    if path is None:
        # Default to root versions.json
        root = Path(__file__).parent.parent.parent.parent
        path = root / "versions.json"

    if not path.exists():
        raise FileNotFoundError(f"versions.json not found at {path}")

    with open(path, 'r') as f:
        versions = json.load(f)

    # Basic validation
    if not isinstance(versions, dict):
        raise ValueError(f"Invalid versions.json format at {path}")

    required_keys = ["version", "adapters"]
    missing = [k for k in required_keys if k not in versions]
    if missing:
        raise ValueError(f"Missing required keys in versions.json: {missing}")

    return versions


def get_adapter_version(adapter_name: str, path: Optional[Path] = None) -> str:
    """Get version for a specific adapter.

    Args:
        adapter_name: Name of the adapter (javascript, java, python)
        path: Optional path to versions.json

    Returns:
        Version string for the adapter

    Raises:
        KeyError: If adapter not found
    """
    versions = load_versions(path)

    if adapter_name not in versions.get("adapters", {}):
        raise KeyError(f"Adapter '{adapter_name}' not found in versions.json")

    adapter_config = versions["adapters"][adapter_name]
    return adapter_config.get("version", adapter_config.get("ref", "unknown"))


