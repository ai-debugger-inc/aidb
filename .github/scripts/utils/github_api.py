"""Shared GitHub API utilities for CI/CD scripts."""

import json
import os
import sys
import time
from typing import Any
from urllib import request
from urllib.error import HTTPError

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_ACCEPT_HEADER = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"


class RetryableError(Exception):
    """Error that should trigger a retry attempt."""


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """
    Decorator for retrying functions with exponential backoff.

    Parameters
    ----------
    max_retries : int, optional
        Maximum number of retry attempts (default: 3)
    base_delay : float, optional
        Initial delay between retries in seconds (default: 1.0)
    max_delay : float, optional
        Maximum delay between retries in seconds (default: 60.0)

    Returns
    -------
    callable
        Decorated function with retry logic

    Notes
    -----
    - Only retries on RetryableError exceptions
    - Uses exponential backoff: delay = min(base_delay * (2 ** attempt), max_delay)
    - Non-retryable errors are raised immediately
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except RetryableError as e:
                    if attempt == max_retries - 1:
                        print(
                            f"Error: Max retries ({max_retries}) reached for {func.__name__}: {e}",
                            file=sys.stderr,
                        )
                        raise

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    print(
                        f"Warning: Retry {attempt + 1}/{max_retries} for {func.__name__} after {delay}s: {e}",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                except Exception:
                    # Non-retryable errors get raised immediately
                    raise

            return None  # Should never reach here
        return wrapper
    return decorator


def get_github_token() -> str:
    """
    Get GitHub authentication token from environment.

    Returns
    -------
    str
        GitHub authentication token

    Raises
    ------
    SystemExit
        If GITHUB_TOKEN environment variable is not set
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)
    return token


def parse_github_repository(owner: str | None = None, repo: str | None = None) -> tuple[str, str]:
    """
    Parse owner and repo from GITHUB_REPOSITORY environment variable.

    Parameters
    ----------
    owner : str | None, optional
        Repository owner (if already provided)
    repo : str | None, optional
        Repository name (if already provided)

    Returns
    -------
    tuple[str, str]
        Tuple of (owner, repo)

    Raises
    ------
    SystemExit
        If GITHUB_REPOSITORY is not set or has invalid format
    """
    if owner and repo:
        return owner, repo

    github_repo = os.environ.get("GITHUB_REPOSITORY")
    if not github_repo:
        print(
            "Error: --owner and --repo required, or set GITHUB_REPOSITORY",
            file=sys.stderr,
        )
        sys.exit(1)

    parts = github_repo.split("/")
    if len(parts) != 2:  # noqa: PLR2004
        print(
            f"Error: Invalid GITHUB_REPOSITORY format: {github_repo}",
            file=sys.stderr,
        )
        sys.exit(1)

    return owner or parts[0], repo or parts[1]


@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=10.0)
def github_api_request(url: str, token: str) -> dict[str, Any]:
    """
    Make authenticated GitHub API request with automatic retry logic.

    Parameters
    ----------
    url : str
        GitHub API endpoint URL
    token : str
        GitHub authentication token

    Returns
    -------
    dict[str, Any]
        API response data (empty dict on 404)

    Raises
    ------
    HTTPError
        If API request fails after retries (except 404)
    URLError
        If network request fails after retries
    RetryableError
        If max retries exceeded on transient errors

    Notes
    -----
    Automatically retries on transient errors (429, 500, 502, 503, 504)
    with exponential backoff. Does not retry on client errors (4xx except 429).
    """
    headers = {
        "Accept": GITHUB_API_ACCEPT_HEADER,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    req = request.Request(url, headers=headers)  # noqa: S310

    try:
        with request.urlopen(req) as response:  # noqa: S310
            return json.loads(response.read().decode())
    except HTTPError as e:
        if e.code == 404:  # noqa: PLR2004
            return {}

        # Retry on rate limits and server errors
        if e.code in {429, 500, 502, 503, 504}:  # noqa: PLR2004
            msg = f"GitHub API returned {e.code}: {e.reason}"
            raise RetryableError(msg) from e

        # Don't retry on client errors (400, 401, 403, etc.)
        raise
