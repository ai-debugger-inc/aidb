"""Root conftest for aidb_common tests.

Provides common fixtures and test utilities for all aidb_common tests.
"""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Clean up environment variables after test.

    Yields
    ------
    None
        Control returns to test after setup
    """
    original_env = dict(os.environ)
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test.

    Yields
    ------
    Path
        Path to temporary directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock user home directory.

    Parameters
    ----------
    tmp_path : Path
        Pytest tmp_path fixture
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture

    Returns
    -------
    Path
        Mocked home directory path
    """
    mock_home_dir = tmp_path / "home"
    mock_home_dir.mkdir()
    monkeypatch.setattr(Path, "home", lambda: mock_home_dir)
    return mock_home_dir
