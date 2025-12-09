"""Python-specific syntax validation."""

import ast

from aidb_common.constants import Language

from ...base.subprocess_validator import SubprocessValidator
from ...base.syntax_validator import SyntaxValidator


class PythonSyntaxValidator(SyntaxValidator):
    """Syntax validator for Python source files."""

    def __init__(self):
        """Initialize Python syntax validator."""
        super().__init__(Language.PYTHON.value)

    def _validate_syntax(self, file_path: str) -> tuple[bool, str | None]:
        """Validate Python syntax using the ast module.

        Parameters
        ----------
        file_path : str
            Path to the Python source file

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct
        """
        success, source, error = SubprocessValidator.safe_file_read(file_path)
        if not success:
            return False, error

        try:
            # Try to parse the Python source
            ast.parse(source or "", filename=file_path)
            return True, None

        except SyntaxError as e:
            # Provide detailed error message with line number and error details
            error_msg = f"Python syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                # Add the problematic line for context
                error_msg += f"\n  {e.text.rstrip()}"
                if e.offset:
                    # Add a pointer to the error position
                    error_msg += f"\n  {' ' * (e.offset - 1)}^"
            return False, error_msg

        except Exception as e:
            # Catch any other unexpected errors
            return False, f"Error validating Python syntax: {e}"
