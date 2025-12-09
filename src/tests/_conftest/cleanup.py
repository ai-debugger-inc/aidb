"""Test cleanup fixtures.

This module provides autouse fixtures that clean up resources after tests, including
orphaned processes, ports, and global state.
"""

import contextlib
import logging
import os

import pytest


@pytest.fixture(autouse=True)
def cleanup_orphaned_processes(request):
    """Clean up orphaned AIDB processes after tests that need it.

    This is a defense-in-depth safety net that runs after normal session cleanup.
    Optimized to skip cleanup for tests that don't create processes (unit tests, etc.).

    Runs cleanup for:
    - Tests in integration/ or e2e/ directories
    - Tests marked with @pytest.mark.requires_cleanup
    - Tests using debug_interface, debug_session, or similar fixtures
    """
    # Skip if running inside an AIDB-spawned debuggee process.
    # Must still yield even for early exit - pytest yield fixtures require this.
    if os.environ.get("AIDB_SESSION_ID"):
        yield
        return

    test_path = str(request.node.fspath)

    yield

    # Determine if cleanup is needed for this test
    needs_cleanup = False

    # Check test path - integration and e2e tests need cleanup
    if "/integration/" in test_path or "/e2e/" in test_path:
        needs_cleanup = True

    # Check for explicit marker
    if request.node.get_closest_marker("requires_cleanup"):
        needs_cleanup = True

    # Check if test uses fixtures that create processes
    process_fixtures = {"debug_interface", "debug_session", "jdtls_pool", "mcp_session"}
    if any(fixture in request.fixturenames for fixture in process_fixtures):
        needs_cleanup = True

    # Skip cleanup for tests that don't need it (fast path for unit tests)
    if not needs_cleanup:
        return

    # After test, run orphan cleanup
    cleanup_logger = logging.getLogger("tests.cleanup")
    try:
        from aidb.resources.orphan_cleanup import OrphanProcessCleaner

        # Get pool-managed session IDs to exclude from cleanup
        active_sessions = set()
        with contextlib.suppress(Exception):
            from tests._fixtures.java_session_pool import get_java_session_pool

            pool = get_java_session_pool()
            if pool:
                pool_sessions = pool.get_managed_session_ids()
                active_sessions.update(pool_sessions)

        cleaner = OrphanProcessCleaner(min_age_seconds=5.0)  # Lower threshold for tests
        terminated, failed = cleaner.cleanup_orphaned_processes(
            active_session_ids=active_sessions,
        )
        if terminated > 0 or failed > 0:
            cleanup_logger.debug(
                "Post-test orphan cleanup: %d terminated, %d failed",
                terminated,
                failed,
            )
    except Exception as e:
        cleanup_logger.error("Orphan cleanup failed: %s", e)


@pytest.fixture(autouse=True)
def cleanup_ports():
    """Clean up any allocated ports after each test."""
    from aidb.resources.ports import PortRegistry

    # Run the test
    yield

    # After test, clean up any leaked ports
    try:
        registry = PortRegistry()
        # Cleanup will happen automatically on next port acquisition
        # or we can force it here for test isolation
        registry.cleanup_stale_allocations()
    except Exception as e:
        msg = f"Failed to cleanup port registry: {e}"
        logging.debug(msg)


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset any global state between tests."""
    # This includes singletons and other stateful components
    from aidb_common.patterns import Singleton

    yield

    # Clear singleton instances to prevent test interference
    Singleton._instances.clear()

    # NOTE: Do NOT clear MCP session state globally (_DEBUG_SESSIONS, _SESSION_CONTEXTS)
    # This breaks parallel test execution (pytest -n 4) because when one test finishes,
    # it would clear sessions belonging to other still-running tests.
    # Each test cleans up its own session via debug_interface.stop_session().
    # The cleanup_orphaned_processes fixture handles any truly leaked processes.
