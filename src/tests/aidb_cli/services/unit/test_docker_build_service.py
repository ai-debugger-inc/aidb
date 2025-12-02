"""Unit tests for DockerBuildService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.docker.docker_build_service import DockerBuildService


class TestDockerBuildService:
    """Test the DockerBuildService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create a DockerBuildService instance with mocks."""
        # Create mock docker-compose file structure
        compose_dir = tmp_path / "src" / "tests" / "docker"
        compose_dir.mkdir(parents=True, exist_ok=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.write_text("version: '3'")

        # Create runtime Dockerfile
        runtime_dockerfile = compose_dir / "Dockerfile.runtime"
        runtime_dockerfile.write_text("FROM python:3.12")

        return DockerBuildService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization sets up paths correctly."""
        # Create compose file
        compose_dir = tmp_path / "src" / "tests" / "_docker"
        compose_dir.mkdir(parents=True, exist_ok=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.write_text("version: '3'")

        # Create service
        service = DockerBuildService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        # Assert
        assert service.repo_root == tmp_path
        assert service.compose_file == compose_file
        assert service.compose_dir == compose_dir

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_base_profile(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test building images with base profile."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        returncode = service.build_images(profile="base")

        # Assert
        assert returncode == 0
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "build" in call_args
        assert "test-runner" in call_args

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_custom_profile(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test building images with custom profile."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
            "postgres",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        returncode = service.build_images(profile="cli")

        # Assert
        assert returncode == 0
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert "build" in call_args
        # Verify services are present
        assert "test-runner" in call_args
        assert "postgres" in call_args

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_with_no_cache(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test building images with no-cache flag."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        returncode = service.build_images(profile="base", no_cache=True)

        # Assert
        assert returncode == 0
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "--no-cache" in call_args

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_failure(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test building images failure handling."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=1)

        # Execute
        returncode = service.build_images()

        # Assert
        assert returncode == 1

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_with_verbose(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
        capsys,
    ):
        """Test building images with verbose output."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        service.build_images(profile="base", verbose=True)

        # Assert - should output the command
        captured = capsys.readouterr()
        assert "docker compose" in captured.out

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_command_structure(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
        tmp_path,
    ):
        """Test that images build command has correct structure."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        service.build_images(profile="base")

        # Assert - verify command structure
        call_args = mock_command_executor.execute.call_args[0][0]
        # Verify project directory
        assert "--project-directory" in call_args
        project_dir_idx = call_args.index("--project-directory")
        assert call_args[project_dir_idx + 1] == str(tmp_path)
        # Verify compose file
        assert "-f" in call_args
        f_idx = call_args.index("-f")
        assert "docker-compose.yaml" in str(call_args[f_idx + 1])
        # Verify project name
        assert "--project-name" in call_args
        # Verify working directory is repo_root
        call_kwargs = mock_command_executor.execute.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    def test_image_exists_when_present(self, service, mock_command_executor):
        """Test _image_exists returns True when image exists."""
        # Setup - image exists (returncode 0)
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Execute
        result = service._image_exists("aidb-test-base:latest")

        # Assert
        assert result is True
        mock_command_executor.execute.assert_called_once()
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "image" in call_args
        assert "inspect" in call_args
        assert "aidb-test-base:latest" in call_args

    def test_image_exists_when_missing(self, service, mock_command_executor):
        """Test _image_exists returns False when image doesn't exist."""
        # Setup - image missing (returncode non-zero)
        mock_command_executor.execute.return_value = Mock(returncode=1)

        # Execute
        result = service._image_exists("aidb-test-base:latest")

        # Assert
        assert result is False

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_auto_builds_missing_base(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test that build_images auto-builds base image when missing."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service

        # Mock image check to return False (missing), then successful builds
        mock_command_executor.execute.side_effect = [
            Mock(returncode=1),  # _image_exists check (missing)
            Mock(returncode=0),  # build_base_image
            Mock(returncode=0),  # build_images compose build
        ]

        # Execute
        returncode = service.build_images(profile="base")

        # Assert
        assert returncode == 0
        # Should have 3 calls: image check, base build, compose build
        assert mock_command_executor.execute.call_count == 3

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_skips_base_when_exists(
        self,
        mock_dep_service_class,
        service,
        mock_command_executor,
    ):
        """Test that build_images skips base image build when it exists."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service

        # Mock image check to return True (exists), then successful compose build
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0),  # _image_exists check (exists)
            Mock(returncode=0),  # build_images compose build
            Mock(returncode=0),  # _mark_images_built checksum update (optional)
        ]

        # Execute
        returncode = service.build_images(profile="base")

        # Assert
        assert returncode == 0
        # Should have at least 2 calls: image check, compose build (no base build)
        assert mock_command_executor.execute.call_count >= 2

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_passes_resolved_env_to_docker(
        self,
        mock_dep_service_class,
        tmp_path,
        mock_command_executor,
    ):
        """Test that resolved_env with build args is passed to Docker commands."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Create resolved_env with build args (simulates VersionManager output)
        resolved_env = {
            "DEBUGPY_VERSION": "1.8.16",
            "PYTHON_VERSION": "3.12",
            "NODE_VERSION": "22",
            "PIP_VERSION": "25.3",
            "SETUPTOOLS_VERSION": "80.9.0",
        }

        # Create service with resolved_env
        service = DockerBuildService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            resolved_env=resolved_env,
        )

        # Execute
        returncode = service.build_images(profile="base")

        # Assert
        assert returncode == 0

        # Verify the environment was passed to the execute call
        call_kwargs = mock_command_executor.execute.call_args[1]
        env_passed = call_kwargs["env"]

        # All build args should be in the environment
        assert env_passed["DEBUGPY_VERSION"] == "1.8.16"
        assert env_passed["PYTHON_VERSION"] == "3.12"
        assert env_passed["NODE_VERSION"] == "22"
        assert env_passed["PIP_VERSION"] == "25.3"
        assert env_passed["SETUPTOOLS_VERSION"] == "80.9.0"

        # REPO_ROOT should always be set
        assert env_passed["REPO_ROOT"] == str(tmp_path)

    @patch(
        "aidb_cli.services.docker.service_dependency_service.ServiceDependencyService",
    )
    def test_build_images_minimal_env_when_no_resolved_env(
        self,
        mock_dep_service_class,
        tmp_path,
        mock_command_executor,
    ):
        """Test that minimal env is used when resolved_env is None."""
        # Setup
        mock_dep_service = Mock()
        mock_dep_service.get_buildable_services_by_profile.return_value = [
            "test-runner",
        ]
        mock_dep_service.get_service_image_tag.return_value = "aidb-test-runner:latest"
        mock_dep_service_class.return_value = mock_dep_service
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Create service without resolved_env (None)
        service = DockerBuildService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            resolved_env=None,
        )

        # Execute
        returncode = service.build_images(profile="base")

        # Assert
        assert returncode == 0

        # Verify only REPO_ROOT is in the environment
        call_kwargs = mock_command_executor.execute.call_args[1]
        env_passed = call_kwargs["env"]

        # Should only have REPO_ROOT
        assert env_passed["REPO_ROOT"] == str(tmp_path)
        # Should not have build args (they would come from versions.json if it existed)
        assert (
            "DEBUGPY_VERSION" not in env_passed
            or env_passed.get("DEBUGPY_VERSION") is None
        )
