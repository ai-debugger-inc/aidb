"""Java-specific source path resolution."""

from __future__ import annotations

from aidb.adapters.base.source_path_resolver import SourcePathResolver


class JavaSourcePathResolver(SourcePathResolver):
    """Java-specific source path resolution.

    Handles:
    - JAR-internal paths: 'lib/foo.jar!/io/trino/Foo.java'
    - Maven source layouts: '/src/main/java/', '/src/test/java/'
    - Gradle source layouts: '/src/main/kotlin/', '/src/test/scala/'
    - Common package prefixes: io/, com/, org/, net/, java/, javax/
    """

    def extract_relative_path(self, file_path: str) -> str | None:
        """Extract the Java class path from various path formats.

        Parameters
        ----------
        file_path : str
            Path from debug adapter (may be JAR-internal or absolute)

        Returns
        -------
        str | None
            Relative class path, or None if cannot be extracted
        """
        # Handle JAR notation: 'foo.jar!/path/to/Class.java'
        if "!/" in file_path:
            return file_path.split("!/", 1)[1]

        # Handle Maven/Gradle source layouts
        source_markers = [
            "/src/main/java/",
            "/src/test/java/",
            "/src/main/scala/",
            "/src/test/scala/",
            "/src/main/kotlin/",
            "/src/test/kotlin/",
            "/src/",
            "/java/",
        ]
        path_lower = file_path.lower()
        for marker in source_markers:
            if marker in path_lower:
                idx = path_lower.find(marker)
                return file_path[idx + len(marker) :]

        # Try to find package-like structure by looking for common
        # top-level package names (io/trino/..., com/example/..., etc.)
        common_packages = ["io/", "com/", "org/", "net/", "java/", "javax/"]
        for pkg in common_packages:
            if f"/{pkg}" in file_path:
                idx = file_path.find(f"/{pkg}")
                return file_path[idx + 1 :]  # Skip the leading /

        return None
