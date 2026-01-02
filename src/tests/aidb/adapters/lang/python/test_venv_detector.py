"""Tests for venv_detector utility."""

from __future__ import annotations

from pathlib import Path

import pytest

from aidb.adapters.lang.python.venv_detector import VenvInfo, detect_venv_from_path


class TestDetectVenvFromPath:
    """Tests for detect_venv_from_path function."""

    def test_detects_venv_with_pyvenv_cfg(self, tmp_path: Path) -> None:
        """Detect venv when pyvenv.cfg marker exists."""
        # Create venv structure
        venv_root = tmp_path / "venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        # Create pyvenv.cfg marker
        (venv_root / "pyvenv.cfg").touch()

        # Create python executable
        python_path = bin_dir / "python"
        python_path.touch()

        # Create target executable (e.g., pytest)
        target = bin_dir / "pytest"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is not None
        assert result.root == venv_root
        assert result.python_path == python_path

    def test_detects_venv_with_activate_script(self, tmp_path: Path) -> None:
        """Detect venv when activate script exists."""
        venv_root = tmp_path / ".venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        # Create activate script as marker
        (bin_dir / "activate").touch()

        # Create python executable
        python_path = bin_dir / "python"
        python_path.touch()

        target = bin_dir / "myapp"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is not None
        assert result.root == venv_root
        assert result.python_path == python_path

    def test_detects_venv_with_lib_directory(self, tmp_path: Path) -> None:
        """Detect venv when lib directory exists."""
        venv_root = tmp_path / "env"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        # Create lib directory as marker
        (venv_root / "lib").mkdir()

        # Create python executable
        python_path = bin_dir / "python"
        python_path.touch()

        target = bin_dir / "flask"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is not None
        assert result.root == venv_root

    def test_uses_python3_fallback(self, tmp_path: Path) -> None:
        """Use python3 when python doesn't exist."""
        venv_root = tmp_path / "venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        (venv_root / "pyvenv.cfg").touch()

        # Only create python3, not python
        python3_path = bin_dir / "python3"
        python3_path.touch()

        target = bin_dir / "pytest"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is not None
        assert result.python_path == python3_path

    def test_returns_none_for_non_bin_path(self, tmp_path: Path) -> None:
        """Return None if path is not in a bin directory."""
        # Target not in bin directory
        target = tmp_path / "scripts" / "run.py"
        target.parent.mkdir(parents=True)
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is None

    def test_returns_none_without_venv_markers(self, tmp_path: Path) -> None:
        """Return None if bin directory exists but no venv markers."""
        # Create bin directory without any venv markers
        some_dir = tmp_path / "some_project"
        bin_dir = some_dir / "bin"
        bin_dir.mkdir(parents=True)

        target = bin_dir / "script"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is None

    def test_returns_none_without_python_executable(self, tmp_path: Path) -> None:
        """Return None if venv markers exist but no python executable."""
        venv_root = tmp_path / "venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        # Create marker but no python executable
        (venv_root / "pyvenv.cfg").touch()

        target = bin_dir / "pytest"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is None

    def test_handles_nested_venv_path(self, tmp_path: Path) -> None:
        """Handle deeply nested venv paths."""
        project = tmp_path / "projects" / "myapp" / "backend"
        venv_root = project / ".venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        (venv_root / "pyvenv.cfg").touch()
        python_path = bin_dir / "python"
        python_path.touch()

        target = bin_dir / "uvicorn"
        target.touch()

        result = detect_venv_from_path(str(target))

        assert result is not None
        assert result.root == venv_root
        assert result.python_path == python_path

    def test_resolves_symlinks(self, tmp_path: Path) -> None:
        """Handle symlinked paths correctly."""
        # Create actual venv
        venv_root = tmp_path / "actual_venv"
        bin_dir = venv_root / "bin"
        bin_dir.mkdir(parents=True)

        (venv_root / "pyvenv.cfg").touch()
        python_path = bin_dir / "python"
        python_path.touch()

        target = bin_dir / "pytest"
        target.touch()

        # Create symlink to target
        link_dir = tmp_path / "links"
        link_dir.mkdir()
        symlink = link_dir / "pytest_link"
        symlink.symlink_to(target)

        result = detect_venv_from_path(str(symlink))

        assert result is not None
        assert result.root == venv_root


class TestVenvInfo:
    """Tests for VenvInfo dataclass."""

    def test_venv_info_attributes(self, tmp_path: Path) -> None:
        """VenvInfo stores root and python_path correctly."""
        root = tmp_path / "venv"
        python_path = root / "bin" / "python"

        info = VenvInfo(root=root, python_path=python_path)

        assert info.root == root
        assert info.python_path == python_path
