"""Unit tests for EndOfLifeSource class."""

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
from version_management.sources.endoflife import EndOfLifeSource


class TestEndOfLifeSource:
    """Test EndOfLifeSource functionality."""

    @patch("version_management.sources.endoflife.requests.get")
    def test_fetch_python_version_success(self, mock_get):
        """Verify Python version fetching returns latest stable non-EOL version."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "3.12", "eol": False, "lts": False},
                {"cycle": "3.11", "eol": False, "lts": False},
                {"cycle": "3.10", "eol": "2026-10-04", "lts": False},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is not None
        assert version_info["version"] == "3.12"
        assert version_info["type"] == "stable"
        assert "end_of_life" in version_info
        assert version_info["notes"] == "Stable production version"

    @patch("version_management.sources.endoflife.requests.get")
    def test_fetch_nodejs_lts_version(self, mock_get):
        """Verify Node.js version fetching returns latest LTS version."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "21", "lts": False, "eol": False},
                {"cycle": "20", "lts": "Iron", "eol": False},
                {"cycle": "18", "lts": "Hydrogen", "eol": "2025-04-30"},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version_info = source.get_version_info("node")

        assert version_info is not None
        assert version_info["version"] == "20"
        assert version_info["type"] == "lts"
        assert "Iron" in version_info["notes"]

    @patch("version_management.sources.endoflife.requests.get")
    def test_fetch_java_lts_version(self, mock_get):
        """Verify Java version fetching returns latest LTS version."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "22", "lts": False, "eol": False},
                {"cycle": "21", "lts": True, "eol": False},
                {"cycle": "17", "lts": True, "eol": "2029-09"},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version_info = source.get_version_info("java")

        assert version_info is not None
        assert version_info["version"] == "21"
        assert version_info["type"] == "lts"
        assert version_info["notes"] == "Latest stable LTS"

    @patch("version_management.sources.endoflife.requests.get")
    def test_handles_api_timeout(self, mock_get):
        """Verify timeout errors are handled gracefully."""
        mock_get.side_effect = create_timeout_mock().side_effect

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is None

    @patch("version_management.sources.endoflife.requests.get")
    def test_handles_invalid_json_response(self, mock_get):
        """Verify malformed JSON responses are handled gracefully."""
        mock_get.return_value = create_json_error_mock()

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is None

    def test_handles_unknown_language(self):
        """Verify unknown languages return None without API calls."""
        source = EndOfLifeSource()
        version_info = source.get_version_info("unknown_language")

        assert version_info is None

    @patch("version_management.sources.endoflife.requests.get")
    def test_filters_eol_versions(self, mock_get):
        """Verify EOL'd versions are skipped in favor of non-EOL versions."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "3.10", "eol": "2026-10-04", "lts": False},
                {"cycle": "3.9", "eol": "2025-10-05", "lts": False},
                {"cycle": "3.12", "eol": False, "lts": False},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is not None
        assert version_info["version"] == "3.12"

    @patch("version_management.sources.endoflife.is_stable_version")
    @patch("version_management.sources.endoflife.requests.get")
    def test_filters_unstable_versions(self, mock_get, mock_is_stable):
        """Verify unstable versions are filtered using is_stable_version check."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "3.13-beta", "eol": False, "lts": False},
                {"cycle": "3.12", "eol": False, "lts": False},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        def is_stable_side_effect(version):
            """Return False for beta versions."""
            return "beta" not in version

        mock_is_stable.side_effect = is_stable_side_effect

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is not None
        assert version_info["version"] == "3.12"
        assert mock_is_stable.called

    @patch("version_management.sources.endoflife.requests.get")
    def test_nodejs_alias_support(self, mock_get):
        """Verify both 'node' and 'nodejs' aliases work for Node.js."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "20", "lts": "Iron", "eol": False},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()

        node_info = source.get_version_info("node")
        nodejs_info = source.get_version_info("nodejs")

        assert node_info is not None
        assert nodejs_info is not None
        assert node_info["version"] == nodejs_info["version"] == "20"

    @patch("version_management.sources.endoflife.requests.get")
    def test_handles_http_error(self, mock_get):
        """Verify HTTP errors (404, 500) are handled gracefully."""
        import requests

        mock_get.side_effect = requests.HTTPError("404 Not Found")

        source = EndOfLifeSource()
        version_info = source.get_version_info("python")

        assert version_info is None

    @patch("version_management.sources.endoflife.requests.get")
    def test_fetch_latest_version_returns_version_string(self, mock_get):
        """Verify fetch_latest_version returns just the version string."""
        mock_response = MockHTTPResponse(
            json_data=[
                {"cycle": "3.12", "eol": False, "lts": False},
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version = source.fetch_latest_version("python")

        assert version == "3.12"
        assert isinstance(version, str)

    @patch("version_management.sources.endoflife.requests.get")
    def test_handles_missing_expected_keys_in_response(self, mock_get):
        """Verify graceful degradation if API schema changes."""
        # Simulates API response with missing 'cycle' key
        mock_response = MockHTTPResponse(
            json_data=[
                {"version": "3.12"},  # Missing 'cycle' key
            ],
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = EndOfLifeSource()
        version = source.fetch_latest_version("python")

        # Should return None when expected keys missing
        assert version is None

    @patch("version_management.sources.endoflife.requests.get")
    def test_no_partial_results_on_incomplete_response(self, mock_get):
        """Verify incomplete data not returned if response interrupted."""
        # Simulates truncated JSON response
        mock_get.side_effect = ValueError("Invalid JSON")

        source = EndOfLifeSource()
        version = source.fetch_latest_version("python")

        # Should return None, not partial data
        assert version is None
