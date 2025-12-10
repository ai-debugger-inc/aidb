"""IO utilities for AIDB common.

Provides safe file operations, atomic writes, structured data handling, file hashing for
cache invalidation and rebuild detection, and subprocess transport cleanup.
"""

from .checksum_service_base import ChecksumServiceBase
from .files import (
    FileOperationError,
    atomic_write,
    ensure_dir,
    read_cache_file,
    safe_read_json,
    safe_write_json,
    write_cache_file,
)
from .hashing import compute_files_hash, compute_pattern_hash
from .subprocess import close_subprocess_transports, is_event_loop_error

__all__ = [
    "ChecksumServiceBase",
    "FileOperationError",
    "safe_read_json",
    "safe_write_json",
    "atomic_write",
    "ensure_dir",
    "read_cache_file",
    "write_cache_file",
    "compute_files_hash",
    "compute_pattern_hash",
    "close_subprocess_transports",
    "is_event_loop_error",
]
