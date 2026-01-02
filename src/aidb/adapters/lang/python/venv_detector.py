"""Utility for detecting Python virtual environments from paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VenvInfo:
    """Information about a detected virtual environment."""

    root: Path
    python_path: Path


def detect_venv_from_path(target_path: str) -> VenvInfo | None:
    """Detect virtual environment from a target path.

    If target is inside a venv bin directory (e.g., /path/to/venv/bin/pytest),
    extract the venv root and Python interpreter path.

    Parameters
    ----------
    target_path : str
        Path to the target executable (e.g., pytest, python script)

    Returns
    -------
    VenvInfo | None
        Detected venv info, or None if not in a venv
    """
    path = Path(target_path).resolve()

    # Check if path is inside a bin directory
    if path.parent.name != "bin":
        return None

    venv_root = path.parent.parent

    # Validate this looks like a venv
    # Check for common venv markers
    venv_markers = [
        venv_root / "pyvenv.cfg",  # Standard venv marker
        venv_root / "lib",  # Has lib directory
        venv_root / "bin" / "activate",  # Has activate script
    ]

    if not any(marker.exists() for marker in venv_markers):
        return None

    # Find Python interpreter
    python_path = venv_root / "bin" / "python"
    if not python_path.exists():
        # Try python3
        python_path = venv_root / "bin" / "python3"
        if not python_path.exists():
            return None

    return VenvInfo(root=venv_root, python_path=python_path)
