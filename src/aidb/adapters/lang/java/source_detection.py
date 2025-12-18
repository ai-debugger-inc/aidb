"""Auto-detection of Java source paths for Maven/Gradle projects.

This module provides utilities to automatically discover source directories in Maven and
Gradle projects, supporting nested multi-module structures.
"""

from __future__ import annotations

from pathlib import Path

from aidb.adapters.lang.java.tooling import JavaBuildSystemDetector

__all__ = ["detect_java_source_paths"]

# Standard source directory names in Maven/Gradle projects
_SOURCE_DIRS = [
    "src/main/java",
    "src/test/java",
    "src/main/kotlin",
    "src/test/kotlin",
    "src/main/scala",
    "src/test/scala",
]

# Directories to skip during recursive scanning
_SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".gradle",
    "node_modules",
    "target",
    "build",
    "out",
    "__pycache__",
    ".settings",
}


def _is_build_root(path: Path) -> bool:
    """Check if path is a Maven/Gradle project root.

    Parameters
    ----------
    path : Path
        Directory to check

    Returns
    -------
    bool
        True if directory contains pom.xml or build.gradle
    """
    return JavaBuildSystemDetector.is_maven_gradle_project(path)


def _collect_source_paths(project_root: Path, source_paths: list[str]) -> None:
    """Collect source paths from a project root.

    Parameters
    ----------
    project_root : Path
        Root of a Maven/Gradle module
    source_paths : list[str]
        List to append discovered source paths to
    """
    for src_dir in _SOURCE_DIRS:
        src_path = project_root / src_dir
        if src_path.exists():
            path_str = str(src_path)
            if path_str not in source_paths:
                source_paths.append(path_str)


def _scan_recursive(directory: Path, source_paths: list[str]) -> None:
    """Recursively scan for Maven/Gradle modules.

    Parameters
    ----------
    directory : Path
        Directory to scan
    source_paths : list[str]
        List to append discovered source paths to
    """
    if not directory.is_dir():
        return

    # Skip hidden directories and common non-source directories
    if directory.name in _SKIP_DIRS or directory.name.startswith("."):
        return

    # If this directory is a build root, collect its source paths
    if _is_build_root(directory):
        _collect_source_paths(directory, source_paths)

    # Recurse into subdirectories
    try:
        for child in directory.iterdir():
            if child.is_dir():
                _scan_recursive(child, source_paths)
    except PermissionError:
        pass  # Skip directories we can't read


def detect_java_source_paths(workspace_root: str | Path) -> list[str]:
    """Auto-detect source paths for Maven/Gradle projects.

    Recursively scans for Maven/Gradle modules and collects standard source
    directories. Handles nested multi-module projects like Trino
    (core/trino-main, plugin/trino-hive, etc.).

    Parameters
    ----------
    workspace_root : str | Path
        Root directory of the workspace to scan

    Returns
    -------
    list[str]
        List of detected source directories (absolute paths)

    Examples
    --------
    >>> paths = detect_java_source_paths("/path/to/trino")
    >>> # Returns paths like:
    >>> # ['/path/to/trino/core/trino-main/src/main/java',
    >>> #  '/path/to/trino/core/trino-spi/src/main/java', ...]
    """
    root = Path(workspace_root)

    # Only proceed if workspace_root is a Maven/Gradle project
    if not _is_build_root(root):
        return []

    source_paths: list[str] = []
    _scan_recursive(root, source_paths)
    return source_paths
