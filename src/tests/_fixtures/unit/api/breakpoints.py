"""Mock breakpoint and registry fixtures for API unit tests.

Provides mock breakpoint specifications and registry objects for testing breakpoint
operations without actual debug adapter interactions.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_adapter_registry() -> MagicMock:
    """Mock AdapterRegistry for language resolution.

    Returns
    -------
    MagicMock
        Mock registry with resolve_lang_for_target method
    """
    registry = MagicMock()
    registry.resolve_lang_for_target.return_value = "python"
    return registry


@pytest.fixture
def sample_breakpoint_spec() -> dict[str, Any]:
    """Sample breakpoint specification.

    Returns
    -------
    dict[str, Any]
        Single breakpoint spec with file and line
    """
    return {"file": "/path/to/test.py", "line": 10}


@pytest.fixture
def sample_breakpoint_specs() -> list[dict[str, Any]]:
    """Multiple breakpoint specifications.

    Returns
    -------
    list[dict[str, Any]]
        List of breakpoint specs for testing batch operations
    """
    return [
        {"file": "/path/to/test.py", "line": 10},
        {"file": "/path/to/test.py", "line": 20},
        {"file": "/path/to/other.py", "line": 5},
    ]


@pytest.fixture
def mock_breakpoint_converter() -> MagicMock:
    """Mock BreakpointConverter.

    Returns
    -------
    MagicMock
        Mock converter with convert method returning empty list
    """
    converter = MagicMock()
    converter.convert.return_value = []
    return converter
