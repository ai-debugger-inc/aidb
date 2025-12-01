"""Pytest configuration and fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def clear_pytest_env_leakage():
    """Clear pytest env vars that would interfere with debugged pytest subprocess.

    When running pytest e2e tests, the outer pytest process sets environment variables
    like PYTEST_ADDOPTS that get inherited by debugged pytest subprocesses. This causes
    test filtering/deselection in the debugged process.

    This fixture clears these vars before each test and restores them after.
    """
    vars_to_clear = ["PYTEST_ADDOPTS", "PYTEST_CURRENT_TEST"]
    saved = {k: os.environ.pop(k, None) for k in vars_to_clear}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
