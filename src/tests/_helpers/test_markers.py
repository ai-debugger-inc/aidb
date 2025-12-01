"""Test marker resolution system for line number tracking.

This module provides a marker-based system for referencing specific lines in test
scripts, avoiding hard-coded line numbers that break when scripts are modified.
"""

import re
from typing import Optional


class TestMarkerResolver:
    """Resolves test markers to line numbers in test scripts.

    Markers are comments with special syntax that mark important lines:
    - Python: #:marker_name:optional_description
    - JavaScript/Java: //:marker_name:optional_description
    """

    COMMENT_CHARS = {
        "python": "#",
        "javascript": "//",
        "java": "//",
        "typescript": "//",
    }

    @classmethod
    def extract_markers(cls, content: str, language: str) -> dict[str, int]:
        """Extract all markers from test content.

        For var.init.* markers that appear on comment-only lines, returns the
        previous executable line number instead, ensuring breakpoints can be set
        on executable code.

        Parameters
        ----------
        content : str
            The test script content
        language : str
            Programming language (python, javascript, java)

        Returns
        -------
        Dict[str, int]
            Mapping of marker names to line numbers
        """
        comment_char = cls.COMMENT_CHARS.get(language, "#")

        escaped_comment = re.escape(comment_char)
        pattern = rf"{escaped_comment}:(\w+(?:\.\w+)*)(?::.*)?$"

        markers = {}
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            match = re.search(pattern, line)
            if match:
                marker_name = match.group(1)
                line_content = line.strip()

                is_comment_only = line_content.startswith(comment_char)
                is_var_marker = marker_name.startswith("var.")

                if is_comment_only and is_var_marker and line_num > 1:
                    markers[marker_name] = line_num - 1
                else:
                    markers[marker_name] = line_num

        return markers

    @classmethod
    def get_line(cls, content: str, marker: str, language: str) -> int:
        """Get line number for a specific marker.

        Parameters
        ----------
        content : str
            The test script content
        marker : str
            Marker name to find
        language : str
            Programming language

        Returns
        -------
        int
            Line number where marker is found

        Raises
        ------
        ValueError
            If marker is not found in content
        """
        markers = cls.extract_markers(content, language)

        if marker not in markers:
            available = ", ".join(sorted(markers.keys()))
            msg = (
                f"Marker '{marker}' not found in {language} content. "
                f"Available markers: {available}"
            )
            raise ValueError(
                msg,
            )

        return markers[marker]

    @classmethod
    def get_lines(cls, content: str, markers: list[str], language: str) -> list[int]:
        """Get line numbers for multiple markers.

        Parameters
        ----------
        content : str
            The test script content
        markers : List[str]
            List of marker names to find
        language : str
            Programming language

        Returns
        -------
        List[int]
            Line numbers in same order as markers

        Raises
        ------
        ValueError
            If any marker is not found
        """
        all_markers = cls.extract_markers(content, language)

        lines = []
        missing = []

        for marker in markers:
            if marker in all_markers:
                lines.append(all_markers[marker])
            else:
                missing.append(marker)

        if missing:
            available = ", ".join(sorted(all_markers.keys()))
            missing_str = ", ".join(missing)
            msg = f"Markers not found: {missing_str}. Available markers: {available}"
            raise ValueError(
                msg,
            )

        return lines

    @classmethod
    def validate_markers(
        cls,
        content: str,
        required_markers: list[str],
        language: str,
    ) -> bool:
        """Validate that all required markers exist in content.

        Parameters
        ----------
        content : str
            The test script content
        required_markers : List[str]
            Markers that must be present
        language : str
            Programming language

        Returns
        -------
        bool
            True if all required markers exist
        """
        markers = cls.extract_markers(content, language)
        return all(marker in markers for marker in required_markers)
