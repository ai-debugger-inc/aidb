"""Pytest configuration and fixtures for adapter unit tests.

Auto-loads all unit test fixtures from the shared fixture infrastructure.
"""

# Re-export all unit fixtures for adapter tests
# Re-export adapter-specific mocks
from tests._fixtures.unit.adapter import *  # noqa: F401, F403
from tests._fixtures.unit.conftest import *  # noqa: F401, F403
