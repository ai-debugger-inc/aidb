"""Fixtures for discovery module tests."""

from unittest.mock import Mock

import pytest


def _create_mock_capabilities(
    conditional_breakpoints: bool = True,
    logpoints: bool = True,
    data_breakpoints: bool = False,
    function_breakpoints: bool = True,
) -> Mock:
    """Create mock adapter capabilities."""
    caps = Mock()
    caps.conditional_breakpoints = conditional_breakpoints
    caps.logpoints = logpoints
    caps.data_breakpoints = data_breakpoints
    caps.function_breakpoints = function_breakpoints
    return caps


@pytest.fixture
def mock_adapter_registry() -> Mock:
    """Create a mock AdapterRegistry for testing.

    Returns
    -------
    Mock
        Mock registry with python and javascript adapter configs
    """
    mock_registry = Mock()

    python_config = Mock(
        language="python",
        file_extensions=[".py", ".pyw"],
        capabilities=_create_mock_capabilities(),
    )
    javascript_config = Mock(
        language="javascript",
        file_extensions=[".js", ".mjs"],
        capabilities=_create_mock_capabilities(),
    )

    mock_registry._configs = {
        "python": python_config,
        "javascript": javascript_config,
    }

    # Set up get_adapter_config to return the appropriate config
    def get_adapter_config(lang: str):
        return mock_registry._configs.get(lang.lower())

    mock_registry.get_adapter_config = get_adapter_config

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
