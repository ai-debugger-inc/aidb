"""Fixtures for config module tests."""

from collections.abc import Generator

import pytest

from aidb_common.config.runtime import ConfigManager


@pytest.fixture(autouse=True)
def reset_config_manager() -> Generator[None, None, None]:
    """Reset ConfigManager singleton before each test.

    This ensures test isolation by resetting the singleton state.
    """
    ConfigManager.reset()
    yield
    ConfigManager.reset()
