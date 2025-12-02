"""Fixtures for command integration tests."""

import contextlib
import io
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def cleanup_aidb_containers():
    """Ensure all AIDB-managed containers are stopped after each test.

    This fixture automatically runs after every test in the integration suite to prevent
    test pollution from Docker containers left running by previous tests.
    """
    yield  # Test runs here

    # After test completes, force stop any remaining AIDB containers
    try:
        # Find containers with AIDB label
        result = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "label=com.aidb.managed=true"],
            capture_output=True,
            text=True,
            check=False,
        )

        container_ids = result.stdout.strip()
        if container_ids:
            # Stop all found containers
            subprocess.run(
                ["docker", "stop"] + container_ids.split(),
                capture_output=True,
                check=False,
                timeout=10,
            )
    except Exception:  # noqa: S110
        # Best effort cleanup - don't fail tests if cleanup fails
        pass


@pytest.fixture(scope="session", autouse=True)
def preserve_adapter_cache():
    """Preserve user's built adapters during integration test session.

    Integration tests that invoke 'adapters clean' will operate on a clean cache, while
    the user's actual built adapters are safely backed up and restored.
    """
    # Get repo root
    current = Path(__file__).parent
    while current.parent != current:
        if (current / ".git").exists():
            repo_root = current
            break
        current = current.parent
    else:
        yield
        return

    cache_dir = repo_root / ".cache" / "adapters"
    backup_dir = repo_root / ".cache" / "adapters.backup"

    # Backup existing cache before test session starts
    if cache_dir.exists():
        # Remove any stale backup from previous interrupted runs
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.move(str(cache_dir), str(backup_dir))

    yield  # Entire test session runs here with clean cache

    # Restore after test session completes
    # Only delete cache if we have a backup to restore from
    try:
        if backup_dir.exists():
            # Safe to delete cache since we have a backup
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            # Restore the backup
            shutil.move(str(backup_dir), str(cache_dir))
    except Exception:
        # If restore fails, preserve the backup at minimum
        # Move backup back if cache deletion succeeded but restore failed
        if backup_dir.exists() and not cache_dir.exists():
            with contextlib.suppress(Exception):
                shutil.move(str(backup_dir), str(cache_dir))


# Standard pytest output for mock - simulates successful test run
MOCK_PYTEST_OUTPUT = """\
============================= test session starts ==============================
platform darwin -- Python 3.11.0, pytest-7.4.0, pluggy-1.0.0
rootdir: /Users/test/project
collected 5 items

tests/test_example.py .....                                               [100%]

============================== 5 passed in 0.25s ===============================
"""

# Pytest output for when no tests match the filter
MOCK_PYTEST_NO_TESTS_OUTPUT = """\
============================= test session starts ==============================
platform darwin -- Python 3.11.0, pytest-7.4.0, pluggy-1.0.0
rootdir: /Users/test/project
collected 0 items

============================= no tests ran in 0.01s ============================
"""


@pytest.fixture
def mock_test_execution(mocker):
    """Mock subprocess.Popen to avoid actual test execution.

    This fixture mocks the test execution at the subprocess level, preventing
    actual pytest invocations while still testing CLI orchestration logic.

    Returns
    -------
    MagicMock
        The mocked Popen instance for assertions
    """
    # Create a mock process that simulates successful pytest execution
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.wait.return_value = 0
    mock_process.poll.return_value = 0

    # Create file-like objects for stdout/stderr
    mock_process.stdout = io.StringIO(MOCK_PYTEST_OUTPUT)
    mock_process.stderr = io.StringIO("")

    # Make stdout iterable for line-by-line reading
    mock_process.stdout.__iter__ = lambda self: iter(self.getvalue().splitlines(True))

    # Patch subprocess.Popen in the test execution service
    return mocker.patch(
        "aidb_cli.services.test.test_execution_service.subprocess.Popen",
        return_value=mock_process,
    )


@pytest.fixture
def mock_test_execution_no_tests(mocker):
    """Mock subprocess.Popen for scenarios where no tests are collected.

    Use this fixture for tests that verify behavior with invalid patterns/markers.

    Returns
    -------
    MagicMock
        The mocked Popen instance for assertions
    """
    mock_process = MagicMock()
    mock_process.returncode = 5  # pytest exit code for no tests collected
    mock_process.wait.return_value = 5
    mock_process.poll.return_value = 5

    mock_process.stdout = io.StringIO(MOCK_PYTEST_NO_TESTS_OUTPUT)
    mock_process.stderr = io.StringIO("")
    mock_process.stdout.__iter__ = lambda self: iter(self.getvalue().splitlines(True))

    return mocker.patch(
        "aidb_cli.services.test.test_execution_service.subprocess.Popen",
        return_value=mock_process,
    )
