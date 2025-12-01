"""Pytest configuration and fixtures for API unit tests.

Auto-loads all unit test fixtures from the shared fixture infrastructure.
"""

# Re-export all unit fixtures for API tests
from tests._fixtures.unit.conftest import *  # noqa: F401, F403
