"""Utility functions for debugging starters."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aidb.common.constants import DEFAULT_PYTHON_DEBUG_PORT
from aidb_common.constants import Language
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_common.network import find_available_port as _find_available_port
from aidb_common.network import is_port_available as _is_port_available
from aidb_common.path import resolve_path
from aidb_common.repo import detect_repo_root
from aidb_logging import get_mcp_logger as get_logger

logger = get_logger(__name__)


def discover_launch_json(workspace_root: str) -> list[dict[str, Any]]:
    """Discover and parse VS Code launch.json configurations.

    Parameters
    ----------
    workspace_root : str
        The workspace root directory

    Returns
    -------
    List[Dict[str, Any]]
        List of launch configurations found
    """
    logger.debug(
        "Discovering launch.json configurations",
        extra={"workspace_root": workspace_root},
    )

    configs = []
    ws_path = Path(workspace_root)

    # Check for .vscode/launch.json
    launch_path = ws_path / ".vscode" / "launch.json"
    if launch_path.exists():
        try:
            data = safe_read_json(launch_path) or {}
            if "configurations" in data:
                configs.extend(data["configurations"])
                logger.info(
                    "Found launch.json configurations",
                    extra={
                        "config_count": len(data["configurations"]),
                        "launch_path": str(launch_path),
                    },
                )
        except FileOperationError as e:
            logger.warning(
                "Failed to parse launch.json",
                extra={"launch_path": str(launch_path), "error": str(e)},
            )

    if not configs:
        logger.debug(
            "No launch configurations found",
            extra={"workspace_root": workspace_root},
        )

    return configs


def find_workspace_root(start_path: str | None = None) -> str | None:
    """Find the workspace root directory.

    Looks for common project indicators like .git, package.json, etc.

    Parameters
    ----------
    start_path : str, optional
        Starting directory for search (defaults to cwd)

    Returns
    -------
    Optional[str]
        Workspace root path if found, None otherwise
    """
    # Prefer shared repo detection first
    repo_root = detect_repo_root(Path(start_path) if start_path else None)

    # Consider detection successful if common indicators are present
    if any(
        (repo_root / marker).exists()
        for marker in (".git", "pyproject.toml", "package.json")
    ):
        return str(repo_root)

    # Fallback heuristic scan from the provided start path or cwd
    current = Path(start_path).resolve() if start_path else Path.cwd()

    indicators = [
        ".vscode",
        "package.json",
        "pyproject.toml",
        "setup.py",
        "pom.xml",
        "build.gradle",
        "Cargo.toml",
        "go.mod",
    ]

    logger.debug(
        "Finding workspace root %s",
        extra={"start_path": str(current)},
    )

    while current != current.parent:
        for indicator in indicators:
            if (current / indicator).exists():
                workspace_root = str(current)
                logger.info(
                    "Found workspace root",
                    extra={
                        "workspace_root": workspace_root,
                        "indicator": indicator,
                    },
                )
                return workspace_root
        current = current.parent

    fallback = str(Path(start_path).resolve()) if start_path else str(Path.cwd())
    logger.debug(
        "No workspace root found, using fallback",
        extra={"fallback": fallback},
    )
    return fallback


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is available for debugging.

    Delegates to aidb_common.network.is_port_available with logging.

    Parameters
    ----------
    port : int
        Port number to check
    host : str, optional
        Host to check on (default: 127.0.0.1)

    Returns
    -------
    bool
        True if port is available, False otherwise
    """
    available = _is_port_available(port, host)
    logger.debug(
        "Checked port availability",
        extra={"port": port, "host": host, "available": available},
    )
    return available


