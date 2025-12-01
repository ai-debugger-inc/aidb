"""Unit tests for AdapterChecker class."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from test_constants import TestRepos, TestVersions
from version_management.checkers.adapters import AdapterChecker


class TestAdapterChecker:
    """Test AdapterChecker functionality."""

    def test_init_creates_github_source(self):
        """Verify checker initializes with GitHubReleasesSource."""
        config = create_mock_versions_config()
        checker = AdapterChecker(config)

        assert checker.config == config
        assert hasattr(checker, "source")
        assert checker.source is not None

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_detects_javascript_adapter_update(self, mock_source_class):
        """Verify JavaScript adapter update detection."""
        config = create_mock_versions_config(
            adapters={
                "javascript": {
                    "version": TestVersions.JS_ADAPTER_OLD,
                    "source": TestRepos.VS_CODE_JS_DEBUG,
                },
            },
        )

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "1.86.0"

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert "javascript" in updates
        assert updates["javascript"]["current"] == "1.85.0"
        assert updates["javascript"]["latest"] == "1.86.0"
        assert updates["javascript"]["repo"] == TestRepos.VS_CODE_JS_DEBUG

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_detects_java_adapter_update(self, mock_source_class):
        """Verify Java adapter update detection."""
        config = create_mock_versions_config(
            adapters={"java": {"version": "0.54.0", "source": TestRepos.JAVA_DEBUG}},
        )

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "0.55.0"

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert "java" in updates
        assert updates["java"]["current"] == "0.54.0"
        assert updates["java"]["latest"] == "0.55.0"
        assert updates["java"]["repo"] == TestRepos.JAVA_DEBUG

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_no_updates_when_versions_match(self, mock_source_class):
        """Verify no updates when current and latest versions match."""
        config = create_mock_versions_config(
            adapters={
                "javascript": {"version": TestVersions.JS_ADAPTER_NEW},
                "java": {"version": "0.55.0"},
            },
        )

        mock_source = mock_source_class.return_value

        def fetch_side_effect(repo):
            """Return matching versions for each repo."""
            if repo == TestRepos.VS_CODE_JS_DEBUG:
                return "1.86.0"
            if repo == TestRepos.JAVA_DEBUG:
                return "0.55.0"
            return None

        mock_source.fetch_latest_version.side_effect = fetch_side_effect

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert updates == {}

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_handles_v_prefix_in_javascript_version(self, mock_source_class):
        """Verify 'v' prefix is stripped when comparing JavaScript versions."""
        config = create_mock_versions_config(
            adapters={"javascript": {"version": TestVersions.JS_ADAPTER_OLD}},
        )

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "1.86.0"

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert "javascript" in updates
        assert updates["javascript"]["current"] == "1.85.0"
        assert not updates["javascript"]["current"].startswith("v")

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_handles_source_returning_none(self, mock_source_class):
        """Verify graceful handling when source returns None."""
        config = create_mock_versions_config(
            adapters={"javascript": {"version": TestVersions.JS_ADAPTER_OLD}},
        )

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = None

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert updates == {}

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_checks_multiple_adapters(self, mock_source_class):
        """Verify multiple adapter updates detected in one pass."""
        config = create_mock_versions_config(
            adapters={
                "javascript": {"version": TestVersions.JS_ADAPTER_OLD},
                "java": {"version": "0.54.0"},
            },
        )

        mock_source = mock_source_class.return_value

        def fetch_side_effect(repo):
            """Return different versions for each repo."""
            if repo == TestRepos.VS_CODE_JS_DEBUG:
                return "1.86.0"
            if repo == TestRepos.JAVA_DEBUG:
                return "0.55.0"
            return None

        mock_source.fetch_latest_version.side_effect = fetch_side_effect

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        assert len(updates) == 2
        assert "javascript" in updates
        assert "java" in updates

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_skips_adapters_not_in_config(self, mock_source_class):
        """Verify only configured adapters (javascript/java) are checked."""
        config = {
            "version": "1.0.0",
            "adapters": {"python": {"version": TestVersions.DEBUGPY_OLD}},
        }

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "1.9.0"

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        # Should return empty since python adapter is not javascript or java
        assert updates == {}
        # Source should not be called since no supported adapters in config
        assert not mock_source.fetch_latest_version.called

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_handles_missing_version_key(self, mock_source_class):
        """Verify graceful handling when adapter config missing version key."""
        config = {
            "version": "1.0.0",
            "adapters": {"javascript": {"source": TestRepos.VS_CODE_JS_DEBUG}},
        }

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "1.86.0"

        checker = AdapterChecker(config)
        updates = checker.check_updates()

        # Should detect update even with empty current version
        assert "javascript" in updates
        assert updates["javascript"]["current"] == ""
        assert updates["javascript"]["latest"] == "1.86.0"

    @patch("version_management.checkers.adapters.GitHubReleasesSource")
    def test_calls_correct_github_repos(self, mock_source_class):
        """Verify correct GitHub repositories are queried for each adapter."""
        config = create_mock_versions_config(
            adapters={
                "javascript": {"version": TestVersions.JS_ADAPTER_OLD},
                "java": {"version": "0.54.0"},
            },
        )

        mock_source = mock_source_class.return_value
        mock_source.fetch_latest_version.return_value = "999.0.0"

        checker = AdapterChecker(config)
        checker.check_updates()

        calls = mock_source.fetch_latest_version.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == TestRepos.VS_CODE_JS_DEBUG
        assert calls[1][0][0] == TestRepos.JAVA_DEBUG
