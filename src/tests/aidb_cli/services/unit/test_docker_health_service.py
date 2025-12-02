"""Unit tests for DockerHealthService."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from aidb_cli.services.docker.docker_health_service import DockerHealthService


class TestDockerHealthService:
    """Test the DockerHealthService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create service instance with mocks."""
        return DockerHealthService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            project_name="test-project",
        )

    def test_wait_for_health_success(self, service, mock_command_executor):
        """Test waiting for service to become healthy."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        result = service.wait_for_health("postgres", timeout=5, verbose=False)

        assert result is True
        mock_command_executor.execute.assert_called()

    def test_wait_for_health_timeout(self, service, mock_command_executor):
        """Test timeout when service doesn't become healthy."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="starting\n",
            stderr="",
        )

        result = service.wait_for_health("postgres", timeout=1, verbose=False)

        assert result is False

    def test_wait_for_health_unhealthy(self, service, mock_command_executor):
        """Test when service is unhealthy and not running."""
        # First call returns unhealthy
        # Second call checks if running - returns false
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="unhealthy\n", stderr=""),
            Mock(returncode=0, stdout="false\n", stderr=""),
        ]

        result = service.wait_for_health("postgres", timeout=5, verbose=False)

        assert result is False
        assert mock_command_executor.execute.call_count == 2

    def test_wait_for_health_unhealthy_but_running(
        self,
        service,
        mock_command_executor,
    ):
        """Test when service is unhealthy but still running."""
        # First call returns unhealthy, then starting, then healthy
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="unhealthy\n", stderr=""),
            Mock(returncode=0, stdout="true\n", stderr=""),  # is running check
            Mock(returncode=0, stdout="starting\n", stderr=""),
            Mock(returncode=0, stdout="healthy\n", stderr=""),
        ]

        result = service.wait_for_health("postgres", timeout=10, verbose=False)

        assert result is True

    def test_wait_for_health_container_not_found(
        self,
        service,
        mock_command_executor,
    ):
        """Test when container doesn't exist."""
        mock_command_executor.execute.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: No such container",
        )

        result = service.wait_for_health("nonexistent", timeout=5, verbose=False)

        assert result is False

    def test_wait_for_health_verbose_output(
        self,
        service,
        mock_command_executor,
        capsys,
    ):
        """Test verbose output during health check."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        result = service.wait_for_health("postgres", timeout=5, verbose=True)

        assert result is True
        captured = capsys.readouterr()
        assert "Waiting for" in captured.out
        assert "is healthy" in captured.out

    def test_wait_for_health_custom_container_name(
        self,
        service,
        mock_command_executor,
    ):
        """Test using custom container name."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        result = service.wait_for_health(
            "postgres",
            timeout=5,
            verbose=False,
            container_name="custom-container",
        )

        assert result is True
        # Verify custom container name was used in command
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "custom-container" in call_args

    def test_check_service_health_healthy(self, service, mock_command_executor):
        """Test checking health of a healthy service."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        status = service.check_service_health("postgres")

        assert status == "healthy"

    def test_check_service_health_unhealthy(self, service, mock_command_executor):
        """Test checking health of an unhealthy service."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="unhealthy\n",
            stderr="",
        )

        status = service.check_service_health("postgres")

        assert status == "unhealthy"

    def test_check_service_health_starting(self, service, mock_command_executor):
        """Test checking health of a starting service."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="starting\n",
            stderr="",
        )

        status = service.check_service_health("postgres")

        assert status == "starting"

    def test_check_service_health_none(self, service, mock_command_executor):
        """Test checking health when no health check is configured."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="\n",
            stderr="",
        )

        status = service.check_service_health("postgres")

        assert status == "none"

    def test_check_service_health_not_found(self, service, mock_command_executor):
        """Test checking health of non-existent service."""
        mock_command_executor.execute.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: No such container",
        )

        status = service.check_service_health("nonexistent")

        assert status == "not_found"

    def test_is_container_running_true(self, service, mock_command_executor):
        """Test checking if container is running."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="true\n",
            stderr="",
        )

        result = service.is_container_running("postgres")

        assert result is True

    def test_is_container_running_false(self, service, mock_command_executor):
        """Test checking if container is stopped."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="false\n",
            stderr="",
        )

        result = service.is_container_running("postgres")

        assert result is False

    def test_is_container_running_not_found(self, service, mock_command_executor):
        """Test checking if non-existent container is running."""
        mock_command_executor.execute.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error: No such container",
        )

        result = service.is_container_running("nonexistent")

        assert result is False

    def test_run_health_checks_all_healthy(self, service, mock_command_executor):
        """Test health checks for multiple healthy services."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        results = service.run_health_checks(["postgres", "redis", "api"])

        assert results["postgres"] is True
        assert results["redis"] is True
        assert results["api"] is True
        assert len(results) == 3

    def test_run_health_checks_mixed_health(self, service, mock_command_executor):
        """Test health checks with mixed health statuses."""
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="healthy\n", stderr=""),
            Mock(returncode=0, stdout="unhealthy\n", stderr=""),
            Mock(returncode=0, stdout="healthy\n", stderr=""),
        ]

        results = service.run_health_checks(["postgres", "redis", "api"])

        assert results["postgres"] is True
        assert results["redis"] is False
        assert results["api"] is True

    def test_wait_for_services_all_succeed(self, service, mock_command_executor):
        """Test waiting for multiple services to become healthy."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="healthy\n",
            stderr="",
        )

        results = service.wait_for_services(
            ["postgres", "redis"],
            timeout=10,
            verbose=False,
        )

        assert results["postgres"] is True
        assert results["redis"] is True

    def test_wait_for_services_partial_failure(
        self,
        service,
        mock_command_executor,
    ):
        """Test waiting for services with one failing."""
        # First service succeeds quickly, second times out
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="healthy\n", stderr=""),
            Mock(returncode=0, stdout="starting\n", stderr=""),
        ]

        results = service.wait_for_services(
            ["postgres", "redis"],
            timeout=2,
            verbose=False,
        )

        assert results["postgres"] is True
        assert results["redis"] is False

    def test_wait_for_services_timeout_distribution(
        self,
        service,
        mock_command_executor,
    ):
        """Test that timeout is distributed across services."""
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First 3 calls are for first service (healthy immediately)
            # Then calls for second service (takes time)
            if call_count == 1:
                return Mock(returncode=0, stdout="healthy\n", stderr="")
            return Mock(returncode=0, stdout="starting\n", stderr="")

        mock_command_executor.execute.side_effect = execute_side_effect

        # With 10 second timeout, first service uses minimal time,
        # so second service should get most of the timeout
        results = service.wait_for_services(
            ["postgres", "redis"],
            timeout=3,
            verbose=False,
        )

        assert results["postgres"] is True
        # Second service should timeout
        assert results["redis"] is False

    def test_cleanup_does_nothing(self, service):
        """Test that cleanup method exists but does nothing."""
        # Should not raise any exceptions
        service.cleanup()
