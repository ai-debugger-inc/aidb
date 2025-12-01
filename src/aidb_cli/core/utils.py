"""Utility functions for AIDB CLI."""

import sys
from pathlib import Path

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons
from aidb_common.repo import detect_repo_root
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


def format_success(msg: str) -> str:
    """Format a success message with green color.

    Parameters
    ----------
    msg : str
        Message to format

    Returns
    -------
    str
        Formatted message
    """
    return click.style(msg, fg="green")


def format_error(msg: str) -> str:
    """Format an error message with red color and icon.

    Parameters
    ----------
    msg : str
        Message to format

    Returns
    -------
    str
        Formatted message
    """
    return click.style(f"{Icons.ERROR} {msg}", fg="red")


def format_warning(msg: str) -> str:
    """Format a warning message with yellow color.

    Parameters
    ----------
    msg : str
        Message to format

    Returns
    -------
    str
        Formatted message
    """
    return click.style(msg, fg="yellow")


def format_info(msg: str) -> str:
    """Format an info message.

    Parameters
    ----------
    msg : str
        Message to format

    Returns
    -------
    str
        Formatted message
    """
    return msg


class CliOutput:
    """Unified CLI output utility with consistent formatting.

    Coalesces consecutive blank lines to a single blank line to keep console output tidy
    without changing call sites.
    """

    # Track whether the last emitted line was blank
    _last_was_blank: bool = False

    @staticmethod
    def _emit(message: str, *, err: bool = False, formatter=None) -> None:
        # Coalesce consecutive blank lines
        if not message or message.strip() == "":
            if CliOutput._last_was_blank:
                return
            click.echo("", err=err)
            CliOutput._last_was_blank = True
            return

        # Non-blank: format (if provided) and emit
        rendered = formatter(message) if formatter else message
        click.echo(rendered, err=err)
        CliOutput._last_was_blank = False

    @staticmethod
    def success(message: str) -> None:
        """Echo success message in green color.

        Parameters
        ----------
        message : str
            Message to echo
        """
        CliOutput._emit(message, formatter=format_success)

    @staticmethod
    def error(message: str, err: bool = True) -> None:
        """Echo error message with red X to stderr by default.

        Parameters
        ----------
        message : str
            Message to echo
        err : bool
            Whether to send to stderr (default: True)
        """
        CliOutput._emit(message, err=err, formatter=format_error)

    @staticmethod
    def warning(message: str) -> None:
        """Echo warning message in yellow color.

        Parameters
        ----------
        message : str
            Message to echo
        """
        CliOutput._emit(message, formatter=format_warning)

    @staticmethod
    def info(message: str) -> None:
        """Echo info message in blue color.

        Parameters
        ----------
        message : str
            Message to echo
        """
        CliOutput._emit(message, formatter=format_info)

    @staticmethod
    def plain(message: str, err: bool = False) -> None:
        """Echo plain message without icon.

        Parameters
        ----------
        message : str
            Message to echo
        err : bool
            Whether to send to stderr (default: False)
        """
        CliOutput._emit(message, err=err)

    @staticmethod
    def separator(char: str = "=", length: int | None = None) -> None:
        """Echo separator line.

        Parameters
        ----------
        char : str
            Character to use for separator (default: "=")
        length : int, optional
            Length of separator line (default: terminal width - 2)
        """
        from aidb_cli.core.formatting import HeadingFormatter

        if length is None:
            length = HeadingFormatter._get_separator_width()
        click.echo(char * length)


def find_repo_root(start_path: Path | None = None) -> Path:
    """Find the repository root directory.

    Parameters
    ----------
    start_path : Path, optional
        Path to start searching from, defaults to current directory

    Returns
    -------
    Path
        Repository root path
    """
    return detect_repo_root(start_path)


def ensure_venv_active() -> bool:
    """Check if virtual environment is active.

    Returns
    -------
    bool
        True if venv is active
    """
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def get_venv_path(repo_root: Path) -> Path:
    """Get the path to the virtual environment.

    Parameters
    ----------
    repo_root : Path
        Repository root directory

    Returns
    -------
    Path
        Virtual environment path
    """
    return repo_root / "venv"


def validate_path_exists(path: Path, error_msg: str | None = None) -> None:
    """Validate that a path exists.

    Parameters
    ----------
    path : Path
        Path to validate
    error_msg : str, optional
        Custom error message

    Raises
    ------
    AidbError
        If path does not exist
    """
    if not path.exists():
        msg = error_msg or f"Path does not exist: {path}"
        raise AidbError(msg)
