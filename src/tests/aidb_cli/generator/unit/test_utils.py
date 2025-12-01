"""Utility functions for generator tests."""

import ast
import re
import subprocess
import tempfile
from pathlib import Path


def assert_valid_python(code: str) -> None:
    """Assert that Python code is syntactically valid.

    Parameters
    ----------
    code : str
        Python source code to validate

    Raises
    ------
    SyntaxError
        If the code is not syntactically valid
    """
    ast.parse(code)


def assert_valid_javascript(code: str) -> None:
    """Assert that JavaScript code is syntactically valid.

    Parameters
    ----------
    code : str
        JavaScript source code to validate

    Raises
    ------
    subprocess.CalledProcessError
        If the code is not syntactically valid
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        result = subprocess.run(
            ["node", "--check", temp_file],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            msg = f"JavaScript syntax error: {result.stderr}"
            raise SyntaxError(msg)
    finally:
        Path(temp_file).unlink()


def assert_valid_java(code: str) -> None:
    """Assert that Java code is syntactically valid.

    Parameters
    ----------
    code : str
        Java source code to validate

    Raises
    ------
    subprocess.CalledProcessError
        If the code is not syntactically valid
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        java_file = temp_path / "TestProgram.java"
        java_file.write_text(code)

        result = subprocess.run(
            ["javac", str(java_file)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(temp_path),
        )
        if result.returncode != 0:
            msg = f"Java compilation error: {result.stderr}"
            raise SyntaxError(msg)


def extract_markers(code: str, comment_prefix: str = "#") -> dict[str, int]:
    """Extract all markers from code and their line numbers.

    Parameters
    ----------
    code : str
        Source code containing markers
    comment_prefix : str
        Comment prefix for the language ('#' or '//')

    Returns
    -------
    dict[str, int]
        Dictionary mapping marker names to line numbers
    """
    markers = {}
    pattern = re.compile(rf"{re.escape(comment_prefix)}:([\w.]+):")

    for line_num, line in enumerate(code.split("\n"), start=1):
        match = pattern.search(line)
        if match:
            marker_name = match.group(1)
            markers[marker_name] = line_num

    return markers


def count_markers(code: str, comment_prefix: str = "#") -> int:
    """Count the total number of markers in code.

    Parameters
    ----------
    code : str
        Source code containing markers
    comment_prefix : str
        Comment prefix for the language

    Returns
    -------
    int
        Number of markers found
    """
    return len(extract_markers(code, comment_prefix))


def extract_marker_names(code: str, comment_prefix: str = "#") -> set[str]:
    """Extract all marker names from code.

    Parameters
    ----------
    code : str
        Source code containing markers
    comment_prefix : str
        Comment prefix for the language

    Returns
    -------
    set[str]
        Set of marker names found
    """
    return set(extract_markers(code, comment_prefix).keys())


def markers_are_consistent(
    python_code: str,
    javascript_code: str,
    java_code: str,
) -> tuple[bool, str]:
    """Check if markers are consistent across all three language implementations.

    Parameters
    ----------
    python_code : str
        Python implementation
    javascript_code : str
        JavaScript implementation
    java_code : str
        Java implementation

    Returns
    -------
    tuple[bool, str]
        (True, "") if consistent, (False, error_message) if not
    """
    py_markers = extract_marker_names(python_code, "#")
    js_markers = extract_marker_names(javascript_code, "//")
    java_markers = extract_marker_names(java_code, "//")

    if py_markers != js_markers:
        missing_in_js = py_markers - js_markers
        extra_in_js = js_markers - py_markers
        msg = "Python/JavaScript marker mismatch. "
        if missing_in_js:
            msg += f"Missing in JS: {missing_in_js}. "
        if extra_in_js:
            msg += f"Extra in JS: {extra_in_js}."
        return False, msg

    if py_markers != java_markers:
        missing_in_java = py_markers - java_markers
        extra_in_java = java_markers - py_markers
        msg = "Python/Java marker mismatch. "
        if missing_in_java:
            msg += f"Missing in Java: {missing_in_java}. "
        if extra_in_java:
            msg += f"Extra in Java: {extra_in_java}."
        return False, msg

    return True, ""


def validate_marker_format(marker: str) -> bool:
    """Validate that a marker follows the expected format.

    Parameters
    ----------
    marker : str
        Marker to validate (without comment prefix and colons)

    Returns
    -------
    bool
        True if valid, False otherwise

    Notes
    -----
    Expected format: category.action.identifier
    Valid categories: bp, var, func, flow, eval
    """
    pattern = re.compile(r"^(bp|var|func|flow|eval)\.[\w]+\.[\w]+$")
    return bool(pattern.match(marker))


def get_duplicates(markers: dict[str, int]) -> set[str]:
    """Find duplicate markers in code.

    Parameters
    ----------
    markers : dict[str, int]
        Dictionary of markers to line numbers

    Returns
    -------
    set[str]
        Set of duplicate marker names
    """
    seen = set()
    duplicates = set()

    for marker_name in markers:
        if marker_name in seen:
            duplicates.add(marker_name)
        seen.add(marker_name)

    return duplicates
