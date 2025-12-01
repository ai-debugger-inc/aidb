"""Unit tests for DockerComposeExecutor."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.managers.docker.docker_executor import DockerComposeExecutor


class TestDockerComposeExecutor:
    """Test the DockerComposeExecutor."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock(return_value=Mock(returncode=0, stdout="", stderr=""))
        executor.create_process = Mock(return_value=Mock())
        return executor

    @pytest.fixture
    def executor(self, tmp_path, mock_command_executor):
        """Create DockerComposeExecutor instance."""
        compose_file = tmp_path / "docker" / "tests" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.touch()

        environment = {"TEST_VAR": "value", "PATH": "/usr/bin"}

        return DockerComposeExecutor(
            compose_file=compose_file,
            environment=environment,
            project_name="test-project",
            command_executor=mock_command_executor,
        )

    def test_initialization(self, tmp_path, mock_command_executor):
        """Test executor initialization."""
        compose_file = tmp_path / "docker" / "tests" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.touch()

        env = {"TEST": "value"}
        executor = DockerComposeExecutor(
            compose_file=compose_file,
            environment=env,
            project_name="test-proj",
            command_executor=mock_command_executor,
        )

        assert executor.compose_file == compose_file
        assert executor.project_name == "test-proj"
        assert executor.repo_root == tmp_path
        assert "TEST" in executor.base_environment

    def test_command_executor_property_uses_provided(
        self,
        executor,
        mock_command_executor,
    ):
        """Test command_executor property uses provided executor."""
        assert executor.command_executor == mock_command_executor

    @patch("aidb_cli.services.CommandExecutor")
    def test_command_executor_property_creates_if_none(
        self,
        mock_executor_class,
        tmp_path,
    ):
        """Test command_executor property creates executor if none provided."""
        compose_file = tmp_path / "docker" / "tests" / "docker-compose.yaml"
        compose_file.parent.mkdir(parents=True)
        compose_file.touch()

        executor = DockerComposeExecutor(
            compose_file=compose_file,
            environment={},
            command_executor=None,
        )

        _ = executor.command_executor
        mock_executor_class.assert_called_once()

    def test_execute_builds_correct_command(self, executor, mock_command_executor):
        """Test execute builds correct docker-compose command."""
        executor.execute(["up", "-d"])

        mock_command_executor.execute.assert_called_once()
        cmd = mock_command_executor.execute.call_args[0][0]

        assert cmd[0] == "docker"
        assert cmd[1] == "compose"
        assert "-f" in cmd
        assert "--project-name" in cmd
        assert "test-project" in cmd
        assert "up" in cmd
        assert "-d" in cmd

    def test_execute_with_single_profile(self, executor, mock_command_executor):
        """Test execute with single profile."""
        executor.execute(["ps"], profile="test")

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "--profile" in cmd
        assert "test" in cmd

    def test_execute_with_multiple_profiles(self, executor, mock_command_executor):
        """Test execute with multiple profiles."""
        executor.execute(["ps"], profile=["test", "dev"])

        cmd = mock_command_executor.execute.call_args[0][0]
        profile_indices = [i for i, x in enumerate(cmd) if x == "--profile"]
        assert len(profile_indices) == 2

    def test_execute_merges_extra_env(self, executor, mock_command_executor):
        """Test execute merges extra environment variables."""
        extra_env = {"EXTRA_VAR": "extra_value"}
        executor.execute(["ps"], extra_env=extra_env)

        call_kwargs = mock_command_executor.execute.call_args[1]
        env = call_kwargs["env"]
        assert env["EXTRA_VAR"] == "extra_value"
        assert env["TEST_VAR"] == "value"

    def test_execute_passes_capture_output(self, executor, mock_command_executor):
        """Test execute passes capture_output parameter."""
        executor.execute(["ps"], capture_output=True)

        call_kwargs = mock_command_executor.execute.call_args[1]
        assert call_kwargs["capture_output"] is True

    def test_execute_streaming_builds_command(self, executor, mock_command_executor):
        """Test execute_streaming builds correct command."""
        executor.execute_streaming(["logs", "-f"])

        mock_command_executor.create_process.assert_called_once()
        cmd = mock_command_executor.create_process.call_args[0][0]

        assert "docker" in cmd
        assert "compose" in cmd
        assert "logs" in cmd

    def test_execute_streaming_with_profile(self, executor, mock_command_executor):
        """Test execute_streaming with profile."""
        executor.execute_streaming(["up"], profile="test")

        cmd = mock_command_executor.create_process.call_args[0][0]
        assert "--profile" in cmd
        assert "test" in cmd

    def test_get_running_services_success(self, executor, mock_command_executor):
        """Test get_running_services returns service list."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="service1\nservice2\nservice3\n",
        )

        services = executor.get_running_services()

        assert services == ["service1", "service2", "service3"]

    def test_get_running_services_handles_error(self, executor, mock_command_executor):
        """Test get_running_services handles errors."""
        mock_command_executor.execute.side_effect = AidbError("error")

        services = executor.get_running_services()

        assert services == []

    def test_get_service_port_success(self, executor, mock_command_executor):
        """Test get_service_port returns port."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="0.0.0.0:8080\n",
        )

        port = executor.get_service_port("web", "8000")

        assert port == "8080"

    def test_get_service_port_handles_error(self, executor, mock_command_executor):
        """Test get_service_port handles errors."""
        mock_command_executor.execute.side_effect = AidbError("error")

        port = executor.get_service_port("web", "8000")

        assert port is None

    def test_build_calls_execute_with_build(self, executor, mock_command_executor):
        """Test build calls execute with build argument."""
        executor.build()

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "build" in cmd

    def test_up_with_detach(self, executor, mock_command_executor):
        """Test up with detach mode."""
        executor.up(detach=True)

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "up" in cmd
        assert "-d" in cmd

    def test_up_without_detach(self, executor, mock_command_executor):
        """Test up without detach mode."""
        executor.up(detach=False)

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "up" in cmd
        assert "-d" not in cmd

    def test_up_with_services(self, executor, mock_command_executor):
        """Test up with specific services."""
        executor.up(services=["web", "db"])

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "web" in cmd
        assert "db" in cmd

    def test_down_basic(self, executor, mock_command_executor):
        """Test down with basic options."""
        executor.down()

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "down" in cmd
        assert "--remove-orphans" in cmd

    def test_down_with_volumes(self, executor, mock_command_executor):
        """Test down with volume removal."""
        executor.down(remove_volumes=True)

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "-v" in cmd

    def test_down_with_timeout(self, executor, mock_command_executor):
        """Test down with timeout."""
        executor.down(timeout=30)

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "--timeout" in cmd
        assert "30" in cmd

    def test_run_service_basic(self, executor, mock_command_executor):
        """Test run_service with basic options."""
        executor.run_service("web")

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "run" in cmd
        assert "--rm" in cmd
        assert "web" in cmd

    def test_run_service_with_command(self, executor, mock_command_executor):
        """Test run_service with custom command."""
        executor.run_service("web", command=["echo", "test"])

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "echo" in cmd
        assert "test" in cmd

    def test_run_service_without_remove(self, executor, mock_command_executor):
        """Test run_service without remove option."""
        executor.run_service("web", remove=False)

        cmd = mock_command_executor.execute.call_args[0][0]
        assert "--rm" not in cmd
