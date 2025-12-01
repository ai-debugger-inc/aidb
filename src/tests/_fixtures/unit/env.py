"""Environment variable fixtures for unit tests.

These fixtures provide utilities for setting and cleaning up environment variables
during tests.
"""

import os
from collections.abc import Callable, Generator

import pytest


@pytest.fixture
def env_var_cleanup() -> Generator[list[str], None, None]:
    """Track environment variables to clean up after test.

    Yields
    ------
    list[str]
        List of environment variable names to clean up
    """
    tracked_vars: list[str] = []
    yield tracked_vars
    # Clean up tracked variables
    for var in tracked_vars:
        os.environ.pop(var, None)


@pytest.fixture
def set_env(env_var_cleanup: list[str]) -> Callable[[str, str], None]:
    """Helper to set environment variable and track for cleanup.

    Parameters
    ----------
    env_var_cleanup : list[str]
        List to track variables for cleanup

    Returns
    -------
    Callable[[str, str], None]
        Function to set environment variable
    """

    def _set_env(key: str, value: str) -> None:
        """Set environment variable and track for cleanup."""
        os.environ[key] = value
        env_var_cleanup.append(key)

    return _set_env


__all__ = [
    "env_var_cleanup",
    "set_env",
]
