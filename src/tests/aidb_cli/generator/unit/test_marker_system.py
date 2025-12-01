"""Tests for marker extraction and validation."""

import pytest

from tests.aidb_cli.generator.unit.test_utils import (
    count_markers,
    extract_marker_names,
    extract_markers,
    get_duplicates,
    markers_are_consistent,
    validate_marker_format,
)


class TestMarkerExtraction:
    """Tests for extracting markers from code."""

    def test_extract_python_markers(self):
        """Test extracting markers from Python code."""
        code = """
x = 10  #:var.init.x:
y = 20  #:var.init.y:
print(x + y)  #:func.print.sum:
"""
        markers = extract_markers(code, "#")

        assert len(markers) == 3
        assert "var.init.x" in markers
        assert "var.init.y" in markers
        assert "func.print.sum" in markers

    def test_extract_javascript_markers(self):
        """Test extracting markers from JavaScript code."""
        code = """
let x = 10;  //:var.init.x:
let y = 20;  //:var.init.y:
console.log(x + y);  //:func.print.sum:
"""
        markers = extract_markers(code, "//")

        assert len(markers) == 3
        assert "var.init.x" in markers
        assert "var.init.y" in markers
        assert "func.print.sum" in markers

    def test_extract_java_markers(self):
        """Test extracting markers from Java code."""
        code = """
int x = 10;  //:var.init.x:
int y = 20;  //:var.init.y:
System.out.println(x + y);  //:func.print.sum:
"""
        markers = extract_markers(code, "//")

        assert len(markers) == 3
        assert "var.init.x" in markers
        assert "var.init.y" in markers
        assert "func.print.sum" in markers

    def test_extract_markers_with_line_numbers(self):
        """Test that line numbers are correctly captured."""
        code = """
# Line 1
x = 10  #:var.init.x:
# Line 3
y = 20  #:var.init.y:
"""
        markers = extract_markers(code, "#")

        assert markers["var.init.x"] == 3
        assert markers["var.init.y"] == 5

    def test_extract_markers_empty_code(self):
        """Test extracting from code with no markers."""
        code = """
x = 10
y = 20
print(x + y)
"""
        markers = extract_markers(code, "#")
        assert len(markers) == 0

    def test_count_markers(self):
        """Test counting markers in code."""
        code = """
x = 10  #:var.init.x:
y = 20  #:var.init.y:
z = 30  #:var.init.z:
"""
        count = count_markers(code, "#")
        assert count == 3

    def test_extract_marker_names(self):
        """Test extracting just marker names."""
        code = """
x = 10  #:var.init.x:
y = 20  #:var.init.y:
"""
        names = extract_marker_names(code, "#")

        assert names == {"var.init.x", "var.init.y"}


class TestMarkerValidation:
    """Tests for marker format validation."""

    def test_valid_marker_formats(self):
        """Test various valid marker formats."""
        valid_markers = [
            "var.init.counter",
            "func.def.add",
            "flow.loop.main",
            "bp.entry.func",
            "eval.result.expr",
        ]

        for marker in valid_markers:
            assert validate_marker_format(marker), f"Should be valid: {marker}"

    def test_invalid_marker_formats(self):
        """Test invalid marker formats."""
        invalid_markers = [
            "invalid",  # No dots
            "var.init",  # Only two parts
            "var",  # Only one part
            "invalid.category.name",  # Invalid category
            "var..name",  # Empty middle part
            "",  # Empty string
        ]

        for marker in invalid_markers:
            assert not validate_marker_format(marker), f"Should be invalid: {marker}"

    def test_marker_categories(self):
        """Test that only valid categories are accepted."""
        valid_categories = ["bp", "var", "func", "flow", "eval"]

        for category in valid_categories:
            marker = f"{category}.action.identifier"
            assert validate_marker_format(marker)

        invalid_marker = "invalid.action.identifier"
        assert not validate_marker_format(invalid_marker)

    def test_duplicate_detection(self):
        """Test detecting duplicate markers."""

        # Note: In a dict, duplicates overwrite, so we need different test
        # This tests the get_duplicates helper with a list approach
        marker_dict = {"var.init.x": 10, "var.init.y": 15}
        duplicates = get_duplicates(marker_dict)

        # No duplicates in this dict
        assert len(duplicates) == 0


