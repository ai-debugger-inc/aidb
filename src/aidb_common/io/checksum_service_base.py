"""Base class for services that track file checksums for cache invalidation.

This module provides a shared foundation for services that need to detect file changes
and determine when cached artifacts need to be regenerated.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from aidb_common.io.files import ensure_dir, read_cache_file, write_cache_file
from aidb_logging import get_logger

logger = get_logger(__name__)


class ChecksumServiceBase(ABC):
    """Abstract base class for checksum-based cache invalidation services.

    This class provides common functionality for services that track file checksums
    to determine when cached artifacts (Docker images, installed dependencies, etc.)
    need to be regenerated or reinstalled.

    Subclasses must implement:
    - _get_hash_cache_file(): Define cache file naming
    - _compute_hash(): Define what to hash
    - _exists(): Check if cached artifact exists

    Examples
    --------
    >>> class MyChecksumService(ChecksumServiceBase):
    ...     def _get_hash_cache_file(self, identifier):
    ...         return self.cache_dir / f"{identifier}-hash"
    ...     def _compute_hash(self, identifier):
    ...         return compute_files_hash([Path("file.txt")])
    ...     def _exists(self, identifier):
    ...         return Path("artifact").exists()
    >>> service = MyChecksumService(Path("/cache"))
    >>> needs_update, reason = service.needs_update("my-artifact")
    """

    def __init__(self, cache_dir: Path) -> None:
        """Initialize the checksum service.

        Parameters
        ----------
        cache_dir : Path
            Directory for storing hash cache files
        """
        self.cache_dir = cache_dir
        ensure_dir(self.cache_dir)

    @abstractmethod
    def _get_hash_cache_file(self, identifier: str) -> Path:
        """Get path to hash cache file for identifier.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact

        Returns
        -------
        Path
            Path to cache file
        """

    @abstractmethod
    def _compute_hash(self, identifier: str) -> str:
        """Compute current hash for identifier.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact

        Returns
        -------
        str
            Hash value (typically SHA256 hex digest)
        """

    @abstractmethod
    def _exists(self, identifier: str) -> bool:
        """Check if cached artifact exists.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact

        Returns
        -------
        bool
            True if artifact exists
        """

    def _get_artifact_context(self, identifier: str) -> dict[str, str]:  # noqa: ARG002
        """Get context metadata that invalidates cache when changed.

        Override this method to provide environment-specific context that should
        invalidate the cache even when file hashes match. For example, container
        ID in containerized environments where artifacts don't persist across
        container restarts.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact (used by subclasses)

        Returns
        -------
        dict[str, str]
            Context metadata (e.g., {"container_id": "abc123"})
            Default returns empty dict (no context tracking)
        """
        return {}

    def _get_cached_hash(self, identifier: str) -> str | None:
        """Get cached hash for identifier.

        Parameters
        ----------
        identifier : str
            Unique identifier

        Returns
        -------
        str | None
            Cached hash or None if not found
        """
        cache_file = self._get_hash_cache_file(identifier)
        content = read_cache_file(cache_file)
        if not content:
            return None

        # Cache format: Line 1 = hash, Line 2 = context JSON (optional)
        lines = content.strip().split("\n")
        cached_hash = lines[0] if lines else None

        logger.debug(
            "Read cached hash for %s from %s: %s",
            identifier,
            cache_file,
            cached_hash[:16] if cached_hash else "None",
        )
        return cached_hash

    def _get_cached_context(self, identifier: str) -> dict[str, str]:
        """Get cached context metadata for identifier.

        Parameters
        ----------
        identifier : str
            Unique identifier

        Returns
        -------
        dict[str, str]
            Cached context metadata or empty dict if not found
        """
        cache_file = self._get_hash_cache_file(identifier)
        content = read_cache_file(cache_file)
        if not content:
            return {}

        # Cache format: Line 1 = hash, Line 2 = context JSON (optional)
        lines = content.strip().split("\n")
        if len(lines) < 2:
            return {}

        try:
            context = json.loads(lines[1])
            logger.debug("Read cached context for %s: %s", identifier, context)
            return context
        except (json.JSONDecodeError, IndexError):
            logger.warning(
                "Failed to parse cached context for %s, treating as empty",
                identifier,
            )
            return {}

    def _save_hash(self, identifier: str, hash_value: str) -> None:
        """Save hash and context to cache.

        Parameters
        ----------
        identifier : str
            Unique identifier
        hash_value : str
            Hash value to save
        """
        cache_file = self._get_hash_cache_file(identifier)

        # Cache format: Line 1 = hash, Line 2 = context JSON (if present)
        content = hash_value + "\n"

        context = self._get_artifact_context(identifier)
        if context:
            content += json.dumps(context) + "\n"
            logger.debug("Saving context for %s: %s", identifier, context)

        write_cache_file(cache_file, content.strip())
        logger.debug(
            "Saved hash for %s to %s: %s",
            identifier,
            cache_file,
            hash_value[:16],
        )

    def needs_update(self, identifier: str) -> tuple[bool, str]:
        """Check if cached artifact needs updating.

        Compares current file hashes against cached hashes to determine
        if the artifact needs to be regenerated.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact

        Returns
        -------
        tuple[bool, str]
            (needs_update, reason) where reason explains why update is needed
            or why it's not needed

        Examples
        --------
        >>> service = MyChecksumService(Path("/cache"))
        >>> needs_update, reason = service.needs_update("my-artifact")
        >>> print(f"Update: {needs_update}, Reason: {reason}")
        Update: True, Reason: Source files changed (hash mismatch)
        """
        # Check if artifact exists
        exists = self._exists(identifier)
        if not exists:
            logger.debug("Checksum check for %s: needs update (not found)", identifier)
            return True, f"Artifact '{identifier}' not found"

        # Check artifact context (e.g., container lifecycle)
        current_context = self._get_artifact_context(identifier)
        cached_context = self._get_cached_context(identifier)

        if current_context != cached_context:
            logger.debug(
                "Checksum check for %s: needs update (context changed: %s -> %s)",
                identifier,
                cached_context,
                current_context,
            )
            return True, "Artifact context changed (e.g., container restart)"

        # Compare hashes
        current_hash = self._compute_hash(identifier)
        cached_hash = self._get_cached_hash(identifier)

        if cached_hash is None:
            logger.debug(
                "Checksum check for %s: needs update (no cached hash)",
                identifier,
            )
            return True, "No cached hash found (first run)"

        if cached_hash != current_hash:
            logger.debug(
                "Checksum check for %s: needs update (hash: %s -> %s)",
                identifier,
                cached_hash[:8],
                current_hash[:8],
            )
            return True, "Source files changed (hash mismatch)"

        logger.debug("Checksum check for %s: up-to-date", identifier)
        return False, "Up-to-date"

    def mark_updated(self, identifier: str) -> None:
        """Mark artifact as updated by saving current hash.

        Call this after successfully generating/installing an artifact
        to update the cached hash and prevent unnecessary future updates.

        Parameters
        ----------
        identifier : str
            Unique identifier for the cached artifact
        """
        current_hash = self._compute_hash(identifier)
        self._save_hash(identifier, current_hash)
        logger.debug(
            "Marked %s as updated (hash: %s)",
            identifier,
            current_hash[:8],
        )
