"""Unit tests for version discovery utilities."""

import json
from pathlib import Path
from unittest.mock import patch

from aidb.adapters.downloader.version import find_project_root, get_project_version

# =============================================================================
# TestFindProjectRoot
# =============================================================================


class TestFindProjectRoot:
    """Tests for find_project_root function.

    Note: find_project_root() uses Path(__file__) internally which is difficult
    to mock reliably. We test the actual behavior against the real codebase
    rather than attempting complex Path mocking.
    """

    def test_returns_actual_project_root(self) -> None:
        """Test that find_project_root returns the actual AIDB project root."""
        # This test verifies the function works with the real codebase
        root = find_project_root()

        # The root should contain versions.json
        versions_file = root / "versions.json"
        assert versions_file.exists(), f"versions.json not found at {root}"

        # The root should also have other project markers
        assert (root / "pyproject.toml").exists() or (root / "setup.py").exists()

    def test_returns_path_containing_versions_json(self) -> None:
        """Test that the returned path contains a valid versions.json file."""
        root = find_project_root()
        versions_file = root / "versions.json"

        # Read and verify it's valid JSON with expected structure
        content = json.loads(versions_file.read_text())
        assert "version" in content or "adapters" in content


# =============================================================================
# TestGetProjectVersion
# =============================================================================


class TestGetProjectVersion:
    """Tests for get_project_version function."""

    def test_returns_version_from_file(self, tmp_path: Path) -> None:
        """Test returns version from versions.json."""
        # Create versions.json with a specific version
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(json.dumps({"version": "2.3.4"}))

        with patch(
            "aidb.adapters.downloader.version.find_project_root",
            return_value=tmp_path,
        ):
            version = get_project_version()

        assert version == "2.3.4"

    def test_returns_latest_when_version_key_missing(self, tmp_path: Path) -> None:
        """Test returns 'latest' when version key is missing."""
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(json.dumps({"adapters": {}}))

        with patch(
            "aidb.adapters.downloader.version.find_project_root",
            return_value=tmp_path,
        ):
            version = get_project_version()

        assert version == "latest"

    def test_returns_latest_on_file_not_found(self) -> None:
        """Test returns 'latest' when versions.json not found."""
        with patch(
            "aidb.adapters.downloader.version.find_project_root",
            side_effect=FileNotFoundError("Not found"),
        ):
            version = get_project_version()

        assert version == "latest"

    def test_returns_latest_on_invalid_json(self, tmp_path: Path) -> None:
        """Test returns 'latest' when versions.json has invalid JSON."""
        versions_file = tmp_path / "versions.json"
        versions_file.write_text("not valid json {{{")

        with patch(
            "aidb.adapters.downloader.version.find_project_root",
            return_value=tmp_path,
        ):
            version = get_project_version()

        assert version == "latest"

    def test_returns_actual_project_version(self) -> None:
        """Test returns the actual AIDB project version."""
        version = get_project_version()

        # Should be a valid version string or 'latest'
        assert version == "latest" or (isinstance(version, str) and len(version) > 0)
