"""Fixtures for patterns module tests."""

from collections.abc import Generator

import pytest

from aidb_common.patterns.singleton import Singleton


@pytest.fixture(autouse=True)
def reset_all_singletons() -> Generator[None, None, None]:
    """Reset all singleton instances before each test.

    This ensures test isolation by clearing the singleton registry.
    """
    # Clear all singleton instances
    Singleton._instances.clear()
    yield
    # Clean up after test
    Singleton._instances.clear()
