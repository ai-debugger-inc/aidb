"""Fixtures for io module tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_json_file(tmp_path: Path) -> Path:
    """Create a sample JSON file for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest tmp_path fixture

    Returns
    -------
    Path
        Path to sample JSON file
    """
    json_file = tmp_path / "sample.json"
    json_file.write_text(json.dumps({"key": "value", "number": 42}))
    return json_file


@pytest.fixture
def malformed_json_file(tmp_path: Path) -> Path:
    """Create a malformed JSON file for testing.

    Parameters
    ----------
    tmp_path : Path
        Pytest tmp_path fixture

    Returns
    -------
    Path
        Path to malformed JSON file
    """
    json_file = tmp_path / "malformed.json"
    json_file.write_text("{invalid json")
    return json_file
