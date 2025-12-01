"""Pytest configuration and fixtures for aidb_shared test suite.

This conftest imports all shared fixtures from the parent test directory, making them
available to all tests in the aidb_shared suite.
"""

import pytest

from tests._fixtures.base import (
    debug_interface,
    temp_workspace,
)
from tests._fixtures.docker_simple import docker_test_mode
from tests._fixtures.generated_programs import (
    generated_program_factory,
    generated_programs_manifest,
    scenario_id,
)
from tests._fixtures.scenarios import language  # noqa: F401

__all__ = [
    "debug_interface",
    "temp_workspace",
    "docker_test_mode",
    "generated_program_factory",
    "generated_programs_manifest",
    "scenario_id",
    "language",
]
