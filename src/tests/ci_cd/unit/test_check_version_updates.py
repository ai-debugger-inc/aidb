"""Unit tests for version_management package."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from version_management.automation.merge_decision import should_auto_merge
from version_management.orchestrator import VersionUpdateOrchestrator
from version_management.validators.debugpy_sync import DebugpySyncValidator
from version_management.validators.version_utils import (
    classify_version_update,
    is_stable_version,
)


@pytest.fixture
def mock_pyproject_toml(tmp_path):
    """Create minimal pyproject.toml file."""
    toml_content = """[project]
dependencies = [
    "debugpy>=1.8.0,<2.0.0",
    "other-package>=1.0.0",
]
"""

    pyproject_path = tmp_path / "pyproject.toml"
    with pyproject_path.open("w") as f:
        f.write(toml_content)

    return pyproject_path


class TestIsStableVersion:
    """Test is_stable_version function."""

    def test_stable_version_no_prerelease_markers(self):
        """Verify stable versions without prerelease markers."""
        assert is_stable_version("1.8.0") is True
        assert is_stable_version("3.12.0") is True
        assert is_stable_version("v2.1.0") is True

    def test_alpha_versions_unstable(self):
        """Verify alpha versions are considered unstable."""
        assert is_stable_version("1.8.0-alpha") is False
        assert is_stable_version("1.8.0-alpha.1") is False
        assert is_stable_version("1.8.0a1") is False

    def test_beta_versions_unstable(self):
        """Verify beta versions are considered unstable."""
        assert is_stable_version("1.8.0-beta") is False
        assert is_stable_version("1.8.0-beta.2") is False
        assert is_stable_version("1.8.0b1") is False

    def test_rc_versions_unstable(self):
        """Verify release candidate versions are considered unstable."""
        assert is_stable_version("1.8.0-rc") is False
        assert is_stable_version("1.8.0-rc.1") is False
        assert is_stable_version("1.8.0rc1") is False

    def test_dev_versions_unstable(self):
        """Verify dev versions are considered unstable."""
        assert is_stable_version("1.8.0-dev") is False
        assert is_stable_version("1.8.0.dev1") is False

    def test_preview_snapshot_versions_unstable(self):
        """Verify preview and snapshot versions are considered unstable."""
        assert is_stable_version("1.8.0-preview") is False
        assert is_stable_version("1.8.0-snapshot") is False

    def test_case_insensitive_check(self):
        """Verify unstable check is case-insensitive."""
        assert is_stable_version("1.8.0-BETA") is False
        assert is_stable_version("1.8.0-Alpha") is False
        assert is_stable_version("1.8.0-RC") is False


class TestClassifyVersionUpdate:
    """Test classify_version_update function."""

    def test_patch_update(self):
        """Verify patch version updates are classified correctly."""
        assert classify_version_update("1.8.0", "1.8.1") == "patch"
        assert classify_version_update("3.11.0", "3.11.5") == "patch"

    def test_minor_update(self):
        """Verify minor version updates are classified correctly."""
        assert classify_version_update("1.8.0", "1.9.0") == "minor"
        assert classify_version_update("3.11.0", "3.12.0") == "minor"

    def test_major_update(self):
        """Verify major version updates are classified correctly."""
        assert classify_version_update("1.8.0", "2.0.0") == "major"
        assert classify_version_update("3.11.0", "4.0.0") == "major"

    def test_invalid_version_returns_unknown(self):
        """Verify invalid versions return 'unknown'."""
        assert classify_version_update("invalid", "1.8.0") == "unknown"
        assert classify_version_update("1.8.0", "not-a-version") == "unknown"

    def test_same_version(self):
        """Verify same versions return 'unknown' (no update)."""
        result = classify_version_update("1.8.0", "1.8.0")
        assert result == "unknown"


class TestValidateDebugpySync:
    """Test DebugpySyncValidator class."""

    def test_sync_validation_when_versions_match(
        self,
        tmp_path,
        mock_pyproject_toml,
    ):
        """Verify validation passes when versions are in sync."""
        config = create_mock_versions_config(adapters={"python": {"version": "1.8.0"}})

        config_path = tmp_path / "versions.yaml"
        with config_path.open("w") as f:
            yaml.dump(config, f)

        validator = DebugpySyncValidator(config_path)
        result = validator.validate(config)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_error_when_pyproject_minimum_below_adapter(
        self,
        tmp_path,
    ):
        """Verify error when pyproject.toml minimum is below adapter version."""
        import yaml

        config = {"adapters": {"python": {"version": "1.8.0"}}}
        config_path = tmp_path / "versions.yaml"
        with config_path.open("w") as f:
            yaml.dump(config, f)

        toml_content = """[project]
