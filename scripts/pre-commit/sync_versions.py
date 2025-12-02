#!/usr/bin/env python3
"""Synchronize version numbers across the codebase based on git tags and branches.

Priority order:
1. Release branch name (release/X.Y.Z takes precedence for active development)
2. Git tag on HEAD (bare X.Y.Z format only, for non-release branches)
3. Default to 0.0.0 for all non-release branches

Version Strategy:
- Production releases only (no pre-release suffixes)
- Release branches: release/X.Y.Z (e.g., release/1.0.0)
- Git tags: X.Y.Z (bare version, no v prefix or suffixes)
- Development branches (main, feature/*, etc.): always 0.0.0
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def get_git_branch():
    """Get the current git branch name."""
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


def get_version_from_git_tag():
    """Get version from git tag if HEAD is tagged.

    Only matches bare X.Y.Z tags (production releases only).
    Examples:
    - 1.0.0 -> 1.0.0
    - 2.1.3 -> 2.1.3

    Rejects tags with prefixes or suffixes:
    - v1.0.0 (has v prefix)
    - 1.0.0-prod (has suffix)
    - 1.0.0-test (has suffix)

    Returns
    -------
    tuple[str | None, str | None]
        (version, source) or (None, None) if no tag found or tag doesn't match
    """
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            # Only match bare X.Y.Z tags (no prefix, no suffix)
            if re.match(r"^(\d+\.\d+\.\d+)$", tag):
                return tag, f"git_tag ({tag})"
    except (subprocess.SubprocessError, OSError):
        # Git command failed or not available
        pass
    return None, None


def extract_version_from_branch(branch_name):
    """Extract version from branch name if it matches release/X.Y.Z pattern.

    Only production releases are supported (no pre-release suffixes).
    Examples:
    - release/1.0.0 -> 1.0.0
    - release/2.1.3 -> 2.1.3
    - release/0.1.0 -> 0.1.0

    All non-release branches default to 0.0.0:
    - main -> 0.0.0
    - develop -> 0.0.0
    - feature/auth -> 0.0.0
    - bugfix/login -> 0.0.0

    Parameters
    ----------
    branch_name : str
        The git branch name to extract version from

    Returns
    -------
    str
        Extracted version (X.Y.Z) or "0.0.0" for non-release branches
    """
    if not branch_name:
        return "0.0.0"

    # Match release/X.Y.Z pattern (production only, no suffixes)
    release_pattern = r"^release/(\d+\.\d+\.\d+)$"
    match = re.match(release_pattern, branch_name)

    if match:
        return match.group(1)  # Extract version number

    # All non-release branches default to 0.0.0
    return "0.0.0"


def update_pyproject_toml(version, repo_root):
    """Update version in pyproject.toml."""
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    content = pyproject_path.read_text()

    # Only update the version in the [project] section, not tool sections
    # Split by sections and only update in project section
    lines = content.split("\n")
    in_project_section = False
    updated = False
    new_lines = []

    for line in lines:
        if line.strip() == "[project]":
            in_project_section = True
        elif line.strip().startswith("[") and in_project_section:
            in_project_section = False

        if in_project_section and line.strip().startswith("version"):
            new_line = f'version = "{version}"'
            if line != new_line:
                updated = True
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if updated:
        pyproject_path.write_text("\n".join(new_lines))
        print(f"Updated pyproject.toml to version {version}")
        return True
    return False


def update_python_init_files(version, repo_root):
    """Update __version__ in Python __init__.py files."""
    init_files = [
        repo_root / "src" / "aidb" / "__init__.py",
        repo_root / "src" / "aidb_mcp" / "__init__.py",
        repo_root / "src" / "aidb_logging" / "__init__.py",
        repo_root / "src" / "aidb_cli" / "__init__.py",
        repo_root / "src" / "aidb_common" / "__init__.py",
        repo_root / "src" / "aidb" / "dap" / "client" / "__init__.py",
    ]

    updated = []
    for init_file in init_files:
        if not init_file.exists():
            # Create with __version__ if doesn't exist
            if init_file == repo_root / "src" / "aidb" / "__init__.py":
                # Read existing content and append version
                content = init_file.read_text()
                if "__version__" not in content:
                    content += f'\n__version__ = "{version}"\n'
                    init_file.write_text(content)
                    updated.append(init_file)
            continue

        content = init_file.read_text()

        # Check if __version__ exists
        if "__version__" in content:
            # Update existing __version__
            pattern = r'__version__\s*=\s*["\'][^"\']+["\']'
            new_content = re.sub(pattern, f'__version__ = "{version}"', content)
        else:
            # Add __version__ at the end
            new_content = content.rstrip() + f'\n\n__version__ = "{version}"\n'

        if content != new_content:
            init_file.write_text(new_content)
            updated.append(init_file)

    if updated:
        for f in updated:
            print(f"Updated {f.relative_to(repo_root)}")

    return len(updated) > 0


def update_config_files(version, repo_root):
    """Update version in config files."""
    updates = []

    # Update MCP config
    mcp_config = repo_root / "src" / "aidb_mcp" / "core" / "config.py"
    if mcp_config.exists():
        content = mcp_config.read_text()
        # Update server_version
        pattern = r'(server_version:\s*str\s*=\s*")[^"]+(")'
        new_content = re.sub(pattern, rf"\g<1>{version}\g<2>", content)

        # Also update the environment variable default
        pattern2 = (
            r'(server_version=os\.environ\.get\("AIDB_SERVER_VERSION",\s*")[^"]+("\))'
        )
        new_content = re.sub(pattern2, rf"\g<1>{version}\g<2>", new_content)

        if content != new_content:
            mcp_config.write_text(new_content)
            updates.append(mcp_config)

    if updates:
        for f in updates:
            print(f"Updated {f.relative_to(repo_root)}")

    return len(updates) > 0


def update_versions_json(version, repo_root):
    """Update version in versions.json."""
    versions_path = repo_root / "versions.json"
    if not versions_path.exists():
        return False

    with versions_path.open() as f:
        data = json.load(f)

    if data.get("version") != version:
        data["version"] = version

        with versions_path.open("w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")  # Add trailing newline

        print(f"Updated versions.json to version {version}")
        return True
    return False


def update_vscode_extension_package_json(version, repo_root):
    """Update version in VSCode extension package.json."""
    package_json_path = (
        repo_root / "src" / "extensions" / "aidb-vscode-bridge" / "package.json"
    )
    if not package_json_path.exists():
        return False

    try:
        with package_json_path.open() as f:
            data = json.load(f)

        if data.get("version") != version:
            data["version"] = version

            with package_json_path.open("w") as f:
                json.dump(data, f, indent=2)

            print(f"Updated {package_json_path.relative_to(repo_root)}")
            return True
    except (json.JSONDecodeError, KeyError):
        pass

    return False


def update_workflow_aidb_version(version, repo_root):
    """Update AIDB_VERSION in GitHub Actions workflows."""
    workflow_files = [
        repo_root / ".github" / "workflows" / "adapters" / "build.yaml",
        repo_root / ".github" / "workflows" / "adapters" / "build-act.yaml",
    ]

    updated = []
    for workflow_file in workflow_files:
        if not workflow_file.exists():
            continue

        content = workflow_file.read_text()
        original_content = content

        # Update AIDB_VERSION
        if "AIDB_VERSION:" in content:
            # Update existing AIDB_VERSION
            pattern = r'(\s+AIDB_VERSION:\s*")[^"]+(".*)'
            content = re.sub(pattern, rf"\g<1>{version}\g<2>", content)

        if original_content != content:
            workflow_file.write_text(content)
            updated.append(workflow_file)

    if updated:
        for f in updated:
            print(f"Updated {f.relative_to(repo_root)}")

    return len(updated) > 0


def create_version_file(version, repo_root):
    """Create .version file with current version."""
    version_file = repo_root / ".version"
    version_file.write_text(f"{version}\n")
    print(f"Created .version file with version {version}")
    return True


def main():
    """Main function to sync versions."""
    # Get repository root
    repo_root = Path(__file__).parent.parent.parent.absolute()

    # Get branch name first
    branch = get_git_branch()

    # Priority 1: Release branch name (takes precedence for active development)
    # This ensures release/X.Y.Z branches use their version, not a stale tag
    if branch and branch.startswith("release/"):
        version = extract_version_from_branch(branch)
        version_source = f"release branch ({branch})"
    else:
        # Priority 2: Git tag on HEAD (for tagged commits on non-release branches)
        version, version_source = get_version_from_git_tag()

        # Priority 3: Branch name fallback (defaults to 0.0.0 for dev branches)
        if not version:
            version = extract_version_from_branch(branch)
            version_source = f"branch ({branch or 'unknown'})"

    print(f"Version source: {version_source}")
    print(f"Version: {version}")

    # Update all version references
    changes = False
    changes |= update_pyproject_toml(version, repo_root)
    changes |= update_python_init_files(version, repo_root)
    changes |= update_config_files(version, repo_root)
    changes |= update_versions_json(version, repo_root)
    changes |= update_vscode_extension_package_json(version, repo_root)
    changes |= update_workflow_aidb_version(version, repo_root)
    changes |= create_version_file(version, repo_root)

    if changes:
        print(f"✅ Version synchronized to {version}")
    else:
        print(f"📄 No version changes needed (already at {version})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
