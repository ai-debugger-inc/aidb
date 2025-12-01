"""Unit tests for AdapterService facade.

Note: This tests the facade pattern delegation. Individual services
(AdapterDiscoveryService, AdapterBuildService, AdapterInstallService)
should have their own dedicated test files.
"""

from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest

from aidb_cli.services.adapter.adapter_service import AdapterService


class TestAdapterServiceFacade:
    """Test the AdapterService facade delegation pattern."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create an AdapterService instance."""
        return AdapterService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization creates facade with no services loaded."""
        service = AdapterService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.repo_root == tmp_path
        assert service.command_executor == mock_command_executor
        assert service._discovery_service is None
        assert service._build_service is None
        assert service._install_service is None

    def test_discovery_service_lazy_initialization(self, service):
        """Test discovery service is lazily initialized."""
        assert service._discovery_service is None
        discovery = service.discovery
        assert discovery is not None
        assert service._discovery_service is not None
        # Accessing again returns same instance
        assert service.discovery is discovery

    def test_build_service_lazy_initialization(self, service):
        """Test build service is lazily initialized."""
        assert service._build_service is None
        build = service.build
        assert build is not None
        assert service._build_service is not None
        # Accessing again returns same instance
        assert service.build is build

    def test_install_service_lazy_initialization(self, service):
        """Test install service is lazily initialized."""
        assert service._install_service is None
        install = service.install
        assert install is not None
        assert service._install_service is not None
        # Accessing again returns same instance
        assert service.install is install

    @patch("aidb_cli.services.adapter.adapter_service.AdapterDiscoveryService")
    def test_get_supported_languages_delegates(
        self,
        mock_discovery_class,
        service,
    ):
        """Test get_supported_languages delegates to discovery service."""
        mock_discovery = Mock()
        mock_discovery.get_supported_languages.return_value = [
            "python",
            "javascript",
            "java",
        ]
        mock_discovery_class.return_value = mock_discovery

        languages = service.get_supported_languages()

        assert languages == ["python", "javascript", "java"]
        mock_discovery.get_supported_languages.assert_called_once()

    @patch("aidb_cli.services.adapter.adapter_service.AdapterDiscoveryService")
    def test_find_adapter_source_delegates(
        self,
        mock_discovery_class,
        service,
        tmp_path,
    ):
        """Test find_adapter_source delegates to discovery service."""
        mock_discovery = Mock()
        expected_path = tmp_path / "python"
        mock_discovery.find_adapter_source.return_value = expected_path
        mock_discovery_class.return_value = mock_discovery

        result = service.find_adapter_source("python", check_built=True, verbose=True)

        assert result == expected_path
        mock_discovery.find_adapter_source.assert_called_once_with(
            "python",
            True,
            True,
        )

    @patch("aidb_cli.services.adapter.adapter_service.AdapterDiscoveryService")
    def test_find_all_adapters_delegates(
        self,
        mock_discovery_class,
        service,
        tmp_path,
    ):
        """Test find_all_adapters delegates to discovery service."""
        mock_discovery = Mock()
        expected_adapters = {"python": tmp_path / "python", "java": None}
        mock_discovery.find_all_adapters.return_value = expected_adapters
        mock_discovery_class.return_value = mock_discovery

        result = service.find_all_adapters(verbose=True)

        assert result == expected_adapters
        mock_discovery.find_all_adapters.assert_called_once_with(True)

    @patch("aidb_cli.services.adapter.adapter_service.AdapterDiscoveryService")
    def test_check_adapters_built_delegates(
        self,
        mock_discovery_class,
        service,
    ):
        """Test check_adapters_built delegates to discovery service."""
        mock_discovery = Mock()
        mock_discovery.check_adapters_built.return_value = (["python"], ["java"])
        mock_discovery_class.return_value = mock_discovery

        built, missing = service.check_adapters_built(["python", "java"], verbose=True)

        assert built == ["python"]
        assert missing == ["java"]
        mock_discovery.check_adapters_built.assert_called_once_with(
            ["python", "java"],
            True,
        )

    @patch("aidb_cli.services.adapter.adapter_service.AdapterBuildService")
    def test_build_locally_delegates(
        self,
        mock_build_class,
        service,
    ):
        """Test build_locally delegates to build service."""
        mock_build = Mock()
        mock_build.build_locally.return_value = True
        mock_build_class.return_value = mock_build

        result = service.build_locally(["python"], verbose=True)

        assert result is True
        mock_build.build_locally.assert_called_once_with(["python"], True, ANY)

    @patch("aidb_cli.services.adapter.adapter_service.AdapterInstallService")
    def test_install_adapters_delegates(
        self,
        mock_install_class,
        service,
    ):
        """Test install_adapters delegates to install service."""
        mock_install = Mock()
        mock_install.install_adapters.return_value = True
        mock_install_class.return_value = mock_install

        result = service.install_adapters(["python"], verbose=True)

        assert result is True
        mock_install.install_adapters.assert_called_once_with(["python"], True)

    @patch("aidb_cli.services.adapter.adapter_service.AdapterInstallService")
    def test_clean_adapter_cache_delegates(
        self,
        mock_install_class,
        service,
    ):
        """Test clean_adapter_cache delegates to install service."""
        mock_install = Mock()
        mock_install_class.return_value = mock_install

        service.clean_adapter_cache(user_only=True)

        # Facade passes as positional argument
        mock_install.clean_adapter_cache.assert_called_once_with(True)

    def test_cleanup(self, service):
        """Test cleanup doesn't fail."""
        # Should not raise
        service.cleanup()
