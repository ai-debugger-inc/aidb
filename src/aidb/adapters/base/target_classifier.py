"""Centralized target classification for debugging.

This module provides a single source of truth for determining whether a target
string represents a file path or an identifier (class name, module, etc.).

The classification logic is used by:
- MCP layer for target validation
- Session layer for target normalization
- Adapter layer for syntax validation
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class TargetClassification(NamedTuple):
    """Result of classifying a target string.

    Attributes
    ----------
    is_file_path : bool
        True if the target appears to be a file path, False if it's an identifier
    has_known_extension : bool
        True if the target has a known debuggable file extension (.py, .js, etc.)
    has_path_separator : bool
        True if the target contains path separators (/ or \\)
    """

    is_file_path: bool
    has_known_extension: bool
    has_path_separator: bool


class TargetClassifier:
    """Centralized target classification - single source of truth.

    Determines whether a target string is a file path or an identifier
    (class name, module name, etc.) based on:
    - Known file extensions from registered adapters
    - Presence of path separators

    Examples
    --------
    >>> classifier = TargetClassifier()
    >>> classifier.is_file_path("src/main.py")
    True
    >>> classifier.is_file_path("pytest")
    False
    >>> classifier.is_file_path("com.example.MyClass")
    False
    >>> classifier.is_file_path("./script.js")
    True
    """

    @staticmethod
    def _get_known_extensions() -> set[str]:
        """Get known file extensions from adapter registry.

        Returns
        -------
        set[str]
            All known debuggable file extensions
        """
        # Import here to avoid circular imports
        from aidb.session.adapter_registry import get_all_cached_file_extensions

        return get_all_cached_file_extensions()

    @classmethod
    def classify(cls, target: str) -> TargetClassification:
        """Classify a target string as file path or identifier.

        Parameters
        ----------
        target : str
            The target string to classify

        Returns
        -------
        TargetClassification
            Classification result with detailed information
        """
        if not target:
            return TargetClassification(
                is_file_path=False,
                has_known_extension=False,
                has_path_separator=False,
            )

        known_extensions = cls._get_known_extensions()
        path = Path(target)
        suffix_lower = path.suffix.lower()

        has_known_extension = suffix_lower in known_extensions
        has_path_separator = ("/" in target) or ("\\" in target)

        # A target is considered a file path if:
        # - It has a known debuggable extension, OR
        # - It contains path separators
        is_file_path = has_known_extension or has_path_separator

        return TargetClassification(
            is_file_path=is_file_path,
            has_known_extension=has_known_extension,
            has_path_separator=has_path_separator,
        )

    @classmethod
    def is_file_path(cls, target: str) -> bool:
        """Check if a target appears to be a file path.

        This is a convenience method for simple boolean checks.

        Parameters
        ----------
        target : str
            The target string to check

        Returns
        -------
        bool
            True if the target appears to be a file path, False otherwise
        """
        return cls.classify(target).is_file_path
