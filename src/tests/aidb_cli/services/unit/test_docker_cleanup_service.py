"""Unit tests for DockerCleanupService."""

from unittest.mock import Mock, patch

import pytest

from aidb.common.errors import AidbError
from aidb_cli.services.docker.docker_cleanup_service import DockerCleanupService


class TestDockerCleanupService:
    """Test the DockerCleanupService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, mock_command_executor):
        """Create a DockerCleanupService instance with mocks."""
        return DockerCleanupService(command_executor=mock_command_executor)

    def test_cleanup_resources_all_success(self, service, mock_command_executor):
        """Test successful cleanup of all resource types."""
        # Setup
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        resources = {
            "containers": [{"ID": "abc123", "Names": "test-container"}],
            "volumes": [{"Name": "test-volume"}],
            "networks": [{"Name": "test-network"}],
            "images": [{"ID": "img123", "Repository": "test", "Tag": "latest"}],
        }

        # Execute
        results = service.cleanup_resources(resources)

        # Assert
        assert len(results["containers"]["success"]) == 1
        assert len(results["volumes"]["success"]) == 1
        assert len(results["networks"]["success"]) == 1
        assert len(results["images"]["success"]) == 1

        assert len(results["containers"]["failed"]) == 0
        assert len(results["volumes"]["failed"]) == 0
        assert len(results["networks"]["failed"]) == 0
        assert len(results["images"]["failed"]) == 0

        # Verify all removal commands were called
        assert (
            mock_command_executor.execute.call_count >= 5
        )  # 2 for container, 1 each for others

    def test_cleanup_resources_mixed_results(self, service, mock_command_executor):
        """Test cleanup with mixed success and failure."""
        # Setup - first call succeeds, second fails
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # container stop
            AidbError("Container removal failed"),  # container rm fails
            Mock(returncode=0, stdout="", stderr=""),  # volume succeeds
        ]

        resources = {
            "containers": [{"ID": "abc123", "Names": "test-container"}],
            "volumes": [{"Name": "test-volume"}],
            "networks": [],
            "images": [],
        }

        # Execute
        results = service.cleanup_resources(resources)

        # Assert
        assert len(results["containers"]["success"]) == 0
        assert len(results["containers"]["failed"]) == 1
        assert "test-container" in results["containers"]["failed"]

        assert len(results["volumes"]["success"]) == 1
        assert "test-volume" in results["volumes"]["success"]

    def test_cleanup_resources_empty(self, service):
        """Test cleanup with empty resources dictionary."""
        # Execute
        results = service.cleanup_resources({})

        # Assert - should return structure with empty lists
        assert len(results["containers"]["success"]) == 0
        assert len(results["containers"]["failed"]) == 0
        assert len(results["volumes"]["success"]) == 0
        assert len(results["volumes"]["failed"]) == 0

    def test_remove_container_success(self, service, mock_command_executor):
        """Test successful container removal."""
        # Setup
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        # Execute
        result = service.remove_container("test-container")

        # Assert
        assert result is True
        assert mock_command_executor.execute.call_count == 2
        # Verify stop command
        stop_call = mock_command_executor.execute.call_args_list[0]
        assert "docker" in stop_call[0][0]
        assert "stop" in stop_call[0][0]
        assert "test-container" in stop_call[0][0]
        # Verify remove command
        rm_call = mock_command_executor.execute.call_args_list[1]
        assert "docker" in rm_call[0][0]
        assert "rm" in rm_call[0][0]
        assert "test-container" in rm_call[0][0]

    def test_remove_container_already_stopped(self, service, mock_command_executor):
        """Test container removal when container is already stopped."""
        # Setup - stop fails (already stopped), but remove succeeds
        mock_command_executor.execute.side_effect = [
            Mock(
                returncode=1,
                stdout="",
                stderr="already stopped",
            ),  # stop fails gracefully
            Mock(returncode=0, stdout="", stderr=""),  # rm succeeds
        ]

        # Execute
        result = service.remove_container("test-container")

        # Assert
        assert result is True
        assert mock_command_executor.execute.call_count == 2

    def test_remove_container_failure(self, service, mock_command_executor):
        """Test container removal failure."""
        # Setup
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # stop succeeds
            AidbError("Container removal failed"),  # rm fails
        ]

        # Execute
        result = service.remove_container("test-container")

        # Assert
        assert result is False

    def test_remove_volume_success(self, service, mock_command_executor):
        """Test successful volume removal."""
        # Setup
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        # Execute
        result = service.remove_volume("test-volume")

        # Assert
        assert result is True
        mock_command_executor.execute.assert_called_once()
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "volume" in call_args
        assert "rm" in call_args
        assert "test-volume" in call_args

    def test_remove_volume_failure(self, service, mock_command_executor):
        """Test volume removal failure."""
        # Setup
        mock_command_executor.execute.side_effect = AidbError("Volume removal failed")

        # Execute
        result = service.remove_volume("test-volume")

        # Assert
        assert result is False

    def test_remove_network_success(self, service, mock_command_executor):
        """Test successful network removal."""
        # Setup
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        # Execute
        result = service.remove_network("test-network")

        # Assert
        assert result is True
        mock_command_executor.execute.assert_called_once()
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "network" in call_args
        assert "rm" in call_args
        assert "test-network" in call_args

    def test_remove_network_failure(self, service, mock_command_executor):
        """Test network removal failure."""
        # Setup
        mock_command_executor.execute.side_effect = AidbError("Network removal failed")

        # Execute
        result = service.remove_network("test-network")

        # Assert
        assert result is False

    def test_remove_image_success(self, service, mock_command_executor):
        """Test successful image removal."""
        # Setup
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        # Execute
        result = service.remove_image("test-image:latest")

        # Assert
        assert result is True
        mock_command_executor.execute.assert_called_once()
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "docker" in call_args
        assert "rmi" in call_args
        assert "test-image:latest" in call_args

    def test_remove_image_failure(self, service, mock_command_executor):
        """Test image removal failure."""
        # Setup
        mock_command_executor.execute.side_effect = AidbError("Image removal failed")

        # Execute
        result = service.remove_image("test-image")

        # Assert
        assert result is False

    def test_display_resources_all_types(self, service, capsys):
        """Test displaying resources with all types present."""
        # Setup
        resources = {
            "containers": [
                {"ID": "abc123", "Names": "test-container", "Status": "running"},
            ],
            "volumes": [{"Name": "test-volume"}],
            "networks": [{"Name": "test-network", "Driver": "bridge"}],
            "images": [
                {
                    "ID": "img123",
                    "Repository": "test",
                    "Tag": "latest",
                    "Size": "100MB",
                },
            ],
        }

        # Execute
        service.display_resources(resources)

        # Capture output and verify key information is displayed
        captured = capsys.readouterr()
        assert "test-container" in captured.out
        assert "test-volume" in captured.out
        assert "test-network" in captured.out
        assert "test:latest" in captured.out

    def test_display_resources_empty_types(self, service, capsys):
        """Test displaying resources with some empty types."""
        # Setup
        resources = {
            "containers": [
                {"ID": "abc123", "Names": "test-container", "Status": "running"},
            ],
            "volumes": [],
            "networks": [],
            "images": [],
        }

        # Execute
        service.display_resources(resources)

        # Capture output and verify container is displayed
        captured = capsys.readouterr()
        assert "test-container" in captured.out

    def test_display_cleanup_results_success_only(self, service, capsys):
        """Test displaying cleanup results with only successes."""
        # Setup
        results = {
            "containers": {"success": ["container1", "container2"], "failed": []},
            "volumes": {"success": ["volume1"], "failed": []},
            "networks": {"success": [], "failed": []},
            "images": {"success": [], "failed": []},
        }

        # Execute
        service.display_cleanup_results(results)

        # Assert - verify output contains success messages
        captured = capsys.readouterr()
        assert "container" in captured.out.lower()
        assert "volume" in captured.out.lower()
        assert "removed" in captured.out.lower()

    def test_display_cleanup_results_with_failures(self, service, capsys):
        """Test displaying cleanup results with some failures."""
        # Setup
        results = {
            "containers": {
                "success": ["container1"],
                "failed": ["container2", "container3"],
            },
            "volumes": {"success": [], "failed": ["volume1"]},
            "networks": {"success": [], "failed": []},
            "images": {"success": [], "failed": []},
        }

        # Execute
        service.display_cleanup_results(results)

        # Assert - verify output contains failure messages (errors go to stderr)
        captured = capsys.readouterr()
        # Success messages go to stdout
        assert "removed" in captured.out.lower()
        # Failure messages go to stderr
        assert "failed" in captured.err.lower()
        assert "container2" in captured.err
        assert "container3" in captured.err
        assert "volume1" in captured.err
