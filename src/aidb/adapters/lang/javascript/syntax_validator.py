"""JavaScript/TypeScript syntax validation."""

from pathlib import Path

from aidb.common.constants import (
    SYNTAX_VALIDATION_EXTENDED_TIMEOUT_S,
    SYNTAX_VALIDATION_TIMEOUT_S,
)
from aidb_common.constants import Language

from ...base.subprocess_validator import SubprocessValidator
from ...base.syntax_validator import SyntaxValidator


class JavaScriptSyntaxValidator(SyntaxValidator):
    """Syntax validator for JavaScript and TypeScript source files."""

    def __init__(self):
        """Initialize JavaScript syntax validator."""
        super().__init__(Language.JAVASCRIPT.value)

    def _validate_syntax(self, file_path: str) -> tuple[bool, str | None]:
        """Validate JavaScript/TypeScript syntax using Node.js.

        Parameters
        ----------
        file_path : str
            Path to the JavaScript/TypeScript source file

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct
        """
        path = Path(file_path)
        is_typescript = path.suffix in [".ts", ".tsx"]

        # Try Node.js syntax check first (works for JavaScript)
        if not is_typescript:
            result = self._validate_with_node(file_path)
            if result is not None:
                return result

        # For TypeScript or if Node.js check failed, try TypeScript compiler
        if is_typescript:
            result = self._validate_with_tsc(file_path)
            if result is not None:
                return result

        # If no validators available, try basic parsing with acorn/esprima if available
        result = self._validate_with_parser(file_path)
        if result is not None:
            return result

        # If we can't validate, assume it's valid (don't block debugging)
        return True, None

    def _validate_with_node(
        self,
        file_path: str,
    ) -> tuple[bool, str | None] | None:
        """Validate JavaScript syntax using Node.js --check flag.

        Parameters
        ----------
        file_path : str
            Path to the JavaScript source file

        Returns
        -------
        Optional[Tuple[bool, Optional[str]]]
            Validation result or None if Node.js is not available
        """
        result = SubprocessValidator.run_validator(
            ["node", "--check", file_path],
            timeout=int(SYNTAX_VALIDATION_TIMEOUT_S),
            language="JavaScript",
        )

        if result is None:
            return None  # Node.js not available

        if result.success:
            return True, None

        # Format error message using shared utility
        return SubprocessValidator.format_validation_error(
            result,
            "JavaScript",
            ["SyntaxError", "Error"],
            use_stderr=True,
        )

    def _validate_with_tsc(
        self,
        file_path: str,
    ) -> tuple[bool, str | None] | None:
        """Validate TypeScript syntax using tsc compiler.

        Parameters
        ----------
        file_path : str
            Path to the TypeScript source file

        Returns
        -------
        Optional[Tuple[bool, Optional[str]]]
            Validation result or None if tsc is not available
        """
        result = SubprocessValidator.run_validator(
            ["tsc", "--noEmit", "--allowJs", "--checkJs", file_path],
            timeout=int(SYNTAX_VALIDATION_EXTENDED_TIMEOUT_S),
            language="TypeScript",
        )

        if result is None:
            return None  # TypeScript compiler not available

        if result.success:
            return True, None

        # Format error message using shared utility (tsc outputs to stdout)
        return SubprocessValidator.format_validation_error(
            result,
            "TypeScript",
            [": error TS"],
            use_stderr=False,
        )

    def _validate_with_parser(
        self,
        _file_path: str,
    ) -> tuple[bool, str | None] | None:
        """Fallback validation using a JavaScript parser library if available.

        Parameters
        ----------
        file_path : str
            Path to the JavaScript source file

        Returns
        -------
        Optional[Tuple[bool, Optional[str]]]
            Validation result or None if no parser is available
        """
        # This could be extended to use esprima, acorn, or other JS parsers
        # For now, return None to indicate no parser available
        return None
