"""Unit tests for DockerHubSource class."""

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
    create_json_error_mock,
    create_timeout_mock,
)
from test_constants import HTTPStatus
from version_management.sources.docker_hub import DockerHubSource


class TestDockerHubSource:
    """Test DockerHubSource functionality."""

    @patch("version_management.sources.docker_hub.requests.get")
    def test_fetch_latest_tag_success(self, mock_get):
        """Verify fetching latest semantic version tag from Docker Hub."""
        mock_response = MockHTTPResponse(
            json_data={
                "results": [
                    {"name": "0.181.0"},
                    {"name": "0.180.0"},
                    {"name": "latest"},
                    {"name": "0.179.0"},
                ],
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag == "0.181.0"
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["params"]["page_size"] == 100

    @patch("version_management.sources.docker_hub.requests.get")
    def test_filters_non_semver_tags(self, mock_get):
        """Verify non-semantic version tags are filtered out."""
        mock_response = MockHTTPResponse(
            json_data={
                "results": [
                    {"name": "latest"},
                    {"name": "edge"},
                    {"name": "dev"},
                    {"name": "0.180.0"},
                    {"name": "alpine"},
                ],
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag == "0.180.0"

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_no_semver_tags(self, mock_get):
        """Verify returns None when no semantic version tags exist."""
        mock_response = MockHTTPResponse(
            json_data={
                "results": [
                    {"name": "latest"},
                    {"name": "edge"},
                    {"name": "alpine"},
                ],
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag is None

    @patch("version_management.sources.docker_hub.requests.get")
    def test_returns_max_semver_tag(self, mock_get):
        """Verify returns the maximum semantic version tag."""
        mock_response = MockHTTPResponse(
            json_data={
                "results": [
                    {"name": "1.2.3"},
                    {"name": "2.0.0"},
                    {"name": "1.10.5"},
                    {"name": "2.1.0"},
                ],
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("example/app")

        assert tag == "2.1.0"

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_v_prefix_in_tags(self, mock_get):
        """Verify handles tags with 'v' prefix correctly."""
        mock_response = MockHTTPResponse(
            json_data={
                "results": [
                    {"name": "v1.85.0"},
                    {"name": "v1.86.0"},
                    {"name": "v1.84.0"},
                ],
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("example/app")

        assert tag == "v1.86.0"

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_http_error(self, mock_get):
        """Verify HTTP errors (404, 500) are handled gracefully."""
        mock_get.return_value = create_http_error_mock(
            status_code=HTTPStatus.NOT_FOUND,
            message="404 Not Found",
        )

        source = DockerHubSource()
        tag = source.fetch_latest_version("nonexistent/image")

        assert tag is None

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_network_timeout(self, mock_get):
        """Verify timeout errors are handled gracefully."""
        mock_get.side_effect = create_timeout_mock().side_effect

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag is None

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_invalid_json_response(self, mock_get):
        """Verify malformed JSON responses are handled gracefully."""
        mock_get.return_value = create_json_error_mock()

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag is None

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_empty_results(self, mock_get):
        """Verify empty results list is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data={"results": []},
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag is None

    @patch("version_management.sources.docker_hub.requests.get")
    def test_handles_missing_results_key(self, mock_get):
        """Verify missing 'results' key is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data={"count": 0},
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = DockerHubSource()
        tag = source.fetch_latest_version("redis")

        assert tag is None
