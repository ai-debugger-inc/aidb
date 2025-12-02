"""Shared test utilities for CI/CD tests."""

from contextlib import contextmanager
from typing import Any
from unittest.mock import patch


@contextmanager
def mock_script_environment(platform="Linux", machine="x86_64", json_data=None):
    """Mock common script execution environment.

    Parameters
    ----------
    platform : str
        Platform name for platform.system()
    machine : str
        Machine type for platform.machine()
    json_data : dict, optional
        Data to return from json.load()

    Yields
    ------
    dict
        Dictionary of mock objects (platform_mock, machine_mock, json_mock, open_mock)
    """
    from unittest.mock import mock_open

    with (
        patch("platform.system", return_value=platform) as platform_mock,
        patch("platform.machine", return_value=machine) as machine_mock,
        patch("json.load", return_value=json_data) as json_mock,
        patch("builtins.open", mock_open(read_data="")) as open_mock,
    ):
        yield {
            "platform": platform_mock,
            "machine": machine_mock,
            "json": json_mock,
            "open": open_mock,
        }


def create_mock_versions_config(**overrides) -> dict[str, Any]:
    """Create a mock versions.json configuration with sensible defaults.

    Parameters
    ----------
    **overrides : dict
        Override default values (deep merge)

    Returns
    -------
    dict[str, Any]
        Mock configuration
    """
    base_config = {
        "version": "1.0.0",
        "platforms": [
            {"platform": "linux", "arch": "x64"},
            {"platform": "linux", "arch": "arm64"},
            {"platform": "darwin", "arch": "x64"},
            {"platform": "darwin", "arch": "arm64"},
            {"platform": "windows", "arch": "x64"},
        ],
        "infrastructure": {
            "python": {"version": "3.11.0"},
            "node": {"version": "20.0.0"},
            "java": {"version": "21.0.0"},
        },
        "adapters": {
            "python": {
                "version": "1.8.0",
                "debugpy_version": "1.8.0",
            },
            "javascript": {"version": "1.85.0"},
            "java": {"version": "0.50.0"},
        },
    }

    # Deep merge overrides
    _deep_merge(base_config, overrides)
    return base_config


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override dict into base dict (in-place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
