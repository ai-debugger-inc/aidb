"""Python-specific source path resolution."""

from __future__ import annotations

from aidb.adapters.base.source_path_resolver import SourcePathResolver


class PythonSourcePathResolver(SourcePathResolver):
    """Python-specific source path resolution.

    Handles:
    - Site-packages paths: '/site-packages/pkg/module.py'
    - Virtual environment paths: '/venv/lib/python3.x/site-packages/...'
    - Egg file paths: '/pkg.egg/pkg/module.py'
    - Common source layouts: '/src/', '/lib/'
    """

    def extract_relative_path(self, file_path: str) -> str | None:
        """Extract the Python package path from various path formats.

        Parameters
        ----------
        file_path : str
            Path from debug adapter (may be container path or venv path)

        Returns
        -------
        str | None
            Relative package path, or None if cannot be extracted
        """
        # Handle site-packages paths
        # e.g., '/usr/lib/python3.11/site-packages/requests/api.py'
        #    -> 'requests/api.py'
        if "/site-packages/" in file_path:
            return file_path.split("/site-packages/", 1)[1]

        # Handle dist-packages (Debian/Ubuntu system packages)
        if "/dist-packages/" in file_path:
            return file_path.split("/dist-packages/", 1)[1]

        # Handle virtual environment paths
        # e.g., '/app/.venv/lib/python3.11/site-packages/pkg/mod.py'
        venv_markers = [
            "/.venv/lib/",
            "/venv/lib/",
            "/env/lib/",
            "/.env/lib/",
            "/virtualenv/lib/",
        ]
        for marker in venv_markers:
            if marker in file_path:
                # The path after the venv marker includes pythonX.X/site-packages/
                # We want the part after site-packages
                remainder = file_path.split(marker, 1)[1]
                if "/site-packages/" in remainder:
                    return remainder.split("/site-packages/", 1)[1]

        # Handle egg paths
        # e.g., '/app/mypackage.egg/mypackage/module.py' -> 'mypackage/module.py'
        if ".egg/" in file_path:
            return file_path.split(".egg/", 1)[1]

        # Handle common source directory layouts
        source_markers = ["/src/", "/lib/", "/app/"]
        for marker in source_markers:
            if marker in file_path:
                return file_path.split(marker, 1)[1]

        return None
