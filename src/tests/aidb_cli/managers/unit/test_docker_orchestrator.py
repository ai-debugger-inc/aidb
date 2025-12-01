"""Unit tests for DockerOrchestrator."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from aidb_cli.managers.docker.docker_orchestrator import DockerOrchestrator


class TestDockerOrchestrator:
    """Test the DockerOrchestrator."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def mock_version_manager(self):
        """Create a mock version manager."""
        manager = Mock()
        manager.get_version = Mock(return_value="1.0.0")
        return manager

    @pytest.fixture
    def mock_docker_executor(self):
        """Create a mock DockerComposeExecutor."""
        executor = Mock()
        executor.execute = Mock()
        executor.command_executor = Mock()
        return executor

    @pytest.fixture
    def mock_services(self):
        """Create mock service definitions."""
        service1 = Mock()
        service1.started = False
        service1.healthy = False
        service1.profiles = ["test"]
        service1.health_check = True

        service2 = Mock()
        service2.started = False
        service2.healthy = False
        service2.profiles = ["test"]
        service2.health_check = False

        return {"service1": service1, "service2": service2}

    @pytest.fixture
    @patch("aidb_cli.managers.docker.docker_orchestrator.ComposeGeneratorService")
    @patch("aidb_cli.managers.docker.docker_orchestrator.VersionManager")
    @patch("aidb_cli.managers.docker.docker_orchestrator.DockerComposeExecutor")
    @patch("aidb_cli.managers.docker.docker_orchestrator.EnvironmentManager")
    def orchestrator(
        self,
        mock_env_manager_class,
        mock_executor_class,
        mock_version_manager_class,
        mock_compose_gen_class,
        tmp_path,
        mock_command_executor,
        mock_docker_executor,
        mock_version_manager,
    ):
        """Create orchestrator instance with mocks."""
        # Mock environment manager
        mock_env_manager = Mock()
        mock_env_manager.get_environment.return_value = {"TEST": "value"}
        mock_env_manager_class.return_value = mock_env_manager

        # Mock docker executor
        mock_executor_class.return_value = mock_docker_executor

        # Mock version manager
        mock_version_manager_class.return_value = mock_version_manager

        # Mock compose generator
        mock_compose_gen = Mock()
        mock_compose_gen.generate.return_value = None
        mock_compose_gen_class.return_value = mock_compose_gen

        # Create compose file
        compose_dir = tmp_path / "src" / "tests" / "_docker"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.touch()

        return DockerOrchestrator(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            ctx=None,
        )

    def test_initialization_with_repo_root(
        self,
        tmp_path,
        mock_command_executor,
    ):
        """Test orchestrator initialization with repo root."""
        compose_dir = tmp_path / "src" / "tests" / "_docker"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.touch()

        with (
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.ComposeGeneratorService",
            ),
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.VersionManager",
            ),
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.DockerComposeExecutor",
            ),
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.EnvironmentManager",
            ),
        ):
            orch = DockerOrchestrator(
                repo_root=tmp_path,
                command_executor=mock_command_executor,
                ctx=None,
            )

            assert orch.repo_root == tmp_path
            assert orch.compose_file == compose_file

    def test_initialization_with_context(self, tmp_path):
        """Test orchestrator initialization with Click context."""
        # Create mock context with resolved_env
        mock_ctx = Mock()
        mock_ctx.obj = Mock()
        mock_ctx.obj.resolved_env = {"TEST": "value"}

        compose_dir = tmp_path / "src" / "tests" / "_docker"
        compose_dir.mkdir(parents=True)
        compose_file = compose_dir / "docker-compose.yaml"
        compose_file.touch()

        with (
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.ComposeGeneratorService",
            ),
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.VersionManager",
            ),
            patch(
                "aidb_cli.managers.docker.docker_orchestrator.DockerComposeExecutor",
            ) as mock_executor_class,
        ):
            orch = DockerOrchestrator(
                repo_root=tmp_path,
                command_executor=None,
                ctx=mock_ctx,
            )

            assert orch.ctx is mock_ctx
            # Verify executor was created with environment from context
            mock_executor_class.assert_called_once()

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.ServiceDependencyService",
    )
    def test_resolve_dependencies(
        self,
        mock_service_class,
        orchestrator,
    ):
        """Test dependency resolution."""
        mock_service = Mock()
        mock_service.resolve_dependencies.return_value = ["dep1", "dep2", "service1"]
        orchestrator.services = {"service1": Mock()}

        with patch.object(orchestrator, "get_service", return_value=mock_service):
            deps = orchestrator.resolve_dependencies("service1")

            assert deps == ["dep1", "dep2", "service1"]
            mock_service.resolve_dependencies.assert_called_once_with("service1")

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.ServiceDependencyService",
    )
    def test_start_service_already_started(
        self,
        mock_dep_class,
        mock_output,
        orchestrator,
        mock_services,
    ):
        """Test starting a service that's already started."""
        orchestrator.services = mock_services
        mock_services["service1"].started = True

        # Mock service registry
        mock_dep_service = Mock()
        with patch.object(orchestrator, "get_service", return_value=mock_dep_service):
            result = orchestrator.start_service("service1")

            assert result is True

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.ServiceDependencyService",
    )
    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerHealthService",
    )
    def test_start_service_success(
        self,
        mock_health_class,
        mock_dep_class,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test successful service startup."""
        orchestrator.services = mock_services

        mock_dep_service = Mock()
        mock_dep_service.resolve_dependencies.return_value = ["service1"]

        mock_health_service = Mock()
        mock_health_service.wait_for_health.return_value = True

        with patch.object(
            orchestrator,
            "get_service",
            side_effect=lambda x: (
                mock_dep_service if x == mock_dep_class else mock_health_service
            ),
        ):
            mock_docker_executor.execute.return_value = Mock(returncode=0)

            result = orchestrator.start_service("service1", wait_healthy=True)

            assert result is True
            assert mock_services["service1"].started is True
            mock_health_service.wait_for_health.assert_called_once()

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.ServiceDependencyService",
    )
    def test_start_service_failure(
        self,
        mock_dep_class,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test failed service startup."""
        orchestrator.services = mock_services

        mock_dep_service = Mock()
        mock_dep_service.resolve_dependencies.return_value = ["service1"]

        with patch.object(orchestrator, "get_service", return_value=mock_dep_service):
            mock_docker_executor.execute.return_value = Mock(
                returncode=1,
                stderr="Failed to start",
            )

            result = orchestrator.start_service("service1")

            assert result is False
            assert mock_services["service1"].started is False

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerHealthService",
    )
    def test_wait_for_health_success(
        self,
        mock_health_class,
        orchestrator,
        mock_services,
    ):
        """Test successful health check waiting."""
        orchestrator.services = mock_services

        mock_health_service = Mock()
        mock_health_service.wait_for_health.return_value = True

        with patch.object(
            orchestrator,
            "get_service",
            return_value=mock_health_service,
        ):
            result = orchestrator.wait_for_health("service1", timeout=30)

            assert result is True
            assert mock_services["service1"].healthy is True

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerHealthService",
    )
    def test_wait_for_health_unknown_service(
        self,
        mock_health_class,
        orchestrator,
    ):
        """Test health check for unknown service."""
        orchestrator.services = {}

        # Mock service even though it won't be used - get_service is called first
        mock_health_service = Mock()
        with patch.object(
            orchestrator,
            "get_service",
            return_value=mock_health_service,
        ):
            result = orchestrator.wait_for_health("unknown")

            assert result is False

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    def test_stop_service_success(
        self,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test successful service stopping."""
        orchestrator.services = mock_services
        mock_services["service1"].started = True

        mock_docker_executor.execute.return_value = Mock(returncode=0)

        result = orchestrator.stop_service("service1")

        assert result is True
        assert mock_services["service1"].started is False
        assert mock_services["service1"].healthy is False

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    def test_stop_service_failure(
        self,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test failed service stopping."""
        orchestrator.services = mock_services

        mock_docker_executor.execute.return_value = Mock(
            returncode=1,
            stderr="Failed to stop",
        )

        result = orchestrator.stop_service("service1")

        assert result is False

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    def test_cleanup_services_success(
        self,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test successful service cleanup."""
        orchestrator.services = mock_services
        mock_services["service1"].started = True

        mock_docker_executor.execute.return_value = Mock(returncode=0)

        result = orchestrator.cleanup_services(profile="test", remove_volumes=True)

        assert result is True
        assert mock_services["service1"].started is False
        assert mock_services["service1"].healthy is False

    @patch("aidb_cli.managers.docker.docker_orchestrator.CliOutput")
    def test_cleanup_services_failure(
        self,
        mock_output,
        orchestrator,
        mock_services,
        mock_docker_executor,
    ):
        """Test failed service cleanup."""
        orchestrator.services = mock_services

        mock_docker_executor.execute.return_value = Mock(
            returncode=1,
            stderr="Cleanup failed",
        )

        result = orchestrator.cleanup_services()

        assert result is False

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerLoggingService",
    )
    def test_get_service_logs(
        self,
        mock_logging_class,
        orchestrator,
    ):
        """Test retrieving service logs."""
        mock_logging_service = Mock()
        mock_logging_service.get_service_logs.return_value = "log output"

        with patch.object(
            orchestrator,
            "get_service",
            return_value=mock_logging_service,
        ):
            logs = orchestrator.get_service_logs("service1", lines=50)

            assert logs == "log output"
            mock_logging_service.get_service_logs.assert_called_once_with(
                "service1",
                lines=50,
            )

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerHealthService",
    )
    def test_run_health_checks(
        self,
        mock_health_class,
        orchestrator,
        mock_services,
    ):
        """Test running health checks on all services."""
        orchestrator.services = mock_services
        mock_services["service1"].started = True
        mock_services["service2"].started = True

        mock_health_service = Mock()
        mock_health_service.wait_for_health.side_effect = [True, False]

        with patch.object(
            orchestrator,
            "get_service",
            return_value=mock_health_service,
        ):
            results = orchestrator.run_health_checks()

            assert results["service1"] is True
            # service2 has no health check, so should be True (assumed healthy)
            assert results["service2"] is True

    @patch(
        "aidb_cli.managers.docker.docker_orchestrator.DockerLoggingService",
    )
    def test_stream_compose_logs(
        self,
        mock_logging_class,
        orchestrator,
    ):
        """Test streaming compose logs."""
        mock_logging_service = Mock()
        mock_process = Mock()
        mock_logging_service.stream_compose_logs.return_value = mock_process

        with patch.object(
            orchestrator,
            "get_service",
            return_value=mock_logging_service,
        ):
            result = orchestrator.stream_compose_logs(follow=True, profile="test")

            assert result is mock_process
            mock_logging_service.stream_compose_logs.assert_called_once()

    def test_wait_for_compose_completion(
        self,
        orchestrator,
        mock_docker_executor,
    ):
        """Test waiting for compose completion."""
        mock_docker_executor.execute.return_value = Mock(returncode=0)

        exit_code = orchestrator.wait_for_compose_completion(
            profile="test",
            stream_logs=False,
            timeout=300,
        )

        assert exit_code == 0
        mock_docker_executor.execute.assert_called_once()

    def test_wait_for_compose_completion_with_streaming(
        self,
        orchestrator,
        mock_docker_executor,
    ):
        """Test waiting for compose completion with log streaming."""
        mock_docker_executor.execute.return_value = Mock(returncode=0)
        mock_process = Mock()

        with patch.object(
            orchestrator,
            "stream_compose_logs",
            return_value=mock_process,
        ):
            exit_code = orchestrator.wait_for_compose_completion(
                profile="test",
                stream_logs=True,
                timeout=300,
            )

            assert exit_code == 0
