"""Unit tests for infrastructure version checker."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from test_constants import TestVersions
from version_management.checkers.infrastructure import InfrastructureChecker


class TestInfrastructureChecker:
    """Test infrastructure version checker functionality."""

    def test_init_creates_endoflife_source(self):
        """Verify checker initializes with EndOfLifeSource."""
        config = create_mock_versions_config()
        checker = InfrastructureChecker(config)

        assert checker.config == config
        assert hasattr(checker, "source")
        assert checker.source is not None

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_no_updates_when_versions_match(self, mock_source_class):
        """Verify no updates when current and latest versions match."""
        config = {
            "version": "1.0.0",
            "infrastructure": {"python": {"version": TestVersions.PYTHON_NEW}},
        }

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.PYTHON_NEW,
            "type": "stable",
            "end_of_life": "2028-10-31",
            "notes": "Latest stable version",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert updates == {}

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_detects_python_update(self, mock_source_class):
        """Verify Python version update is detected."""
        config = create_mock_versions_config(
            infrastructure={"python": {"version": TestVersions.PYTHON_OLD}},
        )

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.PYTHON_NEW,
            "type": "stable",
            "end_of_life": "2028-10-31",
            "notes": "Latest stable version",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert "python" in updates
        assert updates["python"]["old_version"] == TestVersions.PYTHON_OLD
        assert updates["python"]["new_version"] == TestVersions.PYTHON_NEW
        assert updates["python"]["type"] == "stable"
        assert updates["python"]["end_of_life"] == "2028-10-31"
        assert "Latest stable version" in updates["python"]["notes"]

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_detects_node_update(self, mock_source_class):
        """Verify Node.js version update is detected."""
        config = create_mock_versions_config(
            infrastructure={"node": {"version": "18.0.0"}},
        )

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.NODE_NEW,
            "type": "lts",
            "end_of_life": "2026-04-30",
            "notes": "Latest LTS (Iron)",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert "node" in updates
        assert updates["node"]["old_version"] == "18.0.0"
        assert updates["node"]["new_version"] == TestVersions.NODE_NEW
        assert updates["node"]["type"] == "lts"

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_detects_java_update(self, mock_source_class):
        """Verify Java version update is detected."""
        config = create_mock_versions_config(
            infrastructure={"java": {"version": "17.0.0"}},
        )

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.JAVA_NEW,
            "type": "lts",
            "end_of_life": "2031-09",
            "notes": "Latest stable LTS",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert "java" in updates
        assert updates["java"]["old_version"] == "17.0.0"
        assert updates["java"]["new_version"] == TestVersions.JAVA_NEW

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_handles_legacy_version_format(self, mock_source_class):
        """Verify legacy python_version format is supported."""
        config = {
            "version": "1.0.0",
            "infrastructure": {"python_version": "3.10.0"},
        }

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.PYTHON_NEW,
            "type": "stable",
            "end_of_life": "2028-10-31",
            "notes": "Latest stable version",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert "python" in updates
        assert updates["python"]["old_version"] == "3.10.0"

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_skips_language_when_no_current_version(self, mock_source_class):
        """Verify languages without current versions are skipped."""
        config = {
            "version": "1.0.0",
            "infrastructure": {},
        }

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.PYTHON_NEW,
            "type": "stable",
            "end_of_life": "2028-10-31",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert updates == {}
        assert not mock_source.get_version_info.called

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_handles_source_returning_none(self, mock_source_class):
        """Verify graceful handling when source returns None."""
        config = create_mock_versions_config(
            infrastructure={"python": {"version": TestVersions.PYTHON_OLD}},
        )

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = None

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert updates == {}

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_detects_multiple_language_updates(self, mock_source_class):
        """Verify multiple language updates are detected in one pass."""
        config = create_mock_versions_config(
            infrastructure={
                "python": {"version": "3.10.0"},
                "node": {"version": "18.0.0"},
                "java": {"version": "17.0.0"},
            },
        )

        mock_source = mock_source_class.return_value

        def get_version_side_effect(lang):
            """Return different versions for each language."""
            versions = {
                "python": {
                    "version": TestVersions.PYTHON_NEW,
                    "type": "stable",
                    "end_of_life": "2028-10-31",
                    "notes": "Latest stable version",
                },
                "node": {
                    "version": TestVersions.NODE_NEW,
                    "type": "lts",
                    "end_of_life": "2026-04-30",
                    "notes": "Latest LTS (Iron)",
                },
                "java": {
                    "version": TestVersions.JAVA_NEW,
                    "type": "lts",
                    "end_of_life": "2031-09",
                    "notes": "Latest stable LTS",
                },
            }
            return versions.get(lang)

        mock_source.get_version_info.side_effect = get_version_side_effect

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert len(updates) == 3
        assert "python" in updates
        assert "node" in updates
        assert "java" in updates

    @patch("version_management.checkers.infrastructure.EndOfLifeSource")
    def test_includes_default_notes_when_missing(self, mock_source_class):
        """Verify default notes are added when missing from source."""
        config = create_mock_versions_config(
            infrastructure={"python": {"version": TestVersions.PYTHON_OLD}},
        )

        mock_source = mock_source_class.return_value
        mock_source.get_version_info.return_value = {
            "version": TestVersions.PYTHON_NEW,
            "type": "stable",
        }

        checker = InfrastructureChecker(config)
        updates = checker.check_updates()

        assert "python" in updates
        assert updates["python"]["notes"] == "Latest stable version"
