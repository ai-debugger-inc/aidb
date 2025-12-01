"""Tests for Docker operations commands."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli


class TestDockerCommands:
    """Test Docker-related commands."""

    def test_docker_build(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
    ):
        """Test docker build command."""
        # Mock DockerBuildService that docker build command uses
        mock_build_service = Mock()
        mock_build_service.build_images.return_value = 0

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.docker_build_service.DockerBuildService",
                return_value=mock_build_service,
            ):
                result = cli_runner.invoke(cli, ["docker", "build"])
                assert result.exit_code == 0
                # Verify build_service.build_images was called
                mock_build_service.build_images.assert_called_once()

    def test_docker_status(self, cli_runner, mock_repo_root):
        """Test docker status command."""
        # Mock test manager that status command uses
        mock_test_manager = Mock()
        mock_test_manager.get_test_status.return_value = {
            "docker_available": True,
            "docker_version": "20.10.0",
            "compose_file_exists": True,
            "adapters_built": {"python": True, "javascript": False, "java": True},
            "repo_root": str(mock_repo_root),
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.test_manager",
                new_callable=PropertyMock,
                return_value=mock_test_manager,
            ):
                result = cli_runner.invoke(cli, ["docker", "status"])
                assert result.exit_code == 0
                assert "Docker Environment Status" in result.output
                # Verify test_manager.get_test_status was called
                mock_test_manager.get_test_status.assert_called_once()

    def test_docker_env(self, cli_runner, tmp_path):
        """Test docker env command."""
        # Mock build manager that env command uses
        mock_build_manager = Mock()
        env_file_path = tmp_path / ".env.build"
        mock_build_manager.generate_env_file.return_value = env_file_path

        # Create the env file so open() doesn't fail
        env_file_path.write_text("PYTHON_VERSION=3.10\nNODE_VERSION=18\n")

        with patch("aidb_common.repo.detect_repo_root", return_value=tmp_path):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                result = cli_runner.invoke(cli, ["docker", "env"])
                assert result.exit_code == 0
                assert "Generated .env file" in result.output
                # Verify build_manager.generate_env_file was called
                mock_build_manager.generate_env_file.assert_called_once()

    def test_docker_cleanup(self, cli_runner):
        """Test docker cleanup command."""
        result = cli_runner.invoke(cli, ["docker", "cleanup", "--dry-run"])
        assert result.exit_code == 0
        assert (
            "Dry run complete" in result.output
            or "No AIDB resources found" in result.output
            or "Found AIDB resources" in result.output
        )

    def test_docker_compose_validate(self, cli_runner, mock_repo_root):
        """Test docker compose validate command."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.needs_regeneration.return_value = False
        mock_generator.validate_generated_file.return_value = (True, [])

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                result = cli_runner.invoke(cli, ["docker", "compose", "--validate"])
                assert result.exit_code == 0
                assert "Compose file is up-to-date" in result.output
                assert "Compose file is valid YAML" in result.output
                mock_generator.needs_regeneration.assert_called_once()
                mock_generator.validate_generated_file.assert_called_once()

    def test_docker_compose_validate_with_regenerate(self, cli_runner, mock_repo_root):
        """Test docker compose validate command with --regenerate flag."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.generate.return_value = (
            True,
            str(mock_repo_root / "docker-compose.yaml"),
        )
        mock_generator.validate_generated_file.return_value = (True, [])

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["docker", "compose", "--regenerate"],
                )
                assert result.exit_code == 0
                assert "Generated:" in result.output
                assert "Compose file is valid YAML" in result.output
                mock_generator.generate.assert_called_once_with(force=True)
                mock_generator.validate_generated_file.assert_called_once()

    def test_docker_compose_validate_needs_regen(self, cli_runner, mock_repo_root):
        """Test docker compose validate when file needs regeneration."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.needs_regeneration.return_value = True

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                result = cli_runner.invoke(cli, ["docker", "compose", "--validate"])
                assert result.exit_code == 1
                assert "needs regeneration" in result.output

    def test_docker_compose_validate_invalid(self, cli_runner, mock_repo_root):
        """Test docker compose validate with invalid compose file."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.needs_regeneration.return_value = False
        mock_generator.validate_generated_file.return_value = (
            False,
            ["Invalid YAML syntax"],
        )

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                result = cli_runner.invoke(cli, ["docker", "compose", "--validate"])
                assert result.exit_code == 1
                assert "validation failed" in result.output
                assert "Invalid YAML syntax" in result.output

    def test_docker_compose_generate(self, cli_runner, mock_repo_root):
        """Test docker compose generate command."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.generate.return_value = (
            True,
            str(mock_repo_root / "docker-compose.yaml"),
        )
        mock_generator.validate_generated_file.return_value = (True, [])

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                result = cli_runner.invoke(cli, ["docker", "compose", "--generate"])
                assert result.exit_code == 0
                assert "Generated:" in result.output
                # --generate does NOT validate by default, only --regenerate does
                mock_generator.generate.assert_called_once_with(force=True)
                mock_generator.validate_generated_file.assert_not_called()

    def test_docker_compose_regenerate_validation_failed(
        self,
        cli_runner,
        mock_repo_root,
    ):
        """Test docker compose --regenerate with validation failure."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.generate.return_value = (
            True,
            str(mock_repo_root / "docker-compose.yaml"),
        )
        mock_generator.validate_generated_file.return_value = (
            False,
            ["Invalid YAML"],
        )

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                # --regenerate triggers both generate AND validate
                result = cli_runner.invoke(cli, ["docker", "compose", "--regenerate"])
                assert result.exit_code == 1
                assert "validation failed" in result.output

    def test_docker_compose_status_up_to_date(self, cli_runner, mock_repo_root):
        """Test docker compose (default) status when file is up-to-date."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.needs_regeneration.return_value = False
        mock_output_file = MagicMock(spec=Path)
        mock_output_file.exists.return_value = True
        mock_generator.output_file = mock_output_file

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                # Default behavior (no flags) shows status
                result = cli_runner.invoke(cli, ["docker", "compose"])
                assert result.exit_code == 0
                assert "Compose file is up-to-date" in result.output
                mock_generator.needs_regeneration.assert_called_once()

    def test_docker_compose_status_needs_regen(self, cli_runner, mock_repo_root):
        """Test docker compose (default) status when file needs regeneration."""
        # Mock ComposeGeneratorService
        mock_generator = Mock()
        mock_generator.needs_regeneration.return_value = True
        mock_output_file = MagicMock(spec=Path)
        mock_output_file.exists.return_value = True
        mock_generator.output_file = mock_output_file

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.services.docker.ComposeGeneratorService",
                return_value=mock_generator,
            ):
                # Default behavior (no flags) shows status
                result = cli_runner.invoke(cli, ["docker", "compose"])
                assert result.exit_code == 0
                assert "needs regeneration" in result.output
                assert "docker compose --generate" in result.output

    def test_docker_compose_help(self, cli_runner):
        """Test docker compose command help text."""
        result = cli_runner.invoke(cli, ["docker", "compose", "--help"])
        assert result.exit_code == 0
        assert "Docker Compose file management" in result.output
        assert "--generate" in result.output
        assert "--validate" in result.output
        assert "--regenerate" in result.output

    def test_docker_help(self, cli_runner):
        """Test docker command help text."""
        result = cli_runner.invoke(cli, ["docker", "--help"])
        assert result.exit_code == 0
        assert "Docker infrastructure management" in result.output
        assert "build" in result.output
        assert "cleanup" in result.output
        assert "env" in result.output
        assert "status" in result.output
        assert "compose" in result.output
