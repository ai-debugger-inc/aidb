"""Unit tests for AdapterMetadataService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.adapter.adapter_metadata_service import AdapterMetadataService
from aidb_common.io.files import FileOperationError


class TestAdapterMetadataService:
    """Test the AdapterMetadataService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create an AdapterMetadataService instance with mocks."""
        return AdapterMetadataService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization."""
        # Execute
        service = AdapterMetadataService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        # Assert
        assert service.repo_root == tmp_path
        assert service._metadata_cache == {}

    @patch("aidb_cli.services.adapter.adapter_metadata_service.safe_read_json")
    @patch("pathlib.Path.exists")
    def test_load_adapter_metadata_from_cache_path(
        self,
        mock_exists,
        mock_safe_read_json,
        service,
    ):
        """Test loading metadata from cache path."""
        # Setup
        mock_exists.return_value = True
        mock_safe_read_json.return_value = {
            "adapter_version": "1.0.0",
            "aidb_version": "0.1.0",
        }

        # Execute
        metadata = service.load_adapter_metadata("python")

        # Assert
        assert metadata["adapter_version"] == "1.0.0"
        assert metadata["aidb_version"] == "0.1.0"
        # Should be cached
        assert "python" in service._metadata_cache

    @patch("aidb_cli.services.adapter.adapter_metadata_service.safe_read_json")
    @patch("pathlib.Path.exists")
    def test_load_adapter_metadata_from_legacy_path(
        self,
        mock_exists,
        mock_safe_read_json,
        service,
    ):
        """Test loading metadata from legacy .aidb path when cache path doesn't
        exist."""
        # Setup - first path doesn't exist, second does
        mock_exists.side_effect = [False, True]
        mock_safe_read_json.return_value = {
            "adapter_version": "1.0.0",
            "aidb_version": "0.1.0",
        }

        # Execute
        metadata = service.load_adapter_metadata("python")

        # Assert
        assert metadata["adapter_version"] == "1.0.0"
        assert mock_safe_read_json.call_count == 1

    def test_load_adapter_metadata_cache_hit(self, service):
        """Test that cached metadata is returned without file access."""
        # Setup - pre-populate cache
        cached_metadata = {"adapter_version": "cached", "aidb_version": "0.1.0"}
        service._metadata_cache["python"] = cached_metadata

        # Execute
        metadata = service.load_adapter_metadata("python")

        # Assert
        assert metadata == cached_metadata

    @patch("pathlib.Path.exists")
    def test_load_adapter_metadata_file_not_found(self, mock_exists, service):
        """Test loading metadata when file doesn't exist returns empty dict."""
        # Setup - no files exist
        mock_exists.return_value = False

        # Execute
        metadata = service.load_adapter_metadata("python")

        # Assert
        assert metadata == {}

    @patch("aidb_cli.services.adapter.adapter_metadata_service.safe_read_json")
    @patch("pathlib.Path.exists")
    def test_load_adapter_metadata_json_parse_error(
        self,
        mock_exists,
        mock_safe_read_json,
        service,
    ):
        """Test loading metadata handles JSON parse errors."""
        # Setup
        mock_exists.return_value = True
        mock_safe_read_json.side_effect = FileOperationError("Invalid JSON")

        # Execute
        metadata = service.load_adapter_metadata("python")

        # Assert - should return empty dict on error
        assert metadata == {}

    def test_display_adapter_list_with_built_adapters(self, service, capsys):
        """Test displaying adapter list with built adapters."""
        # Setup
        service._metadata_cache["python"] = {
            "adapter_version": "1.0.0",
            "aidb_version": "0.1.0",
        }
        languages = ["python", "javascript"]
        built_list = ["python"]
        missing_list = ["javascript"]

        # Execute
        service.display_adapter_list_with_metadata(languages, built_list, missing_list)

        # Assert - verify output contains expected info
        captured = capsys.readouterr()
        assert "python" in captured.out.lower()
        assert "javascript" in captured.out.lower()

    def test_display_adapter_list_all_missing(self, service, capsys):
        """Test displaying adapter list when all adapters are missing."""
        # Setup
        languages = ["python", "javascript"]
        built_list: list[str] = []
        missing_list = ["python", "javascript"]

        # Execute
        service.display_adapter_list_with_metadata(languages, built_list, missing_list)

        # Assert - verify output contains languages and shows missing
        captured = capsys.readouterr()
        assert "python" in captured.out.lower()
        assert "javascript" in captured.out.lower()
        assert "missing" in captured.out.lower()

    def test_display_adapter_info_with_metadata(self, service, capsys):
        """Test displaying detailed adapter info with metadata."""
        # Setup
        service._metadata_cache["python"] = {
            "adapter_version": "1.0.0",
            "aidb_version": "0.1.0",
            "adapter_name": "Python Debug Adapter",
            "build_date": "2025-01-01",
            "binary_identifier": "debugpy",
            "repo": "https://github.com/microsoft/debugpy",
        }
        adapter_info = {
            "status": "Built",
            "type": "Debug Adapter",
            "location": "/path/to/adapter",
        }

        # Execute
        service.display_adapter_info_with_metadata("python", adapter_info)

        # Assert - verify output contains expected info
        captured = capsys.readouterr()
        assert "python" in captured.out.lower()
        assert "1.0.0" in captured.out
        assert "debugpy" in captured.out.lower()

    def test_display_adapter_info_without_metadata(self, service, capsys):
        """Test displaying adapter info when metadata is not available."""
        # Setup - no metadata cached
        adapter_info = {
            "status": "Built",
            "location": "/path/to/adapter",
        }

        # Execute
        service.display_adapter_info_with_metadata("python", adapter_info)

        # Assert - should display warning about missing metadata
        captured = capsys.readouterr()
        assert "python" in captured.out.lower()
        # Warning goes to stderr or has warning symbol in stdout
        assert "metadata" in captured.out.lower() or "metadata" in captured.err.lower()

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_check_version_mismatches_no_mismatches(self, service):
        """Test checking for version mismatches when all match."""
        # Setup
        service._metadata_cache["python"] = {"aidb_version": "0.1.0"}
        service._metadata_cache["javascript"] = {"aidb_version": "0.1.0"}

        # Execute
        mismatched = service.check_version_mismatches(
            ["python", "javascript"],
            ["python", "javascript"],
        )

        # Assert
        assert mismatched == []

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_check_version_mismatches_with_mismatches(self, service):
        """Test checking for version mismatches when some mismatch."""
        # Setup
        service._metadata_cache["python"] = {"aidb_version": "0.0.9"}  # Mismatch
        service._metadata_cache["javascript"] = {"aidb_version": "0.1.0"}  # Match

        # Execute
        mismatched = service.check_version_mismatches(
            ["python", "javascript"],
            ["python", "javascript"],
        )

        # Assert
        assert "python" in mismatched
        assert "javascript" not in mismatched

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    @patch("pathlib.Path.exists")
    def test_check_version_mismatches_missing_metadata(self, mock_exists, service):
        """Test checking for version mismatches when metadata is missing."""
        # Setup - no metadata files exist
        mock_exists.return_value = False

        # Execute
        mismatched = service.check_version_mismatches(
            ["python"],
            ["python"],
        )

        # Assert - missing metadata should not be reported as mismatch
        assert mismatched == []

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_get_compatibility_icon_matching_version(self, service):
        """Test compatibility icon when versions match."""
        # Execute
        icon = service._get_compatibility_icon("0.1.0")

        # Assert
        from aidb_cli.core.constants import Icons

        assert icon == Icons.SUCCESS

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_get_compatibility_icon_unknown_version(self, service):
        """Test compatibility icon for unknown version."""
        # Execute
        icon = service._get_compatibility_icon("unknown")

        # Assert
        assert icon == "❓"

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_get_compatibility_icon_mismatched_version(self, service):
        """Test compatibility icon when versions mismatch."""
        # Execute
        icon = service._get_compatibility_icon("0.0.9")

        # Assert
        from aidb_cli.core.constants import Icons

        assert icon == Icons.WARNING

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_display_compatibility_status_ok(self, service, capsys):
        """Test displaying compatibility status when OK."""
        # Execute
        service._display_compatibility_status("0.1.0", "python")

        # Assert - verify output shows OK status
        captured = capsys.readouterr()
        assert "compatibility" in captured.out.lower()
        assert "ok" in captured.out.lower()

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_display_compatibility_status_unknown(self, service, capsys):
        """Test displaying compatibility status when unknown."""
        # Execute
        service._display_compatibility_status("unknown", "python")

        # Assert - verify output shows unknown status
        captured = capsys.readouterr()
        assert "compatibility" in captured.out.lower()
        assert "unknown" in captured.out.lower()

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_display_compatibility_status_mismatch(self, service, capsys):
        """Test displaying compatibility status when mismatched."""
        # Execute
        service._display_compatibility_status("0.0.9", "python")

        # Assert - verify output shows mismatch and suggestion
        captured = capsys.readouterr()
        assert "compatibility" in captured.out.lower()
        assert "mismatch" in captured.out.lower()
        assert "install" in captured.out.lower()

    def test_display_summary_all_built(self, service, capsys):
        """Test displaying summary when all adapters built."""
        # Setup
        languages = ["python", "javascript"]
        built_list = ["python", "javascript"]
        missing_list: list[str] = []

        # Execute
        service._display_summary(languages, built_list, missing_list)

        # Assert - verify output shows all adapters built
        captured = capsys.readouterr()
        total = len(languages)
        assert f"{total}/{total}" in captured.out

    @patch(
        "aidb_cli.services.adapter.adapter_metadata_service.current_aidb_version",
        "0.1.0",
    )
    def test_display_summary_with_mismatches(self, service, capsys):
        """Test displaying summary with version mismatches."""
        # Setup
        service._metadata_cache["python"] = {"aidb_version": "0.0.9"}  # Mismatch
        languages = ["python"]
        built_list = ["python"]
        missing_list: list[str] = []

        # Execute
        service._display_summary(languages, built_list, missing_list)

        # Assert - verify output shows version mismatch warning
        captured = capsys.readouterr()
        assert "mismatch" in captured.out.lower()
        assert "python" in captured.out.lower()

    def test_display_summary_none_built(self, service, capsys):
        """Test displaying summary when no adapters built."""
        # Setup
        languages = ["python", "javascript"]
        built_list: list[str] = []
        missing_list = ["python", "javascript"]

        # Execute
        service._display_summary(languages, built_list, missing_list)

        # Assert - verify output shows 0/total and suggest building
        captured = capsys.readouterr()
        # Check for "0/" followed by the total count
        assert f"0/{len(languages)}" in captured.out
        assert "build" in captured.out.lower()

    def test_cleanup(self, service):
        """Test cleanup clears metadata cache."""
        # Setup - add some cached data
        service._metadata_cache["python"] = {"adapter_version": "1.0.0"}
        service._metadata_cache["javascript"] = {"adapter_version": "1.0.0"}

        # Execute
        service.cleanup()

        # Assert
        assert service._metadata_cache == {}
