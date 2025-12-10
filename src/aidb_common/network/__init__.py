"""Network utilities for AIDB.

This module provides portable network utilities that can be used across the AIDB
codebase and tests without introducing circular dependencies.

For cross-process atomic port allocation, use allocate_port() and release_port(). These
functions use file locking to ensure no two processes allocate the same port.
"""

from aidb_common.network.allocator import (
    CrossProcessPortAllocator,
    allocate_port,
    get_allocator,
    release_port,
)
from aidb_common.network.ports import (
    find_available_port,
    get_ephemeral_port,
    is_port_available,
    reserve_port,
)

__all__ = [
    # Cross-process atomic allocation (preferred)
    "CrossProcessPortAllocator",
    "allocate_port",
    "get_allocator",
    "release_port",
    # Lightweight utilities (no cross-process coordination)
    "find_available_port",
    "get_ephemeral_port",
    "is_port_available",
    "reserve_port",
]
