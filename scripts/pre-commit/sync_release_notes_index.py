#!/usr/bin/env python3
"""Synchronize release notes index with discovered release note files.

Scans docs/release-notes/ for version-named markdown files and updates the
toctree in docs/release-notes/index.md to list all discovered release notes
in descending version order (newest first).
"""

import re
import sys
from pathlib import Path


def parse_version(filename):
    """Extract version tuple from filename for sorting.

    Args:
        filename: Filename like "1.2.3.md"

    Returns:
        Tuple of (major, minor, patch) or None if not a valid version
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)\.md$", filename)
    if match:
        return tuple(int(x) for x in match.groups())
    return None


def discover_release_notes(release_notes_dir):
    """Discover all release note markdown files.

    Args:
        release_notes_dir: Path to docs/release-notes directory

    Returns:
        List of (version_tuple, filename) sorted by version descending
    """
    release_notes = []

    for md_file in release_notes_dir.glob("*.md"):
        # Skip template and index files
        if md_file.name in ("template.md", "index.md"):
            continue

        version = parse_version(md_file.name)
        if version:
            release_notes.append((version, md_file.name))
        else:
            print(
                f"Warning: Skipping {md_file.name} - doesn't match version pattern #.#.#.md",
            )

    # Sort by version descending (newest first)
    release_notes.sort(reverse=True)

    return release_notes


def update_index_toctree(index_path, release_notes):
    """Update the toctree section in index.md with discovered release notes.

    Args:
        index_path: Path to docs/release-notes/index.md
        release_notes: List of (version_tuple, filename) tuples

    Returns:
        True if changes were made, False otherwise
    """
    if not index_path.exists():
        print(f"Error: {index_path} not found")
        return False

    content = index_path.read_text()
    lines = content.split("\n")

    # Find the toctree section
    toctree_start = None
    toctree_end = None

    for i, line in enumerate(lines):
        if line.strip() == "```{toctree}":
            toctree_start = i
        elif toctree_start is not None and line.strip() == "```":
            toctree_end = i
            break

    if toctree_start is None or toctree_end is None:
        print("Error: Could not find toctree section in index.md")
        return False

    # Build new toctree content
    new_toctree_lines = [
        "```{toctree}",
        "---",
        "maxdepth: 1",
        "caption: Releases",
        "---",
    ]

    for _version, filename in release_notes:
        # Remove .md extension for toctree reference
        new_toctree_lines.append(f"{filename[:-3]}")

    new_toctree_lines.append("```")

    # Replace the toctree section
    new_lines = lines[:toctree_start] + new_toctree_lines + lines[toctree_end + 1 :]
    new_content = "\n".join(new_lines)

    # Check if changes were made
    if content == new_content:
        return False

    # Write updated content
    index_path.write_text(new_content)
    return True


def main():
    """Main function to sync release notes index."""
    # Get repository root
    repo_root = Path(__file__).parent.parent.parent.absolute()
    release_notes_dir = repo_root / "docs" / "release-notes"
    index_path = release_notes_dir / "index.md"

    if not release_notes_dir.exists():
        print(f"Error: Release notes directory not found: {release_notes_dir}")
        return 1

    # Discover release notes
    release_notes = discover_release_notes(release_notes_dir)

    if release_notes:
        versions = ", ".join(".".join(str(x) for x in v) for v, _ in release_notes)
        print(f"Found {len(release_notes)} release note(s): {versions}")
    else:
        print("No release notes found (this is OK for new repositories)")

    # Update index
    if update_index_toctree(index_path, release_notes):
        print(f"✅ Updated {index_path.relative_to(repo_root)}")
    else:
        print(f"📄 No changes needed to {index_path.relative_to(repo_root)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
