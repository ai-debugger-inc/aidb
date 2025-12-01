"""Unit tests for PackageChecker class."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from test_constants import TestPackages, TestVersions
from version_management.checkers.packages import PackageChecker


class TestPackageChecker:
    """Test PackageChecker functionality."""

    def test_init_creates_package_sources(self):
        """Verify checker initializes with PyPI and npm sources."""
        config = create_mock_versions_config()
        checker = PackageChecker(config)

        assert checker.config == config
        assert hasattr(checker, "pypi_source")
        assert hasattr(checker, "npm_source")
        assert checker.pypi_source is not None
        assert checker.npm_source is not None

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_detects_pip_package_update(self, mock_npm_class, mock_pypi_class):
        """Verify pip package update detection."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {
                    TestPackages.SETUPTOOLS: {
                        "version": TestVersions.SETUPTOOLS_OLD,
                        "description": "Build system",
                    },
                },
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = TestVersions.SETUPTOOLS_NEW

        checker = PackageChecker(config)
        updates = checker.check_pypi_updates()

        assert TestPackages.SETUPTOOLS in updates
        assert (
            updates[TestPackages.SETUPTOOLS]["current"] == TestVersions.SETUPTOOLS_OLD
        )
        assert updates[TestPackages.SETUPTOOLS]["latest"] == TestVersions.SETUPTOOLS_NEW
        assert "update_type" in updates[TestPackages.SETUPTOOLS]

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_detects_npm_package_update(self, mock_npm_class, mock_pypi_class):
        """Verify npm package update detection."""
        config = create_mock_versions_config(
            global_packages={
                "npm": {
                    TestPackages.TYPESCRIPT: {
                        "version": TestVersions.TYPESCRIPT_OLD,
                        "description": "TypeScript",
                    },
                },
            },
        )

        mock_npm = mock_npm_class.return_value
        mock_npm.fetch_latest_version.return_value = TestVersions.TYPESCRIPT_NEW

        checker = PackageChecker(config)
        updates = checker.check_npm_updates()

        assert TestPackages.TYPESCRIPT in updates
        assert (
            updates[TestPackages.TYPESCRIPT]["current"] == TestVersions.TYPESCRIPT_OLD
        )
        assert updates[TestPackages.TYPESCRIPT]["latest"] == TestVersions.TYPESCRIPT_NEW
        assert "update_type" in updates[TestPackages.TYPESCRIPT]

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_no_updates_when_versions_match(self, mock_npm_class, mock_pypi_class):
        """Verify no updates when current and latest versions match."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {
                    TestPackages.SETUPTOOLS: {"version": TestVersions.SETUPTOOLS_NEW},
                },
                "npm": {
                    TestPackages.TYPESCRIPT: {"version": TestVersions.TYPESCRIPT_NEW},
                },
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = TestVersions.SETUPTOOLS_NEW

        mock_npm = mock_npm_class.return_value
        mock_npm.fetch_latest_version.return_value = TestVersions.TYPESCRIPT_NEW

        checker = PackageChecker(config)
        pypi_updates = checker.check_pypi_updates()
        npm_updates = checker.check_npm_updates()

        assert pypi_updates == {}
        assert npm_updates == {}

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_handles_source_returning_none(self, mock_npm_class, mock_pypi_class):
        """Verify graceful handling when sources return None."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {"setuptools": {"version": "68.0.0"}},
                "npm": {"typescript": {"version": "5.3.0"}},
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = None

        mock_npm = mock_npm_class.return_value
        mock_npm.fetch_latest_version.return_value = None

        checker = PackageChecker(config)
        pypi_updates = checker.check_pypi_updates()
        npm_updates = checker.check_npm_updates()

        assert pypi_updates == {}
        assert npm_updates == {}

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_checks_multiple_pip_packages(self, mock_npm_class, mock_pypi_class):
        """Verify multiple pip package updates detected in one pass."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {
                    "setuptools": {"version": "68.0.0"},
                    "pip": {"version": "23.0.0"},
                },
            },
        )

        mock_pypi = mock_pypi_class.return_value

        def fetch_side_effect(package):
            """Return different versions for each package."""
            if package == "setuptools":
                return "69.0.0"
            if package == "pip":
                return "24.0.0"
            return None

        mock_pypi.fetch_latest_version.side_effect = fetch_side_effect

        checker = PackageChecker(config)
        updates = checker.check_pypi_updates()

        assert len(updates) == 2
        assert "setuptools" in updates
        assert "pip" in updates

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_checks_multiple_npm_packages(self, mock_npm_class, mock_pypi_class):
        """Verify multiple npm package updates detected in one pass."""
        config = create_mock_versions_config(
            global_packages={
                "npm": {
                    "typescript": {"version": "5.3.0"},
                    "ts_node": {"version": "10.9.0"},
                },
            },
        )

        mock_npm = mock_npm_class.return_value

        def fetch_side_effect(package):
            """Return different versions for each package."""
            if package == "typescript":
                return "5.3.3"
            if package == "ts_node":
                return "10.9.2"
            return None

        mock_npm.fetch_latest_version.side_effect = fetch_side_effect

        checker = PackageChecker(config)
        updates = checker.check_npm_updates()

        assert len(updates) == 2
        assert "typescript" in updates
        assert "ts_node" in updates

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_skips_packages_with_empty_version(self, mock_npm_class, mock_pypi_class):
        """Verify packages with empty/missing version are skipped."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {
                    "setuptools": {"version": "68.0.0"},
                    "wheel": {"version": ""},
                    "pip": {},
                },
                "npm": {
                    "typescript": {"version": "5.3.0"},
                    "eslint": {"version": ""},
                },
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = "999.0.0"

        mock_npm = mock_npm_class.return_value
        mock_npm.fetch_latest_version.return_value = "999.0.0"

        checker = PackageChecker(config)
        pypi_updates = checker.check_pypi_updates()
        npm_updates = checker.check_npm_updates()

        # Only packages with non-empty versions should be checked
        assert "setuptools" in pypi_updates
        assert "wheel" not in pypi_updates
        assert "pip" not in pypi_updates

        assert "typescript" in npm_updates
        assert "eslint" not in npm_updates

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_includes_update_type_classification(self, mock_npm_class, mock_pypi_class):
        """Verify update_type is included in results."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {"setuptools": {"version": "68.0.0"}},
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = "69.0.0"

        checker = PackageChecker(config)
        updates = checker.check_pypi_updates()

        assert "setuptools" in updates
        assert "update_type" in updates["setuptools"]
        # Should be classified based on semver
        assert updates["setuptools"]["update_type"] in ["patch", "minor", "major"]

    @patch("version_management.checkers.packages.PyPISource")
    @patch("version_management.checkers.packages.NpmRegistrySource")
    def test_calls_correct_sources(self, mock_npm_class, mock_pypi_class):
        """Verify correct sources are called for pip and npm packages."""
        config = create_mock_versions_config(
            global_packages={
                "pip": {"setuptools": {"version": "68.0.0"}},
                "npm": {"typescript": {"version": "5.3.0"}},
            },
        )

        mock_pypi = mock_pypi_class.return_value
        mock_pypi.fetch_latest_version.return_value = "999.0.0"

        mock_npm = mock_npm_class.return_value
        mock_npm.fetch_latest_version.return_value = "999.0.0"

        checker = PackageChecker(config)
        checker.check_pypi_updates()
        checker.check_npm_updates()

        # Verify PyPI source called for setuptools
        pypi_calls = mock_pypi.fetch_latest_version.call_args_list
        assert len(pypi_calls) == 1
        assert pypi_calls[0][0][0] == "setuptools"

        # Verify npm source called for typescript
        npm_calls = mock_npm.fetch_latest_version.call_args_list
        assert len(npm_calls) == 1
        assert npm_calls[0][0][0] == "typescript"
