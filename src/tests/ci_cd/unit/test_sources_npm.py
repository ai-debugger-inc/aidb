"""Unit tests for NpmRegistrySource class."""

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
from test_constants import HTTPStatus, TestPackages, TestTimeouts, TestURLs
from version_management.sources.npm import NpmRegistrySource


class TestNpmRegistrySource:
    """Test NpmRegistrySource functionality."""

    @patch("version_management.sources.npm.requests.get")
    def test_fetch_latest_version_success(self, mock_get):
        """Verify fetching latest package version from npm registry."""
        mock_response = MockHTTPResponse(
            json_data={
                "version": "5.3.3",
                "name": TestPackages.TYPESCRIPT,
                "description": "TypeScript is a language for application-scale JavaScript",
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = NpmRegistrySource()
        version = source.fetch_latest_version(TestPackages.TYPESCRIPT)

        assert version == "5.3.3"
        mock_get.assert_called_once_with(
            TestURLs.NPM_REGISTRY.format(package=TestPackages.TYPESCRIPT),
            timeout=TestTimeouts.HTTP_REQUEST,
        )

    @patch("version_management.sources.npm.requests.get")
    def test_package_name_mapping(self, mock_get):
        """Verify package name mapping for ts_node -> ts-node transformation."""
        mock_response = MockHTTPResponse(
            json_data={
                "version": "10.9.2",
                "name": "ts-node",
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = NpmRegistrySource()
        version = source.fetch_latest_version("ts_node")

        assert version == "10.9.2"
        # Verify the hyphenated name was used in the API call
        mock_get.assert_called_once_with(
            TestURLs.NPM_REGISTRY.format(package="ts-node"),
            timeout=TestTimeouts.HTTP_REQUEST,
        )

    @patch("version_management.sources.npm.requests.get")
    def test_handles_package_not_found(self, mock_get):
        """Verify HTTP 404 errors are handled gracefully."""
        mock_get.return_value = create_http_error_mock(
            status_code=HTTPStatus.NOT_FOUND,
            message="404 Not Found",
        )

        source = NpmRegistrySource()
        version = source.fetch_latest_version("nonexistent-package")

        assert version is None

    @patch("version_management.sources.npm.requests.get")
    def test_handles_network_timeout(self, mock_get):
        """Verify timeout errors are handled gracefully."""
        mock_get.side_effect = create_timeout_mock().side_effect

        source = NpmRegistrySource()
        version = source.fetch_latest_version(TestPackages.TYPESCRIPT)

        assert version is None

    @patch("version_management.sources.npm.requests.get")
    def test_handles_invalid_json_response(self, mock_get):
        """Verify malformed JSON responses are handled gracefully."""
        mock_get.return_value = create_json_error_mock()

        source = NpmRegistrySource()
        version = source.fetch_latest_version(TestPackages.TYPESCRIPT)

        assert version is None

    @patch("version_management.sources.npm.requests.get")
    def test_handles_missing_version_key(self, mock_get):
        """Verify missing 'version' key is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data={
                "name": TestPackages.TYPESCRIPT,
                "description": "Package description",
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = NpmRegistrySource()
        version = source.fetch_latest_version(TestPackages.TYPESCRIPT)

        assert version is None
