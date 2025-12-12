"""Tests for Java build system detection utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from aidb.adapters.lang.java.tooling import JavaBuildSystemDetector


class TestFindBuildRoot:
    """Tests for JavaBuildSystemDetector.find_build_root."""

    def test_finds_maven_project_root(self, tmp_path: Path) -> None:
        """Test detection of Maven project root via pom.xml."""
        (tmp_path / "pom.xml").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        target_file = tmp_path / "src" / "main" / "java" / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.find_build_root(target_file)

        assert result == tmp_path

    def test_finds_gradle_project_root(self, tmp_path: Path) -> None:
        """Test detection of Gradle project root via build.gradle."""
        (tmp_path / "build.gradle").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        target_file = tmp_path / "src" / "main" / "java" / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.find_build_root(target_file)

        assert result == tmp_path

    def test_finds_gradle_kotlin_dsl_root(self, tmp_path: Path) -> None:
        """Test detection of Gradle Kotlin DSL project via build.gradle.kts."""
        (tmp_path / "build.gradle.kts").touch()
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        target_file = tmp_path / "src" / "main" / "java" / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.find_build_root(target_file)

        assert result == tmp_path

    def test_returns_none_for_no_build_file(self, tmp_path: Path) -> None:
        """Test returns None when no build file found."""
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        target_file = tmp_path / "src" / "main" / "java" / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.find_build_root(target_file)

        assert result is None

    def test_handles_directory_input(self, tmp_path: Path) -> None:
        """Test handles directory as input (not just files)."""
        (tmp_path / "pom.xml").touch()
        subdir = tmp_path / "src" / "main" / "java"
        subdir.mkdir(parents=True)

        result = JavaBuildSystemDetector.find_build_root(subdir)

        assert result == tmp_path

    def test_finds_nearest_build_root_in_nested_structure(self, tmp_path: Path) -> None:
        """Test finds nearest build root in nested multi-module structure."""
        # Parent project
        (tmp_path / "pom.xml").touch()

        # Nested module
        module_dir = tmp_path / "modules" / "core"
        module_dir.mkdir(parents=True)
        (module_dir / "pom.xml").touch()
        (module_dir / "src" / "main" / "java").mkdir(parents=True)
        target_file = module_dir / "src" / "main" / "java" / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.find_build_root(target_file)

        # Should find the nearest (module) pom.xml, not the parent
        assert result == module_dir


class TestDetectBuildRootWithFallbacks:
    """Tests for JavaBuildSystemDetector.detect_build_root_with_fallbacks."""

    def test_uses_workspace_root_first(self, tmp_path: Path) -> None:
        """Test workspace_root takes priority when available."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "pom.xml").touch()

        cwd = tmp_path / "cwd"
        cwd.mkdir()
        (cwd / "pom.xml").touch()

        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root=str(workspace),
            cwd=str(cwd),
            target=None,
        )

        assert result == workspace

    def test_falls_back_to_cwd(self, tmp_path: Path) -> None:
        """Test falls back to cwd when workspace_root has no build file."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        # No pom.xml in workspace

        cwd = tmp_path / "cwd"
        cwd.mkdir()
        (cwd / "pom.xml").touch()

        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root=str(workspace),
            cwd=str(cwd),
            target=None,
        )

        assert result == cwd

    def test_falls_back_to_target(self, tmp_path: Path) -> None:
        """Test falls back to target when workspace_root and cwd have no build file."""
        target_dir = tmp_path / "project"
        target_dir.mkdir()
        (target_dir / "pom.xml").touch()
        target_file = target_dir / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root=None,
            cwd=None,
            target=str(target_file),
        )

        assert result == target_dir

    def test_returns_none_when_nothing_found(self, tmp_path: Path) -> None:
        """Test returns None when no build root found anywhere."""
        no_build = tmp_path / "no_build"
        no_build.mkdir()

        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root=str(no_build),
            cwd=str(no_build),
            target=str(no_build / "Main.java"),
        )

        assert result is None

    def test_handles_nonexistent_paths(self, tmp_path: Path) -> None:
        """Test handles paths that don't exist."""
        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root="/nonexistent/path",
            cwd="/another/nonexistent",
            target="/also/nonexistent",
        )

        assert result is None

    def test_handles_all_none_inputs(self) -> None:
        """Test handles all None inputs gracefully."""
        result = JavaBuildSystemDetector.detect_build_root_with_fallbacks(
            workspace_root=None,
            cwd=None,
            target=None,
        )

        assert result is None


