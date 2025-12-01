"""Unit tests for DownloadService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.build.download_service import DownloadService


class TestDownloadService:
    """Test the DownloadService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create a DownloadService instance with mocks."""
        return DownloadService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization."""
        service = DownloadService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.repo_root == tmp_path
        assert service._downloader is None

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_downloader_initialization_success(
        self,
        mock_downloader_class,
        service,
    ):
        """Test successful downloader initialization."""
        mock_instance = Mock()
        mock_downloader_class.return_value = mock_instance

        downloader = service.downloader

        assert downloader == mock_instance
        mock_downloader_class.assert_called_once()

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_downloader_initialization_failure(
        self,
        mock_downloader_class,
        service,
    ):
        """Test downloader initialization fallback on error."""
        mock_downloader_class.side_effect = Exception("Downloader error")

        downloader = service.downloader

        assert downloader is None

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_all_adapters_success(
        self,
        mock_downloader_class,
        service,
    ):
        """Test downloading all adapters successfully."""
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = True
        mock_downloader_class.return_value = mock_instance

        result = service.download_all_adapters(
            languages=["python", "javascript"],
            force=False,
            verbose=False,
        )

        assert result is True
        assert mock_instance.download_adapter.call_count == 2

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_all_adapters_partial_failure(
        self,
        mock_downloader_class,
        service,
    ):
        """Test downloading with some failures."""
        mock_instance = Mock()
        # First download succeeds, second fails
        mock_instance.download_adapter.side_effect = [True, False]
        mock_downloader_class.return_value = mock_instance

        result = service.download_all_adapters(
            languages=["python", "javascript"],
            force=False,
            verbose=False,
        )

        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_all_adapters_no_downloader(
        self,
        mock_downloader_class,
        service,
    ):
        """Test download when downloader is unavailable."""
        mock_downloader_class.side_effect = Exception("Init failed")
        service._downloader = None

        result = service.download_all_adapters()
        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    @patch("aidb_cli.services.build.download_service.Language")
    def test_download_all_adapters_default_languages(
        self,
        mock_language,
        mock_downloader_class,
        service,
    ):
        """Test downloading with default languages (all)."""
        # Setup Language enum mock
        mock_python = Mock()
        mock_python.value = "python"
        mock_js = Mock()
        mock_js.value = "javascript"
        mock_language.__iter__.return_value = [mock_python, mock_js]

        # Setup downloader
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = True
        mock_downloader_class.return_value = mock_instance

        result = service.download_all_adapters(languages=None, force=False)

        assert result is True
        assert mock_instance.download_adapter.call_count == 2

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_all_adapters_exception(
        self,
        mock_downloader_class,
        service,
    ):
        """Test exception handling in download_all_adapters."""
        mock_instance = Mock()
        mock_instance.download_adapter.side_effect = Exception("Download error")
        mock_downloader_class.return_value = mock_instance

        result = service.download_all_adapters(languages=["python"])

        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_success(
        self,
        mock_downloader_class,
        service,
    ):
        """Test downloading a single adapter successfully."""
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = True
        mock_downloader_class.return_value = mock_instance

        result = service.download_single_adapter("python", verbose=False)

        assert result is True
        mock_instance.download_adapter.assert_called_once()

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_with_version(
        self,
        mock_downloader_class,
        service,
    ):
        """Test downloading specific version."""
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = True
        mock_downloader_class.return_value = mock_instance

        result = service.download_single_adapter(
            "python",
            version="1.0.0",
            force=True,
        )

        assert result is True
        mock_instance.download_adapter.assert_called_once_with(
            language="python",
            version="1.0.0",
            force=True,
        )

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_already_exists(
        self,
        mock_downloader_class,
        tmp_path,
        service,
    ):
        """Test when adapter already exists."""
        # Create existing adapter directory
        cache_dir = Path.home() / ".cache" / "aidb" / "adapters" / "python"
        cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            mock_instance = Mock()
            mock_downloader_class.return_value = mock_instance

            result = service.download_single_adapter(
                "python",
                force=False,
                verbose=True,
            )

            assert result is True
            # Should not call download_adapter since already exists
            mock_instance.download_adapter.assert_not_called()
        finally:
            # Cleanup
            import shutil

            if cache_dir.parent.exists():
                shutil.rmtree(cache_dir.parent)

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_force_redownload(
        self,
        mock_downloader_class,
        tmp_path,
        service,
    ):
        """Test force redownload when adapter exists."""
        # Create existing adapter directory
        cache_dir = Path.home() / ".cache" / "aidb" / "adapters" / "python"
        cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            mock_instance = Mock()
            mock_instance.download_adapter.return_value = True
            mock_downloader_class.return_value = mock_instance

            result = service.download_single_adapter("python", force=True)

            assert result is True
            # Should call download_adapter even though exists
            mock_instance.download_adapter.assert_called_once()
        finally:
            # Cleanup
            import shutil

            if cache_dir.parent.exists():
                shutil.rmtree(cache_dir.parent)

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_no_downloader(
        self,
        mock_downloader_class,
        service,
    ):
        """Test download when downloader is unavailable."""
        mock_downloader_class.side_effect = Exception("Init failed")
        service._downloader = None

        result = service.download_single_adapter("python")
        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_download_failure(
        self,
        mock_downloader_class,
        service,
    ):
        """Test handling download failure."""
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = False
        mock_downloader_class.return_value = mock_instance

        result = service.download_single_adapter("python")

        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_download_single_adapter_exception(
        self,
        mock_downloader_class,
        service,
    ):
        """Test exception handling in download_single_adapter."""
        mock_instance = Mock()
        mock_instance.download_adapter.side_effect = Exception("Download error")
        mock_downloader_class.return_value = mock_instance

        result = service.download_single_adapter("python")

        assert result is False

    @patch("aidb_cli.services.build.download_service.AdapterDownloader")
    def test_internal_download_single_adapter(
        self,
        mock_downloader_class,
        service,
    ):
        """Test internal download method."""
        mock_instance = Mock()
        mock_instance.download_adapter.return_value = True
        mock_downloader_class.return_value = mock_instance

        result = service._download_single_adapter(
            "python",
            force=True,
            verbose=True,
        )

        assert result is True
        mock_instance.download_adapter.assert_called_once_with(
            language="python",
            version=None,
            force=True,
        )

    def test_cleanup(self, service):
        """Test service cleanup."""
        service.cleanup()
        # No-op, just verify it doesn't raise
