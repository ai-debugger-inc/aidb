"""Source path resolution for debug adapters.

Provides language-agnostic source path resolution that maps remote/container file paths
to local source files. Used for remote debugging scenarios where the debug adapter
returns paths that don't exist locally.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.patterns import Obj

if TYPE_CHECKING:
    from .adapter import DebugAdapter


class SourcePathResolver(ABC, Obj):
    """Base class for language-specific source path resolution.

    Each adapter implements a resolver to extract relative paths from
    adapter-returned file paths and resolve them against configured source
    directories.

    Parameters
    ----------
    adapter : DebugAdapter
        The debug adapter instance
    ctx : Any
        Context for logging
    """

    def __init__(self, adapter: DebugAdapter, ctx: Any | None = None):
        super().__init__(ctx=ctx or adapter.ctx)
        self.adapter = adapter

    @abstractmethod
    def extract_relative_path(self, file_path: str) -> str | None:
        """Extract the language-specific relative path from a file path.

        Converts adapter-returned paths (which may be container paths,
        JAR-internal paths, etc.) into relative paths that can be searched
        in local source directories.

        Parameters
        ----------
        file_path : str
            Path from debug adapter (may be absolute container path,
            JAR-internal path, or other format)

        Returns
        -------
        str | None
            Relative path suitable for searching in source directories,
            or None if path format is not recognized

        Examples
        --------
        Java:
            'trino.jar!/io/trino/Foo.java' -> 'io/trino/Foo.java'
        Python:
            '/app/site-packages/pkg/mod.py' -> 'pkg/mod.py'
        JavaScript:
            '/app/node_modules/pkg/index.js' -> 'pkg/index.js'
        """

    def resolve(self, file_path: str, source_paths: list[str]) -> Path | None:
        """Resolve a file path using configured source paths.

        Uses extract_relative_path() to get a relative path, then searches
        each source directory for a matching file.

        Parameters
        ----------
        file_path : str
            Path from debug adapter
        source_paths : list[str]
            List of local source directories to search

        Returns
        -------
        Path | None
            Resolved local path if found, None otherwise
        """
        if not source_paths:
            return None

        relative = self.extract_relative_path(file_path)
        if not relative:
            self.ctx.logger.debug(
                "Could not extract relative path from: %s",
                file_path,
            )
            return None

        self.ctx.logger.debug(
            "Attempting source path resolution: %s -> %s",
            file_path,
            relative,
        )

        for source_root in source_paths:
            candidate = Path(source_root) / relative
            if candidate.exists():
                self.ctx.logger.debug(
                    "Resolved source path: %s -> %s",
                    file_path,
                    candidate,
                )
                return candidate

        self.ctx.logger.debug(
            "Could not resolve %s in any source path",
            file_path,
        )
        return None
