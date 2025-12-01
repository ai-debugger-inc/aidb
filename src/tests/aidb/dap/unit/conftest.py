"""Pytest configuration and fixtures for DAP unit tests.

Auto-loads all unit test fixtures from the shared fixture infrastructure.
"""

# Re-export all unit fixtures for DAP tests
# Re-export DAP-specific builders and mocks
from tests._fixtures.unit.builders import (  # noqa: F401
    DAPEventBuilder,
    DAPRequestBuilder,
    DAPResponseBuilder,
)
from tests._fixtures.unit.conftest import *  # noqa: F401, F403
from tests._fixtures.unit.dap import *  # noqa: F401, F403
