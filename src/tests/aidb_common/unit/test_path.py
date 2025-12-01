"""Tests for path utilities module."""

from pathlib import Path

import pytest

from aidb_common.path import (
    get_aidb_adapters_dir,
    get_aidb_cache_dir,
    get_aidb_home,
    get_aidb_log_dir,
    normalize_path,
)


class TestAidbDirectories:
    """Test AIDB directory getter functions."""

    def test_get_aidb_home(self) -> None:
        """Test get_aidb_home returns expected path."""
        home = get_aidb_home()
        assert isinstance(home, Path)
        assert home.name == ".aidb"
        assert home.parent == Path.home()

    def test_get_aidb_adapters_dir(self) -> None:
        """Test get_aidb_adapters_dir returns expected path."""
        adapters_dir = get_aidb_adapters_dir()
        assert isinstance(adapters_dir, Path)
        assert adapters_dir.name == "adapters"
        assert adapters_dir.parent.name == ".aidb"

    def test_get_aidb_log_dir(self) -> None:
        """Test get_aidb_log_dir returns expected path."""
        log_dir = get_aidb_log_dir()
        assert isinstance(log_dir, Path)
        assert log_dir.name == "log"
        assert log_dir.parent.name == ".aidb"

    def test_get_aidb_cache_dir(self) -> None:
        """Test get_aidb_cache_dir returns expected path."""
        cache_dir = get_aidb_cache_dir()
        assert isinstance(cache_dir, Path)
        assert cache_dir.name == "adapters"
        assert cache_dir.parent.name == "aidb"
        assert cache_dir.parent.parent.name == ".cache"

    def test_directory_paths_are_absolute(self) -> None:
        """Test that all directory paths are absolute."""
        assert get_aidb_home().is_absolute()
        assert get_aidb_adapters_dir().is_absolute()
        assert get_aidb_log_dir().is_absolute()
        assert get_aidb_cache_dir().is_absolute()


class TestNormalizePathBasic:
    """Test basic normalize_path functionality."""

    def test_normalize_path_string_input(self, tmp_path: Path) -> None:
        """Test normalize_path with string input returns string."""
        path_str = str(tmp_path)
        result = normalize_path(path_str)
        assert isinstance(result, str)

    def test_normalize_path_path_input(self, tmp_path: Path) -> None:
        """Test normalize_path with Path input returns Path."""
        result = normalize_path(tmp_path)
        assert isinstance(result, Path)

    def test_normalize_path_expands_tilde(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that normalize_path expands ~ to home directory."""
        result = normalize_path("~/test")
        assert "~" not in str(result)
        assert str(result).startswith(str(Path.home()))

    def test_normalize_path_existing_file(self, tmp_path: Path) -> None:
        """Test normalize_path with existing file."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = normalize_path(str(test_file))
        assert isinstance(result, str)
        assert Path(result).exists()

    def test_normalize_path_nonexistent_file(self, tmp_path: Path) -> None:
        """Test normalize_path with nonexistent file."""
        test_file = tmp_path / "nonexistent.txt"
        result = normalize_path(str(test_file))
        assert isinstance(result, str)


class TestNormalizePathReturnType:
    """Test normalize_path return_path parameter."""

    def test_return_path_true_returns_path(self, tmp_path: Path) -> None:
        """Test that return_path=True returns Path."""
        result = normalize_path(str(tmp_path), return_path=True)
        assert isinstance(result, Path)

    def test_return_path_false_returns_str(self, tmp_path: Path) -> None:
        """Test that return_path=False returns str."""
        result = normalize_path(tmp_path, return_path=False)
        assert isinstance(result, str)

    def test_return_path_none_matches_input_type(self, tmp_path: Path) -> None:
        """Test that return_path=None matches input type."""
        str_result = normalize_path(str(tmp_path), return_path=None)
        assert isinstance(str_result, str)

        path_result = normalize_path(tmp_path, return_path=None)
        assert isinstance(path_result, Path)


class TestNormalizePathStrict:
    """Test normalize_path strict parameter."""

    def test_strict_false_with_nonexistent(self, tmp_path: Path) -> None:
        """Test strict=False with nonexistent path."""
        nonexistent = tmp_path / "does_not_exist"
        result = normalize_path(str(nonexistent), strict=False)
        assert isinstance(result, str)

    def test_strict_true_with_nonexistent(self, tmp_path: Path) -> None:
        """Test strict=True with nonexistent path."""
        nonexistent = tmp_path / "does_not_exist"
        result = normalize_path(str(nonexistent), strict=True)
        assert isinstance(result, str)

    def test_strict_true_resolves_symlinks(self, tmp_path: Path) -> None:
        """Test that strict=True resolves symlinks."""
        real_file = tmp_path / "real.txt"
        real_file.touch()
        symlink = tmp_path / "link.txt"

        try:
            symlink.symlink_to(real_file)
            result = normalize_path(str(symlink), strict=True)
            assert "link.txt" not in str(result) or symlink.resolve() == Path(result)
        except OSError:
            pytest.skip("Symlink creation not supported on this system")

    def test_strict_false_with_existing(self, tmp_path: Path) -> None:
        """Test strict=False with existing path."""
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = normalize_path(str(test_file), strict=False)
        assert Path(result).exists()


class TestNormalizePathEdgeCases:
    """Test normalize_path edge cases."""

    def test_normalize_empty_string(self) -> None:
        """Test normalize_path with empty string."""
        result = normalize_path("")
        assert result == ""

    def test_normalize_none(self) -> None:
        """Test normalize_path with None."""
        result = normalize_path(None)  # type: ignore[arg-type]
        assert result is None

    def test_normalize_relative_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test normalize_path with relative path."""
        monkeypatch.chdir(tmp_path)
        result = normalize_path("./test")
        assert isinstance(result, str)

    def test_normalize_path_with_dots(self, tmp_path: Path) -> None:
        """Test normalize_path handles ./ and ../."""
        path = tmp_path / "subdir" / ".." / "test.txt"
        result = normalize_path(str(path), strict=True)
        assert ".." not in str(result)

    def test_normalize_absolute_path(self, tmp_path: Path) -> None:
        """Test normalize_path with absolute path."""
        result = normalize_path(str(tmp_path))
        assert Path(result).is_absolute()

    def test_normalize_path_idempotent(self, tmp_path: Path) -> None:
        """Test that normalizing twice gives same result."""
        path_str = str(tmp_path)
        result1 = normalize_path(path_str)
        result2 = normalize_path(result1)
        assert result1 == result2


class TestNormalizePathWithRealPaths:
    """Test normalize_path with real filesystem paths."""

    def test_normalize_home_directory(self) -> None:
        """Test normalizing home directory path."""
        home = str(Path.home())
        result = normalize_path(home)
        assert result == home

    def test_normalize_current_directory(self) -> None:
        """Test normalizing current directory."""
        result = normalize_path(".")
        assert isinstance(result, str)
        assert Path(result).is_dir()

    def test_normalize_parent_directory(self) -> None:
        """Test normalizing parent directory."""
        result = normalize_path("..")
        assert isinstance(result, str)
        assert Path(result).is_dir()
