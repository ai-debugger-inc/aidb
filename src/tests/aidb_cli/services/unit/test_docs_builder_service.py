"""Unit tests for DocsBuilderService."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from aidb_cli.services.docs.docs_builder_service import DocsBuilderService, DocsTarget


class TestDocsBuilderService:
    """Test the DocsBuilderService."""

    @pytest.fixture
    def versions_json_content(self):
        """Sample versions.json content."""
        return """{
  "infrastructure": {
    "python": {
      "docker_tag": "3.12-slim"
    }
  },
  "global_packages": {
    "pip": {
      "pip": {"version": "25.3"},
      "setuptools": {"version": "80.9.0"},
      "wheel": {"version": "0.45.1"}
    }
  }
}"""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor, versions_json_content):
        """Create a DocsBuilderService instance."""
        # Create versions.json
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_json_content)

        # Create the compose file at the expected location
        compose_file = tmp_path / "docs" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text("version: '3.8'\n")

        with patch(
            "aidb_cli.core.paths.ProjectPaths.DOCS_DOCKER_COMPOSE",
            "docs/docker-compose.yaml",
        ):
            return DocsBuilderService(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

    def test_service_initialization(
        self,
        tmp_path,
        mock_command_executor,
        versions_json_content,
    ):
        """Test service initialization."""
        # Create versions.json
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_json_content)

        compose_file = tmp_path / "docs" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text("version: '3.8'\n")

        with patch(
            "aidb_cli.core.paths.ProjectPaths.DOCS_DOCKER_COMPOSE",
            "docs/docker-compose.yaml",
        ):
            service = DocsBuilderService(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

            assert service.repo_root == tmp_path
            assert service.compose_file == tmp_path / "docs" / "docker-compose.yaml"

    def test_docs_target_constants(self):
        """Test DocsTarget predefined configurations."""
        assert DocsBuilderService.PUBLIC.build_service == "aidb-docs-build"
        assert DocsBuilderService.PUBLIC.serve_service == "aidb-docs"
        assert DocsBuilderService.PUBLIC.port_env_var == "AIDB_DOCS_PORT"
        assert DocsBuilderService.PUBLIC.default_port == 8000

    @patch("aidb_cli.services.docs.docs_env_sync_service.DocsEnvSyncService")
    def test_ensure_compose_file_exists(self, mock_sync_service_class, service):
        """Test ensure_compose_file when file exists and triggers env sync."""
        mock_sync_service = Mock()
        mock_sync_service_class.return_value = mock_sync_service

        result = service.ensure_compose_file()

        assert result == service.compose_file
        assert result.exists()

        # Verify env sync was called
        mock_sync_service_class.assert_called_once_with(service.repo_root)
        mock_sync_service.sync_if_needed.assert_called_once()

    def test_ensure_compose_file_not_found(
        self,
        tmp_path,
        mock_command_executor,
        versions_json_content,
    ):
        """Test ensure_compose_file when file doesn't exist."""
        # Create versions.json
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_json_content)

        with patch(
            "aidb_cli.core.paths.ProjectPaths.DOCS_DOCKER_COMPOSE",
            "docs/docker-compose.yaml",
        ):
            service = DocsBuilderService(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
            )

            with pytest.raises(FileNotFoundError) as exc_info:
                service.ensure_compose_file()

            assert "Docs compose file not found" in str(exc_info.value)

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_docs_executor_with_environment(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test get_docs_executor with existing environment."""
        mock_env = {"FOO": "bar"}
        # Mock the resolved_env property
        with patch.object(
            type(service),
            "resolved_env",
            new_callable=PropertyMock,
            return_value=mock_env,
        ):
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            executor = service.get_docs_executor()

            assert executor == mock_executor
            mock_executor_class.assert_called_once()
            call_kwargs = mock_executor_class.call_args[1]
            assert call_kwargs["environment"] == mock_env
            assert call_kwargs["project_name"] == "aidb-docs"

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_docs_executor_without_environment(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test get_docs_executor creates EnvironmentManager when no context."""
        # Mock the resolved_env property to return None
        with patch.object(
            type(service),
            "resolved_env",
            new_callable=PropertyMock,
            return_value=None,
        ):
            mock_env_manager = Mock()
            mock_env = {"BAZ": "qux"}
            mock_env_manager.get_environment.return_value = mock_env
            mock_env_manager_class.return_value = mock_env_manager

            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            executor = service.get_docs_executor()

            assert executor == mock_executor
            mock_env_manager_class.assert_called_once_with(service.repo_root)
            mock_env_manager.get_environment.assert_called_once()
            call_kwargs = mock_executor_class.call_args[1]
            assert call_kwargs["environment"] == mock_env

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_build_docs_public(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test building public docs."""
        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        service.build_docs(DocsBuilderService.PUBLIC)

        mock_executor.run_service.assert_called_once_with(
            "aidb-docs-build",
            remove=True,
            capture_output=False,
            check=True,
        )

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_running_services(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting running services."""
        mock_executor = Mock()
        mock_executor.get_running_services.return_value = ["aidb-docs"]
        mock_executor_class.return_value = mock_executor

        services = service.get_running_services()

        assert services == ["aidb-docs"]
        mock_executor.get_running_services.assert_called_once()

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_service_port_default(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service port with default internal port."""
        mock_executor = Mock()
        mock_executor.get_service_port.return_value = "8080"
        mock_executor_class.return_value = mock_executor

        port = service.get_service_port("aidb-docs")

        assert port == "8080"
        mock_executor.get_service_port.assert_called_once_with("aidb-docs", "8000")

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_service_port_custom(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service port with custom internal port."""
        mock_executor = Mock()
        mock_executor.get_service_port.return_value = "9090"
        mock_executor_class.return_value = mock_executor

        port = service.get_service_port("aidb-docs", "9000")

        assert port == "9090"
        mock_executor.get_service_port.assert_called_once_with("aidb-docs", "9000")

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_service_port_not_running(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service port when service not running."""
        mock_executor = Mock()
        mock_executor.get_service_port.return_value = None
        mock_executor_class.return_value = mock_executor

        port = service.get_service_port("aidb-docs")

        assert port is None

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    @patch("aidb_cli.services.docs.docs_builder_service.reader.read_str")
    def test_get_service_status_running_with_port(
        self,
        mock_read_str,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service status when running with port."""
        mock_executor = Mock()
        mock_executor.get_running_services.return_value = ["aidb-docs"]
        mock_executor.get_service_port.return_value = "8080"
        mock_executor_class.return_value = mock_executor

        is_running, port = service.get_service_status(DocsBuilderService.PUBLIC)

        assert is_running is True
        assert port == "8080"

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    @patch("aidb_cli.services.docs.docs_builder_service.reader.read_str")
    def test_get_service_status_running_no_port(
        self,
        mock_read_str,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service status when running but no port found."""
        mock_executor = Mock()
        mock_executor.get_running_services.return_value = ["aidb-docs"]
        mock_executor.get_service_port.return_value = None
        mock_executor_class.return_value = mock_executor
        mock_read_str.return_value = "8000"

        is_running, port = service.get_service_status(DocsBuilderService.PUBLIC)

        assert is_running is True
        assert port == "8000"
        mock_read_str.assert_called_once_with("AIDB_DOCS_PORT", default="8000")

    @patch("aidb_cli.managers.docker.DockerComposeExecutor")
    @patch("aidb_cli.managers.environment_manager.EnvironmentManager")
    def test_get_service_status_not_running(
        self,
        mock_env_manager_class,
        mock_executor_class,
        service,
    ):
        """Test getting service status when not running."""
        mock_executor = Mock()
        mock_executor.get_running_services.return_value = []
        mock_executor_class.return_value = mock_executor

        is_running, port = service.get_service_status(DocsBuilderService.PUBLIC)

        assert is_running is False
        assert port is None

    def test_get_compose_file(self, service):
        """Test _get_compose_file returns correct path."""
        compose_file = service._get_compose_file()
        # Verify it's a Path under repo_root and ends with docker-compose.yaml
        assert isinstance(compose_file, Path)
        assert compose_file.name == "docker-compose.yaml"
        assert str(compose_file).startswith(str(service.repo_root))

    def test_initialization_without_command_executor(
        self,
        tmp_path,
        versions_json_content,
    ):
        """Test initialization without explicit command executor."""
        # Create versions.json
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_json_content)

        compose_file = tmp_path / "docs" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.write_text("version: '3.8'\n")

        with patch(
            "aidb_cli.core.paths.ProjectPaths.DOCS_DOCKER_COMPOSE",
            "docs/docker-compose.yaml",
        ):
            service = DocsBuilderService(repo_root=tmp_path)
            assert service.repo_root == tmp_path
            assert service.compose_file.exists()