def find_available_port(
    start_port: int = DEFAULT_PYTHON_DEBUG_PORT,
    max_attempts: int = 10,
    host: str = "127.0.0.1",
) -> int | None:
    """Find an available port for debugging.

    Delegates to aidb_common.network.find_available_port with logging.

    Parameters
    ----------
    start_port : int, optional
        Starting port number (default: DEFAULT_PYTHON_DEBUG_PORT)
    max_attempts : int, optional
        Maximum number of ports to try (default: 10)
    host : str, optional
        Host to check on (default: 127.0.0.1)

    Returns
    -------
    int | None
        Available port number if found, None otherwise
    """
    logger.debug(
        "Finding available port",
        extra={"start_port": start_port, "max_attempts": max_attempts},
    )

    port = _find_available_port(start_port, max_attempts, host)

    if port:
        logger.info("Found available port", extra={"port": port})
    else:
        logger.warning(
            "No available port found",
            extra={"start_port": start_port, "max_attempts": max_attempts},
        )

    return port


def validate_file_path(file_path: str, workspace_root: str | None = None) -> bool:
    """Validate that a file path exists and is readable.

    Parameters
    ----------
    file_path : str
        File path to validate
    workspace_root : str, optional
        Workspace root for relative paths

    Returns
    -------
    bool
        True if file exists and is readable
    """
    # Handle absolute paths
    if Path(file_path).is_absolute():
        path = Path(file_path)
    else:
        # Handle relative paths
        path = Path(workspace_root) / file_path if workspace_root else Path(file_path)

    is_valid = path.exists() and path.is_file() and os.access(path, os.R_OK)

    logger.debug(
        "Validated file path",
        extra={
            "file_path": file_path,
            "resolved_path": str(path),
            "is_valid": is_valid,
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_readable": os.access(path, os.R_OK) if path.exists() else False,
        },
    )

    return is_valid


def expand_path_variables(path: str, workspace_root: str | None = None) -> str:
    """Expand path variables and resolve relative paths against workspace_root.

    This function delegates to aidb_common.path.resolve_path() which handles:
    - VS Code variable expansion (${workspaceFolder}, ${cwd}, ${home}, etc.)
    - Environment variable expansion ($HOME, ${PATH}, etc.)
    - Relative path resolution against workspace_root
    - Path normalization (~ expansion, symlink resolution)

    Parameters
    ----------
    path : str
        Path containing variables or a relative path
    workspace_root : str, optional
        Workspace root directory for resolving relative paths

    Returns
    -------
    str
        Fully resolved absolute path
    """
    original = path
    result = resolve_path(path, workspace_root=workspace_root)

    if result != original:
        logger.debug(
            "Expanded path variables",
            extra={
                "original": original,
                "expanded": result,
                "workspace_root": workspace_root,
            },
        )

    return result


def detect_test_file(file_path: str) -> bool:
    """Detect if a file is likely a test file.

    Parameters
    ----------
    file_path : str
        File path to check

    Returns
    -------
    bool
        True if file appears to be a test file
    """
    path = Path(file_path)
    name = path.name.lower()

    # Common test file patterns
    test_patterns = [
        "test_",
        "_test.",
        ".test.",
        ".spec.",
        "_spec.",
        "tests.",
        "spec_",
    ]

    is_test = any(pattern in name for pattern in test_patterns)

    if is_test:
        matched_pattern = next(p for p in test_patterns if p in name)
        logger.debug(
            "Detected test file",
            extra={"file_path": file_path, "matched_pattern": matched_pattern},
        )

    return is_test


def get_file_language(file_path: str) -> str | None:
    """Detect programming language from file extension.

    Parameters
    ----------
    file_path : str
        File path to analyze

    Returns
    -------
    Optional[str]
        Detected language or None
    """
    # Map file extensions to languages
    # Supported languages use Language enum for consistency
    extension_map: dict[str, str] = {
        # Supported languages (use Language enum)
        ".py": Language.PYTHON.value,
        ".js": Language.JAVASCRIPT.value,
        ".jsx": Language.JAVASCRIPT.value,
        ".ts": Language.JAVASCRIPT.value,
        ".tsx": Language.JAVASCRIPT.value,
        ".java": Language.JAVA.value,
        # Unsupported languages (detection only, no debugging support)
        ".go": "go",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".R": "r",
    }

    path = Path(file_path)
    suffix = path.suffix.lower()
    language = extension_map.get(suffix)

    logger.debug(
        "Detected file language",
        extra={"file_path": file_path, "extension": suffix, "language": language},
    )

    return language
