"""Shared fixtures for CI/CD tests."""

import json
import sys
from pathlib import Path

import pytest

# Add paths for importing CI scripts (must be at module level for import resolution)
sys.path.insert(0, str(Path(__file__).parent / "unit"))
_scripts_path = Path(__file__).parent.parent.parent.parent / ".github" / "scripts"
if str(_scripts_path) not in sys.path:
    sys.path.insert(0, str(_scripts_path))


@pytest.fixture
def repo_root():
    """Return repository root path."""
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def github_dir(repo_root):
    """Return .github directory path."""
    return repo_root / ".github"


@pytest.fixture
def scripts_dir(github_dir):
    """Return .github/scripts directory path."""
    return github_dir / "scripts"


@pytest.fixture
def workflows_dir(github_dir):
    """Return .github/workflows directory path."""
    return github_dir / "workflows"


@pytest.fixture
def versions_json(repo_root):
    """Load versions.json configuration."""
    versions_path = repo_root / "versions.json"
    with versions_path.open() as f:
        return json.load(f)
