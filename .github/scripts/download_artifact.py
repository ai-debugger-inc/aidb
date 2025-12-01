#!/usr/bin/env python3
"""
Download GitHub Actions artifact from another workflow run.

This script provides cross-workflow artifact download functionality,
replacing third-party actions with native GitHub API integration.
"""

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Any
from urllib import request

from utils.github_api import (
    GITHUB_API_ACCEPT_HEADER,
    GITHUB_API_BASE_URL,
    GITHUB_API_VERSION,
    get_github_token,
    github_api_request,
    parse_github_repository,
)


def find_workflow_run(
    owner: str,
    repo: str,
    workflow: str,
    commit: str,
    token: str,
    conclusion: str = "success",
) -> str | None:
    """
    Find workflow run ID for the given commit.

    Parameters
    ----------
    owner : str
        Repository owner
    repo : str
        Repository name
    workflow : str
        Workflow file name (e.g., 'adapter-build.yaml')
    commit : str
        Git commit SHA
    token : str
        GitHub authentication token
    conclusion : str, optional
        Required workflow conclusion (default: 'success')

    Returns
    -------
    str | None
        Workflow run ID if found, None otherwise
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow}/runs"
    params = f"?status=completed&head_sha={commit}"

    data = github_api_request(url + params, token)

    for run in data.get("workflow_runs", []):
        if run.get("conclusion") == conclusion:
            return str(run["id"])

    return None


def find_artifact(
    owner: str, repo: str, run_id: str, artifact_name: str, token: str,
) -> dict[str, Any] | None:
    """
    Find artifact by name in the workflow run.

    Parameters
    ----------
    owner : str
        Repository owner
    repo : str
        Repository name
    run_id : str
        Workflow run ID
    artifact_name : str
        Name of the artifact to find
    token : str
        GitHub authentication token

    Returns
    -------
    dict[str, Any] | None
        Artifact metadata if found, None otherwise
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    data = github_api_request(url, token)

    for artifact in data.get("artifacts", []):
        if artifact["name"] == artifact_name:
            return artifact  # type: ignore[no-any-return]

    return None


def download_artifact(
    owner: str, repo: str, artifact_id: str, output_path: Path, token: str,
) -> None:
    """
    Download and extract artifact to the specified path.

    Parameters
    ----------
    owner : str
        Repository owner
    repo : str
        Repository name
    artifact_id : str
        Artifact ID
    output_path : Path
        Directory to extract artifact contents
    token : str
        GitHub authentication token
    """
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"

    headers = {
        "Accept": GITHUB_API_ACCEPT_HEADER,
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }

    req = request.Request(url, headers=headers)  # noqa: S310

    # GitHub returns the artifact ZIP file directly
    with request.urlopen(req) as response:  # noqa: S310
        # Ensure output directory exists before writing temp file
        output_path.mkdir(parents=True, exist_ok=True)

        # Save to temporary file
        temp_zip = output_path.parent / f"{artifact_id}.zip"
        temp_zip.write_bytes(response.read())

    # Extract
    with zipfile.ZipFile(temp_zip, "r") as zip_ref:
        zip_ref.extractall(output_path)

    # Cleanup
    temp_zip.unlink()


def main() -> None:  # noqa: C901
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Download GitHub Actions artifact from another workflow",
    )
    parser.add_argument("--owner", help="Repository owner")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument(
        "--workflow", required=True, help="Workflow file name (e.g., adapter-build.yaml)",
    )
    parser.add_argument("--commit", required=True, help="Git commit SHA")
    parser.add_argument("--name", required=True, help="Artifact name to download")
    parser.add_argument("--path", required=True, help="Output directory path")
    parser.add_argument(
        "--workflow-conclusion",
        default="success",
        help="Required workflow conclusion (default: success)",
    )
    parser.add_argument(
        "--if-no-artifact-found",
        default="fail",
        choices=["fail", "warn", "ignore"],
        help="Action when artifact not found (default: fail)",
    )

    args = parser.parse_args()

    # Get GitHub token and parse repository
    token = get_github_token()
    owner, repo = parse_github_repository(args.owner, args.repo)

    # Find workflow run
    print(f"Finding workflow run for {args.workflow} @ {args.commit[:8]}...")
    run_id = find_workflow_run(
        owner,
        repo,
        args.workflow,
        args.commit,
        token,
        args.workflow_conclusion,
    )

    if not run_id:
        msg = f"No {args.workflow_conclusion} run found for workflow '{args.workflow}' at commit {args.commit[:8]}"
        if args.if_no_artifact_found == "fail":
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)
        if args.if_no_artifact_found == "warn":
            print(f"Warning: {msg}", file=sys.stderr)
            sys.exit(0)
        # ignore
        sys.exit(0)

    print(f"Found run ID: {run_id}")

    # Find artifact
    print(f"Looking for artifact '{args.name}'...")
    artifact = find_artifact(owner, repo, run_id, args.name, token)

    if not artifact:
        msg = f"Artifact '{args.name}' not found in run {run_id}"
        if args.if_no_artifact_found == "fail":
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(1)
        if args.if_no_artifact_found == "warn":
            print(f"Warning: {msg}", file=sys.stderr)
            sys.exit(0)
        # ignore
        sys.exit(0)

    print(f"Found artifact ID: {artifact['id']} (size: {artifact['size_in_bytes']} bytes)")

    # Download and extract
    output_path = Path(args.path)
    print(f"Downloading to {output_path}...")
    download_artifact(owner, repo, str(artifact["id"]), output_path, token)

    print("✓ Artifact downloaded and extracted successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()
