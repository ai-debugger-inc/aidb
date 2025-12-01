"""File hashing utilities for detecting changes in source files.

This module provides centralized hashing functions used across AIDB for detecting file
changes in build systems, cache invalidation, and incremental rebuild detection.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path


def compute_files_hash(
    file_paths: Sequence[Path | str],
    *,
    hash_algorithm: str = "sha256",
) -> str:
    """Compute hash of multiple files to detect changes.

    This function computes a single hash value representing the combined
    state of all provided files. It's useful for cache invalidation and
    detecting when a rebuild is needed.

    Parameters
    ----------
    file_paths : Sequence[Path | str]
        Paths to files to include in hash computation. Files are processed
        in the order provided. Non-existent files are skipped with a debug
        log message.
    hash_algorithm : str, optional
        Hash algorithm to use. Must be supported by hashlib (default: sha256)

    Returns
    -------
    str
        Hexadecimal hash digest representing the combined state of all files

    Examples
    --------
    >>> from pathlib import Path
    >>> files = [Path("pyproject.toml"), Path("setup.py")]
    >>> hash_value = compute_files_hash(files)
    >>> len(hash_value)  # SHA256 produces 64 hex characters
    64

    Notes
    -----
    - Both the file path and file content are included in the hash
    - Files are processed in the exact order provided (order matters)
    - Non-existent files are skipped (not an error)
    - Empty file list returns hash of empty string
    """
    hasher = hashlib.new(hash_algorithm)

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            # Lazy import to avoid circular dependency
            from aidb_logging import get_logger

            get_logger(__name__).debug("Skipping non-existent file in hash: %s", path)
            continue

        # Include file path in hash for uniqueness
        # This ensures that moving/renaming files changes the hash
        hasher.update(str(path).encode("utf-8"))

        # Include file content
        hasher.update(path.read_bytes())

    return hasher.hexdigest()


def compute_pattern_hash(
    base_path: Path,
    patterns: Sequence[str],
    *,
    hash_algorithm: str = "sha256",
) -> str:
    """Compute hash of files matching glob patterns.

    This function finds all files matching the provided glob patterns
    and computes a single hash representing their combined state. Useful
    for tracking changes in entire directories or file groups.

    Parameters
    ----------
    base_path : Path
        Base directory to search from
    patterns : Sequence[str]
        Glob patterns to match (e.g., ["*.py", "**/*.yaml"])
        Supports standard glob syntax including:
        - * matches any characters within a filename
        - ** matches any characters including path separators
        - ? matches any single character
        - [seq] matches any character in seq
    hash_algorithm : str, optional
        Hash algorithm to use. Must be supported by hashlib (default: sha256)

    Returns
    -------
    str
        Hexadecimal hash digest of all matching files

    Examples
    --------
    >>> from pathlib import Path
    >>> base = Path("src/tests/_docker")
    >>> patterns = ["*.yaml", "dockerfiles/*.dockerfile"]
    >>> hash_value = compute_pattern_hash(base, patterns)

    Notes
    -----
    - Files are sorted before hashing to ensure deterministic results
    - Duplicate matches from overlapping patterns are not deduplicated
    - Empty match results in hash of empty string
    """
    matching_files: list[Path] = []
    for pattern in patterns:
        matching_files.extend(base_path.glob(pattern))

    # Sort for deterministic ordering regardless of filesystem
    # This ensures consistent hashes across different environments
    matching_files.sort()

    return compute_files_hash(matching_files, hash_algorithm=hash_algorithm)
