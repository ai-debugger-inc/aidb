"""Pytest configuration and fixtures for framework tests."""

import logging
import os
from collections.abc import Generator

import pytest

from aidb_common.network import allocate_port, release_port

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def dynamic_dap_port_ranges() -> None:
    """Adjust DAP port ranges per pytest-xdist worker to prevent port conflicts.

    The debug adapter (debugpy) needs to bind to a port for DAP communication.
    By default, Python uses fallback_port_ranges=[6000, 7000], giving 200 ports
    (100 per range). With 4 parallel workers, this causes contention.

    This fixture assigns worker-specific port ranges:
    - master (no parallelism): 6000, 7000 (default)
    - gw0: 6200, 7200
    - gw1: 6400, 7400
    - gw2: 6600, 7600
    - gw3: 6800, 7800

    Each worker gets its own 200-port block, eliminating cross-worker contention.
    """
    from aidb.session.adapter_registry import AdapterRegistry
    from aidb_common.constants import Language

    # Get worker ID from pytest-xdist
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    worker_num = 0 if worker_id == "master" else int(worker_id[2:]) + 1

    # Calculate worker-specific offset (200 ports per worker)
    port_offset = worker_num * 200

    # Get the adapter registry and modify Python config's port ranges
    registry = AdapterRegistry()

    # Ensure adapters are discovered so configs exist
    try:
        config = registry.get_adapter_config(Language.PYTHON.value)
        old_ranges = config.fallback_port_ranges
        # Modify fallback_port_ranges in place with worker-specific offset
        config.fallback_port_ranges = [6000 + port_offset, 7000 + port_offset]
        logger.info(
            "DAP port ranges adjusted for worker %s: %s -> %s",
            worker_id,
            old_ranges,
            config.fallback_port_ranges,
        )
    except Exception as e:  # noqa: BLE001
        # Registry may not be ready during fixture setup; config will get
        # correct defaults when first used. This is a best-effort optimization.
        logger.debug("Could not adjust DAP port ranges: %s", e)


@pytest.fixture(autouse=True)
def dynamic_app_port(monkeypatch: pytest.MonkeyPatch) -> Generator[int, None, None]:
    """Allocate APP_PORT atomically using cross-process file-locked allocator.

    This fixture uses CrossProcessPortAllocator which provides:
    - File-based registry (~/.aidb/port_registry.json) with fcntl.flock()
    - Socket binding verification to handle TIME_WAIT states
    - Automatic cleanup of stale leases from crashed processes

    Each pytest-xdist worker gets its own port range:
    - master (no parallelism): 10000-10999
    - gw0: 11000-11999
    - gw1: 12000-12999
    - gw2: 13000-13999
    - etc.

    Yields
    ------
    int
        The allocated port number
    """
    # Get worker ID from pytest-xdist
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    worker_num = 0 if worker_id == "master" else int(worker_id[2:]) + 1

    # Each worker gets 1000 ports in its own range
    range_start = 10000 + (worker_num * 1000)

    # Allocate port atomically using cross-process allocator
    port = allocate_port(range_start=range_start, range_size=1000)

    logger.debug(
        "Allocated APP_PORT %d for worker %s (range %d-%d)",
        port,
        worker_id,
        range_start,
        range_start + 1000,
    )

    monkeypatch.setenv("APP_PORT", str(port))

    yield port

    # Release port when test completes
    release_port(port)
    logger.debug("Released APP_PORT %d", port)
