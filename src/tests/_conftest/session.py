"""Session-scoped pytest fixtures.

This module provides fixtures that run once per test session, including event loop
management, environment setup, and session cleanup.
"""

import asyncio
import contextlib
import logging
import os

import pytest

from tests._helpers.constants import EnvVar, LogLevel


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session.

    This ensures all async tests share the same event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Harden shutdown to avoid asyncio warnings on suite teardown
    try:
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        with contextlib.suppress(Exception):
            loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment once per session."""
    # Set test environment variables
    os.environ[EnvVar.AIDB_TEST_MODE.value] = "1"
    os.environ[EnvVar.AIDB_DISABLE_TELEMETRY.value] = "1"

    # Ensure debug logging if requested
    if os.getenv(EnvVar.DEBUG_TESTS.value):
        os.environ[EnvVar.AIDB_LOG_LEVEL.value] = LogLevel.DEBUG.value
        os.environ[EnvVar.AIDB_ADAPTER_TRACE.value] = "1"

    return


@pytest.fixture(scope="session", autouse=True)
def deterministic_session_environment():
    """Apply basic deterministic settings for the entire test session.

    - Force UTC timezone when supported
    - Seed Python PRNGs (and NumPy if available)
    """
    # Timezone determinism
    os.environ.setdefault("TZ", "UTC")
    with contextlib.suppress(Exception):
        import time

        if hasattr(time, "tzset"):
            time.tzset()

    # Randomness determinism
    with contextlib.suppress(Exception):
        import random

        random.seed(0)

    with contextlib.suppress(Exception):
        import numpy as np  # type: ignore

        np.random.seed(0)  # type: ignore[attr-defined]


@pytest.fixture(scope="session", autouse=True)
async def cleanup_jdtls_project_pool():
    """Shut down per-project JDT LS pool at end of test session.

    The per-project pool is used when tests debug real Java files (not the shared test
    pool used by generated programs). Without explicit cleanup, pooled bridges remain
    alive with unclosed transports when pytest closes the event loop, causing
    ResourceWarnings.
    """
    yield  # Let all tests run first

    # Cleanup before event loop closes
    try:
        from aidb.adapters.lang.java.jdtls_project_pool import (
            shutdown_jdtls_project_pool,
        )

        await shutdown_jdtls_project_pool()
    except Exception as e:
        logging.getLogger("tests.cleanup").warning(
            "Failed to shutdown per-project JDT LS pool: %s",
            e,
        )
