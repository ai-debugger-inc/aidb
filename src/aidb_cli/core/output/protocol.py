"""Protocol definition for OutputStrategy (for testing/mocking)."""

from typing import Protocol, runtime_checkable

from aidb_cli.core.output.verbosity import Verbosity


@runtime_checkable
class OutputStrategyProtocol(Protocol):
    """Protocol for CLI output strategies.

    This protocol defines the interface for output handling in the CLI.
    Implementations must respect the verbosity contracts:

    | Method     | NORMAL | VERBOSE | DEBUG |
    |------------|--------|---------|-------|
    | error      | Yes    | Yes     | Yes   |
    | warning    | Yes    | Yes     | Yes   |
    | success    | Yes    | Yes     | Yes   |
    | result     | Yes    | Yes     | Yes   |
    | plain      | Yes    | Yes     | Yes   |
    | section    | Yes    | Yes     | Yes   |
    | subsection | Yes    | Yes     | Yes   |
    | info       | No     | Yes     | Yes   |
    | detail     | No     | Yes     | Yes   |
    | debug      | No     | No      | Yes   |
    """

    @property
    def verbosity(self) -> Verbosity:
        """Current verbosity level."""
        ...

    @property
    def is_tty(self) -> bool:
        """Whether output is to a TTY."""
        ...

    @property
    def is_ci(self) -> bool:
        """Whether running in CI environment."""
        ...

    def error(self, message: str, to_stderr: bool = True) -> None:
        """Display error message (red).

        Always visible.
        """
        ...

    def warning(self, message: str) -> None:
        """Display warning message (yellow).

        Always visible.
        """
        ...

    def success(self, message: str) -> None:
        """Display success message (green).

        Always visible.
        """
        ...

    def result(self, message: str) -> None:
        """Display result/output.

        Always visible.
        """
        ...

    def plain(self, message: str, err: bool = False) -> None:
        """Display plain message without formatting.

        Always visible.
        """
        ...

    def section(self, title: str, icon: str | None = None) -> None:
        """Display section heading with separator.

        Always visible.
        """
        ...

    def subsection(self, title: str, icon: str | None = None) -> None:
        """Display subsection heading.

        Always visible.
        """
        ...

    def info(self, message: str) -> None:
        """Display info message.

        Visible at VERBOSE+.
        """
        ...

    def detail(self, message: str) -> None:
        """Display operational detail.

        Visible at VERBOSE+.
        """
        ...

    def debug(self, message: str) -> None:
        """Display debug message.

        Visible at DEBUG only.
        """
        ...

    def should_stream(self) -> bool:
        """Determine if subprocess output should be streamed."""
        ...
