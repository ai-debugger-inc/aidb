"""Shared test utilities for CI/CD tests."""

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, Mock, patch


@contextmanager
def mock_script_environment(platform="Linux", machine="x86_64", json_data=None):
    """Mock common script execution environment.

    Parameters
    ----------
    platform : str
        Platform name for platform.system()
    machine : str
        Machine type for platform.machine()
    json_data : dict, optional
        Data to return from json.load()

    Yields
    ------
    dict
        Dictionary of mock objects (platform_mock, machine_mock, json_mock, open_mock)
    """
    import builtins
    from unittest.mock import mock_open

    with (
        patch("platform.system", return_value=platform) as platform_mock,
        patch("platform.machine", return_value=machine) as machine_mock,
        patch("json.load", return_value=json_data) as json_mock,
        patch("builtins.open", mock_open(read_data="")) as open_mock,
    ):
        yield {
            "platform": platform_mock,
            "machine": machine_mock,
            "json": json_mock,
            "open": open_mock,
        }


def create_mock_versions_config(**overrides) -> dict[str, Any]:
    """Create a mock versions.json configuration with sensible defaults.

    Parameters
    ----------
    **overrides : dict
        Override default values (deep merge)

    Returns
    -------
    dict[str, Any]
        Mock configuration
    """
    base_config = {
        "version": "1.0.0",
        "platforms": [
            {"platform": "linux", "arch": "x64"},
            {"platform": "linux", "arch": "arm64"},
            {"platform": "darwin", "arch": "x64"},
            {"platform": "darwin", "arch": "arm64"},
            {"platform": "windows", "arch": "x64"},
        ],
        "infrastructure": {
            "python": {"version": "3.11.0"},
            "node": {"version": "20.0.0"},
            "java": {"version": "21.0.0"},
        },
        "adapters": {
            "python": {
                "version": "1.8.0",
                "debugpy_version": "1.8.0",
            },
            "javascript": {"version": "1.85.0"},
            "java": {"version": "0.50.0"},
        },
    }

    # Deep merge overrides
    _deep_merge(base_config, overrides)
    return base_config


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override dict into base dict (in-place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def create_mock_github_release(
    tag_name: str = "v1.8.0",
    published_at: str = "2024-01-01T00:00:00Z",
    prerelease: bool = False,
    draft: bool = False,
    body: str = "Release notes",
) -> dict[str, Any]:
    """Create a mock GitHub release data structure.

    Parameters
    ----------
    tag_name : str
        Release tag
    published_at : str
        Publication timestamp (ISO format)
    prerelease : bool
        Whether this is a prerelease
    draft : bool
        Whether this is a draft
    body : str
        Release notes

    Returns
    -------
    dict[str, Any]
        Mock release data
    """
    return {
        "tag_name": tag_name,
        "published_at": published_at,
        "prerelease": prerelease,
        "draft": draft,
        "body": body,
        "html_url": f"https://github.com/example/repo/releases/tag/{tag_name}",
    }


def create_mock_endoflife_response(
    cycle: str = "3.11",
    latest: str = "3.11.7",
    eol: str | bool = "2027-10-31",
    support: str | bool = "2024-10-31",
) -> dict[str, Any]:
    """Create a mock endoflife.date API response.

    Parameters
    ----------
    cycle : str
        Version cycle (e.g., "3.11")
    latest : str
        Latest version in cycle
    eol : str | bool
        End of life date or False
    support : str | bool
        End of support date or False

    Returns
    -------
    dict[str, Any]
        Mock endoflife.date response
    """
    return {
        "cycle": cycle,
        "latest": latest,
        "eol": eol,
        "support": support,
    }


class MockHTTPResponse:
    """Mock HTTP response for testing API interactions."""

    def __init__(
        self,
        json_data: dict[str, Any] | list[Any] | None = None,
        status_code: int = 200,
        text: str = "",
    ):
        """Initialize mock response.

        Parameters
        ----------
        json_data : dict | list | None
            JSON response data
        status_code : int
            HTTP status code
        text : str
            Response text
        """
        self._json_data = json_data
        self.status_code = status_code
        self.text = text or (str(json_data) if json_data else "")

    def json(self) -> dict[str, Any] | list[Any]:
        """Return JSON data."""
        if self._json_data is None:
            msg = "No JSON data"
            raise ValueError(msg)
        return self._json_data

    def raise_for_status(self) -> None:
        """Raise exception for error status codes."""
        if self.status_code >= 400:
            from requests.exceptions import HTTPError

            msg = f"{self.status_code} Error"
            raise HTTPError(msg)


def create_mock_checker_instance(update_results: dict[str, Any] | None = None) -> Mock:
    """Create a mock checker instance.

    Parameters
    ----------
    update_results : dict | None
        Results to return from check_updates()

    Returns
    -------
    Mock
        Mock checker instance
    """
    checker = Mock()
    checker.check_updates.return_value = update_results or {}
    return checker


def create_http_error_mock(status_code: int = 404, message: str = "Not Found") -> Mock:
    """Create a mock HTTP response that raises HTTPError.

    Parameters
    ----------
    status_code : int
        HTTP status code
    message : str
        Error message

    Returns
    -------
    Mock
        Mock response that raises HTTPError when raise_for_status() is called
    """
    import requests

    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = requests.HTTPError(message)
    return mock_response


def create_timeout_mock() -> Mock:
    """Create a mock that raises requests.Timeout.

    Returns
    -------
    Mock
        Mock that raises Timeout when called
    """
    import requests

    mock = Mock()
    mock.side_effect = requests.Timeout("Connection timeout")
    return mock


def create_json_error_mock() -> Mock:
    """Create a mock HTTP response with invalid JSON.

    Returns
    -------
    Mock
        Mock response where json() raises ValueError
    """
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("Invalid JSON")
    return mock_response


def create_rate_limit_mock(status_code: int = 429) -> Mock:
    """Create a mock HTTP response for rate limit errors.

    Parameters
    ----------
    status_code : int
        HTTP status code (typically 429)

    Returns
    -------
    Mock
        Mock response that raises HTTPError for rate limiting
    """
    import requests

    mock_response = Mock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        f"{status_code} Rate Limit Exceeded",
    )
    return mock_response
