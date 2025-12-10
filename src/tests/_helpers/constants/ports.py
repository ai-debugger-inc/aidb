"""Port configuration for AIDB test suite."""

from enum import IntEnum

from aidb.api.constants import (
    DEFAULT_JAVA_DEBUG_PORT,
    DEFAULT_NODE_DEBUG_PORT,
    DEFAULT_PYTHON_DEBUG_PORT,
)


class DebugPorts(IntEnum):
    """Standard debug adapter ports for different languages.

    Values are derived from source constants to ensure consistency.
    """

    PYTHON = DEFAULT_PYTHON_DEBUG_PORT
    PYTHON_ALT = DEFAULT_PYTHON_DEBUG_PORT + 1
    JAVASCRIPT = DEFAULT_NODE_DEBUG_PORT
    JAVASCRIPT_ALT = DEFAULT_NODE_DEBUG_PORT + 1
    JAVA = DEFAULT_JAVA_DEBUG_PORT
    JAVA_ALT = DEFAULT_JAVA_DEBUG_PORT + 1

    # Test port ranges (avoid conflicts with real services)
    TEST_BASE = 40000
    TEST_MAX = 50000


class PortRanges:
    """Port range configurations for fallback allocation."""

    PYTHON = [15678, 25678, 35678]
    JAVASCRIPT = [19229, 29229, 39229]
    JAVA = [15005, 25005, 35005]
    DEFAULT = [20000, 30000, 40000]


__all__ = [
    "DebugPorts",
    "PortRanges",
]
