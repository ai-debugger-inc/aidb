"""Unit tests for PyPISource class."""

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
from version_management.sources.pypi import PyPISource


class TestPyPISource:
    """Test PyPISource functionality."""

    @patch("version_management.sources.pypi.requests.get")
    def test_fetch_latest_version_success(self, mock_get):
        """Verify fetching latest package version from PyPI."""
        mock_response = MockHTTPResponse(
            json_data={
                "info": {
                    "version": "3.12.1",
                    "name": TestPackages.SETUPTOOLS,
                    "summary": "Easily download, build, install, upgrade...",
                },
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = PyPISource()
        version = source.fetch_latest_version(TestPackages.SETUPTOOLS)

        assert version == "3.12.1"
        mock_get.assert_called_once_with(
            TestURLs.PYPI_API.format(package=TestPackages.SETUPTOOLS),
            timeout=TestTimeouts.HTTP_REQUEST,
        )

    @patch("version_management.sources.pypi.requests.get")
    def test_handles_package_not_found(self, mock_get):
        """Verify HTTP 404 errors are handled gracefully."""
        mock_get.return_value = create_http_error_mock(
            status_code=HTTPStatus.NOT_FOUND,
            message="404 Not Found",
        )

        source = PyPISource()
        version = source.fetch_latest_version("nonexistent-package")

        assert version is None

    @patch("version_management.sources.pypi.requests.get")
    def test_handles_network_timeout(self, mock_get):
        """Verify timeout errors are handled gracefully."""
        mock_get.side_effect = create_timeout_mock().side_effect

        source = PyPISource()
        version = source.fetch_latest_version(TestPackages.SETUPTOOLS)

        assert version is None

    @patch("version_management.sources.pypi.requests.get")
    def test_handles_invalid_json_response(self, mock_get):
        """Verify malformed JSON responses are handled gracefully."""
        mock_get.return_value = create_json_error_mock()

        source = PyPISource()
        version = source.fetch_latest_version(TestPackages.SETUPTOOLS)

        assert version is None

    @patch("version_management.sources.pypi.requests.get")
    def test_handles_missing_info_key(self, mock_get):
        """Verify missing 'info' key is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data={"releases": {}, "urls": []},
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = PyPISource()
        version = source.fetch_latest_version(TestPackages.SETUPTOOLS)

        assert version is None

    @patch("version_management.sources.pypi.requests.get")
    def test_handles_missing_version_key(self, mock_get):
        """Verify missing 'version' key in info is handled gracefully."""
        mock_response = MockHTTPResponse(
            json_data={
                "info": {
                    "name": TestPackages.SETUPTOOLS,
                    "summary": "Package description",
                },
            },
            status_code=HTTPStatus.OK,
        )
        mock_get.return_value = mock_response

        source = PyPISource()
        version = source.fetch_latest_version(TestPackages.SETUPTOOLS)

        assert version is None
