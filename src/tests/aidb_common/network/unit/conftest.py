"""Fixtures for aidb_common.network unit tests."""

from collections.abc import Generator
from pathlib import Path

import pytest

from aidb_common.network.allocator import CrossProcessPortAllocator

# Re-export common fixtures
from tests._fixtures.unit import *  # noqa: F401, F403


@pytest.fixture
def temp_registry_dir(tmp_path: Path) -> Path:
    """Create an isolated registry directory for tests.

    Parameters
    ----------
    tmp_path : Path
        Pytest's temporary path fixture

    Returns
    -------
    Path
        Path to the created registry directory
    """
    registry_dir = tmp_path / "port_registry"
    registry_dir.mkdir()
    return registry_dir


@pytest.fixture(autouse=True)
def reset_global_allocator() -> Generator[None, None, None]:
    """Reset module-level _allocator singleton between tests.

    This ensures test isolation by clearing and restoring the global
    allocator instance.

    Yields
    ------
    None
        Control returns to test, then cleanup runs
    """
    import aidb_common.network.allocator as allocator_module

    original = allocator_module._allocator
    allocator_module._allocator = None
    yield
    allocator_module._allocator = original


@pytest.fixture
def allocator(temp_registry_dir: Path) -> CrossProcessPortAllocator:
    """Create an allocator instance with an isolated registry directory.

    Parameters
    ----------
    temp_registry_dir : Path
        Isolated registry directory from fixture

    Returns
    -------
    CrossProcessPortAllocator
        Allocator configured to use the temp directory
    """
    return CrossProcessPortAllocator(registry_dir=temp_registry_dir)
