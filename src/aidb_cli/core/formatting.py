"""CLI output formatting utilities with contextual emojis and smart tables."""

import shutil

import click

from aidb_cli.core.constants import Icons


class HeadingFormatter:
    """Utility for consistent CLI heading formatting with contextual emojis."""

    SEPARATOR_LENGTH = 60  # Fallback if terminal width unavailable

    @staticmethod
    def _get_separator_width() -> int:
        """Get dynamic separator width based on terminal width.

        Returns
        -------
        int
            Terminal width - 2 (for margins), or fallback to 60
        """
        try:
            terminal_size = shutil.get_terminal_size()
            return max(40, terminal_size.columns - 2)  # Minimum 40, max term_width - 2
        except Exception:
            # Fallback if terminal width unavailable (non-TTY, etc.)
            return HeadingFormatter.SEPARATOR_LENGTH

    @staticmethod
    def process(message: str, icon: str | None = None) -> None:
        """Format and display process action heading.

        Parameters
        ----------
        message : str
            Process message (e.g., "Cleaning up Docker resources...")
        icon : str, optional
            Custom icon to use (defaults to appropriate process icon)
        """
        if icon is None:
            icon = HeadingFormatter._get_process_icon(message)
        click.echo(f"{icon} {message}")

    @staticmethod
    def section(title: str, icon: str | None = None) -> None:
        """Format and display section heading with separator.

        Parameters
        ----------
        title : str
            Section title (e.g., "Test Suites")
        icon : str, optional
            Custom icon to use (defaults to section icon)
        """
        if icon is None:
            icon = HeadingFormatter._get_section_icon(title)

        width = HeadingFormatter._get_separator_width()
        click.echo("-" * width)
        click.echo(f"{icon} {title}:")
        click.echo("-" * width)

    @staticmethod
    def subsection(title: str, icon: str | None = None) -> None:
        """Format and display subsection heading without separator.

        Parameters
        ----------
        title : str
            Subsection title (e.g., "Configuration Loading Priority")
        icon : str, optional
            Custom icon to use (defaults to subsection icon)
        """
        if icon is None:
            icon = HeadingFormatter._get_subsection_icon(title)

        click.echo(f"\n{icon} {title}:")

    @staticmethod
    def table_header(title: str, icon: str | None = None) -> None:
        """Format and display table header without bottom separator.

        Use this when you need to add column headers before the data.

        Parameters
        ----------
        title : str
            Table title
        icon : str, optional
            Custom icon to use
        """
        if icon is None:
            icon = HeadingFormatter._get_section_icon(title)

        width = HeadingFormatter._get_separator_width()
        click.echo("-" * width)
        click.echo(f"{icon} {title}:")
        click.echo("-" * width)

    @staticmethod
    def table_separator() -> None:
        """Display table separator line."""
        width = HeadingFormatter._get_separator_width()
        click.echo("-" * width)

    @staticmethod
    def table(
        title: str,
        columns: list[tuple[str, int]],
        icon: str | None = None,
        has_icons: bool = True,
    ) -> None:
        """Format and display table with manual column widths.

        Parameters
        ----------
        title : str
            Table title
        columns : list[tuple[str, int]]
            List of (column_name, width) tuples
        icon : str, optional
            Custom icon to use
        has_icons : bool
            Whether data rows will have icons (adds spacing to header)
        """
        if icon is None:
            icon = HeadingFormatter._get_section_icon(title)

        width = HeadingFormatter._get_separator_width()
        click.echo("-" * width)
        click.echo(f"{icon} {title}:")
        click.echo("-" * width)

        # Build header with proper spacing for icons
        header_parts = []
        for i, (col_name, col_width) in enumerate(columns):
            if i == 0 and has_icons:
                # First column gets icon spacing (3 spaces: icon + space)
                header_parts.append(f"   {col_name:<{col_width - 1}}")
            else:
                # Other columns normal spacing
                header_parts.append(f"{col_name:<{col_width}}")

        click.echo("".join(header_parts).rstrip())
        click.echo("-" * width)

    @staticmethod
    def auto_table(
        title: str,
        data: list[dict],
        column_order: list[str],
        icon: str | None = None,
        has_icons: bool = True,
        min_padding: int = 2,
    ) -> dict[str, int]:
        """Auto-format table header with calculated column widths.

        Parameters
        ----------
        title : str
            Table title
        data : list[dict]
            Data rows to analyze for width calculation
        column_order : list[str]
            Order of columns to display
        icon : str, optional
            Custom icon to use
        has_icons : bool
            Whether data rows will have icons
        min_padding : int
            Minimum padding to add to each column

        Returns
        -------
        dict[str, int]
            Width map for caller to use in data formatting
        """
        # Calculate optimal widths from data + headers
        widths = {}
        for col in column_order:
            # Start with header width
            widths[col] = len(col)
            # Check all data values
            for row in data:
                value_str = str(row.get(col, ""))
                widths[col] = max(widths[col], len(value_str))
            # Add padding
            widths[col] += min_padding

        # Generate columns list and display header
        columns = [(col, widths[col]) for col in column_order]
        HeadingFormatter.table(title, columns, icon, has_icons)

        return widths

    @staticmethod
    def discovery(message: str) -> None:
        """Format and display discovery/search heading.

        Parameters
        ----------
        message : str
            Discovery message (e.g., "Discovering tests...")
        """
        click.echo(f"{Icons.SEARCH} {message}")

    @staticmethod
    def status(message: str, icon: str | None = None) -> None:
        """Format and display status heading.

        Parameters
        ----------
        message : str
            Status message
        icon : str, optional
            Custom icon to use (defaults to status icon)
        """
        if icon is None:
            icon = Icons.PROCESS
        click.echo(f"{icon} {message}")

    @staticmethod
    def _get_process_icon(message: str) -> str:
        """Get appropriate process icon based on message content."""
        message_lower = message.lower()

        if any(word in message_lower for word in ["clean", "cleanup", "removing"]):
            return Icons.CLEAN
        if any(word in message_lower for word in ["build", "building"]):
            return Icons.BUILD
        if any(word in message_lower for word in ["test", "testing", "running tests"]):
            return Icons.TEST
        if any(word in message_lower for word in ["install", "installing", "download"]):
            return Icons.PACKAGE
        if any(word in message_lower for word in ["start", "starting"]):
            return Icons.ROCKET
        if any(word in message_lower for word in ["config", "configur"]):
            return Icons.CONFIG
        return Icons.PROCESS

    @staticmethod
    def _get_section_icon(title: str) -> str:
        """Get appropriate section icon based on title."""
        title_lower = title.lower()

        if any(word in title_lower for word in ["marker", "markers"]):
            return Icons.MARKERS
        if any(word in title_lower for word in ["suite", "suites", "list"]):
            return Icons.LIST
        if any(word in title_lower for word in ["pattern", "example"]):
            return Icons.TARGET
        if any(word in title_lower for word in ["report", "result"]):
            return Icons.REPORT
        return Icons.LIST

    @staticmethod
    def _get_subsection_icon(title: str) -> str:
        """Get appropriate subsection icon based on title."""
        title_lower = title.lower()

        if any(word in title_lower for word in ["config", "configuration"]):
            return Icons.GEAR
        if any(word in title_lower for word in ["version", "versions"]):
            return Icons.PACKAGE
        if any(word in title_lower for word in ["metadata", "information", "info"]):
            return Icons.INFO
        if any(word in title_lower for word in ["coverage", "report"]):
            return Icons.TARGET
        if any(word in title_lower for word in ["priority", "loading"]):
            return Icons.ARROW_RIGHT
        if any(word in title_lower for word in ["service", "logs"]):
            return Icons.DOCKER
        return Icons.ARROW_RIGHT
