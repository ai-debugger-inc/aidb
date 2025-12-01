"""Tests for DocsServerService with dynamic port detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aidb_cli.services.docs.docs_builder_service import DocsBuilderService
from aidb_cli.services.docs.docs_server_service import DocsServerService


class TestDocsServerService:
    """Test DocsServerService functionality."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        return MagicMock()

    @pytest.fixture
    def mock_builder_service(self):
        """Create a mock builder service."""
        return MagicMock(spec=DocsBuilderService)

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create a DocsServerService instance."""
        return DocsServerService(tmp_path, mock_command_executor)

    def test_open_docs_public_with_port_detection(
        self,
        service,
        mock_builder_service,
    ):
        """Test that public docs uses port detection consistently."""
        service.builder_service = mock_builder_service
        mock_builder_service.get_service_status.return_value = (True, "8001")

        with patch("webbrowser.open") as mock_open:
            service.open_docs(DocsBuilderService.PUBLIC, port=8000)

            mock_open.assert_called_once_with("http://localhost:8001")

    def test_open_docs_starts_server_when_not_running(
        self,
        service,
        mock_builder_service,
    ):
        """Test opening docs starts server when not running."""
        service.builder_service = mock_builder_service
        mock_builder_service.get_service_status.side_effect = [
            (False, None),
            (True, "8000"),
        ]

        with patch("webbrowser.open") as mock_open:
            with patch.object(service, "serve_docs") as mock_serve:
                with patch("time.sleep"):
                    service.open_docs(DocsBuilderService.PUBLIC, port=8000)

                    mock_serve.assert_called_once_with(
                        DocsBuilderService.PUBLIC, 8000, build_first=True
                    )
                    mock_open.assert_called_once_with("http://localhost:8000")

    def test_show_all_status_running(self, service, mock_builder_service):
        """Test show_all_status when docs server is running."""
        service.builder_service = mock_builder_service
        mock_builder_service.get_service_status.return_value = (True, "8000")

        with patch("aidb_cli.core.formatting.HeadingFormatter.section"):
            with patch("aidb_cli.core.utils.CliOutput.success") as mock_success:
                service.show_all_status()

                mock_success.assert_called_once_with(
                    "Docs: Running at http://localhost:8000"
                )

    def test_show_all_status_not_running(self, service, mock_builder_service):
        """Test show_all_status when docs server is not running."""
        service.builder_service = mock_builder_service
        mock_builder_service.get_service_status.return_value = (False, None)

        with patch("aidb_cli.core.formatting.HeadingFormatter.section"):
            with patch("aidb_cli.core.utils.CliOutput.info") as mock_info:
                service.show_all_status()

                mock_info.assert_called_once_with("Docs: Not running")
