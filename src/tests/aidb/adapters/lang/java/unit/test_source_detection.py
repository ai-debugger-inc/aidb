"""Tests for Java source path auto-detection."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 - used at runtime via pytest fixtures

import pytest

from aidb.adapters.lang.java.source_detection import detect_java_source_paths


class TestDetectJavaSourcePaths:
    """Tests for detect_java_source_paths function."""

    def test_detects_maven_project(self, tmp_path: Path) -> None:
        """Test detection of Maven project source paths."""
        # Create Maven project structure
        (tmp_path / "pom.xml").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        (tmp_path / "src" / "test" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        assert len(result) == 2
        assert str(tmp_path / "src" / "main" / "java") in result
        assert str(tmp_path / "src" / "test" / "java") in result

    def test_detects_gradle_project(self, tmp_path: Path) -> None:
        """Test detection of Gradle project source paths."""
        # Create Gradle project structure
        (tmp_path / "build.gradle").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        assert len(result) == 1
        assert str(tmp_path / "src" / "main" / "java") in result

    def test_detects_gradle_kotlin_dsl(self, tmp_path: Path) -> None:
        """Test detection with Gradle Kotlin DSL (build.gradle.kts)."""
        # Create Gradle Kotlin DSL project structure
        (tmp_path / "build.gradle.kts").touch()
        (tmp_path / "src" / "main" / "kotlin").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        assert len(result) == 1
        assert str(tmp_path / "src" / "main" / "kotlin") in result

    def test_detects_multi_module_project(self, tmp_path: Path) -> None:
        """Test detection of multi-module Maven project (like Trino)."""
        # Create parent pom
        (tmp_path / "pom.xml").touch()

        # Create nested module: core/main-module
        core_module = tmp_path / "core" / "main-module"
        (core_module / "pom.xml").parent.mkdir(parents=True)
        (core_module / "pom.xml").touch()
        (core_module / "src" / "main" / "java").mkdir(parents=True)

        # Create another nested module: plugin/some-plugin
        plugin_module = tmp_path / "plugin" / "some-plugin"
        (plugin_module / "pom.xml").parent.mkdir(parents=True)
        (plugin_module / "pom.xml").touch()
        (plugin_module / "src" / "main" / "java").mkdir(parents=True)
        (plugin_module / "src" / "test" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        # Should find all source directories
        assert len(result) == 3
        assert str(core_module / "src" / "main" / "java") in result
        assert str(plugin_module / "src" / "main" / "java") in result
        assert str(plugin_module / "src" / "test" / "java") in result

    def test_returns_empty_for_non_maven_gradle(self, tmp_path: Path) -> None:
        """Test that non-Maven/Gradle directories return empty list."""
        # Create some random structure without pom.xml or build.gradle
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        assert result == []

    def test_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Test that hidden directories are skipped."""
        (tmp_path / "pom.xml").touch()

        # Create hidden directory with maven structure
        hidden_module = tmp_path / ".hidden"
        hidden_module.mkdir()
        (hidden_module / "pom.xml").touch()
        (hidden_module / "src" / "main" / "java").mkdir(parents=True)

        # Create visible module
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        # Should only find the visible source path
        assert len(result) == 1
        assert str(tmp_path / "src" / "main" / "java") in result

    def test_skips_target_and_build_directories(self, tmp_path: Path) -> None:
        """Test that target/build directories are skipped."""
        (tmp_path / "pom.xml").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        # Create target directory with structure that looks like a module
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "pom.xml").touch()  # Some builds copy this
        (target_dir / "src" / "main" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        # Should only find the source path, not the one in target
        assert len(result) == 1
        assert str(tmp_path / "src" / "main" / "java") in result

    def test_handles_string_path(self, tmp_path: Path) -> None:
        """Test that string paths work in addition to Path objects."""
        (tmp_path / "pom.xml").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        # Pass as string instead of Path
        result = detect_java_source_paths(str(tmp_path))

        assert len(result) == 1
        assert str(tmp_path / "src" / "main" / "java") in result

    def test_handles_scala_and_kotlin_sources(self, tmp_path: Path) -> None:
        """Test detection of Kotlin and Scala source directories."""
        (tmp_path / "build.gradle.kts").touch()
        (tmp_path / "src" / "main" / "kotlin").mkdir(parents=True)
        (tmp_path / "src" / "main" / "scala").mkdir(parents=True)
        (tmp_path / "src" / "test" / "kotlin").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        assert len(result) == 3
        assert str(tmp_path / "src" / "main" / "kotlin") in result
        assert str(tmp_path / "src" / "main" / "scala") in result
        assert str(tmp_path / "src" / "test" / "kotlin") in result

    def test_no_duplicates_in_result(self, tmp_path: Path) -> None:
        """Test that results don't contain duplicate paths."""
        (tmp_path / "pom.xml").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)

        result = detect_java_source_paths(tmp_path)

        # Check no duplicates
        assert len(result) == len(set(result))
