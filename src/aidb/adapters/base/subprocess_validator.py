"""Shared utilities for subprocess-based syntax validation."""

import subprocess
from pathlib import Path


class SubprocessValidationResult:
    """Result container for subprocess validation operations."""

    def __init__(self, success: bool, stdout: str, stderr: str, returncode: int):
        """Initialize validation result.

        Parameters
        ----------
        success : bool
            True if validation succeeded
        stdout : str
            Standard output from the process
        stderr : str
            Standard error from the process
        returncode : int
            Process return code
        """
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class SubprocessValidator:
    """Shared utilities for running syntax validation subprocesses."""

    @staticmethod
    def run_validator(
        command: list[str],
        timeout: int = 10,
        language: str = "unknown",
    ) -> SubprocessValidationResult | None:
        """Run a subprocess validator command with common error handling.

        Parameters
        ----------
        command : List[str]
            Command and arguments to run
        timeout : int, default=10
            Timeout in seconds
        language : str, default="unknown"
            Language name for error messages

        Returns
        -------
        Optional[SubprocessValidationResult]
            Validation result, or None if the validator is not available
        """
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return SubprocessValidationResult(
                success=(result.returncode == 0),
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )

        except FileNotFoundError:
            # Validator not installed
            return None
        except subprocess.TimeoutExpired:
            return SubprocessValidationResult(
                success=False,
                stdout="",
                stderr=f"{language} validation timed out",
                returncode=-1,
            )
        except Exception as e:
            return SubprocessValidationResult(
                success=False,
                stdout="",
                stderr=f"Error during {language} validation: {e}",
                returncode=-1,
            )

    @staticmethod
    def extract_error_lines(output: str, error_patterns: list[str]) -> str | None:
        """Extract relevant error messages from compiler output.

        Parameters
        ----------
        output : str
            Raw output from the compiler
        error_patterns : List[str]
            List of patterns to look for in error lines

        Returns
        -------
        Optional[str]
            First matching error message, or None if no patterns match
        """
        if not output:
            return None

        lines = output.split("\n")
        for line in lines:
            for pattern in error_patterns:
                if pattern in line:
                    return line

        return None

    @staticmethod
    def format_validation_error(
        result: SubprocessValidationResult,
        language: str,
        error_patterns: list[str],
        use_stderr: bool = True,
    ) -> tuple[bool, str | None]:
        """Format validation error from subprocess result.

        Parameters
        ----------
        result : SubprocessValidationResult
            Result from subprocess validation
        language : str
            Language name for error messages
        error_patterns : List[str]
            Patterns to look for in error output
        use_stderr : bool, default=True
            Whether to look for errors in stderr (True) or stdout (False)

        Returns
        -------
        Tuple[bool, Optional[str]]
            (False, formatted_error_message) for validation failures
        """
        if result.success:
            return True, None

        # Choose which output stream to examine
        error_output = result.stderr if use_stderr else result.stdout
        error_msg = error_output.strip()

        if error_msg:
            # Try to extract specific error
            specific_error = SubprocessValidator.extract_error_lines(
                error_msg,
                error_patterns,
            )
            if specific_error:
                return False, f"{language} syntax error: {specific_error}"

            # Fall back to full error output
            return False, f"{language} syntax error:\n{error_msg}"

        return False, f"{language} syntax error (no details available)"

    @staticmethod
    def is_binary_executable(file_path: str) -> bool:
        """Check if a file is a TRUE binary executable (not just has exec permission).

        This method only returns True for files that are actual compiled binaries
        (ELF, Mach-O, PE) or scripts with shebangs. It does NOT return True for
        source files that merely have executable permissions (common in Docker).

        Parameters
        ----------
        file_path : str
            Path to the file to check

        Returns
        -------
        bool
            True only if file is a compiled binary or has a shebang
        """
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return False

        try:
            with path.open("rb") as f:
                header = f.read(4)
                if len(header) >= 4:
                    # ELF binary
                    if header[:4] == b"\x7fELF":
                        return True
                    # Mach-O binary (various endianness)
                    if header[:4] in [
                        b"\xcf\xfa\xed\xfe",  # 64-bit little-endian
                        b"\xce\xfa\xed\xfe",  # 32-bit little-endian
                        b"\xfe\xed\xfa\xce",  # 32-bit big-endian
                        b"\xfe\xed\xfa\xcf",  # 64-bit big-endian
                        b"\xca\xfe\xba\xbe",  # Fat/universal binary
                        b"\xbe\xba\xfe\xca",  # Fat/universal binary (swapped)
                    ]:
                        return True
                    # PE binary (Windows)
                    if header[:2] == b"MZ":
                        return True
                    # Check for shebang (script that should be run directly)
                    if header[:2] == b"#!":
                        return True
        except Exception:  # noqa: S110
            pass

        return False

    @staticmethod
    def safe_file_read(file_path: str) -> tuple[bool, str | None, str | None]:
        """Safely read a file with common error handling.

        Parameters
        ----------
        file_path : str
            Path to the file to read

        Returns
        -------
        Tuple[bool, Optional[str], Optional[str]]
            (success, content_or_none, error_message_or_none)
        """
        try:
            with Path(file_path).open(encoding="utf-8") as f:
                content = f.read()
            return True, content, None

        except UnicodeDecodeError as e:
            return False, None, f"Unable to decode file as UTF-8: {e}"
        except Exception as e:
            return False, None, f"Error reading file: {e}"
