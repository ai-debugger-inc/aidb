"""Tests for documentation commands."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from aidb.common.errors import AidbError
from aidb_cli.cli import cli


class TestDocsCommands:
    """Test documentation commands."""

    @pytest.fixture
    def mock_docs_builder(self):
        """Create mock DocsBuilderService."""
        with patch("aidb_cli.commands.docs.DocsBuilderService") as mock_class:
            mock_builder = Mock()
            mock_class.return_value = mock_builder
            mock_class.PUBLIC = Mock(default_port=8000)
            yield mock_builder

    @pytest.fixture
    def mock_docs_server(self):
        """Create mock DocsServerService."""
        with patch("aidb_cli.commands.docs.DocsServerService") as mock_class:
            mock_server = Mock()
            mock_class.return_value = mock_server
            yield mock_server

    def test_build_success(self, cli_runner, mock_repo_root, mock_docs_builder):
        """Test successful documentation build."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "build"])

        assert result.exit_code == 0
        mock_docs_builder.build_docs.assert_called_once()

    def test_build_failure(self, cli_runner, mock_repo_root, mock_docs_builder):
        """Test documentation build failure."""
        mock_docs_builder.build_docs.side_effect = AidbError("Build failed")

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "build"])

        assert result.exit_code != 0

    def test_build_docker_not_found(
        self,
        cli_runner,
        mock_repo_root,
        mock_docs_builder,
    ):
        """Test build with Docker not found."""
        mock_docs_builder.build_docs.side_effect = FileNotFoundError()

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "build"])

        assert result.exit_code != 0

    def test_serve_default_port(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test serving docs with default port."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            with patch(
                "aidb_cli.commands.docs.DocsBuilderService.PUBLIC",
            ) as mock_public:
                mock_public.default_port = 8000
                result = cli_runner.invoke(cli, ["docs", "serve"])

        assert result.exit_code == 0
        mock_docs_server.serve_docs.assert_called_once()

    def test_serve_custom_port(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test serving docs with custom port."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "serve", "--port", "9000"])

        assert result.exit_code == 0
        call_args = mock_docs_server.serve_docs.call_args
        assert call_args[0][1] == 9000

    def test_serve_with_build_first(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test serving with build-first flag."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "serve", "--build-first"])

        assert result.exit_code == 0
        call_args = mock_docs_server.serve_docs.call_args
        assert call_args[0][2] is True

    def test_stop_success(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test stopping docs server."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "stop"])

        assert result.exit_code == 0
        mock_docs_server.stop_docs.assert_called_once()

    def test_stop_failure(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test stop failure."""
        mock_docs_server.stop_docs.side_effect = AidbError("Stop failed")

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "stop"])

        assert result.exit_code != 0

    def test_status(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test showing docs status."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "status"])

        assert result.exit_code == 0
        mock_docs_server.show_all_status.assert_called_once()

    def test_open_docs(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test opening docs in browser."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "open"])

        assert result.exit_code == 0
        mock_docs_server.open_docs.assert_called_once()

    def test_open_docs_with_port(self, cli_runner, mock_repo_root, mock_docs_server):
        """Test opening docs with custom port."""
        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "open", "--port", "9000"])

        assert result.exit_code == 0
        call_args = mock_docs_server.open_docs.call_args
        assert call_args[0][1] == 9000

    def test_test_docs(self, cli_runner, mock_repo_root, mock_docs_builder):
        """Test running documentation tests."""
        mock_docs_builder.command_executor = Mock()
        mock_docs_builder.compose_file = "/path/to/compose.yaml"
        mock_docs_builder.repo_root = mock_repo_root

        with patch("aidb_common.repo.detect_repo_root", return_value=mock_repo_root):
            result = cli_runner.invoke(cli, ["docs", "test"])

        assert result.exit_code == 0
        mock_docs_builder.command_executor.execute.assert_called()
