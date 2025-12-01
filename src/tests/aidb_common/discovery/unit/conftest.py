"""Fixtures for discovery module tests."""

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_adapter_registry() -> Mock:
    """Create a mock AdapterRegistry for testing.

    Returns
    -------
    Mock
        Mock registry with python and javascript adapter configs
    """
    mock_registry = Mock()
    mock_registry._configs = {
        "python": Mock(
            language="python",
            file_extensions=[".py", ".pyw"],
            supports_conditional_breakpoints=True,
            supports_logpoints=True,
            supports_data_breakpoints=False,
            supports_function_breakpoints=True,
        ),
        "javascript": Mock(
            language="javascript",
            file_extensions=[".js", ".mjs"],
            supports_conditional_breakpoints=True,
            supports_logpoints=False,
            supports_data_breakpoints=False,
            supports_function_breakpoints=False,
        ),
    }
    return mock_registry


@pytest.fixture
def mock_hit_condition_modes() -> list[Mock]:
    """Create mock hit condition modes.

    Returns
    -------
    list[Mock]
        List of mock hit condition modes (EXACT, MODULO, GREATER_THAN, GREATER_EQUAL)
    """
    modes = []
    for name in ["EXACT", "MODULO", "GREATER_THAN", "GREATER_EQUAL"]:
        mode = Mock()
        mode.name = name
        modes.append(mode)
    return modes