class TestCrossLanguageConsistency:
    """Tests for cross-language marker consistency."""

    def test_consistent_markers_across_languages(self):
        """Test that markers are identical across languages."""
        python_code = """
x = 10  #:var.init.x:
print(x)  #:func.print.value:
"""

        javascript_code = """
let x = 10;  //:var.init.x:
console.log(x);  //:func.print.value:
"""

        java_code = """
int x = 10;  //:var.init.x:
System.out.println(x);  //:func.print.value:
"""

        is_consistent, msg = markers_are_consistent(
            python_code,
            javascript_code,
            java_code,
        )

        assert is_consistent, msg

    def test_inconsistent_markers_missing_in_js(self):
        """Test detection of missing markers in JavaScript."""
        python_code = """
x = 10  #:var.init.x:
y = 20  #:var.init.y:
"""

        javascript_code = """
let x = 10;  //:var.init.x:
"""

        java_code = """
int x = 10;  //:var.init.x:
int y = 20;  //:var.init.y:
"""

        is_consistent, msg = markers_are_consistent(
            python_code,
            javascript_code,
            java_code,
        )

        assert not is_consistent
        assert "missing in js" in msg.lower()

    def test_inconsistent_markers_extra_in_java(self):
        """Test detection of extra markers in Java."""
        python_code = """
x = 10  #:var.init.x:
"""

        javascript_code = """
let x = 10;  //:var.init.x:
"""

        java_code = """
int x = 10;  //:var.init.x:
int y = 20;  //:var.init.y:
"""

        is_consistent, msg = markers_are_consistent(
            python_code,
            javascript_code,
            java_code,
        )

        assert not is_consistent
        assert "extra in java" in msg.lower()

    def test_marker_count_consistency(self):
        """Test that marker counts match across languages."""
        python_code = """
x = 10  #:var.init.x:
y = 20  #:var.init.y:
z = 30  #:var.init.z:
"""

        javascript_code = """
let x = 10;  //:var.init.x:
let y = 20;  //:var.init.y:
let z = 30;  //:var.init.z:
"""

        java_code = """
int x = 10;  //:var.init.x:
int y = 20;  //:var.init.y:
int z = 30;  //:var.init.z:
"""

        py_count = count_markers(python_code, "#")
        js_count = count_markers(javascript_code, "//")
        java_count = count_markers(java_code, "//")

        assert py_count == js_count == java_count == 3


class TestMarkerEdgeCases:
    """Tests for marker edge cases."""

    def test_marker_with_underscores(self):
        """Test markers with underscores in identifier."""
        marker = "var.init.my_variable"
        assert validate_marker_format(marker)

    def test_marker_with_numbers(self):
        """Test markers with numbers in identifier."""
        marker = "var.init.var123"
        assert validate_marker_format(marker)

    def test_multiline_code_with_markers(self):
        """Test extracting markers from multiline constructs."""
        code = """
def add(a, b):  #:func.def.add:
    result = a + b  #:var.calc.result:
    return result  #:func.return.result:
"""
        markers = extract_markers(code, "#")

        assert len(markers) == 3
        assert markers["func.def.add"] == 2
        assert markers["var.calc.result"] == 3
        assert markers["func.return.result"] == 4

    def test_marker_with_complex_identifier(self):
        """Test markers with complex identifiers."""
        code = """
x = 10  #:var.init.x:
y = calculate_value()  #:func.call.calculate_value:
result = x + y  #:var.assign.result:
"""
        markers = extract_markers(code, "#")

        assert len(markers) == 3
        assert "var.init.x" in markers
        assert "func.call.calculate_value" in markers
        assert "var.assign.result" in markers
