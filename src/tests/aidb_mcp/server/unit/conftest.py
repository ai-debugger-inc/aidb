"""Pytest configuration and fixtures for aidb_mcp.server unit tests."""

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

    Yields
    ------
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
    # Force reload NOW while env vars are patched
    config_module.get_config()

    yield log_file

    # Cleanup: reset config so subsequent tests get fresh state
    config_module._config = None


@pytest.fixture(autouse=True)
def clear_span_history():
    """Clear span history and reset config before and after each test.

    This fixture automatically clears performance tracking history and resets the
    MCP config singleton to ensure test isolation. It runs before and after every
    test in this directory.

    Yields
    ------
    None
    """
    import aidb_common.config.runtime as runtime_module
    import aidb_mcp.core.config as config_module
    from aidb_mcp.core.performance import _span_history, _timing_history

    # Clear performance history
    _span_history.clear()
    _timing_history.clear()

    # Reset config singletons so test fixtures can set them up fresh
    config_module._config = None
    runtime_module._config_manager = None

    yield

    # Cleanup after test
    _span_history.clear()
    _timing_history.clear()
    config_module._config = None
    runtime_module._config_manager = None
