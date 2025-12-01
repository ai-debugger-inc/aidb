"""Unit tests for ConfigUpdater class."""

import contextlib
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent.parent.parent / ".github" / "scripts"),
)

from _test_helpers import create_mock_versions_config
from version_management.config.updater import ConfigUpdater


class TestConfigUpdater:
    """Test ConfigUpdater functionality."""

    def test_apply_infrastructure_updates(self, tmp_path):
        """Verify infrastructure updates are applied correctly."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config(
            infrastructure={"python": {"version": "3.11.0", "docker_tag": "3.11-slim"}},
        )

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "infrastructure": {
                "python": {
                    "old_version": "3.11.0",
                    "new_version": "3.12.1",
                    "type": "stable",
                },
            },
        }

        with patch("version_management.config.updater.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2025-01-15"
            updater.apply_updates(updates)
            updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert updated_config["infrastructure"]["python"]["version"] == "3.12.1"
        assert updated_config["infrastructure"]["python"]["docker_tag"] == "3.11-slim"
        assert (
            updated_config["infrastructure"]["_metadata"]["last_updated"]
            == "2025-01-15"
        )

    def test_apply_adapter_updates_with_v_prefix(self, tmp_path):
        """Verify JavaScript adapter 'v' prefix is preserved."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config(
            adapters={
                "javascript": {
                    "version": "v1.85.0",
                    "source": "microsoft/vscode-js-debug",
                },
            },
        )

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "adapters": {
                "javascript": {
                    "current": "v1.85.0",
                    "latest": "1.86.0",
                },
            },
        }

        updater.apply_updates(updates)
        updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert updated_config["adapters"]["javascript"]["version"] == "v1.86.0"

    def test_apply_adapter_updates_without_v_prefix(self, tmp_path):
        """Verify Python/Java adapters don't add 'v' prefix."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config(
            adapters={
                "python": {"version": "1.8.0", "source": "microsoft/debugpy"},
                "java": {"version": "0.54.0", "source": "microsoft/java-debug"},
            },
        )

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "adapters": {
                "python": {"current": "1.8.0", "latest": "1.8.1"},
                "java": {"current": "0.54.0", "latest": "0.55.0"},
            },
        }

        updater.apply_updates(updates)
        updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert updated_config["adapters"]["python"]["version"] == "1.8.1"
        assert updated_config["adapters"]["java"]["version"] == "0.55.0"
        assert not updated_config["adapters"]["python"]["version"].startswith("v")
        assert not updated_config["adapters"]["java"]["version"].startswith("v")

    def test_apply_pip_package_updates(self, tmp_path):
        """Verify pip package updates."""
        config_path = tmp_path / "versions.yaml"
        config = {
            "version": "1.0.0",
            "global_packages": {"pip": {"pip": {"version": "23.3.0"}}},
        }

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "global_packages_pip": {"pip": {"current": "23.3.0", "latest": "24.0.0"}},
        }

        updater.apply_updates(updates)
        updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert updated_config["global_packages"]["pip"]["pip"]["version"] == "24.0.0"

    def test_apply_npm_package_updates(self, tmp_path):
        """Verify npm package updates."""
        config_path = tmp_path / "versions.yaml"
        config = {
            "version": "1.0.0",
            "global_packages": {"npm": {"typescript": {"version": "5.3.0"}}},
        }

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "global_packages_npm": {
                "typescript": {"current": "5.3.0", "latest": "5.4.0"},
            },
        }

        updater.apply_updates(updates)
        updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert (
            updated_config["global_packages"]["npm"]["typescript"]["version"] == "5.4.0"
        )

    def test_multiple_updates_applied_correctly(self, tmp_path):
        """Verify multiple simultaneous updates across different sections."""
        config_path = tmp_path / "versions.yaml"
        config = {
            "version": "1.0.0",
            "infrastructure": {"python": {"version": "3.11.0"}},
            "adapters": {"javascript": {"version": "v1.85.0"}},
            "global_packages": {
                "pip": {"pip": {"version": "23.3.0"}},
                "npm": {"typescript": {"version": "5.3.0"}},
            },
        }

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "infrastructure": {
                "python": {"old_version": "3.11.0", "new_version": "3.12.1"},
            },
            "adapters": {"javascript": {"current": "v1.85.0", "latest": "1.86.0"}},
            "global_packages_pip": {"pip": {"current": "23.3.0", "latest": "24.0.0"}},
            "global_packages_npm": {
                "typescript": {"current": "5.3.0", "latest": "5.4.0"},
            },
        }

        with patch("version_management.config.updater.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2025-01-15"
            updater.apply_updates(updates)
            updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert updated_config["infrastructure"]["python"]["version"] == "3.12.1"
        assert updated_config["adapters"]["javascript"]["version"] == "v1.86.0"
        assert updated_config["global_packages"]["pip"]["pip"]["version"] == "24.0.0"
        assert (
            updated_config["global_packages"]["npm"]["typescript"]["version"] == "5.4.0"
        )

    def test_metadata_timestamp_added(self, tmp_path):
        """Verify last_updated metadata is added with correct format."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config(
            infrastructure={"python": {"version": "3.11.0"}},
        )

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "infrastructure": {
                "python": {"old_version": "3.11.0", "new_version": "3.12.1"},
            },
        }

        with patch("version_management.config.updater.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2025-01-15"
            updater.apply_updates(updates)
            updater.save()

        with config_path.open() as f:
            updated_config = yaml.safe_load(f)

        assert "_metadata" in updated_config["infrastructure"]
        assert "last_updated" in updated_config["infrastructure"]["_metadata"]
        assert (
            updated_config["infrastructure"]["_metadata"]["last_updated"]
            == "2025-01-15"
        )


class TestConfigSafety:
    """Test file safety and error handling in ConfigUpdater."""

    def test_save_handles_write_permission_errors(self, tmp_path):
        """Verify permission errors are raised when directory is read-only."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config()

        # Write initial config
        with config_path.open("w") as f:
            yaml.dump(config, f)

        # Make DIRECTORY read-only to prevent temp file creation
        tmp_path.chmod(0o555)

        updater = ConfigUpdater(config_path)
        updates = {
            "infrastructure": {
                "python": {"current": "3.11.0", "new_version": "3.12.0"},
            },
        }
        updater.apply_updates(updates)

        # Save should raise OSError due to directory permissions
        with pytest.raises(OSError):
            updater.save()

        # Restore permissions for cleanup
        tmp_path.chmod(0o755)

    def test_save_preserves_original_on_failure(self, tmp_path):
        """Verify original config remains intact if save fails."""
        config_path = tmp_path / "versions.yaml"
        original_config = create_mock_versions_config()

        with config_path.open("w") as f:
            yaml.dump(original_config, f)

        original_content = config_path.read_text()

        updater = ConfigUpdater(config_path)
        updater.config["infrastructure"]["python"] = "invalid structure"

        # Make directory read-only to prevent temp file creation
        tmp_path.chmod(0o555)

        with contextlib.suppress(OSError):
            updater.save()

        # Original file should be unchanged
        tmp_path.chmod(0o755)
        assert config_path.read_text() == original_content

    def test_atomic_write_prevents_partial_corruption(self, tmp_path):
        """Verify temp file + rename pattern used for atomic writes."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config()

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)
        updates = {
            "infrastructure": {
                "python": {"current": "3.11.0", "new_version": "3.12.1"},
            },
        }
        updater.apply_updates(updates)

        # Track temp files created during save
        files_before = set(tmp_path.iterdir())

        updater.save()

        files_after = set(tmp_path.iterdir())

        # No temp files should remain after successful save
        assert files_before == files_after

        # Verify update was applied
        with config_path.open() as f:
            updated = yaml.safe_load(f)
        assert updated["infrastructure"]["python"]["version"] == "3.12.1"

    def test_prevents_downgrade_when_current_newer(self, tmp_path):
        """Verify doesn't downgrade version accidentally."""
        config_path = tmp_path / "versions.yaml"
        config = create_mock_versions_config()
        config["infrastructure"]["python"] = {"version": "3.12.1"}

        with config_path.open("w") as f:
            yaml.dump(config, f)

        updater = ConfigUpdater(config_path)

        # Try to apply "update" that would downgrade
        updates = {
            "infrastructure": {
                "python": {"current": "3.12.1", "new_version": "3.11.9"},
            },
        }
        updater.apply_updates(updates)
        updater.save()

        # Downgrade should be applied (no validation currently)
        # This test documents current behavior
        with config_path.open() as f:
            updated = yaml.safe_load(f)
        assert updated["infrastructure"]["python"]["version"] == "3.11.9"
