"""Tests for aidb_cli.core.project_config module."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from aidb_cli.core.project_config import (
    deep_merge,
    default_config,
    get_project_config_path,
    get_user_config_path,
    load_merged_config,
    load_yaml,
)


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_merges_flat_dictionaries(self):
        """Test merging of flat dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}
        assert result is base  # Returns base dict

    def test_merges_nested_dictionaries(self):
        """Test recursive merging of nested dictionaries."""
        base = {
            "level1": {
                "level2": {"a": 1, "b": 2},
                "other": "value",
            },
        }
        override = {
            "level1": {
                "level2": {"b": 3, "c": 4},
            },
        }

        result = deep_merge(base, override)

        expected = {
            "level1": {
                "level2": {"a": 1, "b": 3, "c": 4},
                "other": "value",
            },
        }
        assert result == expected

    def test_overrides_non_dict_values(self):
        """Test that non-dict values are completely replaced."""
        base = {"key": [1, 2, 3]}
        override = {"key": [4, 5]}

        result = deep_merge(base, override)

        assert result == {"key": [4, 5]}

    def test_adds_new_keys(self):
        """Test that new keys from override are added."""
        base = {"existing": 1}
        override = {"new1": 2, "new2": {"nested": 3}}

        result = deep_merge(base, override)

        assert result == {"existing": 1, "new1": 2, "new2": {"nested": 3}}

    def test_handles_empty_base(self):
        """Test merging into empty base dictionary."""
        base: dict[str, Any] = {}
        override = {"a": 1, "b": {"c": 2}}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": {"c": 2}}

    def test_handles_empty_override(self):
        """Test merging with empty override dictionary."""
        base = {"a": 1, "b": 2}
        override: dict[str, Any] = {}

        result = deep_merge(base, override)

        assert result == {"a": 1, "b": 2}

    def test_replaces_dict_with_non_dict(self):
        """Test that dict values can be replaced with non-dict values."""
        base = {"key": {"nested": "value"}}
        override = {"key": "simple_value"}

        result = deep_merge(base, override)

        assert result == {"key": "simple_value"}

    def test_replaces_non_dict_with_dict(self):
        """Test that non-dict values can be replaced with dict values."""
        base = {"key": "simple_value"}
        override = {"key": {"nested": "value"}}

        result = deep_merge(base, override)

        assert result == {"key": {"nested": "value"}}

    def test_deeply_nested_merge(self):
        """Test merging of deeply nested structures."""
        base = {
            "a": {
                "b": {
                    "c": {
                        "d": 1,
                        "e": 2,
                    },
                },
            },
        }
        override = {
            "a": {
                "b": {
                    "c": {
                        "e": 3,
                        "f": 4,
                    },
                },
            },
        }

        result = deep_merge(base, override)

        expected = {
            "a": {
                "b": {
                    "c": {
                        "d": 1,
                        "e": 3,
                        "f": 4,
                    },
                },
            },
        }
        assert result == expected


class TestDefaultConfig:
    """Tests for default_config function."""

    def test_returns_dict_with_expected_sections(self, tmp_path: Path):
        """Test that default config contains expected sections."""
        config = default_config(tmp_path)

        assert "defaults" in config
        assert "adapters" in config
        assert "docker" in config
        assert "test" in config

    def test_defaults_section_has_expected_keys(self, tmp_path: Path):
        """Test that defaults section has expected configuration."""
        config = default_config(tmp_path)

        assert config["defaults"]["verbose"] is False
        assert config["defaults"]["log_level"] == "INFO"
        assert config["defaults"]["env"] == "dev"

    def test_adapters_section_has_language_config(self, tmp_path: Path):
        """Test that adapters section includes language configuration."""
        config = default_config(tmp_path)

        languages = config["adapters"]["languages"]
        assert languages["python"]["enabled"] is True
        assert languages["javascript"]["enabled"] is True
        assert languages["java"]["enabled"] is True

    def test_adapters_auto_build_enabled(self, tmp_path: Path):
        """Test that adapter auto_build is enabled by default."""
        config = default_config(tmp_path)

        assert config["adapters"]["auto_build"] is True

    def test_docker_compose_file_points_to_repo(self, tmp_path: Path):
        """Test that docker compose_file path is relative to repo root."""
        config = default_config(tmp_path)

        compose_file = config["docker"]["compose_file"]
        assert "src/tests/_docker/docker-compose.yaml" in compose_file
        assert str(tmp_path) in compose_file

    def test_docker_auto_build_enabled(self, tmp_path: Path):
        """Test that docker auto_build is enabled by default."""
        config = default_config(tmp_path)

        assert config["docker"]["auto_build"] is True

    def test_test_auto_install_deps_enabled(self, tmp_path: Path):
        """Test that test auto_install_deps is enabled by default."""
        config = default_config(tmp_path)

        assert config["test"]["auto_install_deps"] is True

    def test_test_pytest_args_configured(self, tmp_path: Path):
        """Test that pytest args are configured by default."""
        config = default_config(tmp_path)

        assert config["test"]["pytest_args"] == "-v --tb=short"