dependencies = ["debugpy>=1.6.0"]
"""
        pyproject_path = tmp_path / "pyproject.toml"
        with pyproject_path.open("w") as f:
            f.write(toml_content)

        validator = DebugpySyncValidator(config_path)
        result = validator.validate(config)

        assert result["valid"] is False
        assert len(result["errors"]) >= 1
        assert any("older than" in err for err in result["errors"])

    def test_warning_when_pyproject_minimum_above_adapter(
        self,
        tmp_path,
    ):
        """Verify warning when pyproject.toml minimum is above adapter version."""
        import yaml

        config = {"adapters": {"python": {"version": "1.6.0"}}}
        config_path = tmp_path / "versions.yaml"
        with config_path.open("w") as f:
            yaml.dump(config, f)

        toml_content = """[project]
dependencies = ["debugpy>=1.8.0"]
"""
        pyproject_path = tmp_path / "pyproject.toml"
        with pyproject_path.open("w") as f:
            f.write(toml_content)

        validator = DebugpySyncValidator(config_path)
        result = validator.validate(config)

        assert result["valid"] is True
        assert len(result["warnings"]) >= 1
        assert any("newer than" in warn for warn in result["warnings"])

    def test_warning_when_no_adapter_version(self, tmp_path):
        """Verify warning when no adapter version in versions.yaml."""
        from typing import Any

        import yaml

        config: dict[str, Any] = {"adapters": {"python": {}}}
        config_path = tmp_path / "versions.yaml"
        with config_path.open("w") as f:
            yaml.dump(config, f)

        validator = DebugpySyncValidator(config_path)
        result = validator.validate(config)

        assert result["valid"] is True
        assert len(result["warnings"]) >= 1
        assert any("No Python adapter version" in warn for warn in result["warnings"])

    def test_warning_when_no_debugpy_in_pyproject(
        self,
        tmp_path,
    ):
        """Verify warning when debugpy not in pyproject.toml dependencies."""
        import yaml

        config = {"adapters": {"python": {"version": "1.8.0"}}}
        config_path = tmp_path / "versions.yaml"
        with config_path.open("w") as f:
            yaml.dump(config, f)

        toml_content = """[project]
dependencies = ["other-package>=1.0.0"]
"""
        pyproject_path = tmp_path / "pyproject.toml"
        with pyproject_path.open("w") as f:
            f.write(toml_content)

        validator = DebugpySyncValidator(config_path)
        result = validator.validate(config)

        assert result["valid"] is True
        assert len(result["warnings"]) >= 1
        assert any("debugpy not found" in warn for warn in result["warnings"])


class TestShouldAutoMergeUpdates:
    """Test should_auto_merge function."""

    def test_auto_merge_for_patch_updates_only(self):
        """Verify auto-merge allowed only for patch version updates."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "1.8.0",
                    "latest": "1.8.1",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is True

    def test_no_auto_merge_for_minor_updates(self):
        """Verify auto-merge blocked for minor version updates."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "1.8.0",
                    "latest": "1.9.0",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is False

    def test_no_auto_merge_for_major_updates(self):
        """Verify auto-merge blocked for major version updates."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "1.8.0",
                    "latest": "2.0.0",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is False

    def test_no_auto_merge_for_invalid_versions(self):
        """Verify auto-merge blocked when version parsing fails."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "invalid",
                    "latest": "1.8.0",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is False

    def test_auto_merge_when_no_updates(self):
        """Verify auto-merge returns False when no updates found."""
        from typing import Any

        all_updates: dict[str, Any] = {}
        result = should_auto_merge(all_updates)
        assert result is False

    def test_auto_merge_with_multiple_patch_updates(self):
        """Verify auto-merge allowed when all updates are patches."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "1.8.0",
                    "latest": "1.8.1",
                },
                "javascript": {
                    "current": "2.5.0",
                    "latest": "2.5.2",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is True

    def test_no_auto_merge_with_mixed_update_types(self):
        """Verify auto-merge blocked when updates have mixed types."""
        all_updates = {
            "adapters": {
                "python": {
                    "current": "1.8.0",
                    "latest": "1.8.1",
                },
                "javascript": {
                    "current": "2.5.0",
                    "latest": "2.6.0",
                },
            },
        }

        result = should_auto_merge(all_updates)
        assert result is False
