"""Unit tests for DockerCleanupManager."""

from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from aidb_cli.managers.docker.docker_cleanup_manager import DockerCleanupManager


class TestDockerCleanupManager:
    """Test the DockerCleanupManager."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def manager(self, tmp_path, mock_command_executor):
        """Create a DockerCleanupManager instance."""
        return DockerCleanupManager(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_manager_initialization(self, tmp_path, mock_command_executor):
        """Test manager initialization."""
        manager = DockerCleanupManager(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert manager.repo_root == tmp_path
        assert manager.command_executor == mock_command_executor
        assert manager._resource_service is None
        assert manager._cleanup_service is None

    def test_resource_service_lazy_initialization(self, manager):
        """Test resource service is lazily initialized."""
        assert manager._resource_service is None

        service = manager.resource_service

        assert service is not None
        assert manager._resource_service is service

    def test_resource_service_caching(self, manager):
        """Test resource service is cached after first access."""
        service1 = manager.resource_service
        service2 = manager.resource_service

        assert service1 is service2

    def test_cleanup_service_lazy_initialization(self, manager):
        """Test cleanup service is lazily initialized."""
        assert manager._cleanup_service is None

        service = manager.cleanup_service

        assert service is not None
        assert manager._cleanup_service is service

    def test_cleanup_service_caching(self, manager):
        """Test cleanup service is cached after first access."""
        service1 = manager.cleanup_service
        service2 = manager.cleanup_service

        assert service1 is service2

    def test_find_aidb_resources_default(self, manager):
        """Test finding AIDB resources with default options."""
        mock_resources = {
            "containers": [{"id": "abc123"}],
            "volumes": [{"name": "vol1"}],
        }

        mock_service = Mock()
        mock_service.find_aidb_resources.return_value = mock_resources

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.find_aidb_resources()

            assert result == mock_resources
            mock_service.find_aidb_resources.assert_called_once_with(
                all_resources=False,
                volumes_only=False,
                orphaned_only=False,
            )

    def test_find_aidb_resources_all(self, manager):
        """Test finding all AIDB resources."""
        mock_resources = {
            "containers": [{"id": "abc123"}],
            "volumes": [{"name": "vol1"}],
            "networks": [{"id": "net1"}],
            "images": [{"id": "img1"}],
        }

        mock_service = Mock()
        mock_service.find_aidb_resources.return_value = mock_resources

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.find_aidb_resources(all_resources=True)

            assert result == mock_resources
            mock_service.find_aidb_resources.assert_called_once_with(
                all_resources=True,
                volumes_only=False,
                orphaned_only=False,
            )

    def test_find_aidb_resources_volumes_only(self, manager):
        """Test finding only volumes."""
        mock_resources = {
            "volumes": [{"name": "vol1"}, {"name": "vol2"}],
        }

        mock_service = Mock()
        mock_service.find_aidb_resources.return_value = mock_resources

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.find_aidb_resources(volumes_only=True)

            assert result == mock_resources
            mock_service.find_aidb_resources.assert_called_once_with(
                all_resources=False,
                volumes_only=True,
                orphaned_only=False,
            )

    def test_find_aidb_resources_orphaned_only(self, manager):
        """Test finding only orphaned resources."""
        mock_resources = {
            "volumes": [{"name": "orphan_vol"}],
        }

        mock_service = Mock()
        mock_service.find_aidb_resources.return_value = mock_resources

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.find_aidb_resources(orphaned_only=True)

            assert result == mock_resources
            mock_service.find_aidb_resources.assert_called_once_with(
                all_resources=False,
                volumes_only=False,
                orphaned_only=True,
            )

    def test_cleanup_resources(self, manager):
        """Test cleaning up resources."""
        resources = {
            "containers": [{"id": "abc123"}],
            "volumes": [{"name": "vol1"}],
        }
        cleanup_results = {
            "containers": {"success": ["abc123"], "failed": []},
            "volumes": {"success": ["vol1"], "failed": []},
        }

        mock_service = Mock()
        mock_service.cleanup_resources.return_value = cleanup_results

        with patch.object(
            type(manager),
            "cleanup_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.cleanup_resources(resources)

            assert result == cleanup_results
            mock_service.cleanup_resources.assert_called_once_with(resources)

    def test_cleanup_resources_with_failures(self, manager):
        """Test cleanup with some failures."""
        resources = {
            "containers": [{"id": "abc123"}, {"id": "def456"}],
            "volumes": [{"name": "vol1"}],
        }
        cleanup_results = {
            "containers": {"success": ["abc123"], "failed": ["def456"]},
            "volumes": {"success": ["vol1"], "failed": []},
        }

        mock_service = Mock()
        mock_service.cleanup_resources.return_value = cleanup_results

        with patch.object(
            type(manager),
            "cleanup_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.cleanup_resources(resources)

            assert result == cleanup_results
            assert len(result["containers"]["failed"]) == 1

    def test_display_resources(self, manager):
        """Test displaying resources."""
        resources = {
            "containers": [{"id": "abc123", "name": "container1"}],
            "volumes": [{"name": "vol1"}],
        }

        mock_service = Mock()

        with patch.object(
            type(manager),
            "cleanup_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            manager.display_resources(resources)

            mock_service.display_resources.assert_called_once_with(resources)

    def test_display_cleanup_results(self, manager):
        """Test displaying cleanup results."""
        results = {
            "containers": {"success": ["abc123"], "failed": []},
            "volumes": {"success": ["vol1"], "failed": []},
        }

        mock_service = Mock()

        with patch.object(
            type(manager),
            "cleanup_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            manager.display_cleanup_results(results)

            mock_service.display_cleanup_results.assert_called_once_with(results)

    def test_count_resources(self, manager):
        """Test counting total resources."""
        resources = {
            "containers": [{"id": "abc123"}, {"id": "def456"}],
            "volumes": [{"name": "vol1"}],
            "networks": [{"id": "net1"}, {"id": "net2"}, {"id": "net3"}],
        }

        mock_service = Mock()
        mock_service.count_resources.return_value = 6

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.count_resources(resources)

            assert result == 6
            mock_service.count_resources.assert_called_once_with(resources)

    def test_count_resources_empty(self, manager):
        """Test counting resources when none exist."""
        resources: dict[str, list[dict[str, str]]] = {}

        mock_service = Mock()
        mock_service.count_resources.return_value = 0

        with patch.object(
            type(manager),
            "resource_service",
            new_callable=PropertyMock,
            return_value=mock_service,
        ):
            result = manager.count_resources(resources)

            assert result == 0