class TestLoadYaml:
    """Tests for load_yaml function."""

    def test_loads_valid_yaml_file(self, tmp_path: Path):
        """Test loading of valid YAML file."""
        yaml_file = tmp_path / "config.yaml"
        data = {"key": "value", "number": 42}
        yaml_file.write_text(yaml.dump(data))

        result = load_yaml(yaml_file)

        assert result == data

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path):
        """Test that empty dict is returned for non-existent file."""
        missing_file = tmp_path / "missing.yaml"

        result = load_yaml(missing_file)

        assert result == {}

    def test_returns_empty_dict_for_non_dict_data(self, tmp_path: Path):
        """Test that empty dict is returned when top level is not a dict."""
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2")

        result = load_yaml(list_file)

        assert result == {}

    def test_returns_empty_dict_for_invalid_yaml(self, tmp_path: Path):
        """Test that empty dict is returned for malformed YAML."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("key: value\n  bad: indentation:\n    invalid")

        result = load_yaml(invalid_file)

        assert result == {}

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path):
        """Test that empty dict is returned for empty YAML file."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        result = load_yaml(empty_file)

        assert result == {}

    def test_handles_permission_errors_gracefully(self, tmp_path: Path):
        """Test that permission errors are handled gracefully."""
        yaml_file = tmp_path / "restricted.yaml"
        yaml_file.write_text("key: value")
        yaml_file.chmod(0o000)

        try:
            result = load_yaml(yaml_file)
            assert result == {}
        finally:
            yaml_file.chmod(0o644)


class TestGetUserConfigPath:
    """Tests for get_user_config_path function."""

    def test_returns_path_in_config_directory(self):
        """Test that user config path is in .config/aidb."""
        path = get_user_config_path()

        assert path.parts[-3:] == (".config", "aidb", "config.yaml")
        assert path.is_absolute()

    def test_points_to_home_directory(self):
        """Test that user config path is relative to home directory."""
        path = get_user_config_path()

        assert str(path).startswith(str(Path.home()))


