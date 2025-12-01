"""Port configuration for AIDB test suite."""

from enum import IntEnum


class DebugPorts(IntEnum):
    """Standard debug adapter ports for different languages."""

    PYTHON = 5678
    PYTHON_ALT = 5679
    JAVASCRIPT = 9229
    JAVASCRIPT_ALT = 9230
    JAVA = 5005
    JAVA_ALT = 5006

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
