"""Unit tests for GitHubReleasesSource class."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import (
    MockHTTPResponse,
    create_http_error_mock,
    create_mock_github_release,
    create_rate_limit_mock,
    create_timeout_mock,
)
from test_constants import HTTPStatus, TestRepos, TestVersions
from version_management.sources.github import GitHubReleasesSource


class TestGitHubReleasesSource:
    """Test GitHubReleasesSource functionality."""

    @patch("version_management.sources.github.requests.get")
    def test_fetch_latest_release_success(self, mock_get):
        """Verify fetching latest stable release from GitHub API."""
        mock_response = MockHTTPResponse(
            json_data=[
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_NEW,
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_OLD,
                    published_at="2024-01-01",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version == "1.86.0"
        assert not version.startswith("v")

    @patch("version_management.sources.github.requests.get")
    def test_filters_prereleases(self, mock_get):
        """Verify prerelease versions are skipped."""
        mock_response = MockHTTPResponse(
            json_data=[
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_NEWER,
                    published_at="2024-01-20",
                    prerelease=True,
                    draft=False,
                ),
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_NEW,
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version == "1.86.0"

    @patch("version_management.sources.github.requests.get")
    def test_filters_draft_releases(self, mock_get):
        """Verify draft releases are skipped."""
        mock_response = MockHTTPResponse(
            json_data=[
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_NEWER,
                    published_at="2024-01-20",
                    prerelease=False,
                    draft=True,
                ),
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_NEW,
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version == "1.86.0"

    @patch("version_management.sources.github.requests.get")
    def test_strips_v_prefix_from_tag_name(self, mock_get):
        """Verify 'v' prefix is stripped from tag names."""
        mock_response = MockHTTPResponse(
            json_data=[
                create_mock_github_release(
                    tag_name=f"v{TestVersions.DEBUGPY_OLD}",
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.DEBUGPY)

        assert version == TestVersions.DEBUGPY_OLD
        assert not version.startswith("v")

    @patch("version_management.sources.github.requests.get")
    def test_handles_rate_limit_exceeded(self, mock_get):
        """Verify rate limit errors are handled gracefully."""
        mock_get.return_value = create_rate_limit_mock()

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version is None

    @patch("version_management.sources.github.requests.get")
    def test_handles_repository_not_found(self, mock_get):
        """Verify 404 errors are handled gracefully."""
        mock_get.return_value = create_http_error_mock(
            status_code=HTTPStatus.NOT_FOUND,
            message="404 Not Found",
        )

        source = GitHubReleasesSource()
        version = source.fetch_latest_version("nonexistent/repo")

        assert version is None

    @patch("version_management.sources.github.requests.get")
    def test_handles_network_timeout(self, mock_get):
        """Verify timeout errors are handled gracefully."""
        mock_get.side_effect = create_timeout_mock().side_effect

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version is None

    @patch("version_management.sources.github.is_stable_version")
    @patch("version_management.sources.github.requests.get")
    def test_uses_is_stable_version_check(self, mock_get, mock_is_stable):
        """Verify is_stable_version is used to validate releases."""
        mock_response = MockHTTPResponse(
            json_data=[
                create_mock_github_release(
                    tag_name="v1.86.0-beta",
                    published_at="2024-01-20",
                    prerelease=False,
                    draft=False,
                ),
                create_mock_github_release(
                    tag_name=TestVersions.JS_ADAPTER_OLD,
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        def is_stable_side_effect(version):
            """Return False for beta versions."""
            return "beta" not in version

        mock_is_stable.side_effect = is_stable_side_effect

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version == "1.85.0"
        assert mock_is_stable.called

    @patch("version_management.sources.github.is_stable_version")
    @patch("version_management.sources.github.requests.get")
    def test_handles_malformed_release_data(self, mock_get, mock_is_stable):
        """Verify malformed release data is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"name": "Release without tag_name"},
                create_mock_github_release(
                    tag_name="",
                    published_at="2024-01-15",
                    prerelease=False,
                    draft=False,
                ),
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response
        mock_is_stable.return_value = False

        source = GitHubReleasesSource()
        version = source.fetch_latest_version(TestRepos.VS_CODE_JS_DEBUG)

        assert version is None

    @patch("version_management.sources.github.requests.get")
    def test_find_latest_stable_release(self, mock_get):
        """Verify find_latest_stable_release filters correctly."""
        releases = [
            create_mock_github_release(
                tag_name=TestVersions.JS_ADAPTER_NEWER,
                published_at="2024-01-20",
                prerelease=True,
                draft=False,
            ),
            create_mock_github_release(
                tag_name=TestVersions.JS_ADAPTER_NEW,
                published_at="2024-01-15",
                prerelease=False,
                draft=False,
            ),
        ]

        source = GitHubReleasesSource()
        latest = source.find_latest_stable_release(releases)

        assert latest is not None
        assert latest["tag_name"] == TestVersions.JS_ADAPTER_NEW
        assert latest["prerelease"] is False
