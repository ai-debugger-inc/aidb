"""Environment detection and configuration for AIDB test suite."""

import os
from enum import Enum
from pathlib import Path


class EnvVar(Enum):
    """Environment variables used in tests."""

    # Logging
    AIDB_LOG_LEVEL = "AIDB_LOG_LEVEL"
    AIDB_TEST_LOG_LEVEL = "AIDB_TEST_LOG_LEVEL"
    AIDB_ADAPTER_TRACE = "AIDB_ADAPTER_TRACE"

    # Test mode
    AIDB_TEST_MODE = "AIDB_TEST_MODE"
    AIDB_DISABLE_TELEMETRY = "AIDB_DISABLE_TELEMETRY"
    DEBUG_TESTS = "DEBUG_TESTS"

    # Configuration
    AIDB_WORKSPACE = "AIDB_WORKSPACE"

    # Language-specific
    PYTHONDONTWRITEBYTECODE = "PYTHONDONTWRITEBYTECODE"
    NODE_ENV = "NODE_ENV"
    JAVA_HOME = "JAVA_HOME"


def is_running_in_container() -> bool:
    """Detect if tests are running inside a Docker container.

    Returns
    -------
    bool
        True if running in a container, False otherwise

    Notes
    -----
    Checks for common container indicators:
    - /.dockerenv file (Docker-specific)
    - /run/.containerenv (Podman-specific)
    - container=docker in /proc/1/environ (systemd-based)
    """
    # Check for Docker-specific file
    if Path("/.dockerenv").exists():
        return True

    # Check for Podman-specific file
    if Path("/run/.containerenv").exists():
        return True

    # Check /proc/1/environ for container= entry
    try:
        with Path("/proc/1/environ").open() as f:
            environ = f.read()
            if "container=docker" in environ or "container=podman" in environ:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


# Cache the result since it won't change during test run
_IS_CONTAINER = is_running_in_container()


def get_container_multiplier() -> float:
    """Get performance multiplier for container environments.

    Returns
    -------
    float
        Performance multiplier (1.0 for native, 2.5 for GitHub Actions CI, 1.3 for other containers)

    Notes
    -----
    Container environments typically show ~20-30% performance degradation
    due to resource constraints, I/O overhead, and networking layers.

    GitHub Actions CI runners show significantly higher variance (1.9-2.4x slower)
    due to shared virtualization, network latency, and resource contention.
    The 2.5x multiplier is data-driven from actual CI failures and provides
    5% headroom for variance while still validating performance.
    """
    # GitHub Actions CI environments need higher multiplier due to shared resources
    if os.getenv("GITHUB_ACTIONS") == "true":
        return 2.5

    # Standard container environments (Docker local, etc.)
    return 1.3 if _IS_CONTAINER else 1.0


__all__ = [
    "EnvVar",
    "get_container_multiplier",
    "is_running_in_container",
]
