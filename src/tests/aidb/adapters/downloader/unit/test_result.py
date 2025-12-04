"""Unit tests for AdapterDownloaderResult."""

from aidb.adapters.downloader import AdapterDownloaderResult

# =============================================================================
# TestAdapterDownloaderResultInit
# =============================================================================


class TestAdapterDownloaderResultInit:
    """Tests for AdapterDownloaderResult initialization."""

    def test_init_with_minimal_params(self) -> None:
        """Test initialization with only required parameters."""
        result = AdapterDownloaderResult(success=True, message="Test message")

        assert result.success is True
        assert result.message == "Test message"
        assert result.language is None
        assert result.path is None
        assert result.instructions is None
        assert result.error is None

    def test_init_with_all_params(self) -> None:
        """Test initialization with all parameters."""
        result = AdapterDownloaderResult(
            success=False,
            message="Download failed",
            language="python",
            path="/path/to/adapter",
            status="error",
            instructions="Try again later",
            error="Connection timeout",
        )

        assert result.success is False
        assert result.message == "Download failed"
        assert result.language == "python"
        assert result.path == "/path/to/adapter"
        assert result.status == "error"
        assert result.instructions == "Try again later"
        assert result.error == "Connection timeout"

    def test_status_defaults_to_success_when_success_true(self) -> None:
        """Test status defaults to 'success' when success=True."""
        result = AdapterDownloaderResult(success=True, message="OK")

        assert result.status == "success"

    def test_status_defaults_to_error_when_success_false(self) -> None:
        """Test status defaults to 'error' when success=False."""
        result = AdapterDownloaderResult(success=False, message="Failed")

        assert result.status == "error"

    def test_status_can_be_overridden(self) -> None:
        """Test status can be set explicitly."""
        result = AdapterDownloaderResult(
            success=True,
            message="Already installed",
            status="already_installed",
        )

        assert result.status == "already_installed"

    def test_extra_kwargs_stored(self) -> None:
        """Test extra kwargs are stored in extra dict."""
        result = AdapterDownloaderResult(
            success=True,
            message="OK",
            version="1.2.3",
            custom_field="custom_value",
        )

        assert result.extra["version"] == "1.2.3"
        assert result.extra["custom_field"] == "custom_value"


# =============================================================================
# TestAdapterDownloaderResultToDict
# =============================================================================


class TestAdapterDownloaderResultToDict:
    """Tests for AdapterDownloaderResult.to_dict method."""

    def test_to_dict_minimal(self) -> None:
        """Test to_dict with minimal result."""
        result = AdapterDownloaderResult(success=True, message="OK")

        d = result.to_dict()

        assert d == {
            "success": True,
            "status": "success",
            "message": "OK",
        }

    def test_to_dict_includes_optional_fields_when_set(self) -> None:
        """Test to_dict includes optional fields when they have values."""
        result = AdapterDownloaderResult(
            success=True,
            message="Installed",
            language="python",
            path="/adapters/python",
        )

        d = result.to_dict()

        assert d["language"] == "python"
        assert d["path"] == "/adapters/python"

    def test_to_dict_includes_error_fields(self) -> None:
        """Test to_dict includes error-related fields."""
        result = AdapterDownloaderResult(
            success=False,
            message="Failed",
            instructions="See manual",
            error="Network error",
        )

        d = result.to_dict()

        assert d["instructions"] == "See manual"
        assert d["error"] == "Network error"

    def test_to_dict_includes_extra_kwargs(self) -> None:
        """Test to_dict includes extra kwargs."""
        result = AdapterDownloaderResult(
            success=True,
            message="OK",
            version="1.8.16",
            platform="darwin-arm64",
        )

        d = result.to_dict()

        assert d["version"] == "1.8.16"
        assert d["platform"] == "darwin-arm64"

    def test_to_dict_excludes_none_optional_fields(self) -> None:
        """Test to_dict excludes optional fields that are None."""
        result = AdapterDownloaderResult(success=True, message="OK")

        d = result.to_dict()

        assert "language" not in d
        assert "path" not in d
        assert "instructions" not in d
        assert "error" not in d
