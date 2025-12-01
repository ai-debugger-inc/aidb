"""Fixtures for CLI unit tests."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide Click CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def mock_repo_root(tmp_path):
    """Provide a mocked repository root."""
    return tmp_path


@pytest.fixture(autouse=True)
def auto_mock_repo_root(tmp_path):
    """Automatically mock detect_repo_root for all CLI unit tests.

    This ensures the CLI context is properly initialized with a valid repo root. Without
    this, ctx.obj would be None when commands try to access it.
    """
    with patch("aidb_common.repo.detect_repo_root", return_value=tmp_path):
        yield tmp_path


@pytest.fixture
def mock_output():
    """Provide a mock OutputStrategy for testing helper functions.

    This mock captures output to stdout/stderr through click.echo-like behavior.
    """
    mock = Mock()

    # Configure mock methods to write to stdout/stderr via click.echo
    def make_echo_side_effect(is_err=False):
        def side_effect(msg):
            import click

            click.echo(msg, err=is_err)

        return side_effect

    mock.plain.side_effect = make_echo_side_effect(is_err=False)
    mock.success.side_effect = make_echo_side_effect(is_err=False)
    mock.warning.side_effect = make_echo_side_effect(is_err=False)
    mock.error.side_effect = make_echo_side_effect(is_err=True)
    mock.info.side_effect = make_echo_side_effect(is_err=False)
    mock.debug.side_effect = make_echo_side_effect(is_err=False)
    mock.section.side_effect = lambda title, icon="": make_echo_side_effect()(
        f"{icon} {title}" if icon else title,
    )
    mock.subsection.side_effect = lambda title, icon="": make_echo_side_effect()(
        f"  {icon} {title}" if icon else f"  {title}",
    )

    return mock
