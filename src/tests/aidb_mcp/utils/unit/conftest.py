"""Pytest configuration and fixtures for aidb_mcp.utils unit tests."""

import pytest


@pytest.fixture
def sample_response():
    """Sample MCP response for testing.

    Returns
    -------
    dict
        Sample response dictionary
    """
    return {
        "success": True,
        "data": {
            "code_context": "x" * 2000,  # Large field
            "variables": {"a": 1, "b": 2, "c": 3},
            "stack_frames": [
                {"function": "main", "line": 10},
                {"function": "helper", "line": 25},
            ],
        },
        "message": "Operation completed",
        "next_steps": ["step", "continue", "inspect"],
    }


@pytest.fixture
def large_response():
    """Large MCP response for stress testing.

    Returns
    -------
    dict
        Large response dictionary
    """
    return {
        "success": True,
        "data": {
            "code_context": "x" * 10000,
            "variables": {f"var_{i}": i for i in range(100)},
            "output": ["line " * 100 for _ in range(50)],
        },
        "message": "Large operation completed",
    }


@pytest.fixture
def small_response():
    """Small MCP response for testing.

    Returns
    -------
    dict
        Small response dictionary
    """
    return {
        "success": True,
        "message": "OK",
    }
