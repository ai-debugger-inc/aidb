"""Marker system for embedding debugging markers in generated code."""

import re

from aidb_common.constants import Language


class MarkerSystem:
    """Manages debugging markers in generated code."""

    # Marker format: #:category.action.identifier:
    MARKER_PATTERN = re.compile(
        r"(?:#|//):([\w]+)\.([\w]+)\.([\w]+):",
    )

    # Standard marker categories
    CATEGORIES = {
        "bp": "Breakpoint markers",
        "var": "Variable operation markers",
        "func": "Function operation markers",
        "flow": "Control flow markers",
        "eval": "Expression evaluation markers",
    }

    @classmethod
    def format_marker(
        cls,
        category: str,
        action: str,
        identifier: str,
        comment_prefix: str = "#",
    ) -> str:
        """Format a marker string for embedding in code.

        Args
        ----
            category: Marker category (bp, var, func, flow, eval)
            action: Specific action within category
            identifier: Unique identifier within scenario
            comment_prefix: Language-specific comment prefix

        Returns
        -------
            Formatted marker string
        """
        return f"{comment_prefix}:{category}.{action}.{identifier}:"

    @classmethod
    def parse_marker(cls, marker_string: str) -> tuple[str, str, str] | None:
        """Parse a marker string into its components.

        Args
        ----
            marker_string: Raw marker string (e.g., "var.assign.counter")

        Returns
        -------
            Tuple of (category, action, identifier) or None if invalid
        """
        # Handle both full format and shorthand format
        if ":" in marker_string:
            # Full format with comment prefix
            match = cls.MARKER_PATTERN.search(marker_string)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    return (str(groups[0]), str(groups[1]), str(groups[2]))
        else:
            # Shorthand format without comment prefix
            parts = marker_string.split(".")
            if len(parts) == 3:
                return (parts[0], parts[1], parts[2])
            if len(parts) == 2:
                # Auto-generate action from context if needed
                return (parts[0], "default", parts[1])
        return None

    @classmethod
    def extract_markers(cls, code: str, language: str = "python") -> dict[str, int]:
        """Extract all markers from generated code.

        For var.* markers that appear on comment-only lines, returns the
        previous executable line number instead, ensuring breakpoints can be set
        on executable code.

        Args
        ----
            code: Generated code containing markers
            language: Programming language (for comment syntax)

        Returns
        -------
            Dictionary mapping marker names to line numbers
        """
        markers = {}
        comment_prefix = cls._get_comment_prefix(language)
        lines = code.splitlines()

        for line_num, line in enumerate(lines, 1):
            if ":" in line and comment_prefix in line:
                match = cls.MARKER_PATTERN.search(line)
                if match:
                    category, action, identifier = match.groups()
                    marker_name = f"{category}.{action}.{identifier}"

                    line_content = line.strip()
                    is_comment_only = line_content.startswith(comment_prefix)
                    is_var_marker = category == "var"

                    if is_comment_only and is_var_marker and line_num > 1:
                        markers[marker_name] = line_num - 1
                    else:
                        markers[marker_name] = line_num

        return markers

    @classmethod
    def validate_markers(cls, code_files: dict[str, str]) -> tuple[bool, list[str]]:
        """Validate marker consistency across language implementations.

        Args
        ----
            code_files: Dictionary mapping language names to generated code

        Returns
        -------
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []
        marker_sets: dict[str, set[str]] = {}

        # Extract markers for each language
        for language, code in code_files.items():
            markers = cls.extract_markers(code, language)
            marker_sets[language] = set(markers.keys())

        # Check for consistency
        if not marker_sets:
            return True, []

        reference_language = next(iter(marker_sets.keys()))
        reference_markers = marker_sets[reference_language]

        for language, language_markers in marker_sets.items():
            if language == reference_language:
                continue

            missing = reference_markers - language_markers
            extra = language_markers - reference_markers

            if missing:
                errors.append(
                    f"{language} missing markers: {', '.join(sorted(missing))}",
                )
            if extra:
                errors.append(
                    f"{language} has extra markers: {', '.join(sorted(extra))}",
                )

        return len(errors) == 0, errors

    @classmethod
    def validate_marker_format(cls, marker: str) -> bool:
        """Validate that a marker string has correct format.

        Args
        ----
            marker: Marker string to validate

        Returns
        -------
            True if valid format
        """
        parsed = cls.parse_marker(marker)
        if not parsed:
            return False

        category, action, identifier = parsed

        # Check category is valid
        if category not in cls.CATEGORIES:
            return False

        # Check identifier is not empty
        return bool(identifier)

    @classmethod
    def _get_comment_prefix(cls, language: str) -> str:
        """Get the comment prefix for a language.

        Args
        ----
            language: Programming language name

        Returns
        -------
            Comment prefix string
        """
        comment_prefixes = {
            Language.PYTHON.value: Language.PYTHON.comment_prefix,
            Language.JAVASCRIPT.value: Language.JAVASCRIPT.comment_prefix,
            Language.JAVA.value: Language.JAVA.comment_prefix,
            "typescript": "//",
            "go": "//",
            "rust": "//",
            "c": "//",
            "cpp": "//",
        }
        return comment_prefixes.get(language.lower(), "#")

    @classmethod
    def generate_marker_index(
        cls,
        scenario_id: str,  # noqa: ARG003
        code_files: dict[str, str],
    ) -> dict[str, dict[str, int]]:
        """Generate an index of all markers across languages.

        Args
        ----
            scenario_id: Scenario identifier
            code_files: Dictionary mapping language names to generated code

        Returns
        -------
            Nested dictionary: language -> marker -> line_number
        """
        index = {}
        for language, code in code_files.items():
            markers = cls.extract_markers(code, language)
            index[language] = markers
        return index

    @classmethod
    def find_marker_in_code(
        cls,
        code: str,
        marker_name: str,
        language: str = "python",
    ) -> int | None:
        """Find a specific marker in code and return its line number.

        Args
        ----
            code: Generated code
            marker_name: Marker to find (e.g., "var.assign.counter")
            language: Programming language

        Returns
        -------
            Line number where marker is found, or None
        """
        markers = cls.extract_markers(code, language)
        return markers.get(marker_name)
