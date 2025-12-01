"""Mock config fixtures for MCP unit testing."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class MockSessionConfig:
    """Mock session config for testing."""

    default_cleanup_timeout: float = 5.0
    max_retry_attempts: int = 3
    retry_delay: float = 0.5


@pytest.fixture
def mock_session_config() -> MockSessionConfig:
    """Mock session configuration for testing.

    Returns
    -------
    MockSessionConfig
        A mock config with default values:
        - default_cleanup_timeout: 5.0
        - max_retry_attempts: 3
        - retry_delay: 0.5
    """
    return MockSessionConfig()


@pytest.fixture
def mock_session_config_fast() -> MockSessionConfig:
    """Mock session configuration with fast timeouts for testing.

    Returns
    -------
    MockSessionConfig
        A mock config with fast values for quick test execution:
        - default_cleanup_timeout: 0.1
        - max_retry_attempts: 1
        - retry_delay: 0.01
    """
    return MockSessionConfig(
        default_cleanup_timeout=0.1,
        max_retry_attempts=1,
        retry_delay=0.01,
    )


@pytest.fixture
def mock_mcp_config() -> MagicMock:
    """Mock the full MCP config object.

    Returns
    -------
    MagicMock
        A mock config with session attribute configured
    """
    config = MagicMock()
    config.session = MockSessionConfig()
    return config


@pytest.fixture
def patch_mcp_config(mock_mcp_config: MagicMock):
    """Patch the MCP config module to use mock config.

    Parameters
    ----------
    mock_mcp_config : MagicMock
        The mock config to use

    Yields
    ------
    MagicMock
        The patched config
    """
    with patch("aidb_mcp.session.manager_lifecycle.config", mock_mcp_config):
        yield mock_mcp_config


__all__ = [
    "MockSessionConfig",
    "mock_session_config",
    "mock_session_config_fast",
    "mock_mcp_config",
    "patch_mcp_config",
]
