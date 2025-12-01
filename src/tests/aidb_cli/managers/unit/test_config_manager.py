"""Unit tests for ConfigManager."""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from aidb_cli.managers.config_manager import ConfigManager, get_config_manager
from aidb_common.io.files import FileOperationError


class TestConfigManager:
    """Test the ConfigManager."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ConfigManager._instance = None
        ConfigManager._initialized = False
        yield
        ConfigManager._instance = None
        ConfigManager._initialized = False

    @pytest.fixture
    def tmp_config_files(self, tmp_path):
        """Create temporary config directory structure."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create versions.yaml
        versions_file = repo_root / "versions.yaml"
        versions_file.write_text(
            "infrastructure:\n  python: '3.12'\nadapters:\n  python: '1.0.0'\n",
        )

        return repo_root

    @patch("aidb_cli.managers.config_manager.detect_repo_root")
    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_singleton_behavior(
        self,
        mock_load_config,
        mock_vm_class,
        mock_detect,
        tmp_config_files,
    ):
        """Test that ConfigManager is a singleton."""
        mock_detect.return_value = tmp_config_files
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager1 = ConfigManager()
        manager2 = ConfigManager()

        assert manager1 is manager2

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_initialization_with_repo_root(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test initialization with explicit repo root."""
        mock_vm = Mock()
        mock_vm_class.return_value = mock_vm
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)

        assert manager.repo_root == tmp_config_files
        assert manager.versions_file == tmp_config_files / "versions.yaml"

    @patch("aidb_cli.managers.config_manager.detect_repo_root")
    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_initialization_without_repo_root(
        self,
        mock_load_config,
        mock_vm_class,
        mock_detect,
        tmp_config_files,
    ):
        """Test initialization without repo root uses detect_repo_root."""
        mock_detect.return_value = tmp_config_files
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager()

        assert manager.repo_root == tmp_config_files
        mock_detect.assert_called_once()

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_config_property_loads_on_first_access(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test config property loads configuration on first access."""
        mock_vm_class.return_value = Mock()
        test_config = {"test": "value"}
        mock_load_config.return_value = test_config

        manager = ConfigManager(tmp_config_files)
        config = manager.config

        assert config == test_config
        mock_load_config.assert_called_once_with(tmp_config_files)

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_config_property_caches_result(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test config property caches loaded configuration."""
        mock_vm_class.return_value = Mock()
        test_config = {"test": "value"}
        mock_load_config.return_value = test_config

        manager = ConfigManager(tmp_config_files)
        config1 = manager.config
        config2 = manager.config

        assert config1 == config2
        mock_load_config.assert_called_once()

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_get_versions_delegates_to_version_manager(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test get_versions delegates to VersionManager."""
        mock_vm = Mock()
        mock_vm.format_versions_output.return_value = "versions output"
        mock_vm_class.return_value = mock_vm
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        result = manager.get_versions("json")

        assert result == "versions output"
        mock_vm.format_versions_output.assert_called_once_with("json")

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_get_config_value_simple_key(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test get_config_value with simple key."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {"test": "value"}

        manager = ConfigManager(tmp_config_files)
        result = manager.get_config_value("test")

        assert result == "value"

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_get_config_value_nested_key(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test get_config_value with nested dot notation."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {"a": {"b": {"c": "nested"}}}

        manager = ConfigManager(tmp_config_files)
        result = manager.get_config_value("a.b.c")

        assert result == "nested"

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_get_config_value_missing_key_returns_default(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test get_config_value returns default for missing key."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {"a": "value"}

        manager = ConfigManager(tmp_config_files)
        result = manager.get_config_value("missing.key", default="default")

        assert result == "default"

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.safe_read_yaml")
    @patch("aidb_cli.managers.config_manager.safe_write_yaml")
    def test_set_config_value_user_config(
        self,
        mock_write,
        mock_read,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test set_config_value saves to user config."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}
        mock_read.return_value = {"existing": "value"}

        manager = ConfigManager(tmp_config_files)
        result = manager.set_config_value("test.key", "new_value", "user")

        assert result is True
        mock_write.assert_called_once()
        written_config = mock_write.call_args[0][1]
        assert written_config["test"]["key"] == "new_value"
        assert manager._config_cache is None

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.safe_write_yaml")
    def test_set_config_value_creates_new_file(
        self,
        mock_write,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test set_config_value creates new file if not exists."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        result = manager.set_config_value("test", "value", "user")

        assert result is True
        mock_write.assert_called_once()

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.safe_write_yaml")
    def test_set_config_value_write_failure(
        self,
        mock_write,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test set_config_value handles write failure."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}
        mock_write.side_effect = FileOperationError("write failed")

        manager = ConfigManager(tmp_config_files)
        result = manager.set_config_value("test", "value", "user")

        assert result is False

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.safe_write_yaml")
    @patch("aidb_cli.managers.config_manager.CliOutput")
    def test_create_default_config_success(
        self,
        mock_output,
        mock_write,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test create_default_config creates config file."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        manager.user_config.parent.mkdir(parents=True, exist_ok=True)
        if manager.user_config.exists():
            manager.user_config.unlink()

        result = manager.create_default_config("user")

        assert result is True
        mock_write.assert_called_once()
        written_config = mock_write.call_args[0][1]
        assert "defaults" in written_config
        assert "adapters" in written_config

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.CliOutput")
    def test_create_default_config_file_exists(
        self,
        mock_output,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test create_default_config returns False if file exists."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        manager.user_config.parent.mkdir(parents=True, exist_ok=True)
        manager.user_config.touch()

        result = manager.create_default_config("user")

        assert result is False

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.CliOutput")
    def test_show_config_yaml_format(
        self,
        mock_output,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test show_config with YAML format."""
        mock_vm_class.return_value = Mock()
        test_config = {"test": "value"}
        mock_load_config.return_value = test_config

        manager = ConfigManager(tmp_config_files)
        manager.show_config("yaml", "merged")

        mock_output.plain.assert_called_once()
        output = mock_output.plain.call_args[0][0]
        assert "test" in output

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.CliOutput")
    def test_show_config_json_format(
        self,
        mock_output,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test show_config with JSON format."""
        mock_vm_class.return_value = Mock()
        test_config = {"test": "value"}
        mock_load_config.return_value = test_config

        manager = ConfigManager(tmp_config_files)
        manager.show_config("json", "merged")

        mock_output.plain.assert_called_once()
        output = mock_output.plain.call_args[0][0]
        assert '"test"' in output

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    @patch("aidb_cli.managers.config_manager.CliOutput")
    def test_show_config_versions(
        self,
        mock_output,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test show_config with versions type."""
        mock_vm = Mock()
        mock_vm.format_versions_output.return_value = "versions"
        mock_vm_class.return_value = mock_vm
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        manager.show_config("text", "versions")

        mock_output.plain.assert_called_once()
        assert "versions" in mock_output.plain.call_args[0][0]

    @patch("aidb_cli.managers.config_manager.detect_repo_root")
    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_get_config_manager_returns_singleton(
        self,
        mock_load_config,
        mock_vm_class,
        mock_detect,
        tmp_config_files,
    ):
        """Test get_config_manager convenience function."""
        mock_detect.return_value = tmp_config_files
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager1 = get_config_manager()
        manager2 = get_config_manager()

        assert manager1 is manager2

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_format_config_text_simple(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test _format_config_text with simple config."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        result = manager._format_config_text({"key": "value"})

        assert "key: value" in result

    @patch("aidb_cli.managers.config_manager.VersionManager")
    @patch("aidb_cli.managers.config_manager.load_merged_config")
    def test_format_config_text_nested(
        self,
        mock_load_config,
        mock_vm_class,
        tmp_config_files,
    ):
        """Test _format_config_text with nested config."""
        mock_vm_class.return_value = Mock()
        mock_load_config.return_value = {}

        manager = ConfigManager(tmp_config_files)
        result = manager._format_config_text({"parent": {"child": "value"}})

        assert "parent:" in result
        assert "child: value" in result
