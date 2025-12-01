"""Pytest configuration and fixtures for aidb_mcp.core integration tests."""

import pytest


@pytest.fixture
def enable_timing(monkeypatch, tmp_path):
    """Enable performance timing for tests.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture
    tmp_path : pathlib.Path
        Pytest temporary directory fixture

    Returns
    -------
    pathlib.Path
        Path to temporary log file
    """
    log_file = tmp_path / "test-perf.log"

    monkeypatch.setenv("AIDB_MCP_TIMING", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_DETAILED", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_FILE", str(log_file))
    monkeypatch.setenv("AIDB_MCP_TIMING_FORMAT", "text")

    import aidb_mcp.core.config as config_module

    config_module._config = None

    return log_file


@pytest.fixture
def enable_json_timing(monkeypatch, tmp_path):
    """Enable JSON performance timing for tests.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture
    tmp_path : pathlib.Path
        Pytest temporary directory fixture

    Returns
    -------
    pathlib.Path
        Path to temporary log file
    """
    log_file = tmp_path / "test-perf.json"

    monkeypatch.setenv("AIDB_MCP_TIMING", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_DETAILED", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_FILE", str(log_file))
    monkeypatch.setenv("AIDB_MCP_TIMING_FORMAT", "json")

    import aidb_mcp.core.config as config_module

    config_module._config = None

    return log_file


@pytest.fixture
def enable_csv_timing(monkeypatch, tmp_path):
    """Enable CSV performance timing for tests.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture
    tmp_path : pathlib.Path
        Pytest temporary directory fixture

    Returns
    -------
    pathlib.Path
        Path to temporary log file
    """
    log_file = tmp_path / "test-perf.csv"

    monkeypatch.setenv("AIDB_MCP_TIMING", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_DETAILED", "1")
    monkeypatch.setenv("AIDB_MCP_TIMING_FILE", str(log_file))
    monkeypatch.setenv("AIDB_MCP_TIMING_FORMAT", "csv")

    import aidb_mcp.core.config as config_module

    config_module._config = None

    return log_file


@pytest.fixture
def clear_span_history():
    """Clear span history before test.

    Yields
    ------
    None
    """
    from aidb_mcp.core.performance import _span_history, _timing_history

    _span_history.clear()
    _timing_history.clear()

    yield

    _span_history.clear()
    _timing_history.clear()
