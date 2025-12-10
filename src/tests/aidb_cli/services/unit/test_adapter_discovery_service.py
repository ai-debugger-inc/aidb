"""Unit tests for AdapterDiscoveryService.

Tests for adapter discovery and cache checking functionality.
"""

from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.adapter.adapter_discovery_service import AdapterDiscoveryService
from aidb_common.constants import SUPPORTED_LANGUAGES


class TestAdapterDiscoveryService:
    """Test the AdapterDiscoveryService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        return Mock()

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create an AdapterDiscoveryService instance."""
        return AdapterDiscoveryService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )


class TestCheckAdaptersInCache:
    """Test the check_adapters_in_cache method."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        return Mock()

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create an AdapterDiscoveryService instance with cache dir."""
        service = AdapterDiscoveryService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )
        # Ensure cache dir is set
        service._cache_dir = tmp_path / ".cache" / "adapters"
        return service

    def test_returns_missing_when_cache_dir_not_set(
        self,
        tmp_path,
        mock_command_executor,
    ):
        """Test returns all missing when cache dir is not set."""
        service = AdapterDiscoveryService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )
        service._cache_dir = None

        with patch.object(
            service, "get_supported_languages", return_value=["python", "javascript"]
        ):
            built, missing = service.check_adapters_in_cache()

        assert built == []
        assert missing == ["python", "javascript"]

    def test_returns_missing_when_cache_dir_empty(self, service, tmp_path):
        """Test returns missing when cache directory is empty."""
        # Create empty cache dir
        cache_dir = tmp_path / ".cache" / "adapters"
        cache_dir.mkdir(parents=True)
        service._cache_dir = cache_dir

        with patch.object(
            service,
            "get_supported_languages",
            return_value=SUPPORTED_LANGUAGES,
        ):
            built, missing = service.check_adapters_in_cache()

        assert built == []
        assert set(missing) == set(SUPPORTED_LANGUAGES)

    def test_returns_built_when_binary_exists(self, service, tmp_path):
        """Test returns built when binary file exists in cache."""
        cache_dir = tmp_path / ".cache" / "adapters"

        # Create Python adapter with debugpy
        python_dir = cache_dir / "python" / "debugpy"
        python_dir.mkdir(parents=True)
        (python_dir / "__init__.py").write_text("")

        # Create JavaScript adapter with dapDebugServer
        js_dir = cache_dir / "javascript" / "src"
        js_dir.mkdir(parents=True)
        (js_dir / "dapDebugServer.js").write_text("")

        service._cache_dir = cache_dir

        with patch.object(
            service,
            "get_supported_languages",
            return_value=SUPPORTED_LANGUAGES,
        ):
            built, missing = service.check_adapters_in_cache()

        assert set(built) == {"python", "javascript"}
        assert missing == ["java"]

    def test_returns_missing_when_wrong_binary_file(self, service, tmp_path):
        """Test returns missing when directory exists but binary file doesn't match."""
        cache_dir = tmp_path / ".cache" / "adapters"

        # Create Python adapter dir but wrong file (not debugpy/__init__.py)
        python_dir = cache_dir / "python"
        python_dir.mkdir(parents=True)
        (python_dir / "wrong_file.py").write_text("")

        service._cache_dir = cache_dir

        with patch.object(service, "get_supported_languages", return_value=["python"]):
            built, missing = service.check_adapters_in_cache()

        assert built == []
        assert missing == ["python"]

    def test_checks_specific_languages_only(self, service, tmp_path):
        """Test only checks specified languages."""
        cache_dir = tmp_path / ".cache" / "adapters"

        # Create Python adapter
        python_dir = cache_dir / "python" / "debugpy"
        python_dir.mkdir(parents=True)
        (python_dir / "__init__.py").write_text("")

        service._cache_dir = cache_dir

        # Only check python (which exists)
        built, missing = service.check_adapters_in_cache(languages=["python"])

        assert built == ["python"]
        assert missing == []

    def test_checks_java_jar_file(self, service, tmp_path):
        """Test checks Java adapter JAR file."""
        cache_dir = tmp_path / ".cache" / "adapters"

        # Create Java adapter with jar
        java_dir = cache_dir / "java"
        java_dir.mkdir(parents=True)
        (java_dir / "java-debug.jar").write_text("")

        service._cache_dir = cache_dir

        built, missing = service.check_adapters_in_cache(languages=["java"])

        assert built == ["java"]
        assert missing == []

    def test_unknown_language_returns_missing(self, service, tmp_path):
        """Test unknown language without binary mapping returns missing."""
        cache_dir = tmp_path / ".cache" / "adapters"
        cache_dir.mkdir(parents=True)
        service._cache_dir = cache_dir

        # Check an unknown language (not in ADAPTER_BINARY_FILES)
        built, missing = service.check_adapters_in_cache(languages=["unknown"])

        assert built == []
        assert missing == ["unknown"]
