"""Fixtures for command integration tests."""

import contextlib
import os
import shutil
import subprocess
from pathlib import Path

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
