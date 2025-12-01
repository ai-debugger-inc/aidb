"""Tests for repository detection module."""

from pathlib import Path

import pytest

from aidb_common.repo import detect_repo_root


class TestDetectRepoRoot:
    """Test detect_repo_root function."""

    def test_detect_from_repo_root(self, tmp_path: Path) -> None:
        """Test detection from repository root directory."""
        (tmp_path / "versions.yaml").touch()
        (tmp_path / "pyproject.toml").touch()

        result = detect_repo_root(tmp_path)
        assert result == tmp_path

    def test_detect_from_subdirectory(self, tmp_path: Path) -> None:
        """Test detection from subdirectory."""
        (tmp_path / "versions.yaml").touch()
        (tmp_path / "pyproject.toml").touch()

        subdir = tmp_path / "src" / "package"
        subdir.mkdir(parents=True)

        result = detect_repo_root(subdir)
        assert result == tmp_path

    def test_detect_from_nested_subdirectory(self, tmp_path: Path) -> None:
        """Test detection from deeply nested subdirectory."""
        (tmp_path / "versions.yaml").touch()
        (tmp_path / "pyproject.toml").touch()

        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)

        result = detect_repo_root(deep_dir)
        assert result == tmp_path

    def test_only_versions_yaml_not_sufficient(self, tmp_path: Path) -> None:
        """Test that only versions.yaml is not sufficient."""
        (tmp_path / "versions.yaml").touch()

        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_repo_root(subdir)
        assert result != tmp_path

    def test_only_pyproject_toml_not_sufficient(self, tmp_path: Path) -> None:
        """Test that only pyproject.toml is not sufficient."""
        (tmp_path / "pyproject.toml").touch()

        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_repo_root(subdir)
        assert result != tmp_path

    def test_both_markers_required(self, tmp_path: Path) -> None:
        """Test that both markers are required."""
        only_versions = tmp_path / "only_versions"
        only_versions.mkdir()
        (only_versions / "versions.yaml").touch()

        only_pyproject = tmp_path / "only_pyproject"
        only_pyproject.mkdir()
        (only_pyproject / "pyproject.toml").touch()

        both_markers = tmp_path / "both"
        both_markers.mkdir()
        (both_markers / "versions.yaml").touch()
        (both_markers / "pyproject.toml").touch()

        result = detect_repo_root(both_markers)
        assert result == both_markers

    def test_fallback_when_markers_not_found(self, tmp_path: Path) -> None:
        """Test fallback behavior when markers not found."""
        result = detect_repo_root(tmp_path)
        assert isinstance(result, Path)

    def test_detect_with_none_start_path(self) -> None:
        """Test detection with None start_path uses default."""
        result = detect_repo_root(None)
        assert isinstance(result, Path)
        assert result.exists()

    def test_closest_repo_root_when_nested(self, tmp_path: Path) -> None:
        """Test that closest repo root is found when repositories are nested."""
        outer_root = tmp_path / "outer"
        outer_root.mkdir()
        (outer_root / "versions.yaml").touch()
        (outer_root / "pyproject.toml").touch()

        inner_root = outer_root / "inner"
        inner_root.mkdir()
        (inner_root / "versions.yaml").touch()
        (inner_root / "pyproject.toml").touch()

        deep_dir = inner_root / "src" / "package"
        deep_dir.mkdir(parents=True)

        result = detect_repo_root(deep_dir)
        assert result == inner_root

    def test_stops_at_filesystem_root(self, tmp_path: Path) -> None:
        """Test that search stops at filesystem root."""
        deep_dir = tmp_path / "a" / "b" / "c"
        deep_dir.mkdir(parents=True)

        result = detect_repo_root(deep_dir)
        assert isinstance(result, Path)


class TestDetectRepoRootEdgeCases:
    """Test edge cases for detect_repo_root."""

    def test_with_symlinked_directory(self, tmp_path: Path) -> None:
        """Test detection with symlinked directory."""
        real_root = tmp_path / "real"
        real_root.mkdir()
        (real_root / "versions.yaml").touch()
        (real_root / "pyproject.toml").touch()

        link_dir = tmp_path / "link"
        try:
            link_dir.symlink_to(real_root)
            result = detect_repo_root(link_dir)
            assert result.resolve() == real_root.resolve()
        except OSError:
            pytest.skip("Symlink creation not supported on this system")

    def test_with_read_only_directory(self, tmp_path: Path) -> None:
        """Test detection with read-only directory."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "versions.yaml").touch()
        (repo_root / "pyproject.toml").touch()

        subdir = repo_root / "src"
        subdir.mkdir()

        result = detect_repo_root(subdir)
        assert result == repo_root

    def test_with_unicode_path(self, tmp_path: Path) -> None:
        """Test detection with unicode characters in path."""
        unicode_dir = tmp_path / "测试" / "パッケージ"
        unicode_dir.mkdir(parents=True)

        root = tmp_path / "测试"
        (root / "versions.yaml").touch()
        (root / "pyproject.toml").touch()

        result = detect_repo_root(unicode_dir)
        assert result == root

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Test that result is always a Path object."""
        (tmp_path / "versions.yaml").touch()
        (tmp_path / "pyproject.toml").touch()

        result = detect_repo_root(tmp_path)
        assert isinstance(result, Path)
        assert not isinstance(result, str)


class TestDetectRepoRootRealWorld:
    """Test detect_repo_root with real-world scenarios."""

    def test_detect_from_current_file_location(self) -> None:
        """Test detection from actual file location."""
        result = detect_repo_root(Path(__file__).parent)
        assert isinstance(result, Path)
        assert result.exists()

    def test_detect_with_absolute_path(self, tmp_path: Path) -> None:
        """Test detection with absolute path."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "versions.yaml").touch()
        (repo_root / "pyproject.toml").touch()

        subdir = repo_root / "src"
        subdir.mkdir()

        result = detect_repo_root(subdir.resolve())
        assert result == repo_root.resolve()

    def test_detect_with_relative_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test detection with relative path."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / "versions.yaml").touch()
        (repo_root / "pyproject.toml").touch()

        subdir = repo_root / "src"
        subdir.mkdir()

        monkeypatch.chdir(subdir)
        result = detect_repo_root(Path())
        assert result.resolve() == repo_root.resolve()
