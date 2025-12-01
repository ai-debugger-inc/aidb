"""Fixtures for E2E generator tests."""

from pathlib import Path

import pytest

from aidb_cli.generators.core.generator import Generator


@pytest.fixture
def scenarios_dir():
    """Return scenarios directory."""
    return Path("src/aidb_cli/generators/scenarios")


@pytest.fixture
def generator():
    """Return generator instance."""
    return Generator()
