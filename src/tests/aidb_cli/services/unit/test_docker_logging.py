"""Unit tests for Docker container log collection functionality."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from aidb_cli.services.docker.docker_logging_service import DockerLoggingService


class TestDockerLoggingService:
    """Test the DockerLoggingService container log collection."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def logging_service(self, tmp_path, mock_command_executor):
        """Create a DockerLoggingService instance with mocks."""
        return DockerLoggingService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_collect_test_container_logs_no_containers(
        self,
        logging_service,
        mock_command_executor,
    ):
        """Test log collection when no containers exist."""
        # Mock no containers found
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=None,
        )

        results = logging_service.collect_test_container_logs()

        assert results == {}
        # Should call docker ps to list containers
        assert mock_command_executor.execute.called

    def test_collect_test_container_logs_with_containers(
        self,
        logging_service,
        mock_command_executor,
        tmp_path,
    ):
        """Test successful log collection from containers."""
        # Mock container list responses
        mock_command_executor.execute.side_effect = [
            # First call: list test containers
            Mock(returncode=0, stdout="aidb-test-runner\n", stderr=None),
            # Second call: list mcp containers
            Mock(returncode=0, stdout="aidb-mcp-test\n", stderr=None),
            # Third call: list adapter containers
            Mock(returncode=0, stdout="", stderr=None),
            # Fourth call: get logs from aidb-test-runner
            Mock(returncode=0, stdout="Test log output 1", stderr=None),
            # Fifth call: get logs from aidb-mcp-test
            Mock(returncode=0, stdout="Test log output 2", stderr=None),
        ]

        # Use a specific output file
        output_file = tmp_path / "test.log"

        results = logging_service.collect_test_container_logs(
            output_file=output_file,
        )

        # Check results
        assert results == {
            "aidb-test-runner": True,
            "aidb-mcp-test": True,
        }

        # Check that logs were written
        assert output_file.exists()
        log_content = output_file.read_text()
        assert "aidb-test-runner" in log_content
        assert "Test log output 1" in log_content
        assert "aidb-mcp-test" in log_content
        assert "Test log output 2" in log_content
        assert "CONTAINER LOGS:" in log_content
        assert "END CONTAINER LOGS:" in log_content

    def test_collect_test_container_logs_with_failure(
        self,
        logging_service,
        mock_command_executor,
        tmp_path,
    ):
        """Test log collection with some container failures."""
        # Mock container list and log fetch
        mock_command_executor.execute.side_effect = [
            # List test containers
            Mock(returncode=0, stdout="aidb-test-runner\n", stderr=None),
            # List mcp containers
            Mock(returncode=0, stdout="", stderr=None),
            # List adapter containers
            Mock(returncode=0, stdout="", stderr=None),
            # Get logs from aidb-test-runner (fails)
            Mock(returncode=1, stdout="", stderr="Container not found"),
        ]

        output_file = tmp_path / "test.log"

        results = logging_service.collect_test_container_logs(
            output_file=output_file,
        )

        assert results == {"aidb-test-runner": False}

    def test_collect_test_container_logs_truncation(
        self,
        logging_service,
        mock_command_executor,
        tmp_path,
    ):
        """Test that large logs are truncated."""
        # Create a large log output (more than 10MB)
        large_log = "x" * (11 * 1024 * 1024)  # 11MB

        mock_command_executor.execute.side_effect = [
            # List test containers
            Mock(returncode=0, stdout="aidb-test-runner\n", stderr=None),
            # List mcp containers
            Mock(returncode=0, stdout="", stderr=None),
            # List adapter containers
            Mock(returncode=0, stdout="", stderr=None),
            # Get logs (large)
            Mock(returncode=0, stdout=large_log, stderr=None),
        ]

        output_file = tmp_path / "test.log"

        results = logging_service.collect_test_container_logs(
            output_file=output_file,
        )

        assert results == {"aidb-test-runner": True}

        # Check that logs were truncated
        log_content = output_file.read_text()
        assert "[TRUNCATED" in log_content
        # Should be less than original
        assert len(log_content.encode("utf-8")) < len(large_log.encode("utf-8"))

    def test_get_test_containers_with_filter(
        self,
        logging_service,
        mock_command_executor,
    ):
        """Test container listing with custom filter."""
        mock_command_executor.execute.side_effect = [
            # Only test component
            Mock(returncode=0, stdout="", stderr=None),
            # MCP component
            Mock(returncode=0, stdout="aidb-mcp-test\n", stderr=None),
            # Adapter component
            Mock(returncode=0, stdout="", stderr=None),
        ]

        container_filter = {
            "label": ["com.aidb.managed=true", "com.aidb.component=mcp"],
        }

        containers = logging_service._get_test_containers(container_filter)

        assert containers == ["aidb-mcp-test"]

    def test_write_container_logs_to_file(self, logging_service, tmp_path):
        """Test writing formatted logs to file."""
        output_file = tmp_path / "test.log"
        container_name = "test-container"
        logs = "Sample log content\nLine 2\nLine 3"

        logging_service._write_container_logs_to_file(
            container_name,
            logs,
            output_file,
        )

        assert output_file.exists()
        content = output_file.read_text()

        # Check formatting
        assert f"CONTAINER LOGS: {container_name}" in content
        assert "Sample log content" in content
        assert "Line 2" in content
        assert "Line 3" in content
        assert f"END CONTAINER LOGS: {container_name}" in content
        assert "Collected at:" in content

    @patch("aidb_cli.services.docker.docker_logging_service.get_log_file_path")
    def test_default_output_file(
        self,
        mock_get_log_file_path,
        logging_service,
        mock_command_executor,
    ):
        """Test that default output file uses test-container-output.log."""
        mock_get_log_file_path.return_value = (
            "/home/user/.aidb/log/test-container-output.log"
        )

        # Mock no containers
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=None,
        )

        # Call without specifying output_file
        logging_service.collect_test_container_logs()

        # Check that get_log_file_path was called with "test-container-output"
        mock_get_log_file_path.assert_called_once_with("test-container-output")
