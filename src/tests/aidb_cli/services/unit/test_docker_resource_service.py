"""Unit tests for DockerResourceService."""

import json
from unittest.mock import Mock

import pytest

from aidb.common.errors import AidbError
from aidb_cli.services.docker.docker_resource_service import DockerResourceService


class TestDockerResourceService:
    """Test the DockerResourceService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, mock_command_executor):
        """Create a DockerResourceService instance."""
        return DockerResourceService(command_executor=mock_command_executor)

    def test_service_initialization(self, mock_command_executor):
        """Test service initialization."""
        service = DockerResourceService(command_executor=mock_command_executor)

        assert service.command_executor == mock_command_executor
        assert service.project_filter == "com.aidb.project=aidb"

    def test_find_aidb_resources_all(self, service, mock_command_executor):
        """Test finding all AIDB resources."""
        # Mock responses for each resource type
        mock_command_executor.execute.side_effect = [
            Mock(stdout='{"ID": "c1"}\n{"ID": "c2"}', returncode=0),  # containers
            Mock(stdout='{"Name": "n1"}', returncode=0),  # networks
            Mock(stdout='{"ID": "i1"}', returncode=0),  # images
            Mock(stdout='{"Name": "v1"}', returncode=0),  # volumes
        ]

        resources = service.find_aidb_resources(all_resources=True)

        assert len(resources["containers"]) == 2
        assert len(resources["networks"]) == 1
        assert len(resources["images"]) == 1
        assert len(resources["volumes"]) == 1

    def test_find_aidb_resources_volumes_only(self, service, mock_command_executor):
        """Test finding only volumes."""
        mock_command_executor.execute.return_value = Mock(
            stdout='{"Name": "v1"}\n{"Name": "v2"}',
            returncode=0,
        )

        resources = service.find_aidb_resources(volumes_only=True)

        assert len(resources["containers"]) == 0
        assert len(resources["volumes"]) == 2
        assert len(resources["networks"]) == 0
        assert len(resources["images"]) == 0

    def test_find_aidb_resources_default(self, service, mock_command_executor):
        """Test finding resources with default settings."""
        mock_command_executor.execute.side_effect = [
            Mock(stdout='{"ID": "c1"}', returncode=0),  # containers
            Mock(stdout='{"Name": "v1"}', returncode=0),  # volumes
        ]

        resources = service.find_aidb_resources()

        assert len(resources["containers"]) == 1
        assert len(resources["volumes"]) == 1
        assert len(resources["networks"]) == 0
        assert len(resources["images"]) == 0

    def test_find_aidb_resources_graceful_error(self, service, mock_command_executor):
        """Test finding resources handles errors gracefully."""
        # Individual methods catch AidbError and return empty lists
        mock_command_executor.execute.side_effect = AidbError("Docker not available")

        resources = service.find_aidb_resources()

        # Should return empty resources when Docker is unavailable
        assert len(resources["containers"]) == 0
        assert len(resources["volumes"]) == 0
        assert len(resources["networks"]) == 0
        assert len(resources["images"]) == 0

    def test_find_containers_success(self, service, mock_command_executor):
        """Test finding containers successfully."""
        container_json = json.dumps({"ID": "abc123", "Names": "test-container"})
        mock_command_executor.execute.return_value = Mock(
            stdout=f"{container_json}\n",
            returncode=0,
        )

        containers = service.find_containers()

        assert len(containers) == 1
        assert containers[0]["ID"] == "abc123"
        assert containers[0]["Names"] == "test-container"

    def test_find_containers_orphaned_only(self, service, mock_command_executor):
        """Test finding only orphaned (exited) containers."""
        container_json = json.dumps({"ID": "abc123", "Status": "exited"})
        mock_command_executor.execute.return_value = Mock(
            stdout=f"{container_json}\n",
            returncode=0,
        )

        containers = service.find_containers(orphaned_only=True)

        assert len(containers) == 1
        # Verify the command included the exited filter
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "--filter" in call_args
        assert "status=exited" in call_args

    def test_find_containers_empty(self, service, mock_command_executor):
        """Test finding containers when none exist."""
        mock_command_executor.execute.return_value = Mock(stdout="", returncode=0)

        containers = service.find_containers()

        assert len(containers) == 0

    def test_find_containers_docker_error(self, service, mock_command_executor):
        """Test finding containers when Docker is unavailable."""
        mock_command_executor.execute.side_effect = AidbError("Docker not found")

        containers = service.find_containers()

        assert len(containers) == 0

    def test_find_volumes_success(self, service, mock_command_executor):
        """Test finding volumes successfully."""
        volume_json = json.dumps({"Name": "aidb_test_volume", "Driver": "local"})
        mock_command_executor.execute.return_value = Mock(
            stdout=f"{volume_json}\n",
            returncode=0,
        )

        volumes = service.find_volumes()

        assert len(volumes) == 1
        assert volumes[0]["Name"] == "aidb_test_volume"

    def test_find_volumes_orphaned_only(self, service, mock_command_executor):
        """Test finding only orphaned volumes."""
        volume_json = json.dumps({"Name": "aidb_orphan_volume"})
        mock_command_executor.execute.side_effect = [
            Mock(stdout=f"{volume_json}\n", returncode=0),  # find volumes
            Mock(stdout="", returncode=0),  # check if in use
        ]

        volumes = service.find_volumes(orphaned_only=True)

        assert len(volumes) == 1
        assert volumes[0]["Name"] == "aidb_orphan_volume"

    def test_find_volumes_skip_in_use(self, service, mock_command_executor):
        """Test finding orphaned volumes skips volumes in use."""
        volume_json = json.dumps({"Name": "aidb_in_use_volume"})
        mock_command_executor.execute.side_effect = [
            Mock(stdout=f"{volume_json}\n", returncode=0),  # find volumes
            Mock(stdout="aidb_in_use_volume\n", returncode=0),  # check if in use
        ]

        volumes = service.find_volumes(orphaned_only=True)

        assert len(volumes) == 0

    def test_find_volumes_empty(self, service, mock_command_executor):
        """Test finding volumes when none exist."""
        mock_command_executor.execute.return_value = Mock(stdout="", returncode=0)

        volumes = service.find_volumes()

        assert len(volumes) == 0

    def test_find_volumes_docker_error(self, service, mock_command_executor):
        """Test finding volumes when Docker is unavailable."""
        mock_command_executor.execute.side_effect = AidbError("Docker not found")

        volumes = service.find_volumes()

        assert len(volumes) == 0

    def test_find_networks_success(self, service, mock_command_executor):
        """Test finding networks successfully."""
        network_json = json.dumps({"ID": "net123", "Name": "aidb_network"})
        mock_command_executor.execute.return_value = Mock(
            stdout=f"{network_json}\n",
            returncode=0,
        )

        networks = service.find_networks()

        assert len(networks) == 1
        assert networks[0]["ID"] == "net123"
        assert networks[0]["Name"] == "aidb_network"

    def test_find_networks_empty(self, service, mock_command_executor):
        """Test finding networks when none exist."""
        mock_command_executor.execute.return_value = Mock(stdout="", returncode=0)

        networks = service.find_networks()

        assert len(networks) == 0

    def test_find_networks_docker_error(self, service, mock_command_executor):
        """Test finding networks when Docker is unavailable."""
        mock_command_executor.execute.side_effect = AidbError("Docker not found")

        networks = service.find_networks()

        assert len(networks) == 0

    def test_find_images_success(self, service, mock_command_executor):
        """Test finding images successfully."""
        image_json = json.dumps({"ID": "img123", "Repository": "aidb/test"})
        mock_command_executor.execute.return_value = Mock(
            stdout=f"{image_json}\n",
            returncode=0,
        )

        images = service.find_images()

        assert len(images) == 1
        assert images[0]["ID"] == "img123"
        assert images[0]["Repository"] == "aidb/test"

    def test_find_images_empty(self, service, mock_command_executor):
        """Test finding images when none exist."""
        mock_command_executor.execute.return_value = Mock(stdout="", returncode=0)

        images = service.find_images()

        assert len(images) == 0

    def test_find_images_docker_error(self, service, mock_command_executor):
        """Test finding images when Docker is unavailable."""
        mock_command_executor.execute.side_effect = AidbError("Docker not found")

        images = service.find_images()

        assert len(images) == 0

    def test_is_volume_in_use_true(self, service, mock_command_executor):
        """Test checking if volume is in use returns True."""
        mock_command_executor.execute.return_value = Mock(
            stdout="aidb_volume\n",
            returncode=0,
        )

        result = service.is_volume_in_use("aidb_volume")

        assert result is True
        call_args = mock_command_executor.execute.call_args[0][0]
        assert "volume=aidb_volume" in call_args

    def test_is_volume_in_use_false(self, service, mock_command_executor):
        """Test checking if volume is in use returns False."""
        mock_command_executor.execute.return_value = Mock(stdout="", returncode=0)

        result = service.is_volume_in_use("aidb_orphan")

        assert result is False

    def test_is_volume_in_use_error(self, service, mock_command_executor):
        """Test checking volume in use when Docker error occurs."""
        mock_command_executor.execute.side_effect = AidbError("Docker error")

        result = service.is_volume_in_use("aidb_volume")

        assert result is False

    def test_count_resources(self, service):
        """Test counting resources."""
        resources: dict[str, list[dict[str, str]]] = {
            "containers": [{"ID": "c1"}, {"ID": "c2"}],
            "volumes": [{"Name": "v1"}],
            "networks": [],
            "images": [{"ID": "i1"}, {"ID": "i2"}, {"ID": "i3"}],
        }

        count = service.count_resources(resources)

        assert count == 6

    def test_count_resources_empty(self, service):
        """Test counting resources when all are empty."""
        resources: dict[str, list[dict[str, str]]] = {
            "containers": [],
            "volumes": [],
            "networks": [],
            "images": [],
        }

        count = service.count_resources(resources)

        assert count == 0

    def test_initialization_without_command_executor(self):
        """Test initialization without explicit command executor."""
        service = DockerResourceService()
        assert service.command_executor is not None
        assert service.project_filter == "com.aidb.project=aidb"
