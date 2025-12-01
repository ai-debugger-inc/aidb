"""Mock launch configuration fixtures for API unit tests.

Provides mock LaunchConfig objects for testing session creation without requiring real
launch.json files.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_launch_config() -> MagicMock:
    """Sample launch configuration for debugging.

    Returns
    -------
    MagicMock
        Mock launch config with name, request, type, and to_adapter_args method
    """
    config = MagicMock()
    config.name = "Python: Current File"
    config.request = "launch"
    config.type = "python"
    config.to_adapter_args = MagicMock(
        return_value={
            "target": "/path/to/script.py",
            "args": ["--verbose"],
        }
    )
    return config


@pytest.fixture
def sample_launch_config_attach() -> MagicMock:
    """Sample attach launch configuration.

    Returns
    -------
    MagicMock
        Mock attach config with host and port settings
    """
    config = MagicMock()
    config.name = "Python: Attach"
    config.request = "attach"
    config.type = "python"
    config.to_adapter_args = MagicMock(
        return_value={
            "host": "localhost",
            "port": 5678,
        }
    )
    return config
