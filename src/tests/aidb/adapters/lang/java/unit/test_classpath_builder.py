"""Tests for Java classpath builder utilities."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - used at runtime via pytest fixtures

import pytest

from aidb.adapters.lang.java.tooling import JavaClasspathBuilder


class TestFlattenClasspath:
    """Tests for JavaClasspathBuilder.flatten_classpath."""

    def test_flattens_nested_lists(self) -> None:
        """Test flattening nested list structures from JDT LS."""
        classpath = [
            "/path/to/jar1.jar",
            ["/path/to/jar2.jar", "/path/to/jar3.jar"],
            "/path/to/jar4.jar",
        ]

        result = JavaClasspathBuilder.flatten_classpath(classpath)

        assert result == [
            "/path/to/jar1.jar",
            "/path/to/jar2.jar",
            "/path/to/jar3.jar",
            "/path/to/jar4.jar",
        ]

    def test_handles_flat_list(self) -> None:
        """Test handles already flat list."""
        classpath = ["/path/to/jar1.jar", "/path/to/jar2.jar"]

        result = JavaClasspathBuilder.flatten_classpath(classpath)

        assert result == ["/path/to/jar1.jar", "/path/to/jar2.jar"]

    def test_filters_empty_strings(self) -> None:
        """Test filters out empty strings."""
        classpath = ["/path/to/jar1.jar", "", "/path/to/jar2.jar", ""]

        result = JavaClasspathBuilder.flatten_classpath(classpath)

        assert result == ["/path/to/jar1.jar", "/path/to/jar2.jar"]

    def test_handles_empty_list(self) -> None:
        """Test handles empty list."""
        result = JavaClasspathBuilder.flatten_classpath([])

        assert result == []

    def test_handles_deeply_nested(self) -> None:
        """Test handles deeply nested structures (one level only)."""
        classpath = [
            ["/jar1.jar"],
            ["/jar2.jar", "/jar3.jar"],
            "/jar4.jar",
        ]

        result = JavaClasspathBuilder.flatten_classpath(classpath)

        assert result == ["/jar1.jar", "/jar2.jar", "/jar3.jar", "/jar4.jar"]


class TestAddTargetClasses:
    """Tests for JavaClasspathBuilder.add_target_classes."""

    def test_adds_target_classes_when_exists(self, tmp_path: Path) -> None:
        """Test adds target/classes when it exists."""
        target_classes = tmp_path / "target" / "classes"
        target_classes.mkdir(parents=True)

        classpath = ["/existing/jar.jar"]

        result = JavaClasspathBuilder.add_target_classes(classpath, tmp_path)

        assert result[0] == str(target_classes)
        assert result[1] == "/existing/jar.jar"

    def test_does_not_add_when_missing(self, tmp_path: Path) -> None:
        """Test does not add when target/classes doesn't exist."""
        classpath = ["/existing/jar.jar"]

        result = JavaClasspathBuilder.add_target_classes(classpath, tmp_path)

        assert result == ["/existing/jar.jar"]

    def test_does_not_duplicate(self, tmp_path: Path) -> None:
        """Test does not add duplicate entry."""
        target_classes = tmp_path / "target" / "classes"
        target_classes.mkdir(parents=True)

        classpath = [str(target_classes), "/other/jar.jar"]

        result = JavaClasspathBuilder.add_target_classes(classpath, tmp_path)

        # Should not duplicate
        assert result.count(str(target_classes)) == 1
        assert result == classpath

    def test_preserves_original_classpath(self, tmp_path: Path) -> None:
        """Test original classpath is preserved (immutable)."""
        target_classes = tmp_path / "target" / "classes"
        target_classes.mkdir(parents=True)

        original = ["/existing/jar.jar"]
        original_copy = original.copy()

        JavaClasspathBuilder.add_target_classes(original, tmp_path)

        # Original should be unchanged (returns new list)
        assert original == original_copy


class TestAddTestClasses:
    """Tests for JavaClasspathBuilder.add_test_classes."""

    def test_adds_test_classes_for_junit(self, tmp_path: Path) -> None:
        """Test adds test-classes for JUnit launcher."""
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = ["/some/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="org.junit.platform.console.ConsoleLauncher",
        )

        assert str(test_classes) in result

    def test_inserts_after_main_classes(self, tmp_path: Path) -> None:
        """Test inserts test-classes after target/classes."""
        main_classes = tmp_path / "target" / "classes"
        main_classes.mkdir(parents=True)
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = [str(main_classes), "/other/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="JUnitRunner",
        )

        # test-classes should be right after main classes
        assert result == [str(main_classes), str(test_classes), "/other/jar.jar"]

    def test_inserts_at_beginning_if_no_main_classes(self, tmp_path: Path) -> None:
        """Test inserts at beginning if target/classes not in classpath."""
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = ["/other/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="JUnitRunner",
        )

        assert result[0] == str(test_classes)

    def test_skips_for_non_junit(self, tmp_path: Path) -> None:
        """Test skips for non-JUnit main class."""
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = ["/some/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="com.example.Main",
        )

        assert str(test_classes) not in result

    def test_skips_if_test_classes_missing(self, tmp_path: Path) -> None:
        """Test skips if test-classes directory doesn't exist."""
        classpath = ["/some/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="JUnitRunner",
        )

        assert result == classpath

    def test_skips_if_project_root_none(self) -> None:
        """Test skips if project_root is None."""
        classpath = ["/some/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=None,
            main_class="JUnitRunner",
        )

        assert result == classpath

    def test_does_not_duplicate(self, tmp_path: Path) -> None:
        """Test does not add duplicate test-classes entry."""
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = [str(test_classes), "/other/jar.jar"]

        result = JavaClasspathBuilder.add_test_classes(
            classpath,
            project_root=tmp_path,
            main_class="JUnitRunner",
        )

        # Should not duplicate
        assert result.count(str(test_classes)) == 1

    def test_case_insensitive_junit_detection(self, tmp_path: Path) -> None:
        """Test JUnit detection is case-insensitive."""
        test_classes = tmp_path / "target" / "test-classes"
        test_classes.mkdir(parents=True)

        classpath = ["/some/jar.jar"]

        # Test various case combinations
        for main_class in ["JUnit", "JUNIT", "junit", "JuNiT"]:
            result = JavaClasspathBuilder.add_test_classes(
                classpath.copy(),
                project_root=tmp_path,
                main_class=main_class,
            )
            assert str(test_classes) in result, f"Failed for {main_class}"
