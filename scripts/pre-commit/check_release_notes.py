#!/usr/bin/env python3
"""Check that release notes exist for release branches.

On release branches (release/X.Y.Z), this script verifies that the corresponding
release notes file exists at docs/release-notes/X.Y.Z.md.

This prevents pushing release branches without documentation, which causes CI
failures in the validate-and-extract-version job.
"""

import re
import subprocess
import sys
from pathlib import Path


def get_git_branch() -> str | None:
    """Get the current git branch name.

    Returns
    -------
    str | None
        Branch name or None if not in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def extract_version_from_branch(branch_name: str) -> str | None:
    """Extract version from release branch name.

    Parameters
    ----------
    branch_name : str
        Git branch name (e.g., 'release/1.0.0')

    Returns
    -------
    str | None
        Version string (e.g., '1.0.0') or None if not a release branch
    """
    match = re.match(r"^release/(\d+\.\d+\.\d+)$", branch_name)
    if match:
        return match.group(1)
    return None


def main() -> int:
    """Check release notes exist for release branches.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure)
    """
    # Get repository root
    repo_root = Path(__file__).parent.parent.parent.absolute()
    release_notes_dir = repo_root / "docs" / "release-notes"
    template_path = release_notes_dir / "template.md"

    # Get current branch
    branch = get_git_branch()
    if not branch:
        # Not in a git repository or detached HEAD - skip check
        return 0

    # Check if on a release branch
    version = extract_version_from_branch(branch)
    if not version:
        # Not a release branch - skip check
        return 0

    # Check if release notes exist
    release_notes_path = release_notes_dir / f"{version}.md"
    if release_notes_path.exists():
        print(f"✅ Release notes found: docs/release-notes/{version}.md")
        return 0

    # Release notes missing - fail with helpful message
    print(f"❌ Release notes missing for version {version}")
    print()
    print(f"You are on branch '{branch}' but the release notes file is missing:")
    print(f"  docs/release-notes/{version}.md")
    print()
    print("This will cause CI to fail at the validate-and-extract-version step.")
    print()
    print("To fix this:")
    print(
        f"  1. Copy the template: cp docs/release-notes/template.md docs/release-notes/{version}.md",
    )
    print("  2. Update the version number and add release notes content")
    print(f"  3. Stage and commit the file: git add docs/release-notes/{version}.md")
    print()

    if template_path.exists():
        print("Template contents for reference:")
        print("-" * 60)
        print(template_path.read_text())
        print("-" * 60)

    return 1


if __name__ == "__main__":
    sys.exit(main())
