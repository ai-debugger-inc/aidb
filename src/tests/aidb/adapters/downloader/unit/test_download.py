"""Unit tests for AdapterDownloader."""

import json
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from aidb.adapters.downloader import AdapterDownloader, AdapterDownloaderResult

# =============================================================================
# TestAdapterDownloaderInit
# =============================================================================


class TestAdapterDownloaderInit:
    """Tests for AdapterDownloader initialization."""

    def test_init_defaults(self, mock_ctx: MagicMock) -> None:
        """Test initialization with default values."""
        with patch(
            "aidb.adapters.downloader.download.AdapterRegistry",
        ) as mock_registry_class:
            downloader = AdapterDownloader(ctx=mock_ctx)

        assert downloader.ctx is mock_ctx
        assert downloader._project_root is None
        assert downloader._versions_cache is None
        mock_registry_class.assert_called_once_with(ctx=mock_ctx)

    def test_init_without_ctx(self) -> None:
        """Test initialization without context uses default."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            downloader = AdapterDownloader()

        assert downloader.ctx is not None


# =============================================================================
# TestAdapterDownloaderGetPlatformInfo
# =============================================================================


class TestAdapterDownloaderGetPlatformInfo:
    """Tests for _get_platform_info method."""

    def test_darwin_arm64(self, mock_ctx: MagicMock) -> None:
        """Test platform detection for macOS ARM64."""
        with (
            patch("aidb.adapters.downloader.download.AdapterRegistry"),
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
        ):
            downloader = AdapterDownloader(ctx=mock_ctx)
            platform_name, arch_name = downloader._get_platform_info()

        assert platform_name == "darwin"
        assert arch_name == "arm64"

    def test_darwin_x64(self, mock_ctx: MagicMock) -> None:
        """Test platform detection for macOS x64."""
        with (
            patch("aidb.adapters.downloader.download.AdapterRegistry"),
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
        ):
            downloader = AdapterDownloader(ctx=mock_ctx)
            platform_name, arch_name = downloader._get_platform_info()

        assert platform_name == "darwin"
        assert arch_name == "x64"

    def test_linux_x64(self, mock_ctx: MagicMock) -> None:
        """Test platform detection for Linux x64."""
        with (
            patch("aidb.adapters.downloader.download.AdapterRegistry"),
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):
            downloader = AdapterDownloader(ctx=mock_ctx)
            platform_name, arch_name = downloader._get_platform_info()

        assert platform_name == "linux"
        assert arch_name == "x64"


# =============================================================================
# TestAdapterDownloaderBuildArtifactUrl
# =============================================================================


class TestAdapterDownloaderBuildArtifactUrl:
    """Tests for _build_artifact_url method."""

    @pytest.fixture
    def downloader(self, mock_ctx: MagicMock) -> AdapterDownloader:
        """Create downloader instance for tests."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            return AdapterDownloader(ctx=mock_ctx)

    def test_platform_specific_url_with_version(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test URL for platform-specific adapter with version."""
        artifact, url = downloader._build_artifact_url(
            adapter_name="python",
            adapter_version="1.8.16",
            release_tag="0.0.5",
            platform_name="darwin",
            arch_name="arm64",
            is_universal=False,
        )

        assert artifact == "python-1.8.16-darwin-arm64.tar.gz"
        assert url == (
            "https://github.com/ai-debugger-inc/aidb/releases/download/"
            "0.0.5/python-1.8.16-darwin-arm64.tar.gz"
        )

    def test_platform_specific_url_without_version(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test URL for platform-specific adapter without version."""
        artifact, url = downloader._build_artifact_url(
            adapter_name="python",
            adapter_version=None,
            release_tag="0.0.5",
            platform_name="darwin",
            arch_name="arm64",
            is_universal=False,
        )

        assert artifact == "python-darwin-arm64.tar.gz"
        assert "python-darwin-arm64.tar.gz" in url

    def test_universal_url_with_version(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test URL for universal adapter with version."""
        artifact, url = downloader._build_artifact_url(
            adapter_name="java",
            adapter_version="0.58.1",
            release_tag="0.0.5",
            platform_name="darwin",
            arch_name="arm64",
            is_universal=True,
        )

        assert artifact == "java-0.58.1-universal.tar.gz"
        assert "java-0.58.1-universal.tar.gz" in url

    def test_universal_url_without_version(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test URL for universal adapter without version."""
        artifact, url = downloader._build_artifact_url(
            adapter_name="java",
            adapter_version=None,
            release_tag="0.0.5",
            platform_name="darwin",
            arch_name="arm64",
            is_universal=True,
        )

        assert artifact == "java-universal.tar.gz"


# =============================================================================
# TestAdapterDownloaderResolveAdapterVersion
# =============================================================================


class TestAdapterDownloaderResolveAdapterVersion:
    """Tests for _resolve_adapter_version method."""

    @pytest.fixture
    def downloader(self, mock_ctx: MagicMock) -> AdapterDownloader:
        """Create downloader instance for tests."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            return AdapterDownloader(ctx=mock_ctx)

    def test_prefers_manifest_version(
        self,
        downloader: AdapterDownloader,
        mock_release_manifest: dict[str, Any],
    ) -> None:
        """Test prefers version from manifest over local config."""
        with patch.object(
            downloader,
            "_fetch_release_manifest",
            return_value=mock_release_manifest,
        ):
            version = downloader._resolve_adapter_version(
                adapter_name="python",
                release_tag="0.0.5",
                adapter_config={"version": "1.0.0"},  # Different version
            )

        assert version == "1.8.16"  # From manifest

    def test_falls_back_to_local_config(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test falls back to local config when manifest unavailable."""
        with patch.object(downloader, "_fetch_release_manifest", return_value=None):
            version = downloader._resolve_adapter_version(
                adapter_name="python",
                release_tag="0.0.5",
                adapter_config={"version": "1.5.0"},
            )

        assert version == "1.5.0"

    def test_returns_none_when_no_version(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test returns None when no version available anywhere."""
        with patch.object(downloader, "_fetch_release_manifest", return_value=None):
            version = downloader._resolve_adapter_version(
                adapter_name="python",
                release_tag="0.0.5",
                adapter_config={},  # No version
            )

        assert version is None


# =============================================================================
# TestAdapterDownloaderDownloadToTemp
# =============================================================================


class TestAdapterDownloaderDownloadToTemp:
    """Tests for _download_to_temp method."""

    @pytest.fixture
    def downloader(self, mock_ctx: MagicMock) -> AdapterDownloader:
        """Create downloader instance for tests."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            return AdapterDownloader(ctx=mock_ctx)

    def test_downloads_to_temp_file(
        self,
        downloader: AdapterDownloader,
        mock_urlopen_response: MagicMock,
    ) -> None:
        """Test downloads content to a temporary file."""
        with patch(
            "aidb.adapters.downloader.download.urlopen",
            return_value=mock_urlopen_response,
        ):
            tmp_path = downloader._download_to_temp("https://example.com/file.tar.gz")

        assert tmp_path is not None
        assert tmp_path.endswith(".tar.gz")

        # Clean up
        Path(tmp_path).unlink(missing_ok=True)

    def test_raises_on_non_https(self, downloader: AdapterDownloader) -> None:
        """Test raises ValueError for non-HTTPS URLs."""
        with pytest.raises(ValueError, match="Disallowed URL scheme"):
            downloader._download_to_temp("http://example.com/file.tar.gz")

    def test_raises_on_file_scheme(self, downloader: AdapterDownloader) -> None:
        """Test raises ValueError for file:// URLs."""
        with pytest.raises(ValueError, match="Disallowed URL scheme"):
            downloader._download_to_temp("file:///etc/passwd")

    def test_propagates_http_error(self, downloader: AdapterDownloader) -> None:
        """Test propagates HTTPError from urlopen."""
        with (
            patch(
                "aidb.adapters.downloader.download.urlopen",
                side_effect=HTTPError(
                    "https://example.com",
                    404,
                    "Not Found",
                    {},  # type: ignore[arg-type]
                    None,
                ),
            ),
            pytest.raises(HTTPError),
        ):
            downloader._download_to_temp("https://example.com/file.tar.gz")


# =============================================================================
# TestAdapterDownloaderSafeExtractTarball
# =============================================================================


class TestAdapterDownloaderSafeExtractTarball:
    """Tests for _safe_extract_tarball method."""

    @pytest.fixture
    def downloader(self, mock_ctx: MagicMock) -> AdapterDownloader:
        """Create downloader instance for tests."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            return AdapterDownloader(ctx=mock_ctx)

    def test_extracts_valid_tarball(
        self,
        downloader: AdapterDownloader,
        sample_tarball: Path,
        tmp_path: Path,
    ) -> None:
        """Test extracts valid tarball to target directory."""
        target_dir = tmp_path / "extract_target"

        downloader._safe_extract_tarball(str(sample_tarball), target_dir)

        assert target_dir.exists()
        assert (target_dir / "metadata.json").exists()
        assert (target_dir / "debugpy").exists()

    def test_creates_target_dir_if_missing(
        self,
        downloader: AdapterDownloader,
        sample_tarball: Path,
        tmp_path: Path,
    ) -> None:
        """Test creates target directory if it doesn't exist."""
        target_dir = tmp_path / "new" / "nested" / "dir"
        assert not target_dir.exists()

        downloader._safe_extract_tarball(str(sample_tarball), target_dir)

        assert target_dir.exists()

    def test_rejects_path_traversal(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
    ) -> None:
        """Test rejects tarballs with path traversal attacks."""
        # Create a malicious tarball with path traversal
        malicious_tarball = tmp_path / "malicious.tar.gz"
        with tarfile.open(malicious_tarball, "w:gz") as tar:
            # Add a file with a path traversal name
            data = b"malicious content"
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = len(data)

            import io

            tar.addfile(info, io.BytesIO(data))

        target_dir = tmp_path / "target"

        with pytest.raises(ValueError, match="Unsafe path in tar archive"):
            downloader._safe_extract_tarball(str(malicious_tarball), target_dir)


# =============================================================================
# TestAdapterDownloaderDownloadAdapter
# =============================================================================


class TestAdapterDownloaderDownloadAdapter:
    """Tests for download_adapter method."""

    @pytest.fixture
    def downloader(
        self,
        mock_ctx: MagicMock,
        tmp_install_dir: Path,
    ) -> AdapterDownloader:
        """Create downloader instance with mocked dependencies."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry") as mock_reg:
            mock_class = MagicMock()
            mock_class.__name__ = "PythonAdapter"
            mock_reg.return_value.get_adapter_class.return_value = mock_class

            downloader = AdapterDownloader(ctx=mock_ctx)
            downloader.install_dir = tmp_install_dir
            return downloader

    def test_returns_already_installed_when_exists(
        self,
        downloader: AdapterDownloader,
        tmp_install_dir: Path,
    ) -> None:
        """Test returns 'already_installed' when adapter directory exists."""
        # Create the adapter directory
        adapter_dir = tmp_install_dir / "python"
        adapter_dir.mkdir(parents=True)

        result = downloader.download_adapter("python", force=False)

        assert result.success is True
        assert result.status == "already_installed"
        assert "already installed" in result.message

    def test_force_redownloads_existing(
        self,
        downloader: AdapterDownloader,
        tmp_install_dir: Path,
        sample_tarball: Path,
        sample_metadata: dict[str, Any],
    ) -> None:
        """Test force=True redownloads even when adapter exists."""
        # Create existing adapter directory
        adapter_dir = tmp_install_dir / "python"
        adapter_dir.mkdir(parents=True)

        # Read actual tarball content
        tarball_content = sample_tarball.read_bytes()

        mock_response = MagicMock()
        mock_response.read.return_value = tarball_content
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(downloader, "get_versions_config", return_value={}),
            patch.object(downloader, "_resolve_adapter_version", return_value="1.8.16"),
            patch.object(
                downloader, "_get_platform_info", return_value=("darwin", "arm64")
            ),
            patch(
                "aidb.adapters.downloader.download.urlopen",
                return_value=mock_response,
            ),
            patch.object(
                downloader,
                "_validate_extracted_metadata",
                return_value=None,
            ),
        ):
            result = downloader.download_adapter("python", force=True)

        assert result.success is True
        assert result.status != "already_installed"

    def test_returns_404_with_instructions(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test returns helpful instructions on 404 error."""
        with (
            patch.object(downloader, "get_versions_config", return_value={}),
            patch.object(downloader, "_resolve_adapter_version", return_value="1.8.16"),
            patch.object(
                downloader, "_get_platform_info", return_value=("darwin", "arm64")
            ),
            patch(
                "aidb.adapters.downloader.download.urlopen",
                side_effect=HTTPError(
                    "https://github.com/...",
                    404,
                    "Not Found",
                    {},  # type: ignore[arg-type]
                    None,
                ),
            ),
        ):
            result = downloader.download_adapter("python")

        assert result.success is False
        assert "not found" in result.message.lower()
        assert result.instructions is not None
        assert "manual" in result.instructions.lower()

    def test_returns_network_error_with_instructions(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test returns offline instructions on network error."""
        with (
            patch.object(downloader, "get_versions_config", return_value={}),
            patch.object(downloader, "_resolve_adapter_version", return_value="1.8.16"),
            patch.object(
                downloader, "_get_platform_info", return_value=("darwin", "arm64")
            ),
            patch(
                "aidb.adapters.downloader.download.urlopen",
                side_effect=URLError("Network unreachable"),
            ),
        ):
            result = downloader.download_adapter("python")

        assert result.success is False
        assert "network" in result.message.lower()
        assert result.instructions is not None
        assert "offline" in result.instructions.lower()


# =============================================================================
# TestAdapterDownloaderListInstalledAdapters
# =============================================================================


class TestAdapterDownloaderListInstalledAdapters:
    """Tests for list_installed_adapters method."""

    @pytest.fixture
    def downloader(
        self,
        mock_ctx: MagicMock,
        tmp_install_dir: Path,
    ) -> AdapterDownloader:
        """Create downloader instance with mocked install directory."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            downloader = AdapterDownloader(ctx=mock_ctx)
            downloader.install_dir = tmp_install_dir
            return downloader

    def test_returns_empty_when_no_adapters(
        self,
        downloader: AdapterDownloader,
    ) -> None:
        """Test returns empty dict when no adapters installed."""
        installed = downloader.list_installed_adapters()

        assert installed == {}

    def test_lists_installed_adapters(
        self,
        downloader: AdapterDownloader,
        tmp_install_dir: Path,
    ) -> None:
        """Test lists all installed adapters with versions."""
        # Create adapter directories with version files
        python_dir = tmp_install_dir / "python"
        python_dir.mkdir()
        (python_dir / ".version").write_text("1.8.16")

        java_dir = tmp_install_dir / "java"
        java_dir.mkdir()
        (java_dir / ".version").write_text("0.58.1")

        installed = downloader.list_installed_adapters()

        assert len(installed) == 2
        assert "python" in installed
        assert installed["python"]["version"] == "1.8.16"
        assert "java" in installed
        assert installed["java"]["version"] == "0.58.1"

    def test_handles_missing_version_file(
        self,
        downloader: AdapterDownloader,
        tmp_install_dir: Path,
    ) -> None:
        """Test handles adapter without version file."""
        adapter_dir = tmp_install_dir / "python"
        adapter_dir.mkdir()
        # No .version file

        installed = downloader.list_installed_adapters()

        assert installed["python"]["version"] == "unknown"

    def test_returns_empty_when_install_dir_missing(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
    ) -> None:
        """Test returns empty dict when install directory doesn't exist."""
        downloader.install_dir = tmp_path / "nonexistent"

        installed = downloader.list_installed_adapters()

        assert installed == {}


# =============================================================================
# TestAdapterDownloaderValidateExtractedMetadata
# =============================================================================


class TestAdapterDownloaderValidateExtractedMetadata:
    """Tests for _validate_extracted_metadata method."""

    @pytest.fixture
    def downloader(self, mock_ctx: MagicMock) -> AdapterDownloader:
        """Create downloader instance for tests."""
        with patch("aidb.adapters.downloader.download.AdapterRegistry"):
            return AdapterDownloader(ctx=mock_ctx)

    def test_validates_complete_metadata(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
        sample_metadata: dict[str, Any],
    ) -> None:
        """Test accepts complete valid metadata."""
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        (adapter_dir / "metadata.json").write_text(json.dumps(sample_metadata))

        # Should not raise
        downloader._validate_extracted_metadata(adapter_dir, "python")

    def test_raises_on_missing_metadata_file(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
    ) -> None:
        """Test raises when metadata.json is missing."""
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        # No metadata.json

        with pytest.raises(ValueError, match="metadata.json file not found"):
            downloader._validate_extracted_metadata(adapter_dir, "python")

    def test_raises_on_missing_required_fields(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
    ) -> None:
        """Test raises when required fields are missing."""
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        # Incomplete metadata
        (adapter_dir / "metadata.json").write_text(
            json.dumps({"adapter_name": "python"}),
        )

        with pytest.raises(ValueError, match="Missing required metadata fields"):
            downloader._validate_extracted_metadata(adapter_dir, "python")

    def test_raises_on_invalid_json(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
    ) -> None:
        """Test raises when metadata.json has invalid JSON."""
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        (adapter_dir / "metadata.json").write_text("not valid json {{{")

        with pytest.raises(ValueError, match="Invalid JSON"):
            downloader._validate_extracted_metadata(adapter_dir, "python")

    def test_moves_nested_contents_up(
        self,
        downloader: AdapterDownloader,
        tmp_path: Path,
        sample_metadata: dict[str, Any],
    ) -> None:
        """Test moves contents from nested directory up one level."""
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()

        # Create nested structure
        nested_dir = adapter_dir / "python-1.8.16"
        nested_dir.mkdir()
        (nested_dir / "metadata.json").write_text(json.dumps(sample_metadata))
        (nested_dir / "debugpy").write_text("binary")

        downloader._validate_extracted_metadata(adapter_dir, "python")

        # Contents should now be at top level
        assert (adapter_dir / "metadata.json").exists()
        assert (adapter_dir / "debugpy").exists()
        # Nested directory should be removed
        assert not nested_dir.exists()
