"""Tests for adapter management commands."""

from unittest.mock import ANY, Mock, PropertyMock, patch

import pytest
from click.testing import CliRunner

from aidb_cli.cli import cli
from aidb_common.constants import SUPPORTED_LANGUAGES


class TestAdapterCommands:
    """Test adapter management commands."""

    def test_list_adapters(self, cli_runner, mock_repo_root, mock_build_manager):
        """Test listing available adapters."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.commands.adapters.AdapterMetadataService",
            ) as mock_metadata_service_class:
                # Mock the metadata service instance and its methods
                mock_metadata_service = Mock()
                mock_metadata_service_class.return_value = mock_metadata_service

                # Create a mock CLI context and inject our mock build manager
                from unittest.mock import PropertyMock

                with patch(
                    "aidb_cli.cli.Context.build_manager",
                    new_callable=PropertyMock,
                    return_value=mock_build_manager,
                ):
                    result = cli_runner.invoke(cli, ["adapters", "list"])
                    assert result.exit_code == 0

                    # Verify the service was called with the correct data
                    mock_metadata_service.display_adapter_list_with_metadata.assert_called_once()
                    call_args = mock_metadata_service.display_adapter_list_with_metadata.call_args

                    # Verify the arguments passed to the metadata service
                    languages, built_list, missing_list = call_args[0]

                    assert len(languages) > 0  # Should have languages
                    assert len(built_list) >= 0  # Should have some built/missing split

                    # Verify our mock was used correctly
                    expected_languages = (
                        mock_build_manager.get_supported_languages.return_value
                    )
                    assert languages == expected_languages

    def test_build_all_adapters(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
    ):
        """Test building all adapters."""
        # Mock the AdapterService that build_manager returns
        mock_adapter_service = Mock()
        mock_adapter_service.build_locally.return_value = True
        mock_build_manager.get_service.return_value = mock_adapter_service
        mock_build_manager.get_supported_languages.return_value = [
            "javascript",
            "java",
            "python",
        ]

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            mock_build_manager,
            ["adapters", "build"],
        )
        assert result.exit_code == 0
        mock_adapter_service.build_locally.assert_called_once_with(
            languages=SUPPORTED_LANGUAGES,
            verbose=False,
            resolved_env=ANY,
        )

    def test_build_specific_language(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
    ):
        """Test building adapters for specific languages."""
        # Mock the AdapterService that build_manager returns
        mock_adapter_service = Mock()
        mock_adapter_service.build_locally.return_value = True
        mock_build_manager.get_service.return_value = mock_adapter_service

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            mock_build_manager,
            ["adapters", "build", "-l", "javascript", "-l", "java"],
        )
        assert result.exit_code == 0
        mock_adapter_service.build_locally.assert_called_once_with(
            languages=["javascript", "java"],
            verbose=False,
            resolved_env=ANY,
        )

    def test_build_invalid_language(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
    ):
        """Test error handling for invalid language."""
        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            mock_build_manager,
            ["adapters", "build", "-l", "rust"],
        )
        assert result.exit_code == 2
        assert "Invalid value" in result.output
        assert "invalid choice: rust" in result.output

    def test_info_adapter(self, cli_runner, mock_repo_root, mock_build_manager):
        """Test showing adapter information."""
        # Mock build manager to return that Python adapter is built
        mock_build_manager.check_adapters_built.return_value = (["python"], [])
        mock_build_manager.get_adapter_info.return_value = {
            "language": "python",
            "status": "built",
            "type": "pip package (debugpy)",
            "location": "/usr/local/lib/python3.10/site-packages/debugpy",
        }

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.commands.adapters.AdapterMetadataService",
            ) as mock_metadata_service_class:
                # Mock the metadata service instance and its methods
                mock_metadata_service = Mock()
                mock_metadata_service_class.return_value = mock_metadata_service

                with patch(
                    "aidb_cli.cli.Context.build_manager",
                    new_callable=PropertyMock,
                    return_value=mock_build_manager,
                ):
                    result = cli_runner.invoke(cli, ["adapters", "info", "python"])
                    assert result.exit_code == 0

                    # Verify the metadata service was called correctly
                    mock_metadata_service.display_adapter_info_with_metadata.assert_called_once()
                    call_args = mock_metadata_service.display_adapter_info_with_metadata.call_args
                    language, adapter_info = call_args[0]
                    assert language == "python"
                    assert adapter_info["language"] == "python"

    def test_info_invalid_adapter(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
    ):
        """Test error handling for invalid adapter in info command."""
        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            mock_build_manager,
            ["adapters", "info", "rust"],
        )
        assert result.exit_code == 2
        assert "Invalid value" in result.output
        assert "invalid choice: rust" in result.output

    def test_download_adapters(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
        tmp_path,
    ):
        """Test downloading adapters to repo cache."""
        # Mock AdapterDownloader
        mock_downloader = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_downloader.download_adapter.return_value = mock_result
        mock_downloader.install_dir = tmp_path / ".aidb" / "adapters"

        # Create fake downloaded adapter directory
        (tmp_path / ".aidb" / "adapters" / "javascript").mkdir(parents=True)

        mock_build_manager.repo_root = tmp_path
        mock_build_manager.get_supported_languages.return_value = [
            "javascript",
            "java",
            "python",
        ]

        with patch(
            "aidb_cli.commands.adapters.AdapterDownloader",
            return_value=mock_downloader,
        ):
            with patch("shutil.copytree"):
                with patch("shutil.rmtree"):
                    result = cli_context_mock(
                        cli_runner,
                        mock_repo_root,
                        mock_build_manager,
                        ["adapters", "download"],
                    )
                    assert result.exit_code == 0
                    assert "Downloaded" in result.output

    def test_download_specific_language(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
        tmp_path,
    ):
        """Test downloading specific language adapters to repo cache."""
        # Mock AdapterDownloader
        mock_downloader = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_downloader.download_adapter.return_value = mock_result
        mock_downloader.install_dir = tmp_path / ".aidb" / "adapters"

        # Create fake downloaded adapter directory
        (tmp_path / ".aidb" / "adapters" / "javascript").mkdir(parents=True)

        mock_build_manager.repo_root = tmp_path

        with patch(
            "aidb_cli.commands.adapters.AdapterDownloader",
            return_value=mock_downloader,
        ):
            with patch("shutil.copytree"):
                with patch("shutil.rmtree"):
                    result = cli_context_mock(
                        cli_runner,
                        mock_repo_root,
                        mock_build_manager,
                        ["adapters", "download", "-l", "javascript"],
                    )
                    assert result.exit_code == 0
                    assert "Downloaded" in result.output

    def test_download_force(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
        tmp_path,
    ):
        """Test force download rebuilds even if cache exists."""
        # Mock AdapterDownloader
        mock_downloader = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_downloader.download_adapter.return_value = mock_result
        mock_downloader.install_dir = tmp_path / ".aidb" / "adapters"

        # Create fake downloaded adapter directory
        (tmp_path / ".aidb" / "adapters" / "javascript").mkdir(parents=True)

        mock_build_manager.repo_root = tmp_path
        mock_build_manager.get_supported_languages.return_value = ["javascript"]

        with patch(
            "aidb_cli.commands.adapters.AdapterDownloader",
            return_value=mock_downloader,
        ):
            with patch("shutil.copytree"):
                with patch("shutil.rmtree"):
                    result = cli_context_mock(
                        cli_runner,
                        mock_repo_root,
                        mock_build_manager,
                        ["adapters", "download", "--force"],
                    )
                    assert result.exit_code == 0
                    assert "Downloaded" in result.output

    def test_build_with_install(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
    ):
        """Test building adapters with --install flag."""
        # Mock the AdapterService
        mock_adapter_service = Mock()
        mock_adapter_service.build_locally.return_value = True
        mock_adapter_service.install_adapters.return_value = True
        mock_build_manager.get_service.return_value = mock_adapter_service
        mock_build_manager.get_supported_languages.return_value = ["javascript"]

        result = cli_context_mock(
            cli_runner,
            mock_repo_root,
            mock_build_manager,
            ["adapters", "build", "-l", "javascript", "--install"],
        )
        assert result.exit_code == 0
        mock_adapter_service.build_locally.assert_called_once()
        mock_adapter_service.install_adapters.assert_called_once_with(
            languages=["javascript"],
            verbose=False,
        )

    def test_download_with_install(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        cli_context_mock,
        tmp_path,
    ):
        """Test downloading adapters with --install flag."""
        # Mock AdapterDownloader
        mock_downloader = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_downloader.download_adapter.return_value = mock_result
        mock_downloader.install_dir = tmp_path / ".aidb" / "adapters"

        # Create fake downloaded adapter directory
        (tmp_path / ".aidb" / "adapters" / "javascript").mkdir(parents=True)

        # Mock AdapterService for install
        mock_adapter_service = Mock()
        mock_adapter_service.install_adapters.return_value = True
        mock_build_manager.get_service.return_value = mock_adapter_service
        mock_build_manager.repo_root = tmp_path

        with patch(
            "aidb_cli.commands.adapters.AdapterDownloader",
            return_value=mock_downloader,
        ):
            with patch("shutil.copytree"):
                with patch("shutil.rmtree"):
                    result = cli_context_mock(
                        cli_runner,
                        mock_repo_root,
                        mock_build_manager,
                        ["adapters", "download", "-l", "javascript", "--install"],
                    )
                    assert result.exit_code == 0
                    assert "Downloaded" in result.output
                    mock_adapter_service.install_adapters.assert_called_once()

    def test_clean_cache_with_confirmation(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
    ):
        """Test cleaning adapter cache with confirmation."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                # Simulate user confirming
                result = cli_runner.invoke(cli, ["adapters", "clean"], input="y\n")
                assert result.exit_code == 0
                mock_build_manager.clean_adapter_cache.assert_called_once_with(
                    user_only=False,
                )

    def test_clean_cache_abort(self, cli_runner, mock_repo_root, mock_build_manager):
        """Test aborting cache cleaning."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                # Simulate user aborting
                result = cli_runner.invoke(cli, ["adapters", "clean"], input="n\n")
                assert result.exit_code == 1
                mock_build_manager.clean_adapter_cache.assert_not_called()

    def test_clean_user_only(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
    ):
        """Test cleaning only user cache."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                result = cli_runner.invoke(
                    cli,
                    ["adapters", "clean", "--user-only"],
                    input="y\n",
                )
                assert result.exit_code == 0
                mock_build_manager.clean_adapter_cache.assert_called_once_with(
                    user_only=True,
                )

    def test_adapter_status(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
        mock_adapter_downloader,
    ):
        """Test showing adapter status."""
        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.commands.adapters.AdapterDownloader",
                return_value=mock_adapter_downloader,
            ):
                result = cli_runner.invoke(cli, ["adapters", "status"])
                assert result.exit_code == 0
                assert "Installed Debug Adapters:" in result.output
                assert "python" in result.output
                assert "javascript" in result.output
                assert "java" in result.output
                assert "Total: 3 adapters installed" in result.output
                mock_adapter_downloader.list_installed_adapters.assert_called_once()

    def test_adapter_status_no_adapters(
        self,
        cli_runner,
        mock_repo_root,
        mock_build_manager,
    ):
        """Test status when no adapters are installed."""
        # Create a mock downloader that returns empty dict
        mock_empty_downloader = Mock()
        mock_empty_downloader.list_installed_adapters.return_value = {}

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.commands.adapters.AdapterDownloader",
                return_value=mock_empty_downloader,
            ):
                result = cli_runner.invoke(cli, ["adapters", "status"])
                assert result.exit_code == 0
                assert "No runtime debug adapters are installed" in result.output
                assert "download --install" in result.output

    def test_adapter_help(self, cli_runner):
        """Test adapter command help text."""
        result = cli_runner.invoke(cli, ["adapters", "--help"])
        assert result.exit_code == 0
        assert "Debug adapter management commands" in result.output
        assert "build" in result.output
        assert "list" in result.output
        assert "info" in result.output
        assert "download" in result.output
        assert "clean" in result.output
        assert "status" in result.output
