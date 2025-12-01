"""Tests for configuration commands."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


class TestConfigCommands:
    """Test configuration management commands."""

    def test_show_default(self, cli_runner, mock_repo_root):
        """Test config show with default options (merged, yaml)."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(cli, ["config", "show"])
                assert result.exit_code == 0
                assert "Configuration (type: merged, format: yaml)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="yaml",
                    config_type="merged",
                )

    def test_show_json_format(self, cli_runner, mock_repo_root):
        """Test config show with JSON format."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(cli, ["config", "show", "--format", "json"])
                assert result.exit_code == 0
                assert "Configuration (type: merged, format: json)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="json",
                    config_type="merged",
                )

    def test_show_text_format(self, cli_runner, mock_repo_root):
        """Test config show with text format."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(cli, ["config", "show", "--format", "text"])
                assert result.exit_code == 0
                assert "Configuration (type: merged, format: text)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="text",
                    config_type="merged",
                )

    def test_show_user_type(self, cli_runner, mock_repo_root):
        """Test config show with user config type."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(cli, ["config", "show", "--type", "user"])
                assert result.exit_code == 0
                assert "Configuration (type: user, format: yaml)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="yaml",
                    config_type="user",
                )

    def test_show_project_type(self, cli_runner, mock_repo_root):
        """Test config show with project config type."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(cli, ["config", "show", "--type", "project"])
                assert result.exit_code == 0
                assert "Configuration (type: project, format: yaml)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="yaml",
                    config_type="project",
                )

    def test_show_versions_type(self, cli_runner, mock_repo_root):
        """Test config show with versions type."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                result = cli_runner.invoke(
                    cli,
                    ["config", "show", "--type", "versions"],
                )
                assert result.exit_code == 0
                assert "Configuration (type: versions, format: yaml)" in result.output
                mock_cm.show_config.assert_called_once_with(
                    format_type="yaml",
                    config_type="versions",
                )

    def test_set_string_value_user_scope(self, cli_runner, mock_repo_root):
        """Test setting a string value in user scope."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "test.key", "value"],
                )
                assert result.exit_code == 0
                assert "Set test.key = value (user config)" in result.output
                mock_cm.set_config_value.assert_called_once_with(
                    key_path="test.key",
                    value="value",
                    save_to="user",
                )

    def test_set_boolean_value_true(self, cli_runner, mock_repo_root):
        """Test setting a boolean value (YAML parsing: 'true' -> True)."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "adapters.auto_build", "true"],
                )
                assert result.exit_code == 0
                assert "Set adapters.auto_build = True (user config)" in result.output
                mock_cm.set_config_value.assert_called_once_with(
                    key_path="adapters.auto_build",
                    value=True,
                    save_to="user",
                )

    def test_set_boolean_value_false(self, cli_runner, mock_repo_root):
        """Test setting a boolean value (YAML parsing: 'false' -> False)."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "defaults.verbose", "false"],
                )
                assert result.exit_code == 0
                assert "Set defaults.verbose = False (user config)" in result.output
                mock_cm.set_config_value.assert_called_once_with(
                    key_path="defaults.verbose",
                    value=False,
                    save_to="user",
                )

    def test_set_number_value(self, cli_runner, mock_repo_root):
        """Test setting a number value (YAML parsing: '123' -> 123)."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "test.timeout", "123"],
                )
                assert result.exit_code == 0
                assert "Set test.timeout = 123 (user config)" in result.output
                mock_cm.set_config_value.assert_called_once_with(
                    key_path="test.timeout",
                    value=123,
                    save_to="user",
                )

    def test_set_project_scope(self, cli_runner, mock_repo_root):
        """Test setting value with project scope."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "test.key", "value", "--scope", "project"],
                )
                assert result.exit_code == 0
                assert "Set test.key = value (project config)" in result.output
                mock_cm.set_config_value.assert_called_once_with(
                    key_path="test.key",
                    value="value",
                    save_to="project",
                )

    def test_set_failure_exits_with_error(self, cli_runner, mock_repo_root):
        """Test that set command exits with code 1 on failure."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.set_config_value.return_value = False

                result = cli_runner.invoke(
                    cli,
                    ["config", "set", "test.key", "value"],
                )
                assert result.exit_code == 1
                assert "Failed to set configuration" in result.output

    def test_get_existing_value(self, cli_runner, mock_repo_root):
        """Test getting an existing configuration value."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.get_config_value.return_value = "test_value"

                result = cli_runner.invoke(cli, ["config", "get", "test.key"])
                assert result.exit_code == 0
                assert "test_value" in result.output
                mock_cm.get_config_value.assert_called_once_with("test.key")

    def test_get_nonexistent_value(self, cli_runner, mock_repo_root):
        """Test getting a non-existent value exits with code 1."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.get_config_value.return_value = None

                result = cli_runner.invoke(cli, ["config", "get", "nonexistent.key"])
                assert result.exit_code == 1
                assert "Configuration key 'nonexistent.key' not found" in result.output

    def test_get_boolean_value(self, cli_runner, mock_repo_root):
        """Test getting a boolean configuration value."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.get_config_value.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "get", "adapters.auto_build"],
                )
                assert result.exit_code == 0
                assert "True" in result.output

    def test_init_default_user_scope(self, cli_runner, mock_repo_root):
        """Test config init with default (user) scope."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.create_default_config.return_value = True

                result = cli_runner.invoke(cli, ["config", "init"])
                assert result.exit_code == 0
                mock_cm.create_default_config.assert_called_once_with(save_to="user")

    def test_init_project_scope(self, cli_runner, mock_repo_root):
        """Test config init with project scope."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.create_default_config.return_value = True

                result = cli_runner.invoke(
                    cli,
                    ["config", "init", "--scope", "project"],
                )
                assert result.exit_code == 0
                mock_cm.create_default_config.assert_called_once_with(save_to="project")

    def test_init_failure_exits_with_error(self, cli_runner, mock_repo_root):
        """Test that init command exits with code 1 on failure."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.create_default_config.return_value = False

                result = cli_runner.invoke(cli, ["config", "init"])
                assert result.exit_code == 1

    def test_paths_all_exist(self, cli_runner, mock_repo_root):
        """Test paths command when all config files exist."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                mock_user_path = Mock()
                mock_user_path.exists.return_value = True
                mock_user_path.__str__ = Mock(  # type: ignore[method-assign]
                    return_value="/home/user/.config/aidb/config.yaml",
                )
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock()
                mock_project_path.exists.return_value = True
                mock_project_path.__str__ = Mock(return_value="/repo/.aidb.yaml")  # type: ignore[method-assign]
                mock_cm.project_config = mock_project_path

                mock_versions_path = Mock()
                mock_versions_path.exists.return_value = True
                mock_versions_path.__str__ = Mock(return_value="/repo/versions.yaml")  # type: ignore[method-assign]
                mock_cm.versions_file = mock_versions_path

                result = cli_runner.invoke(cli, ["config", "paths"])
                assert result.exit_code == 0
                assert "Configuration File Paths" in result.output
                assert "User config:" in result.output
                assert "Project config:" in result.output
                assert "Versions file:" in result.output
                assert "Configuration Loading Priority" in result.output

    def test_paths_some_missing(self, cli_runner, mock_repo_root):
        """Test paths command when some files are missing (shows error icon)."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                mock_user_path = Mock()
                mock_user_path.exists.return_value = True
                mock_user_path.__str__ = Mock(  # type: ignore[method-assign]
                    return_value="/home/user/.config/aidb/config.yaml",
                )
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock()
                mock_project_path.exists.return_value = False
                mock_project_path.__str__ = Mock(return_value="/repo/.aidb.yaml")  # type: ignore[method-assign]
                mock_cm.project_config = mock_project_path

                mock_versions_path = Mock()
                mock_versions_path.exists.return_value = True
                mock_versions_path.__str__ = Mock(return_value="/repo/versions.yaml")  # type: ignore[method-assign]
                mock_cm.versions_file = mock_versions_path

                result = cli_runner.invoke(cli, ["config", "paths"])
                assert result.exit_code == 0

    def test_paths_priority_order(self, cli_runner, mock_repo_root):
        """Test that paths command shows configuration priority order."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm

                mock_user_path = Mock()
                mock_user_path.exists.return_value = False
                mock_user_path.__str__ = Mock(  # type: ignore[method-assign]
                    return_value="/home/user/.config/aidb/config.yaml",
                )
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock()
                mock_project_path.exists.return_value = False
                mock_project_path.__str__ = Mock(return_value="/repo/.aidb.yaml")  # type: ignore[method-assign]
                mock_cm.project_config = mock_project_path

                mock_versions_path = Mock()
                mock_versions_path.exists.return_value = False
                mock_versions_path.__str__ = Mock(return_value="/repo/versions.yaml")  # type: ignore[method-assign]
                mock_cm.versions_file = mock_versions_path

                result = cli_runner.invoke(cli, ["config", "paths"])
                assert result.exit_code == 0
                assert "1. Default values (built-in)" in result.output
                assert "2. User config (~/.config/aidb/config.yaml)" in result.output
                assert "3. Project config (.aidb.yaml)" in result.output
                assert "4. Environment variables" in result.output
                assert "5. Command line arguments" in result.output

    def test_validate_all_valid(self, cli_runner, mock_repo_root):
        """Test validate when all configurations are valid."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.validate_versions.return_value = {
                    "infrastructure": True,
                    "adapters": True,
                }

                mock_user_path = Mock(spec=Path)
                mock_user_path.exists.return_value = True
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock(spec=Path)
                mock_project_path.exists.return_value = True
                mock_cm.project_config = mock_project_path

                with patch("aidb_cli.commands.config.safe_read_yaml"):
                    result = cli_runner.invoke(cli, ["config", "validate"])
                    assert result.exit_code == 0
                    assert "Configuration Validation" in result.output
                    assert "All configurations are valid!" in result.output

    def test_validate_version_failure(self, cli_runner, mock_repo_root):
        """Test validate when version validation fails."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.validate_versions.return_value = {
                    "infrastructure": True,
                    "adapters": False,
                }

                mock_user_path = Mock(spec=Path)
                mock_user_path.exists.return_value = False
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock(spec=Path)
                mock_project_path.exists.return_value = False
                mock_cm.project_config = mock_project_path

                result = cli_runner.invoke(cli, ["config", "validate"])
                assert result.exit_code == 1
                assert "Some configuration issues found" in result.output
                assert "versions.yaml adapters" in result.output

    def test_validate_user_config_syntax_error(self, cli_runner, mock_repo_root):
        """Test validate when user config has syntax errors."""
        from aidb_common.io.files import FileOperationError

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.validate_versions.return_value = {
                    "infrastructure": True,
                    "adapters": True,
                }

                mock_user_path = Mock(spec=Path)
                mock_user_path.exists.return_value = True
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock(spec=Path)
                mock_project_path.exists.return_value = False
                mock_cm.project_config = mock_project_path

                with patch(
                    "aidb_cli.commands.config.safe_read_yaml",
                    side_effect=FileOperationError("YAML syntax error"),
                ):
                    result = cli_runner.invoke(cli, ["config", "validate"])
                    assert result.exit_code == 1
                    assert "User config syntax: YAML syntax error" in result.output
                    assert "Some configuration issues found" in result.output

    def test_validate_project_config_syntax_error(self, cli_runner, mock_repo_root):
        """Test validate when project config has syntax errors."""
        from aidb_common.io.files import FileOperationError

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.validate_versions.return_value = {
                    "infrastructure": True,
                    "adapters": True,
                }

                mock_user_path = Mock(spec=Path)
                mock_user_path.exists.return_value = False
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock(spec=Path)
                mock_project_path.exists.return_value = True
                mock_cm.project_config = mock_project_path

                def safe_read_yaml_side_effect(path):
                    if path == mock_project_path:
                        msg = "Invalid YAML"
                        raise FileOperationError(msg)
                    return {}

                with patch(
                    "aidb_cli.commands.config.safe_read_yaml",
                    side_effect=safe_read_yaml_side_effect,
                ):
                    result = cli_runner.invoke(cli, ["config", "validate"])
                    assert result.exit_code == 1
                    assert "Project config syntax: Invalid YAML" in result.output
                    assert "Some configuration issues found" in result.output

    def test_validate_no_user_config(self, cli_runner, mock_repo_root):
        """Test validate shows info message when no user config exists."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
                mock_cm = Mock()
                mock_cm_class.return_value = mock_cm
                mock_cm.validate_versions.return_value = {
                    "infrastructure": True,
                    "adapters": True,
                }

                mock_user_path = Mock(spec=Path)
                mock_user_path.exists.return_value = False
                mock_cm.user_config = mock_user_path

                mock_project_path = Mock(spec=Path)
                mock_project_path.exists.return_value = False
                mock_cm.project_config = mock_project_path

                result = cli_runner.invoke(cli, ["config", "validate"])
                assert result.exit_code == 0
                assert "No user config file" in result.output
                assert "No project config file" in result.output

    def test_config_help(self, cli_runner):
        """Test config command help text."""
        result = cli_runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "Manage AIDB configuration settings" in result.output
        assert "show" in result.output
        assert "set" in result.output
        assert "get" in result.output
        assert "init" in result.output
        assert "paths" in result.output
        assert "validate" in result.output