class TestResolveTargetDirectory:
    """Tests for JavaBuildSystemDetector.resolve_target_directory."""

    def test_uses_file_parent_for_existing_file(self, tmp_path: Path) -> None:
        """Test uses parent directory for existing file."""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        target_file = src_dir / "Main.java"
        target_file.touch()

        result = JavaBuildSystemDetector.resolve_target_directory(
            target=str(target_file),
            build_root=None,
            cwd=None,
        )

        assert result == src_dir

    def test_uses_path_as_is_for_path_like_target(self, tmp_path: Path) -> None:
        """Test uses target path as-is when it contains path separators."""
        target = "com/example/Main"

        result = JavaBuildSystemDetector.resolve_target_directory(
            target=target,
            build_root=tmp_path,
            cwd=None,
        )

        assert result == Path(target)

    def test_uses_build_root_for_class_name(self, tmp_path: Path) -> None:
        """Test uses build_root for class name identifier."""
        (tmp_path / "pom.xml").touch()

        result = JavaBuildSystemDetector.resolve_target_directory(
            target="com.example.Main",
            build_root=tmp_path,
            cwd=None,
        )

        assert result == tmp_path

    def test_falls_back_to_cwd(self, tmp_path: Path) -> None:
        """Test falls back to cwd when no build_root."""
        cwd = tmp_path / "cwd"
        cwd.mkdir()

        result = JavaBuildSystemDetector.resolve_target_directory(
            target="com.example.Main",
            build_root=None,
            cwd=str(cwd),
        )

        assert result == cwd

    def test_last_resort_uses_target_as_path(self) -> None:
        """Test uses target as path when nothing else available."""
        result = JavaBuildSystemDetector.resolve_target_directory(
            target="com.example.Main",
            build_root=None,
            cwd=None,
        )

        assert result == Path("com.example.Main")


class TestIsMavenGradleProject:
    """Tests for JavaBuildSystemDetector.is_maven_gradle_project."""

    def test_detects_maven_project(self, tmp_path: Path) -> None:
        """Test detects Maven project via pom.xml."""
        (tmp_path / "pom.xml").touch()

        result = JavaBuildSystemDetector.is_maven_gradle_project(tmp_path)

        assert result is True

    def test_detects_gradle_project(self, tmp_path: Path) -> None:
        """Test detects Gradle project via build.gradle."""
        (tmp_path / "build.gradle").touch()

        result = JavaBuildSystemDetector.is_maven_gradle_project(tmp_path)

        assert result is True

    def test_detects_gradle_kotlin_dsl(self, tmp_path: Path) -> None:
        """Test detects Gradle Kotlin DSL via build.gradle.kts."""
        (tmp_path / "build.gradle.kts").touch()

        result = JavaBuildSystemDetector.is_maven_gradle_project(tmp_path)

        assert result is True

    def test_returns_false_for_no_build_file(self, tmp_path: Path) -> None:
        """Test returns False when no build file present."""
        result = JavaBuildSystemDetector.is_maven_gradle_project(tmp_path)

        assert result is False

    def test_returns_false_for_nonexistent_directory(self) -> None:
        """Test returns False for nonexistent directory."""
        result = JavaBuildSystemDetector.is_maven_gradle_project(
            Path("/nonexistent/path"),
        )

        assert result is False
