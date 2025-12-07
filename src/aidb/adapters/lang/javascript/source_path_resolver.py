"""JavaScript/TypeScript-specific source path resolution."""

from __future__ import annotations

from aidb.adapters.base.source_path_resolver import SourcePathResolver


class JavaScriptSourcePathResolver(SourcePathResolver):
    """JavaScript/TypeScript-specific source path resolution.

    Handles:
    - Node modules: '/node_modules/pkg/dist/index.js'
    - Build outputs: '/dist/', '/build/', '/out/'
    - Bundler source maps: 'webpack://./src/...'
    - Common source layouts: '/src/', '/lib/', '/app/'
    """

    # Bundler URL prefixes (webpack://, vite://, etc.)
    BUNDLER_PREFIXES = ("webpack://", "vite://", "rollup://", "esbuild://", "parcel://")

    # Build output directory markers
    BUILD_MARKERS = ("/dist/", "/build/", "/out/", "/.next/", "/.nuxt/")

    # Common source directory markers
    SOURCE_MARKERS = ("/src/", "/lib/", "/app/")

    def extract_relative_path(self, file_path: str) -> str | None:
        """Extract the JavaScript module path from various path formats.

        Parameters
        ----------
        file_path : str
            Path from debug adapter (may be container path or bundler path)

        Returns
        -------
        str | None
            Relative module path, or None if cannot be extracted
        """
        # Handle bundler source map paths (webpack://, vite://, etc.)
        for prefix in self.BUNDLER_PREFIXES:
            if file_path.startswith(prefix):
                path = file_path[len(prefix) :].lstrip("/.")
                return path if path else None

        # Handle node_modules paths
        if "/node_modules/" in file_path:
            return file_path.split("/node_modules/", 1)[1]

        # Handle common build output directories
        for marker in self.BUILD_MARKERS:
            if marker in file_path:
                return file_path.split(marker, 1)[1]

        # Handle common source directory layouts
        for marker in self.SOURCE_MARKERS:
            if marker in file_path:
                return file_path.split(marker, 1)[1]

        return None
