"""Java syntax validation."""

import re
import tempfile

from aidb.common.constants import SYNTAX_VALIDATION_EXTENDED_TIMEOUT_S
from aidb_common.constants import Language

from ...base.subprocess_validator import SubprocessValidator
from ...base.syntax_validator import SyntaxValidator


class JavaSyntaxValidator(SyntaxValidator):
    """Syntax validator for Java source files."""

    def __init__(self):
        """Initialize Java syntax validator."""
        super().__init__(Language.JAVA.value)

    def _validate_syntax(self, file_path: str) -> tuple[bool, str | None]:
        """Validate Java syntax using the javac compiler.

        Parameters
        ----------
        file_path : str
            Path to the Java source file

        Returns
        -------
        Tuple[bool, Optional[str]]
            (is_valid, error_message) where is_valid is True if syntax is correct
        """
        # Skip validation for compiled artifacts - syntax was already validated
        # during compilation. This is important because Java compiles .java to
        # .class before the PRE_LAUNCH hook runs, so the target path passed to
        # validate_syntax() will be a .class file, not a .java file.
        if file_path.endswith((".class", ".jar")):
            return True, None

        # Try javac for syntax checking
        result = self._validate_with_javac(file_path)
        if result is not None:
            return result

        # If javac is not available, try basic validation
        result = self._validate_basic_syntax(file_path)
        if result is not None:
            return result

        # If we can't validate, assume it's valid (don't block debugging)
        return True, None

    def _validate_with_javac(
        self,
        file_path: str,
    ) -> tuple[bool, str | None] | None:
        """Validate Java syntax using javac compiler.

        Parameters
        ----------
        file_path : str
            Path to the Java source file

        Returns
        -------
        Optional[Tuple[bool, Optional[str]]]
            Validation result or None if javac is not available
        """
        # Create a temporary directory for compilation output
        with tempfile.TemporaryDirectory() as tmpdir:
            result = SubprocessValidator.run_validator(
                ["javac", "-d", tmpdir, "-Xlint:all", file_path],
                timeout=int(SYNTAX_VALIDATION_EXTENDED_TIMEOUT_S),
                language="Java",
            )

            if result is None:
                return None  # javac not available

            if result.success:
                return True, None

            # Custom error parsing for javac output
            error_msg = result.stderr.strip()
            if error_msg:
                # Extract the most relevant error using existing parser
                errors = self._parse_javac_errors(error_msg)
                if errors:
                    return False, errors[0]  # Return first error
                return False, f"Java compilation error:\n{error_msg}"
            return False, "Java compilation error (no details available)"

    def _parse_javac_errors(self, error_output: str) -> list:
        """Parse javac error output to extract meaningful error messages.

        Parameters
        ----------
        error_output : str
            Raw error output from javac

        Returns
        -------
        list
            List of formatted error messages
        """
        errors = []
        lines = error_output.split("\n")

        for i, line in enumerate(lines):
            # Look for error patterns like "file.java:10: error: ..."
            if ": error:" in line:
                # Extract the error message
                parts = line.split(": error:", 1)
                if len(parts) == 2:
                    location = parts[0].split(":")[-1] if ":" in parts[0] else ""
                    error_desc = parts[1].strip()

                    # Try to get the line with the caret (^) showing error position
                    error_msg = "Java syntax error"
                    if location:
                        error_msg += f" at line {location}"
                    error_msg += f": {error_desc}"

                    # Look for the source line and caret in the next few lines
                    for j in range(i + 1, min(i + 4, len(lines))):
                        if "^" in lines[j]:
                            # Include the problematic line and the caret
                            if j > 0 and j - 1 < len(lines):
                                error_msg += f"\n  {lines[j - 1]}"
                            error_msg += f"\n  {lines[j]}"
                            break

                    errors.append(error_msg)

        return errors

    def _validate_basic_syntax(
        self,
        file_path: str,
    ) -> tuple[bool, str | None] | None:
        """Perform basic Java syntax validation without compiler.

        This is a fallback that checks for common syntax issues when javac
        is not available.

        Parameters
        ----------
        file_path : str
            Path to the Java source file

        Returns
        -------
        Optional[Tuple[bool, Optional[str]]]
            Validation result or None if unable to validate
        """
        success, content, error = SubprocessValidator.safe_file_read(file_path)
        if not success:
            return False, error

        if content is None:
            return False, "File content is empty or could not be read"

        # Check for basic syntax issues

        # 1. Check for balanced braces
        brace_count = content.count("{") - content.count("}")
        if brace_count != 0:
            return (
                False,
                f"Unbalanced braces: {abs(brace_count)} "
                f"{'opening' if brace_count > 0 else 'closing'} brace(s) unmatched",
            )

        # 2. Check for balanced parentheses
        paren_count = content.count("(") - content.count(")")
        if paren_count != 0:
            return (
                False,
                f"Unbalanced parentheses: {abs(paren_count)} "
                f"{'opening' if paren_count > 0 else 'closing'} parenthesis unmatched",
            )

        # 3. Check for class declaration
        if not re.search(r"\bclass\s+\w+", content) and not re.search(
            r"\binterface\s+\w+",
            content,
        ):
            return False, "No class or interface declaration found"

        # 4. Check for unclosed string literals (simple check)
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("//"):
                continue
            # Count quotes (excluding escaped quotes)
            quote_count = len(re.findall(r'(?<!\\)"', line))
            if quote_count % 2 != 0:
                return False, f"Unclosed string literal at line {i}"

        # Basic checks passed, but can't guarantee full syntax correctness
        return None  # Return None to indicate incomplete validation
