"""Tests for version management commands."""

from unittest.mock import Mock, PropertyMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


class TestVersionsCommands:
    """Test version management commands."""

    def test_show_default_text_format(self, cli_runner, mock_repo_root):
        """Test versions show with default text format."""
        mock_config_manager = Mock()
        mock_config_manager.get_versions.return_value = "Python: 3.12\nNode: 20.0.0"

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(cli, ["versions", "show"])
                assert result.exit_code == 0
                mock_config_manager.get_versions.assert_called_once_with("text")
                assert "Python: 3.12" in result.output

    def test_show_json_format(self, cli_runner, mock_repo_root):
        """Test versions show with JSON format."""
        mock_config_manager = Mock()
        mock_config_manager.get_versions.return_value = '{"python": "3.12"}'

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["versions", "show", "--format", "json"],
                )
                assert result.exit_code == 0
                mock_config_manager.get_versions.assert_called_once_with("json")

    def test_show_yaml_format(self, cli_runner, mock_repo_root):
        """Test versions show with YAML format."""
        mock_config_manager = Mock()
        mock_config_manager.get_versions.return_value = "python: '3.12'"

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["versions", "show", "--format", "yaml"],
                )
                assert result.exit_code == 0
                mock_config_manager.get_versions.assert_called_once_with("yaml")

    def test_show_env_format(self, cli_runner, mock_repo_root):
        """Test versions show with env format."""
        mock_config_manager = Mock()
        mock_config_manager.get_versions.return_value = "PYTHON_VERSION=3.12"

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(cli, ["versions", "show", "--format", "env"])
                assert result.exit_code == 0
                mock_config_manager.get_versions.assert_called_once_with("env")

    def test_validate_all_valid(self, cli_runner, mock_repo_root):
        """Test versions validate with all valid sections."""
        # Mock the entire ConfigManager class at import time
        with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
            mock_config_manager = Mock()
            mock_config_manager.validate_versions.return_value = {
                "infrastructure": True,
                "adapters": True,
                "runtime": True,
            }
            mock_cm_class.return_value = mock_config_manager

            with patch(
                "aidb_common.repo.detect_repo_root",
                return_value=mock_repo_root,
            ):
                result = cli_runner.invoke(cli, ["versions", "validate"])
                assert result.exit_code == 0
                mock_config_manager.validate_versions.assert_called_once()
                assert "All version configurations are valid!" in result.output

    def test_validate_with_errors(self, cli_runner, mock_repo_root):
        """Test versions validate with some invalid sections."""
        with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
            mock_config_manager = Mock()
            mock_config_manager.validate_versions.return_value = {
                "infrastructure": True,
                "adapters": False,
                "runtime": True,
            }
            mock_cm_class.return_value = mock_config_manager

            with patch(
                "aidb_common.repo.detect_repo_root",
                return_value=mock_repo_root,
            ):
                result = cli_runner.invoke(cli, ["versions", "validate"])
                assert result.exit_code == 1
                mock_config_manager.validate_versions.assert_called_once()
                assert (
                    "Some version configurations are missing or invalid"
                    in result.output
                )
                assert "Check versions.json for missing sections" in result.output

    def test_validate_output_format(self, cli_runner, mock_repo_root):
        """Test versions validate output shows section status."""
        with patch("aidb_cli.cli.ConfigManager") as mock_cm_class:
            mock_config_manager = Mock()
            mock_config_manager.validate_versions.return_value = {
                "infrastructure": True,
                "adapters": False,
            }
            mock_cm_class.return_value = mock_config_manager

            with patch(
                "aidb_common.repo.detect_repo_root",
                return_value=mock_repo_root,
            ):
                result = cli_runner.invoke(cli, ["versions", "validate"])
                assert result.exit_code == 1
                assert "Infrastructure" in result.output
                assert "Adapters" in result.output

    def test_docker_text_format(self, cli_runner, mock_repo_root):
        """Test versions docker with text format."""
        mock_config_manager = Mock()
        mock_config_manager.get_docker_build_args.return_value = {
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "20.0.0",
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(cli, ["versions", "docker"])
                assert result.exit_code == 0
                mock_config_manager.get_docker_build_args.assert_called_once()
                assert "PYTHON_VERSION" in result.output

    def test_docker_json_format(self, cli_runner, mock_repo_root):
        """Test versions docker with JSON format."""
        mock_config_manager = Mock()
        mock_config_manager.get_docker_build_args.return_value = {
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "20.0.0",
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["versions", "docker", "--format", "json"],
                )
                assert result.exit_code == 0
                mock_config_manager.get_docker_build_args.assert_called_once()
                assert '"PYTHON_VERSION": "3.12"' in result.output

    def test_docker_env_format(self, cli_runner, mock_repo_root):
        """Test versions docker with env format."""
        mock_config_manager = Mock()
        mock_config_manager.get_docker_build_args.return_value = {
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "20.0.0",
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.config_manager",
                new_callable=PropertyMock,
                return_value=mock_config_manager,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["versions", "docker", "--format", "env"],
                )
                assert result.exit_code == 0
                mock_config_manager.get_docker_build_args.assert_called_once()
                assert "export PYTHON_VERSION=3.12" in result.output
                assert "export NODE_VERSION=20.0.0" in result.output

    def test_check_consistency_success(self, cli_runner, mock_repo_root):
        """Test check-consistency when validation passes."""
        from aidb_cli.services.version import ConsistencyReport

        mock_report = ConsistencyReport(mismatches=[], files_checked=["test.yaml"])

        with patch(
            "aidb_cli.cli.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.cli.ConfigManager"):
                with patch(
                    "aidb_cli.services.version.VersionConsistencyService",
                ) as mock_service_class:
                    mock_service = Mock()
                    mock_service.check_all.return_value = mock_report
                    mock_service_class.return_value = mock_service

                    result = cli_runner.invoke(cli, ["versions", "check-consistency"])
                    assert result.exit_code == 0
                    assert "Version consistency check passed!" in result.output

    def test_check_consistency_failure(self, cli_runner, mock_repo_root):
        """Test check-consistency when validation fails."""
        from aidb_cli.services.version import ConsistencyReport, VersionMismatch

        mock_report = ConsistencyReport(
            mismatches=[
                VersionMismatch(
                    file="docker-compose.yaml",
                    line=10,
                    variable="PYTHON_VERSION",
                    expected="3.12",
                    found="3.11",
                    severity="error",
                ),
            ],
            files_checked=["docker-compose.yaml"],
        )

        with patch(
            "aidb_cli.cli.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.cli.ConfigManager"):
                with patch(
                    "aidb_cli.services.version.VersionConsistencyService",
                ) as mock_service_class:
                    mock_service = Mock()
                    mock_service.check_all.return_value = mock_report
                    mock_service_class.return_value = mock_service

                    result = cli_runner.invoke(cli, ["versions", "check-consistency"])
                    assert result.exit_code == 1
                    assert "Version inconsistencies detected!" in result.output

    def test_check_consistency_with_warnings(self, cli_runner, mock_repo_root):
        """Test check-consistency with warnings only passes."""
        from aidb_cli.services.version import ConsistencyReport, VersionMismatch

        mock_report = ConsistencyReport(
            mismatches=[
                VersionMismatch(
                    file="Dockerfile.java",
                    line=18,
                    variable="JAVA_VERSION",
                    expected="21",
                    found="21",
                    severity="warning",
                ),
            ],
            files_checked=["Dockerfile.java"],
        )

        with patch(
            "aidb_cli.cli.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch("aidb_cli.cli.ConfigManager"):
                with patch(
                    "aidb_cli.services.version.VersionConsistencyService",
                ) as mock_service_class:
                    mock_service = Mock()
                    mock_service.check_all.return_value = mock_report
                    mock_service_class.return_value = mock_service

                    result = cli_runner.invoke(cli, ["versions", "check-consistency"])
                    # Warnings only = exit 0
                    assert result.exit_code == 0
                    assert "1 warning(s)" in result.output

    def test_info_valid_language(self, cli_runner, mock_repo_root):
        """Test info command with valid language."""
        mock_build_manager = Mock()
        mock_build_manager.get_supported_languages.return_value = [
            "python",
            "javascript",
            "java",
        ]
        mock_build_manager.get_adapter_info.return_value = {
            "status": "built",
            "version": "1.8.0",
            "path": "/cache/adapters/python",
        }

        mock_config_manager = Mock()
        mock_config_manager.get_adapter_version.return_value = "1.8.0"

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                with patch(
                    "aidb_cli.cli.Context.config_manager",
                    new_callable=PropertyMock,
                    return_value=mock_config_manager,
                ):
                    result = cli_runner.invoke(cli, ["versions", "info", "python"])
                    assert result.exit_code == 0
                    assert "Python Adapter Information" in result.output
                    assert "Configured Version: 1.8.0" in result.output
                    assert "Build Status: built" in result.output
                    assert "Installed Version: 1.8.0" in result.output

    def test_info_unsupported_language(self, cli_runner, mock_repo_root):
        """Test info command with unsupported language."""
        mock_build_manager = Mock()
        mock_build_manager.get_supported_languages.return_value = [
            "python",
            "javascript",
            "java",
        ]

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                result = cli_runner.invoke(cli, ["versions", "info", "rust"])
                assert result.exit_code == 2
                assert "Invalid value" in result.output

    def test_info_no_configured_version(self, cli_runner, mock_repo_root):
        """Test info command when no version is configured."""
        mock_build_manager = Mock()
        mock_build_manager.get_supported_languages.return_value = ["python"]
        mock_build_manager.get_adapter_info.return_value = {
            "status": "not built",
            "version": "",
            "path": None,
        }

        mock_config_manager = Mock()
        mock_config_manager.get_adapter_version.return_value = None

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                with patch(
                    "aidb_cli.cli.Context.config_manager",
                    new_callable=PropertyMock,
                    return_value=mock_config_manager,
                ):
                    result = cli_runner.invoke(cli, ["versions", "info", "python"])
                    assert result.exit_code == 0
                    assert "Configured Version: Not configured" in result.output

    def test_info_calls_correct_methods(self, cli_runner, mock_repo_root):
        """Test info command calls correct manager methods."""
        mock_build_manager = Mock()
        mock_build_manager.get_supported_languages.return_value = ["javascript"]
        mock_build_manager.get_adapter_info.return_value = {
            "status": "built",
            "version": "1.84.0",
            "path": "/cache/adapters/javascript",
        }

        mock_config_manager = Mock()
        mock_config_manager.get_adapter_version.return_value = "1.84.0"

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                with patch(
                    "aidb_cli.cli.Context.config_manager",
                    new_callable=PropertyMock,
                    return_value=mock_config_manager,
                ):
                    result = cli_runner.invoke(cli, ["versions", "info", "javascript"])
                    assert result.exit_code == 0
                    # get_supported_languages gets called twice: once by LanguageParamType,
                    # once by the command itself
                    assert mock_build_manager.get_supported_languages.call_count >= 1
                    mock_config_manager.get_adapter_version.assert_called_once_with(
                        "javascript",
                    )
                    mock_build_manager.get_adapter_info.assert_called_once_with(
                        "javascript",
                    )

    def test_versions_help(self, cli_runner):
        """Test versions command help text."""
        result = cli_runner.invoke(cli, ["versions", "--help"])
        assert result.exit_code == 0
        assert "Manage and display version information" in result.output
        assert "show" in result.output
        assert "validate" in result.output
        assert "docker" in result.output
        assert "check-consistency" in result.output
        assert "info" in result.output