class TestGetProjectConfigPath:
    """Tests for get_project_config_path function."""

    def test_returns_aidb_yaml_in_repo_root(self, tmp_path: Path):
        """Test that project config path is .aidb.yaml in repo root."""
        path = get_project_config_path(tmp_path)

        assert path == tmp_path / ".aidb.yaml"

    def test_is_relative_to_provided_root(self, tmp_path: Path):
        """Test that path is relative to provided repo root."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        path = get_project_config_path(subdir)

        assert path.parent == subdir


class TestLoadMergedConfig:
    """Tests for load_merged_config function."""

    def test_returns_default_config_when_no_files_exist(self, tmp_path: Path):
        """Test that default config is returned when no override files exist."""
        config = load_merged_config(tmp_path)

        # Should contain default sections
        assert "defaults" in config
        assert "adapters" in config
        assert "docker" in config
        assert "test" in config

    def test_merges_user_config_with_defaults(self, tmp_path: Path, monkeypatch):
        """Test that user config is merged with defaults."""
        user_config_dir = tmp_path / ".config" / "aidb"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.yaml"

        user_data = {
            "defaults": {"verbose": True, "log_level": "DEBUG"},
        }
        user_config_file.write_text(yaml.dump(user_data))

        monkeypatch.setattr(
            "aidb_cli.core.project_config.get_user_config_path",
            lambda: user_config_file,
        )

        config = load_merged_config(tmp_path)

        assert config["defaults"]["verbose"] is True
        assert config["defaults"]["log_level"] == "DEBUG"
        assert config["defaults"]["env"] == "dev"  # Default value preserved

    def test_merges_project_config_with_user_and_defaults(
        self,
        tmp_path: Path,
        monkeypatch,
    ):
        """Test that project config overrides user config and defaults."""
        user_config_dir = tmp_path / ".config" / "aidb"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.yaml"

        user_data = {"defaults": {"verbose": True, "log_level": "DEBUG"}}
        user_config_file.write_text(yaml.dump(user_data))

        project_config_file = tmp_path / ".aidb.yaml"
        project_data = {
            "defaults": {"log_level": "WARNING", "env": "prod"},
        }
        project_config_file.write_text(yaml.dump(project_data))

        monkeypatch.setattr(
            "aidb_cli.core.project_config.get_user_config_path",
            lambda: user_config_file,
        )

        config = load_merged_config(tmp_path)

        # Project overrides user and defaults
        assert config["defaults"]["verbose"] is True  # From user
        assert config["defaults"]["log_level"] == "WARNING"  # From project
        assert config["defaults"]["env"] == "prod"  # From project

    def test_nested_config_merging(self, tmp_path: Path):
        """Test that nested configurations are merged correctly."""
        project_config_file = tmp_path / ".aidb.yaml"
        project_data = {
            "adapters": {
                "languages": {
                    "python": {"enabled": False},
                    "rust": {"enabled": True},
                },
            },
        }
        project_config_file.write_text(yaml.dump(project_data))

        config = load_merged_config(tmp_path)

        # Python disabled by project config
        assert config["adapters"]["languages"]["python"]["enabled"] is False
        # JavaScript still enabled from defaults
        assert config["adapters"]["languages"]["javascript"]["enabled"] is True
        # Rust added by project config
        assert config["adapters"]["languages"]["rust"]["enabled"] is True

    def test_handles_missing_user_and_project_configs(self, tmp_path: Path):
        """Test graceful handling when both override configs are missing."""
        config = load_merged_config(tmp_path)

        # Should just return default config
        assert config["defaults"]["verbose"] is False
        assert config["defaults"]["log_level"] == "INFO"

    def test_handles_invalid_user_config(self, tmp_path: Path, monkeypatch):
        """Test graceful handling of invalid user config."""
        user_config_dir = tmp_path / ".config" / "aidb"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text("invalid: yaml:\n  bad indentation")

        monkeypatch.setattr(
            "aidb_cli.core.project_config.get_user_config_path",
            lambda: user_config_file,
        )

        # Should not raise, just return defaults
        config = load_merged_config(tmp_path)

        assert config["defaults"]["verbose"] is False

    def test_handles_invalid_project_config(self, tmp_path: Path):
        """Test graceful handling of invalid project config."""
        project_config_file = tmp_path / ".aidb.yaml"
        project_config_file.write_text("invalid: yaml:\n  bad indentation")

        # Should not raise, just return defaults
        config = load_merged_config(tmp_path)

        assert config["defaults"]["verbose"] is False

    def test_priority_order_project_over_user(self, tmp_path: Path, monkeypatch):
        """Test that project config has highest priority."""
        user_config_dir = tmp_path / ".config" / "aidb"
        user_config_dir.mkdir(parents=True)
        user_config_file = user_config_dir / "config.yaml"
        user_config_file.write_text(yaml.dump({"test": {"auto_install_deps": False}}))

        project_config_file = tmp_path / ".aidb.yaml"
        project_config_file.write_text(
            yaml.dump({"test": {"auto_install_deps": True}}),
        )

        monkeypatch.setattr(
            "aidb_cli.core.project_config.get_user_config_path",
            lambda: user_config_file,
        )

        config = load_merged_config(tmp_path)

        # Project should win
        assert config["test"]["auto_install_deps"] is True
