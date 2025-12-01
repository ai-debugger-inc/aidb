"""Default output strategy implementation."""

from __future__ import annotations

import shutil

import click

from aidb_cli.core.output.verbosity import Verbosity


class OutputStrategy:
    """Unified output strategy with verbosity contracts.

    This class is the single source of truth for all CLI output decisions.
    It provides verbosity-aware output methods that respect the contracts:

    | Level    | Flag      | User Sees                           | Streaming |
    |----------|-----------|-------------------------------------|-----------|
    | NORMAL   | (default) | Progress, results, errors, warnings | No        |
    | VERBOSE  | -v        | + Operation details, step-by-step   | TTY only  |
    | DEBUG    | -vvv      | + Full subprocess output, traces    | TTY only  |

    Parameters
    ----------
    verbosity : Verbosity
        Current verbosity level
    is_tty : bool | None
        Whether output is to a TTY (auto-detected if None)
    is_ci : bool | None
        Whether running in CI environment (auto-detected if None)
    """

    def __init__(
        self,
        verbosity: Verbosity = Verbosity.NORMAL,
        is_tty: bool | None = None,
        is_ci: bool | None = None,
    ) -> None:
        self._verbosity = verbosity
        self._is_tty = is_tty if is_tty is not None else self._detect_tty()
        self._is_ci = is_ci if is_ci is not None else self._detect_ci()
        self._last_was_blank = False  # Track for blank line coalescing

    @property
    def verbosity(self) -> Verbosity:
        """Current verbosity level."""
        return self._verbosity

    @property
    def is_tty(self) -> bool:
        """Whether output is to a TTY."""
        return self._is_tty

    @property
    def is_ci(self) -> bool:
        """Whether running in CI environment."""
        return self._is_ci

    def _emit(
        self,
        message: str,
        *,
        err: bool = False,
        style: dict | None = None,
    ) -> None:
        """Emit a message with optional styling and blank line coalescing.

        Parameters
        ----------
        message : str
            Message to emit
        err : bool
            Whether to output to stderr
        style : dict | None
            Click style kwargs (fg, bold, etc.)
        """
        # Coalesce consecutive blank lines
        if not message or message.strip() == "":
            if self._last_was_blank:
                return
            click.echo("", err=err)
            self._last_was_blank = True
            return

        # Non-blank: format and emit
        rendered = click.style(message, **style) if style else message
        click.echo(rendered, err=err)
        self._last_was_blank = False

    def error(self, message: str, to_stderr: bool = True) -> None:
        """Display error message (red). Always visible.

        Parameters
        ----------
        message : str
            Error message
        to_stderr : bool
            Whether to send to stderr (default: True)
        """
        from aidb_cli.core.constants import Icons

        self._emit(f"{Icons.ERROR} {message}", err=to_stderr, style={"fg": "red"})

    def warning(self, message: str) -> None:
        """Display warning message (yellow). Always visible.

        Parameters
        ----------
        message : str
            Warning message
        """
        self._emit(message, style={"fg": "yellow"})

    def success(self, message: str) -> None:
        """Display success message (green). Always visible.

        Parameters
        ----------
        message : str
            Success message
        """
        self._emit(message, style={"fg": "green"})

    def result(self, message: str) -> None:
        """Display result/output. Always visible.

        Parameters
        ----------
        message : str
            Result message
        """
        self._emit(message)

    def plain(self, message: str, err: bool = False) -> None:
        """Display plain message without formatting. Always visible.

        Parameters
        ----------
        message : str
            Plain message
        err : bool
            Whether to send to stderr
        """
        self._emit(message, err=err)

    def section(self, title: str, icon: str | None = None) -> None:
        """Display section heading with separator. Always visible.

        Parameters
        ----------
        title : str
            Section title
        icon : str | None
            Optional icon to display
        """
        width = self._get_separator_width()
        icon_prefix = f"{icon} " if icon else ""
        click.echo("-" * width)
        click.echo(f"{icon_prefix}{title}:")
        click.echo("-" * width)
        self._last_was_blank = False

    def subsection(self, title: str, icon: str | None = None) -> None:
        """Display subsection heading. Always visible.

        Parameters
        ----------
        title : str
            Subsection title
        icon : str | None
            Optional icon to display
        """
        icon_prefix = f"{icon} " if icon else ""
        click.echo(f"\n{icon_prefix}{title}:")
        self._last_was_blank = False

    def info(self, message: str) -> None:
        """Display info message. Visible at VERBOSE+.

        Parameters
        ----------
        message : str
            Info message
        """
        if self._verbosity >= Verbosity.VERBOSE:
            self._emit(message)

    def detail(self, message: str) -> None:
        """Display operational detail (dimmed). Visible at VERBOSE+.

        Parameters
        ----------
        message : str
            Detail message
        """
        if self._verbosity >= Verbosity.VERBOSE:
            self._emit(f"  {message}", style={"dim": True})

    def debug(self, message: str) -> None:
        """Display debug message (cyan). Visible at DEBUG only.

        Parameters
        ----------
        message : str
            Debug message
        """
        if self._verbosity >= Verbosity.DEBUG:
            self._emit(f"[DEBUG] {message}", style={"fg": "cyan"})

    def should_stream(self) -> bool:
        """Determine if subprocess output should be streamed.

        Streaming is enabled when:
        - Verbosity is VERBOSE or DEBUG (user wants to see output)
        - Not in CI environment (CI output is too noisy)
        - Running in TTY mode (can use ANSI escape codes)

        Returns
        -------
        bool
            True if streaming should be enabled
        """
        if self._verbosity < Verbosity.VERBOSE:
            return False
        if self._is_ci:
            return False
        return self._is_tty

    def separator(self, char: str = "=", length: int | None = None) -> None:
        """Display separator line. Always visible.

        Parameters
        ----------
        char : str
            Character to use for separator
        length : int | None
            Length of separator (defaults to terminal width)
        """
        if length is None:
            length = self._get_separator_width()
        click.echo(char * length)
        self._last_was_blank = False

    def _get_separator_width(self) -> int:
        """Get dynamic separator width based on terminal width.

        Returns
        -------
        int
            Terminal width - 2 (for margins), minimum 40
        """
        try:
            terminal_size = shutil.get_terminal_size()
            return max(40, terminal_size.columns - 2)
        except Exception:
            return 60

    @staticmethod
    def _detect_tty() -> bool:
        """Detect if stdout is a TTY.

        Returns
        -------
        bool
            True if stdout is a TTY
        """
        import sys

        return sys.stdout.isatty()

    @staticmethod
    def _detect_ci() -> bool:
        """Detect if running in CI/CD environment.

        Returns
        -------
        bool
            True if CI environment detected
        """
        import os

        from aidb_cli.core.constants import EnvVars

        return any(os.environ.get(v) for v in EnvVars.CI_ENVIRONMENT_VARS)

    @classmethod
    def from_click_context(cls, ctx: click.Context) -> OutputStrategy:
        """Create OutputStrategy from Click context.

        Parameters
        ----------
        ctx : click.Context
            Click context

        Returns
        -------
        OutputStrategy
            Output strategy configured from context
        """
        aidb_ctx = ctx.obj
        verbose = getattr(aidb_ctx, "verbose", False) if aidb_ctx else False
        verbose_debug = getattr(aidb_ctx, "verbose_debug", False) if aidb_ctx else False
        verbosity = Verbosity.from_flags(verbose, verbose_debug)
        return cls(verbosity=verbosity)
