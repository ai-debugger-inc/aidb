"""Tests for refactored BuildManager with orchestrator pattern."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.managers.build import BuildManager
from aidb_cli.services.adapter import AdapterService
from aidb_cli.services.build import DownloadService
from aidb_cli.services.docker import DockerContextService


class TestBuildManager:
    """Test the refactored BuildManager."""

    def test_build_manager_initialization(self, tmp_path):
        """Test that BuildManager initializes correctly."""
        manager = BuildManager(repo_root=tmp_path)

        assert manager.repo_root == tmp_path
        assert manager.versions_file == tmp_path / "versions.json"
        assert manager.user_cache_dir.exists()
        assert manager.repo_cache_dir.exists()

    def test_service_registration(self, tmp_path):
        """Test that services are registered correctly."""
        manager = BuildManager(repo_root=tmp_path)

        # Check that services are registered
        assert manager.has_service(AdapterService)
        assert manager.has_service(DownloadService)
        assert manager.has_service(DockerContextService)

        # Check that services can be retrieved
        adapter_service = manager.get_service(AdapterService)
        assert isinstance(adapter_service, AdapterService)

    def test_delegation_to_adapter_service(self, tmp_path):
        """Test that methods delegate to AdapterService correctly."""
        manager = BuildManager(repo_root=tmp_path)

        # Mock the adapter service
        with patch.object(manager, "get_service") as mock_get_service:
            mock_adapter_service = Mock()
            mock_adapter_service.get_supported_languages.return_value = [
                "python",
                "java",
            ]
            mock_adapter_service.find_adapter_source.return_value = tmp_path / "adapter"
            mock_adapter_service.check_adapters_built.return_value = (
                ["python"],
                ["java"],
            )

            mock_get_service.return_value = mock_adapter_service

            # Test delegated methods
            languages = manager.get_supported_languages()
            assert languages == ["python", "java"]
            mock_adapter_service.get_supported_languages.assert_called_once()

            path = manager.find_adapter_source("python", verbose=True)
            assert path == tmp_path / "adapter"
            mock_adapter_service.find_adapter_source.assert_called_once_with(
                "python",
                False,
                True,
            )

            built, missing = manager.check_adapters_built(
                ["python", "java"],
                verbose=True,
            )
            assert built == ["python"]
            assert missing == ["java"]

    def test_delegation_to_download_service(self, tmp_path):
        """Test that methods delegate to DownloadService correctly."""
        manager = BuildManager(repo_root=tmp_path)

        with patch.object(manager, "get_service") as mock_get_service:
            mock_download_service = Mock()
            mock_download_service.download_all_adapters.return_value = True

            def get_service_side_effect(service_class):
                if service_class == DownloadService:
                    return mock_download_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            result = manager.download_all_adapters(["python"], force=True, verbose=True)
            assert result is True
            mock_download_service.download_all_adapters.assert_called_once_with(
                ["python"],
                True,
                True,
            )

    def test_delegation_to_docker_context_service(self, tmp_path):
        """Test that methods delegate to DockerContextService correctly."""
        manager = BuildManager(repo_root=tmp_path)

        with patch.object(manager, "get_service") as mock_get_service:
            mock_docker_service = Mock()
            mock_docker_service.get_build_args.return_value = {"VERSION": "1.0.0"}
            mock_docker_service.prepare_docker_context.return_value = (
                tmp_path / "context"
            )

            def get_service_side_effect(service_class):
                if service_class == DockerContextService:
                    return mock_docker_service
                return Mock()

            mock_get_service.side_effect = get_service_side_effect

            build_args = manager.get_build_args()
            assert build_args == {"VERSION": "1.0.0"}
            mock_docker_service.get_build_args.assert_called_once()

            context = manager.prepare_docker_context(verbose=True)
            assert context == tmp_path / "context"
            mock_docker_service.prepare_docker_context.assert_called_once_with(
                True,
                True,
                True,
            )

    def test_build_adapters_download_method(self, tmp_path):
        """Test build_adapters with download method."""
        manager = BuildManager(repo_root=tmp_path)

        with patch.object(manager, "_build_with_download") as mock_build:
            mock_build.return_value = True

            result = manager.build_adapters(["python"], method="download", verbose=True)
            assert result is True
            mock_build.assert_called_once_with(["python"], True)

    def test_build_adapters_local_method(self, tmp_path):
        """Test build_adapters with local method."""
        manager = BuildManager(repo_root=tmp_path)

        with patch.object(manager, "_build_locally") as mock_build:
            mock_build.return_value = True

            result = manager.build_adapters(["python"], method="local", verbose=True)
            assert result is True
            mock_build.assert_called_once_with(["python"], True)

    def test_singleton_pattern(self, tmp_path):
        """Test that BuildManager follows singleton pattern."""
        manager1 = BuildManager(repo_root=tmp_path)
        manager2 = BuildManager(repo_root=tmp_path)

        assert manager1 is manager2

    def test_cleanup_services_on_reset(self, tmp_path):
        """Test that services are cleaned up on reset."""
        manager = BuildManager(repo_root=tmp_path)

        # Get a service to ensure it's created
        manager.get_service(AdapterService)

        # Reset the manager
        BuildManager.reset()

        # Create new instance
        new_manager = BuildManager(repo_root=tmp_path)

        # Should be a different instance after reset
        assert new_manager is not manager

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton after each test."""
        yield
        BuildManager.reset()
