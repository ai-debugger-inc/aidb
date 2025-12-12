"""Code context extraction utilities for debugging sessions."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from aidb.patterns.base import Obj
from aidb_common.config import config

if TYPE_CHECKING:
    from aidb.adapters.base.source_path_resolver import SourcePathResolver
    from aidb.common import AidbContext


class CodeContextResult(TypedDict):
    """Result of code context extraction.

    Attributes
    ----------
    lines : list[tuple[int, str]]
        List of (line_number, text) tuples for context lines
    current_line : int
        The target line number that was requested
    formatted : str
        Pre-formatted string representation for display
    """

    lines: list[tuple[int, str]]
    current_line: int
    formatted: str


class CodeContext(Obj):
    """Utility for extracting code context around specific lines."""

    def __init__(
        self,
        ctx: "AidbContext | None" = None,
        source_paths: list[str] | None = None,
        source_path_resolver: "SourcePathResolver | None" = None,
    ):
        """Initialize code context extractor.

        Parameters
        ----------
        ctx : AidbContext, optional
            Application context for logging and configuration access
        source_paths : list[str], optional
            Additional source directories to search when resolving file paths.
            Used for remote debugging where debug adapter returns paths that
            don't exist locally (e.g., JAR-internal paths like
            'trino-main.jar!/io/trino/Foo.java').
        source_path_resolver : SourcePathResolver, optional
            Language-specific source path resolver for mapping debug adapter
            paths to local source files. If not provided, falls back to
            simple filename matching.
        """
        super().__init__(ctx)
        self.source_paths = source_paths or []
        self.source_path_resolver = source_path_resolver

    def extract_context(
        self,
        file_path: str,
        line: int,
        column: int | None = None,
        breadth: int | None = None,
    ) -> CodeContextResult:
        """Extract code context around a line.

        Parameters
        ----------
        file_path : str
            Path to the source file
        line : int
            Target line number (1-indexed)
        column : Optional[int]
            Target column number (1-indexed), used for minified files
        breadth : Optional[int]
            Number of lines to show before/after target line.
            If None, uses AIDB_CODE_CONTEXT_LINES config (default: 5)

        Returns
        -------
        CodeContextResult
            Dictionary containing lines, current_line, and formatted output
        """
        if breadth is None:
            breadth = config.get_code_context_lines()

        self.ctx.logger.debug(
            "Extracting code context for %s:%s (column=%s, breadth=%s)",
            file_path,
            line,
            column,
            breadth,
        )

        # Check if we should use minified handling
        minified_mode = config.get_code_context_minified_mode()
        is_minified = False

        if minified_mode == "force":
            is_minified = True
        elif minified_mode == "auto":
            is_minified = self._is_likely_minified(file_path)
        # minified_mode == "disable" keeps is_minified = False

        self.ctx.logger.debug(
            "Minified mode: %s, is_minified: %s",
            minified_mode,
            is_minified,
        )

        try:
            path = Path(file_path)
            resolved_path: Path | None = None

            if path.exists():
                resolved_path = path
            else:
                # Try to resolve via source paths for remote debugging scenarios
                resolved_path = self._resolve_from_source_paths(file_path)

            if not resolved_path:
                # Suppress warning for node_internals (virtual paths that never exist)
                if not file_path.startswith("<node_internals>"):
                    self.ctx.logger.warning("File not found: %s", file_path)
                return CodeContextResult(
                    lines=[],
                    current_line=line,
                    formatted=f"File not found: {file_path}",
                )

            # Use the resolved path for file operations
            path = resolved_path

            with path.open(encoding="utf-8") as f:
                all_lines = f.readlines()

            self.ctx.logger.debug(
                "Loaded %d lines from %s",
                len(all_lines),
                file_path,
            )

            # Convert to 0-indexed for array access
            target_idx = line - 1

            # Calculate range
            start_idx = max(0, target_idx - breadth)
            end_idx = min(len(all_lines), target_idx + breadth + 1)

            self.ctx.logger.debug(
                "Context range: lines %d-%d (target: %d)",
                start_idx + 1,
                end_idx,
                line,
            )

            # Extract context lines with line numbers
            context_lines = []
            max_line_width = config.get_code_context_max_width()
            truncated_lines = 0

            for i in range(start_idx, end_idx):
                line_num = i + 1  # Convert back to 1-indexed
                line_text = all_lines[i].rstrip("\n\r")

                # Apply smart truncation for long lines or minified files
                if is_minified or len(line_text) > max_line_width:
                    target_col = column if line_num == line else None
                    original_length = len(line_text)
                    line_text = self._format_long_line(line_text, target_col)
                    if len(line_text) < original_length:
                        truncated_lines += 1

                context_lines.append((line_num, line_text))

            if truncated_lines > 0:
                self.ctx.logger.debug(
                    "Truncated %d lines for display (max_width=%d)",
                    truncated_lines,
                    max_line_width,
                )

            # Format for display
            formatted = self._format_context(
                context_lines,
                line,
                file_path,
                column,
                is_minified,
            )

            self.ctx.logger.debug(
                "Successfully extracted context: %d lines, %s mode",
                len(context_lines),
                "minified" if is_minified else "normal",
            )

            return CodeContextResult(
                lines=context_lines,
                current_line=line,
                formatted=formatted,
            )

        except (OSError, UnicodeDecodeError) as e:
            self.ctx.logger.error(
                "Error reading file %s: %s",
                file_path,
                e,
            )
            return CodeContextResult(
                lines=[],
                current_line=line,
                formatted=f"Error reading {file_path}: {e}",
            )

    def _format_context(
        self,
        context_lines: list[tuple[int, str]],
        target_line: int,
        file_path: str,
        target_column: int | None = None,
        is_minified: bool = False,
    ) -> str:
        """Format context lines for display.

        Parameters
        ----------
        context_lines : list[tuple[int, str]]
            List of (line_number, text) tuples
        target_line : int
            The target line to highlight
        file_path : str
            Path to the file for header
        target_column : Optional[int]
            The target column to highlight (for minified files)
        is_minified : bool
            Whether this is a minified file

        Returns
        -------
        str
            Formatted string with line numbers and target line indicator
        """
        if not context_lines:
            return f"No context available for {file_path}:{target_line}"

        # Determine width for line number padding
        max_line_num = max(line_num for line_num, _ in context_lines)
        line_width = len(str(max_line_num))

        # Create header with minified indicator
        file_header = f"File: {file_path}"
        if is_minified:
            file_header += " (minified)"

        lines = [file_header]

        # Add column information for minified files
        if is_minified and target_column is not None:
            lines.append(f"Line {target_line}, Column {target_column}:")

        for line_num, line_text in context_lines:
            # Add arrow indicator for target line
            indicator = "→" if line_num == target_line else " "
            formatted_line = f"{line_num:>{line_width}}{indicator} {line_text}"
            lines.append(formatted_line)

            # Add column position indicator for minified files
            if is_minified and line_num == target_line and target_column is not None:
                # Create a position indicator showing where the column is
                padding = " " * (
                    line_width + 2
                )  # Account for line number and indicator
                if target_column <= len(line_text):
                    pos_marker = " " * (target_column - 1) + "^"
                    lines.append(f"{padding}{pos_marker}")

        return "\n".join(lines)

    def _is_likely_minified(self, file_path: str) -> bool:
        """Detect if a file is likely minified.

        Parameters
        ----------
        file_path : str
            Path to the file to check

        Returns
        -------
        bool
            True if the file is likely minified
        """
        path = Path(file_path)

        # Check file extension patterns
        if path.name.endswith((".min.js", ".min.css", ".min.html")):
            self.ctx.logger.debug(
                "File detected as minified by extension: %s",
                path.name,
            )
            return True

        # Check for common minified patterns in filename
        if re.search(r"\.(bundle|chunk|vendor|dist)\.(js|css)$", path.name.lower()):
            self.ctx.logger.debug(
                "File detected as minified by pattern: %s",
                path.name,
            )
            return True

        try:
            # Sample first few lines to check average line length
            with path.open(encoding="utf-8", errors="ignore") as f:
                lines = []
                for _ in range(3):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.rstrip("\n\r"))

            if not lines:
                self.ctx.logger.debug(
                    "No lines found in file %s, not minified",
                    file_path,
                )
                return False

            # Calculate average line length
            total_chars = sum(len(line) for line in lines)
            avg_length = total_chars / len(lines)

            self.ctx.logger.debug(
                "File %s average line length: %.1f chars",
                file_path,
                avg_length,
            )

            # If average line length is over 500 characters, likely minified
            is_minified = avg_length > 500
            if is_minified:
                self.ctx.logger.debug(
                    "File detected as minified by line length analysis: %s",
                    file_path,
                )
            return is_minified

        except (OSError, UnicodeDecodeError) as e:
            # Suppress warning for node_internals (virtual paths that can't be analyzed)
            if not file_path.startswith("<node_internals>"):
                self.ctx.logger.warning(
                    "Could not analyze file for minification: %s - %s",
                    file_path,
                    e,
                )
            return False

    def _format_long_line(
        self,
        line_text: str,
        target_column: int | None = None,
    ) -> str:
        """Format long lines with intelligent truncation.

        Parameters
        ----------
        line_text : str
            The line text to format
        target_column : Optional[int]
            The target column to center on (1-indexed)

        Returns
        -------
        str
            Formatted line with intelligent truncation
        """
        max_width = config.get_code_context_max_width()

        if len(line_text) <= max_width:
            return line_text

        if target_column is None:
            # Just truncate from start with ellipsis
            return f"{line_text[: max_width - 3]}..."

        # Convert to 0-indexed for string slicing
        target_idx = target_column - 1

        # Show context around target column
        half_width = max_width // 2
        start_idx = max(0, target_idx - half_width)
        end_idx = start_idx + max_width

        # Adjust if we're near the end of the line
        if end_idx > len(line_text):
            end_idx = len(line_text)
            start_idx = max(0, end_idx - max_width)

        # Build the truncated string with ellipsis indicators
        prefix = "..." if start_idx > 0 else ""
        suffix = "..." if end_idx < len(line_text) else ""

        truncated = line_text[start_idx:end_idx]
        return f"{prefix}{truncated}{suffix}"

    def _resolve_from_source_paths(self, file_path: str) -> Path | None:
        """Resolve file path using configured source paths.

        For remote debugging scenarios (e.g., attaching to a JVM in a container),
        the debug adapter may return paths that don't exist locally, such as:
        - JAR-internal paths: 'trino-main.jar!/io/trino/execution/Foo.java'
        - Container paths: '/opt/app/io/trino/Foo.java'

        Uses the language-specific source path resolver if available, otherwise
        falls back to simple filename matching.

        Parameters
        ----------
        file_path : str
            Path from debug adapter (may be JAR-internal or absolute container path)

        Returns
        -------
        Path | None
            Resolved local path if found, None otherwise
        """
        if not self.source_paths:
            return None

        # Use language-specific resolver if available
        if self.source_path_resolver:
            return self.source_path_resolver.resolve(file_path, self.source_paths)

        # Fallback: try simple filename matching
        filename = Path(file_path).name
        self.ctx.logger.debug(
            "No source path resolver, trying filename match: %s",
            filename,
        )

        for source_root in self.source_paths:
            # Try direct filename match in source root
            candidate = Path(source_root) / filename
            if candidate.exists():
                self.ctx.logger.debug(
                    "Resolved via filename match: %s -> %s",
                    file_path,
                    candidate,
                )
                return candidate

        self.ctx.logger.debug(
            "Could not resolve %s in any source path",
            file_path,
        )
        return None
