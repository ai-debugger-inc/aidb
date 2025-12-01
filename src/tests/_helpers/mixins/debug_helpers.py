"""Debug session management helpers for integration tests."""

from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Optional


class DebugSessionMixin:
    """Mixin providing debug session management utilities."""

    @asynccontextmanager
    async def managed_debug_session(
        self,
        start_session_func,
        stop_session_func,
        target: str | None = None,
        language: str = "python",
        breakpoints: list[str] | None = None,
        **kwargs,
    ):
        """Create context manager for debug sessions with automatic cleanup.

        Parameters
        ----------
        start_session_func : callable
            Function to start the session
        stop_session_func : callable
            Function to stop the session
        target : str, optional
            File to debug
        language : str
            Programming language
        breakpoints : List[str], optional
            Initial breakpoints
        **kwargs
            Additional session arguments

        Yields
        ------
        Tuple[str, Dict[str, Any]]
            Session ID and session data
        """
        session_id = None
        try:
            # Start session
            session_id, response = await start_session_func(
                target=target,
                language=language,
                breakpoints=breakpoints,
                **kwargs,
            )

            yield session_id, response

        finally:
            # Always clean up session
            if session_id:
                with suppress(Exception):
                    # Ignore cleanup errors
                    await stop_session_func(session_id)

    async def setup_debug_environment(
        self,
        temp_dir: Path,
        language: str = "python",
        scenario: str = "calculate_function",
        with_breakpoints: bool = True,
    ) -> dict[str, Any]:
        """Set up a complete debugging environment for any language.

        Parameters
        ----------
        temp_dir : Path
            Temporary directory
        language : str
            Programming language
        scenario : str
            Test scenario name
        with_breakpoints : bool
            Whether to suggest breakpoints

        Returns
        -------
        Dict[str, Any]
            Debug setup information
        """
        from tests._assets.test_content import get_breakpoint_lines, get_test_content

        # Determine file extension
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "java": ".java",
            "typescript": ".ts",
        }
        ext = extensions.get(language, ".txt")

        # Create test file (assuming FileTestMixin is available)
        if hasattr(self, "create_test_file"):
            test_file = self.create_test_file(
                temp_dir / f"test_debug{ext}",
                language=language,
                scenario=scenario,
            )
        else:
            # Fallback if mixin not available
            test_file = temp_dir / f"test_debug{ext}"
            test_file.parent.mkdir(parents=True, exist_ok=True)
            content = get_test_content(language, scenario)
            test_file.write_text(content)

        # Get breakpoint info
        bp_info = get_breakpoint_lines(language, scenario) if with_breakpoints else {}

        return {
            "file": test_file,
            "language": language,
            "scenario": scenario,
            "breakpoints": bp_info.get("lines", []),
            "breakpoint_descriptions": bp_info.get("descriptions", []),
            "workspace": temp_dir,
        }

    def format_breakpoint_location(
        self,
        file_path: Path,
        line: int,
        column: int | None = None,
    ) -> str:
        """Format a breakpoint location string.

        Parameters
        ----------
        file_path : Path
            File path
        line : int
            Line number
        column : int, optional
            Column number

        Returns
        -------
        str
            Formatted location string
        """
        if column:
            return f"{file_path}:{line}:{column}"
        return f"{file_path}:{line}"

    def parse_breakpoint_location(
        self,
        location: str,
    ) -> tuple[str, int, int | None]:
        """Parse a breakpoint location string.

        Parameters
        ----------
        location : str
            Location string (file:line or file:line:column)

        Returns
        -------
        Tuple[str, int, Optional[int]]
            File path, line number, and optional column
        """
        parts = location.split(":")

        if len(parts) == 2:
            return parts[0], int(parts[1]), None
        if len(parts) == 3:
            return parts[0], int(parts[1]), int(parts[2])
        msg = f"Invalid breakpoint location format: {location}"
        raise ValueError(msg)
