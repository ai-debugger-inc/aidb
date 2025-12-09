"""Test marker registration and application.

This module provides functions for registering custom pytest markers and applying them
to test items based on location, parametrization, and patterns.
"""

import subprocess
from pathlib import Path

import pytest


def _is_docker_daemon_running() -> bool:
    """Check if Docker daemon is running and accessible.

    Returns
    -------
    bool
        True if Docker daemon is running, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# Cache the Docker daemon check result (checked once per test session)
_docker_daemon_available: bool | None = None


def is_docker_available() -> bool:
    """Check if Docker daemon is available (cached).

    Returns
    -------
    bool
        True if Docker daemon is running, False otherwise.
    """
    global _docker_daemon_available
    if _docker_daemon_available is None:
        _docker_daemon_available = _is_docker_daemon_running()
    return _docker_daemon_available


def register_custom_markers(config) -> None:
    """Register custom pytest markers.

    Note: Most markers are defined in pyproject.toml. This function registers
    additional markers that may be applied dynamically during test collection.

    Parameters
    ----------
    config
        Pytest configuration object
    """
    # These markers are also in pyproject.toml but registered here for
    # completeness since they are dynamically applied by add_location_based_markers


def add_location_based_markers(item) -> None:
    """Add markers based on test file location.

    Parameters
    ----------
    item
        Pytest test item
    """
    test_path = Path(item.fspath)
    test_path_str = str(test_path)

    # Test type markers
    if "smoke" in test_path.parts:
        item.add_marker(pytest.mark.smoke)
    elif "unit" in test_path.parts:
        item.add_marker(pytest.mark.unit)
    elif "integration" in test_path.parts:
        item.add_marker(pytest.mark.integration)
    elif "e2e" in test_path.parts:
        item.add_marker(pytest.mark.e2e)

    # Language markers - iterate over supported languages
    from aidb_common.constants import SUPPORTED_LANGUAGES

    for lang in SUPPORTED_LANGUAGES:
        # Check for framework tests: /frameworks/{lang}/
        # Check for launch tests: /launch/{lang}/
        if (
            f"/frameworks/{lang}/" in test_path_str
            or f"/launch/{lang}/" in test_path_str
        ):
            marker = getattr(pytest.mark, f"language_{lang}")
            item.add_marker(marker())
            break  # Only one language marker per test
    else:
        # No language marker added yet - check for core tests
        # Core tests use Python (match specific directories, not the repo name)
        if (
            "/tests/aidb/" in test_path_str
            and "/tests/aidb_mcp/" not in test_path_str
            and "/tests/aidb_shared/" not in test_path_str
        ):
            item.add_marker(pytest.mark.language_python())


def add_parametrization_markers(item) -> None:
    """Add language markers based on parametrized language parameter.

    Parameters
    ----------
    item
        Pytest test item
    """
    if hasattr(item, "callspec") and "language" in item.callspec.params:
        lang = item.callspec.params["language"]
        # Handle both enum values and strings
        lang_str = lang.value if hasattr(lang, "value") else str(lang)
        # Add language-specific marker (language_python, language_javascript, language_java)
        marker_name = f"language_{lang_str}"
        item.add_marker(getattr(pytest.mark, marker_name)())


def add_default_language_marker(item) -> None:
    """Add default Python language marker if no language marker exists.

    Parameters
    ----------
    item
        Pytest test item
    """
    # Check if any language marker exists
    has_language_marker = any(
        marker.name.startswith("language_") for marker in item.iter_markers()
    )
    if not has_language_marker:
        item.add_marker(pytest.mark.language_python())


def add_pattern_based_markers(item) -> None:
    """Add markers based on test name patterns.

    Parameters
    ----------
    item
        Pytest test item
    """
    if "docker" in item.nodeid.lower():
        item.add_marker(pytest.mark.requires_docker)


def check_marker_requirements(item) -> None:
    """Check and skip tests based on marker requirements.

    Parameters
    ----------
    item
        Pytest test item
    """
    marker_names = [marker.name for marker in item.iter_markers()]

    # Skip tests requiring Docker if daemon is not running
    if "requires_docker" in marker_names and not is_docker_available():
        item.add_marker(pytest.mark.skip(reason="Docker daemon is not running"))

    # Note: xdist_group markers for serial tests must be applied directly as decorators
    # on test classes, not dynamically here. pytest-xdist workers collect tests
    # independently and don't see markers added on the controller.
