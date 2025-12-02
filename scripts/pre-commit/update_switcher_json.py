"""Update docs/_static/switcher.json for PyData Sphinx Theme version switcher.

Priority order (matches sync_versions.py):
1. Release branch name (release/X.Y.Z takes precedence for active development)
2. Git tag on HEAD (bare X.Y.Z format only)
3. Skip update for non-release branches (main, feature/*, etc.)

Only the most recent version gets "preferred": true.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

SWITCHER_PATH = Path("docs/_static/switcher.json")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_BRANCH_PATTERN = re.compile(r"^release/(\d+\.\d+\.\d+)$")


def get_current_version():
    """Get version from release branch or git tag.

    Priority:
    1. Release branch (release/X.Y.Z -> X.Y.Z)
    2. Git tag on HEAD (bare X.Y.Z only)
    3. None for other branches
    """
    # Check branch first (release branches take precedence)
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    # Priority 1: Release branch
    match = RELEASE_BRANCH_PATTERN.match(branch)
    if match:
        return match.group(1)

    # Priority 2: Git tag on HEAD
    tag = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if tag and VERSION_PATTERN.match(tag):
        return tag

    # Non-release branches don't get switcher entries
    return None


def parse_version(version_str):
    """Parse version string into tuple for comparison."""
    try:
        return tuple(int(x) for x in version_str.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


current_version = get_current_version()

# Skip if not a release branch or tagged commit
if current_version is None:
    print("Skipping switcher update: not a release branch or tagged commit.")
    sys.exit(0)

current_url = f"https://ai-debugger.com/en/{current_version}/"

with SWITCHER_PATH.open() as f:
    entries = json.load(f)

modified = False

# Add entry if it doesn't exist
if not any(e["version"] == current_version for e in entries):
    new_entry = {
        "version": current_version,
        "url": current_url,
    }
    entries.append(new_entry)
    modified = True
    print(f"Added entry for {current_version}")
else:
    print(f"Entry for {current_version} already exists.")


# Sort versions: semantic versions descending, then main, then latest
def version_key(e):
    v = e["version"]
    if v == "latest":
        return (2, (0, 0, 0))
    if v == "main":
        return (1, (0, 0, 0))
    return (0, parse_version(v))


entries = sorted(entries, key=version_key, reverse=True)

# Update preferred flag: only the highest semantic version gets it
highest_version = None
for entry in entries:
    if VERSION_PATTERN.match(entry["version"]):
        if highest_version is None:
            highest_version = entry["version"]
        break

for entry in entries:
    should_be_preferred = entry["version"] == highest_version
    current_preferred = entry.get("preferred", False)

    if should_be_preferred and not current_preferred:
        entry["preferred"] = True
        modified = True
    elif not should_be_preferred and current_preferred:
        del entry["preferred"]
        modified = True

if modified:
    with SWITCHER_PATH.open("w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")
    print(f"Updated switcher.json (preferred: {highest_version})")
