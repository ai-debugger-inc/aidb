"""Java build system detection utilities.

This module provides utilities for detecting Maven/Gradle build systems and resolving
project roots from various path sources.
"""

from pathlib import Path


class JavaBuildSystemDetector:
    """Detects Maven/Gradle build systems and resolves project roots.

    This class provides static methods for detecting build system configuration files
    (pom.xml, build.gradle, build.gradle.kts) and resolving project directories from
    various path sources.
    """

    # Build files that indicate a Maven or Gradle project
    BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")

    @staticmethod
    def find_build_root(start: Path) -> Path | None:
        """Walk up directory tree to find Maven/Gradle project root.

        Parameters
        ----------
        start : Path
            Starting path (file or directory) to search from

        Returns
        -------
        Path | None
            Path to project root containing pom.xml or build.gradle,
            or None if no build file found
        """
        cur = start
        if cur.is_file():
            cur = cur.parent

        # Check current directory and all parents
        for p in [cur, *list(cur.parents)]:
            if JavaBuildSystemDetector._has_build_file(p):
                return p

        return None

    @staticmethod
    def detect_build_root_with_fallbacks(
        workspace_root: str | None,
        cwd: str | None,
        target: str | None,
    ) -> Path | None:
        """Try multiple sources to find build root with fallback chain.

        Tries sources in priority order:
        1. workspace_root (most specific, from launch.json)
        2. cwd (current working directory)
        3. target path (walk up from target file)

        Parameters
        ----------
        workspace_root : str | None
            Root directory from workspace configuration
        cwd : str | None
            Current working directory
        target : str | None
            Target file or class path

        Returns
        -------
        Path | None
            Path to project root, or None if not found
        """
        # Primary: workspace_root (most specific, from launch.json)
        if workspace_root:
            wr_path = Path(workspace_root)
            if wr_path.exists():
                build_root = JavaBuildSystemDetector.find_build_root(wr_path)
                if build_root:
                    return build_root

        # Secondary: cwd (current working directory)
        if cwd:
            cwd_path = Path(cwd)
            if cwd_path.exists():
                build_root = JavaBuildSystemDetector.find_build_root(cwd_path)
                if build_root:
                    return build_root

        # Tertiary: target path (walk up)
        if target:
            t_path = Path(target)
            if t_path.exists():
                build_root = JavaBuildSystemDetector.find_build_root(t_path)
                if build_root:
                    return build_root

        return None

    @staticmethod
    def resolve_target_directory(
        target: str,
        build_root: Path | None,
        cwd: str | None,
    ) -> Path:
        """Resolve target directory with 5-case fallback logic.

        Determines the appropriate directory to use for Maven/Gradle detection
        based on the target type (file path, directory, class name).

        Parameters
        ----------
        target : str
            Target path or class name
        build_root : Path | None
            Previously detected build root
        cwd : str | None
            Current working directory

        Returns
        -------
        Path
            Resolved target directory
        """
        target_path = Path(target)

        # Case 1: Target is an existing file - use its parent directory
        if target_path.is_file():
            return target_path.parent

        # Case 2: Target contains path separators but isn't a file
        # (path-like but doesn't exist or is a directory)
        if "/" in target or "\\" in target:
            return target_path

        # Case 3: Target is an identifier (class name) - use build_root
        if build_root:
            return build_root

        # Case 4: Fallback to cwd
        if cwd:
            return Path(cwd)

        # Case 5: Last resort - use target as path
        return target_path

    @staticmethod
    def is_maven_gradle_project(target_dir: Path) -> bool:
        """Check if directory contains Maven/Gradle build files.

        Parameters
        ----------
        target_dir : Path
            Directory to check for build files

        Returns
        -------
        bool
            True if pom.xml or build.gradle(.kts) exists
        """
        return JavaBuildSystemDetector._has_build_file(target_dir)

    @staticmethod
    def _has_build_file(directory: Path) -> bool:
        """Check if directory contains any build file.

        Parameters
        ----------
        directory : Path
            Directory to check

        Returns
        -------
        bool
            True if any build file exists
        """
        return any(
            (directory / build_file).exists()
            for build_file in JavaBuildSystemDetector.BUILD_FILES
        )
