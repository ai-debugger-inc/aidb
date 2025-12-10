"""CLI-specific test configuration and fixtures.

This module provides fixtures and configuration specific to CLI testing, ensuring
complete isolation from core AIDB dependencies.

Note: Fixtures from _fixtures/base, _fixtures/docker_simple, and _fixtures/mcp are
available through the root conftest.py which already imports them.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from aidb_common.constants import SUPPORTED_LANGUAGES
from aidb_common.discovery import get_supported_languages


def _get_test_languages() -> list[str]:
    """Get supported languages with fallback for tests."""
    try:
        languages = get_supported_languages()
        return languages if languages else SUPPORTED_LANGUAGES
    except Exception:
        # Fallback if registry is not available during testing
        return SUPPORTED_LANGUAGES


@pytest.fixture
def cli_runner():
    """Provide Click CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def mock_repo_root(tmp_path):
    """Provide a mocked repository root."""
    return tmp_path


@pytest.fixture
def mock_build_manager():
    """Provide a mocked BuildManager instance."""
    manager = Mock()

    # Get dynamic language list for realistic testing
    test_languages = _get_test_languages()

    # Configure common methods used in tests
    manager.get_supported_languages.return_value = test_languages

    # check_adapters_built should return two separate lists: built and missing
    # Assume first language is built, rest are missing for test variety
    built_langs = test_languages[:1] if test_languages else []
    missing_langs = test_languages[1:] if len(test_languages) > 1 else []

    manager.check_adapters_built.return_value = (
        built_langs,  # built list
        missing_langs,  # missing list
    )

    # Create cache paths using .cache directory structure
    adapter_paths = {}
    download_paths = {}
    for i, lang in enumerate(test_languages):
        cache_path = Path(f"/.cache/adapters/{lang}")
        # First language has adapter built, others don't
        adapter_paths[lang] = cache_path if i == 0 else None
        # All languages can be downloaded
        download_paths[lang] = cache_path

    manager.find_all_adapters.return_value = adapter_paths
    manager.download_all_adapters.return_value = download_paths

    # Mock methods that need to be callable
    manager.list_adapters = Mock()
    manager.build_adapters = Mock()
    manager.clean_adapter_cache = Mock()
    manager.get_adapter_info = Mock()

    return manager


@pytest.fixture
def mock_adapter_downloader():
    """Provide a mocked AdapterDownloader instance."""
    downloader = Mock()

    # Get dynamic language list for realistic testing
    test_languages = _get_test_languages()

    # Create a mock result object for download_adapter
    mock_result = Mock()
    mock_result.success = True
    mock_result.status = "downloaded"
    mock_result.message = "Successfully downloaded javascript debug adapter"
    mock_result.path = Path("/.cache/adapters/test")
    mock_result.instructions = None
    downloader.download_adapter.return_value = mock_result

    # Create dynamic download and installed adapter data for download_all_adapters
    download_data = {}
    installed_data = {}
    for lang in test_languages:
        cache_path = Path(f"/.cache/adapters/{lang}")
        # Each result should be a result object for download_all_adapters
        result_obj = Mock()
        result_obj.success = True
        result_obj.status = "downloaded"
        result_obj.message = f"Successfully downloaded {lang} debug adapter"
        result_obj.path = cache_path
        download_data[lang] = result_obj

        installed_data[lang] = {
            "version": "1.0.0",
            "path": cache_path,
        }

    downloader.download_all_adapters.return_value = download_data
    downloader.list_installed_adapters.return_value = installed_data

    return downloader


@pytest.fixture
def cli_context_mock():
    """Helper for mocking CLI context and build manager properly."""
    from unittest.mock import PropertyMock

    def _mock_cli_command(cli_runner, mock_repo_root, mock_build_manager, command_args):
        """Execute CLI command with proper mocking context."""
        from aidb_cli.cli import cli

        with patch(
            "aidb_common.repo.detect_repo_root",
            return_value=mock_repo_root,
        ):
            with patch(
                "aidb_cli.cli.Context.build_manager",
                new_callable=PropertyMock,
                return_value=mock_build_manager,
            ):
                return cli_runner.invoke(cli, command_args)

    return _mock_cli_command
