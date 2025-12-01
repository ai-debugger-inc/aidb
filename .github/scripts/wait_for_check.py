#!/usr/bin/env python3
"""
Wait for a GitHub status check to complete before proceeding.

This script polls the GitHub Checks API until the specified check reaches
a terminal state (success or failure), then exits with the appropriate code.
"""

import argparse
import sys
import time
from typing import Any

from utils.github_api import (
    GITHUB_API_BASE_URL,
    get_github_token,
    github_api_request,
    parse_github_repository,
)


def get_check_status(owner: str, repo: str, ref: str, check_name: str, token: str) -> dict[str, Any]:
    """
    Get the status of a specific check run.

    Parameters
    ----------
    owner : str
        Repository owner
    repo : str
        Repository name
    ref : str
        Git commit SHA to check
    check_name : str
        Name of the check to query
    token : str
        GitHub authentication token

    Returns
    -------
    dict[str, Any]
        Dict with 'status' and 'conclusion' fields
        Returns {"status": "not_found", "conclusion": None} if check not found

    Raises
    ------
    HTTPError
        If API request fails
    URLError
        If network request fails
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/commits/{ref}/check-runs"

    try:
        data = github_api_request(url, token)

        # Find the specific check by name
        for check in data.get("check_runs", []):
            if check["name"] == check_name:
                return {
                    "status": check["status"],
                    "conclusion": check.get("conclusion"),
                }

        # Check not found
        return {"status": "not_found", "conclusion": None}

    except Exception as e:
        print(f"API request failed: {e}", file=sys.stderr)
        raise


def wait_for_check(owner: str, repo: str, ref: str, check_name: str, token: str,
                   timeout: int = 600, poll_interval: int = 10) -> bool:
    """
    Wait for a check to complete, polling at regular intervals.

    Parameters
    ----------
    owner : str
        Repository owner
    repo : str
        Repository name
    ref : str
        Git commit SHA to check
    check_name : str
        Name of the check to wait for
    token : str
        GitHub authentication token
    timeout : int, optional
        Maximum time to wait in seconds (default: 600)
    poll_interval : int, optional
        Time between polls in seconds (default: 10)

    Returns
    -------
    bool
        True if check succeeded, False if failed or timed out
    """
    start_time = time.time()

    print(f"Waiting for check '{check_name}' on {ref[:8]}...")

    while True:
        elapsed = time.time() - start_time

        if elapsed > timeout:
            print(f"Timeout after {timeout}s waiting for check '{check_name}'", file=sys.stderr)
            return False

        try:
            result = get_check_status(owner, repo, ref, check_name, token)
            status = result["status"]
            conclusion = result["conclusion"]

            if status == "not_found":
                print(f"Check '{check_name}' not found yet, waiting... ({int(elapsed)}s)")
            elif status == "completed":
                if conclusion == "success":
                    print(f"✓ Check '{check_name}' succeeded")
                    return True
                print(f"✗ Check '{check_name}' failed with conclusion: {conclusion}", file=sys.stderr)
                return False
            else:
                # In progress
                print(f"Check '{check_name}' is {status}, waiting... ({int(elapsed)}s)")

        except Exception as e:
            print(f"Error checking status: {e}", file=sys.stderr)
            # Continue polling on transient errors

        time.sleep(poll_interval)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Wait for a GitHub check to complete")
    parser.add_argument("--owner", help="Repository owner")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument("--ref", required=True, help="Git commit SHA to check")
    parser.add_argument("--check-name", required=True, help="Name of the check to wait for")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")
    parser.add_argument("--poll-interval", type=int, default=10, help="Poll interval in seconds (default: 10)")

    args = parser.parse_args()

    # Get GitHub token and parse repository
    token = get_github_token()
    owner, repo = parse_github_repository(args.owner, args.repo)

    # Wait for the check
    success = wait_for_check(
        owner,
        repo,
        args.ref,
        args.check_name,
        token,
        args.timeout,
        args.poll_interval,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
