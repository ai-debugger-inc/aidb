#!/usr/bin/env python3
"""Validate skill references and suggest updates.

This pre-commit hook performs two key validations:

1. Validates all file links in SKILL.md files point to existing files
2. Suggests new directories that may benefit from skill triggers

Exit codes:
    0: Success (warnings are informational only)
    1: Validation failure (broken links found)
"""

import json
import re
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Get repository root directory.

    Returns
    -------
    Path
        Repository root directory
    """
    return Path(__file__).parent.parent.parent


def find_markdown_links(content: str, base_path: Path) -> set[Path]:
    """Extract and resolve all file links from markdown content.

    Parameters
    ----------
    content : str
        Markdown content to parse
    base_path : Path
        Base path for resolving relative links

    Returns
    -------
    Set[Path]
        Set of absolute paths referenced in the markdown
    """
    links = set()

    # Match markdown links: [text](path) and [text](path#anchor)
    md_link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
    for match in re.finditer(md_link_pattern, content):
        link_target = match.group(2)

        # Skip external URLs
        if link_target.startswith(("http://", "https://", "mailto:")):
            continue

        # Remove anchor fragments
        if "#" in link_target:
            link_target = link_target.split("#")[0]

        # Skip empty links (pure anchors)
        if not link_target:
            continue

        # Resolve relative path
        resolved = (base_path / link_target).resolve()
        links.add(resolved)

    return links


def validate_skill_links(skills_dir: Path, repo_root: Path) -> tuple[list[str], int]:
    """Validate all file links in skill files exist.

    Parameters
    ----------
    skills_dir : Path
        Path to .claude/skills directory
    repo_root : Path
        Repository root directory

    Returns
    -------
    tuple[list[str], int]
        List of broken link error messages and total links checked
    """
    errors = []
    total_links = 0

    for skill_file in skills_dir.glob("*/SKILL.md"):
        content = skill_file.read_text()
        links = find_markdown_links(content, skill_file.parent)

        for link in links:
            total_links += 1
            if not link.exists():
                rel_skill = skill_file.relative_to(repo_root)
                rel_link = (
                    link.relative_to(repo_root)
                    if link.is_relative_to(repo_root)
                    else link
                )
                errors.append(f"  {rel_skill} → {rel_link} (MISSING)")

    # Also check resource files
    for resource_file in skills_dir.glob("*/resources/*.md"):
        content = resource_file.read_text()
        links = find_markdown_links(content, resource_file.parent)

        for link in links:
            total_links += 1
            if not link.exists():
                rel_resource = resource_file.relative_to(repo_root)
                rel_link = (
                    link.relative_to(repo_root)
                    if link.is_relative_to(repo_root)
                    else link
                )
                errors.append(f"  {rel_resource} → {rel_link} (MISSING)")

    return errors, total_links


def get_skill_path_patterns(repo_root: Path) -> set[str]:
    """Extract all pathPatterns from skill-rules.json.

    Parameters
    ----------
    repo_root : Path
        Repository root directory

    Returns
    -------
    Set[str]
        Set of path patterns from fileTriggers
    """
    skill_rules_path = repo_root / ".claude" / "skills" / "skill-rules.json"
    if not skill_rules_path.exists():
        return set()

    try:
        with skill_rules_path.open() as f:
            data = json.load(f)

        # Handle both old and new schema formats
        skills = data.get("skills", data)

        patterns = set()
        for skill_config in skills.values():
            # Skip if the value is not a dict (e.g., version string)
            if not isinstance(skill_config, dict):
                continue

            file_triggers = skill_config.get("fileTriggers", {})
            path_patterns = file_triggers.get("pathPatterns", [])
            patterns.update(path_patterns)

        return patterns
    except (json.JSONDecodeError, KeyError):
        return set()


def suggest_new_path_patterns(repo_root: Path) -> list[str]:
    """Suggest new directories that might benefit from skill triggers.

    Parameters
    ----------
    repo_root : Path
        Repository root directory

    Returns
    -------
    list[str]
        List of suggestions for new path patterns
    """
    existing_patterns = get_skill_path_patterns(repo_root)
    suggestions: list[str] = []

    # Check key src directories
    src_dir = repo_root / "src"
    if not src_dir.exists():
        return suggestions

    key_dirs = [
        "aidb/adapters/lang/",
        "aidb/api/",
        "aidb/session/",
        "aidb_mcp/",
        "aidb_cli/",
        "aidb_common/",
        "aidb_logging/",
        "tests/frameworks/",
    ]

    for key_dir in key_dirs:
        full_path = src_dir / key_dir
        if not full_path.exists():
            continue

        # Check subdirectories
        for subdir in full_path.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name.startswith((".", "__")):
                continue

            # Check if pattern exists and directory has Python files
            pattern = f"src/{key_dir}{subdir.name}/**"
            if not any(pattern in p for p in existing_patterns) and list(
                subdir.rglob("*.py"),
            ):
                suggestions.append(
                    f"  src/{key_dir}{subdir.name}/ (consider adding to relevant skill)",
                )

    return suggestions


def main() -> int:  # noqa: C901 (complexity acceptable for pre-commit script)
    """Run skill reference validation.

    Returns
    -------
    int
        Exit code (0 for success, 1 for failure)
    """
    repo_root = get_repo_root()
    skills_dir = repo_root / ".claude" / "skills"

    if not skills_dir.exists():
        print("⚠️ Skills directory not found, skipping validation")
        return 0

    exit_code = 0

    # 1. Validate existing links
    print("Validating skill file references...")
    broken_links, total_links = validate_skill_links(skills_dir, repo_root)

    if broken_links:
        print(f"\n❌ Found {len(broken_links)} broken reference(s) in skills:")
        for error in broken_links:
            print(error)
        print("\nPlease fix broken references before committing.")
        exit_code = 1
    else:
        print(f"✅ All {total_links} skill file references are valid")

    # 2. Suggest new path patterns (informational)
    suggestions = suggest_new_path_patterns(repo_root)
    if suggestions:
        print(
            f"\n💡 Found {len(suggestions)} new director(ies) that may benefit from skill triggers:",
        )
        for suggestion in suggestions[:10]:  # Limit to avoid spam
            print(suggestion)
        if len(suggestions) > 10:
            print(f"  ... and {len(suggestions) - 10} more")

    if exit_code == 0 and not suggestions:
        print("\n✨ All skill references are valid and up to date!")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
