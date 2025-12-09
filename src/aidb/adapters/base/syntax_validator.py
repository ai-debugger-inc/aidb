"""Base syntax validation for debug adapters."""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from aidb_common.constants import Language


class SyntaxValidator(ABC):
    """Abstract base class for language-specific syntax validators.

    Each language adapter should implement its own validator that knows how to check
    syntax for that specific language.
    """

    def __init__(self, language: str):
        """Initialize syntax validator.

        Parameters
        ----------
        language : str
            The programming language identifier (e.g., 'python', 'javascript')
        """
        self.language = language

    def validate(self, file_path: str) -> tuple[bool, str | None]:
        """Validate syntax of a source file.

        Parameters
        ----------
        file_path : str
            Path to the source file to validate, or an identifier (class name, module)

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct,
            and error_message contains details if validation fails
        """
        # Determine if target is a file path or identifier using same heuristic as Session
        from aidb.session.adapter_registry import get_all_cached_file_extensions

        known_extensions = get_all_cached_file_extensions()
        path = Path(file_path)
        suffix_lower = path.suffix.lower()
        has_known_extension = suffix_lower in known_extensions
        has_path_separator = ("/" in file_path) or ("\\" in file_path)

        is_file_path = has_known_extension or has_path_separator

        if not is_file_path:
            # Target is an identifier (class name, module, etc.) - skip syntax validation
            # Identifiers don't have file syntax to validate
            return True, None

        # Target is a file path - validate it
        if not path.exists():
            return False, f"File not found: {file_path}"

        if not path.is_file():
            return False, f"Not a file: {file_path}"

        if not os.access(file_path, os.R_OK):
            return False, f"File not readable: {file_path}"

        # Check if target is an executable binary (e.g., pytest, node, java)
        # Executables are valid targets for debugging (test runners, etc.)
        # IMPORTANT: Only skip validation for TRUE BINARY executables, not source files
        # with executable permissions (common in Docker containers)
        from .subprocess_validator import SubprocessValidator

        # Check if it's a binary executable (not just has executable permission)
        # Source files (.js, .py, .java etc) should always go through syntax validation
        if SubprocessValidator.is_binary_executable(file_path):
            return True, None

        # Delegate to language-specific validation
        return self._validate_syntax(file_path)

    @abstractmethod
    def _validate_syntax(self, file_path: str) -> tuple[bool, str | None]:
        """Perform language-specific syntax validation.

        Parameters
        ----------
        file_path : str
            Path to the source file (already verified to exist and be readable)

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct
        """

    @classmethod
    def for_language(cls, language: str) -> Optional["SyntaxValidator"]:
        """Get a validator for a specific language.

        Parameters
        ----------
        language : str
            The programming language identifier

        Returns
        -------
        Optional[SyntaxValidator]
            A validator instance for the language, or None if not supported
        """
        language = language.lower()

        # Import language-specific validators on demand to avoid circular imports
        if language == Language.PYTHON:
            from ..lang.python.syntax_validator import PythonSyntaxValidator

            return PythonSyntaxValidator()
        if language in (Language.JAVASCRIPT, "js", "node"):
            from ..lang.javascript.syntax_validator import JavaScriptSyntaxValidator

            return JavaScriptSyntaxValidator()
        if language == Language.JAVA:
            from ..lang.java.syntax_validator import JavaSyntaxValidator

            return JavaSyntaxValidator()

        # Return None for unsupported languages - validation will be skipped
        return None


class NoOpSyntaxValidator(SyntaxValidator):
    """No-operation validator for unsupported languages."""

    def __init__(self):
        """Initialize no-op validator."""
        super().__init__("unknown")

    def _validate_syntax(self, _file_path: str) -> tuple[bool, str | None]:
        """Return valid for unsupported languages.

        Parameters
        ----------
        _file_path : str
            Path to the source file

        Returns
        -------
        Tuple[bool, Optional[str]]
            Always returns (True, None)
        """
        return True, None
