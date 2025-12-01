"""Java toolchain management utilities.

This module provides utilities for discovering and managing Java and JDK installations,
including finding Java and javac executables.
"""

import shutil
from pathlib import Path

from aidb.common.errors import AidbError
from aidb_common.config import config


class JavaToolchain:
    """Manages Java toolchain discovery and validation.

    This class provides methods for locating Java and javac executables, validating JDK
    installations, and managing Java-related paths.
    """

    def __init__(self, jdk_home: str | None = None):
        """Initialize Java toolchain.

        Parameters
        ----------
        jdk_home : Optional[str]
            Explicit JDK home path to use. If not provided, will search
            standard locations (JAVA_HOME, system PATH).
        """
        self._configured_jdk_home = jdk_home

    async def get_java_executable(self) -> str:
        """Get the Java executable path.

        Searches for Java in the following order:
        1. Configured JDK home (if provided)
        2. JAVA_HOME environment variable
        3. System PATH

        Returns
        -------
        str
            Path to java executable

        Raises
        ------
        AidbError
            If Java is not found
        """
        # Check configured JDK home first
        if self._configured_jdk_home:
            java_path = str(Path(self._configured_jdk_home) / "bin" / "java")
            if Path(java_path).exists():
                return java_path

        # Check JAVA_HOME and system PATH
        java_home = config.get_java_home()
        if java_home:
            java_path = str(Path(java_home) / "bin" / "java")
            if Path(java_path).exists():
                return java_path

        # Check system PATH
        if shutil.which("java"):
            return "java"

        msg = "Java not found. Please install Java and set JAVA_HOME"
        raise AidbError(msg)

    def get_javac_executable(self) -> str:
        """Get the javac compiler executable path.

        Searches for javac in the following order:
        1. Configured JDK home (if provided)
        2. JAVA_HOME environment variable
        3. System PATH

        Returns
        -------
        str
            Path to javac executable

        Raises
        ------
        AidbError
            If javac is not found (JDK not installed)
        """
        # Check configured JDK home first
        if self._configured_jdk_home:
            javac_path = str(Path(self._configured_jdk_home) / "bin" / "javac")
            if Path(javac_path).exists():
                return javac_path

        # Check JAVA_HOME
        java_home = config.get_java_home()
        if java_home:
            javac_path = str(Path(java_home) / "bin" / "javac")
            if Path(javac_path).exists():
                return javac_path

        # Check system PATH
        if shutil.which("javac"):
            return "javac"

        msg = "javac not found. Please install a JDK and set JAVA_HOME"
        raise AidbError(msg)

    def get_jdk_home(self) -> str | None:
        """Get the JDK home directory.

        Returns
        -------
        Optional[str]
            Path to JDK home directory, or None if not found
        """
        # Return configured JDK home if available
        if self._configured_jdk_home:
            return self._configured_jdk_home

        # Check JAVA_HOME environment variable
        return config.get_java_home()

    def validate_jdk(self) -> bool:
        """Validate that a full JDK is installed (not just JRE).

        Returns
        -------
        bool
            True if a valid JDK with javac is found, False otherwise
        """
        try:
            self.get_javac_executable()
            return True
        except AidbError:
            return False

    async def validate_java_installation(self) -> None:
        """Validate that Java is properly installed and accessible.

        Raises
        ------
        AidbError
            If Java installation is not valid
        """
        await self.get_java_executable()  # Will raise if not found

    @staticmethod
    def resolve_project_root(
        target: str | None,
        cwd: str | None = None,
    ) -> Path | None:
        """Resolve project root directory from target and cwd.

        Determines the project root by examining the target parameter:
        - If target is a directory: use it as project root
        - If target is a file path: use its parent directory
        - If target is a class identifier: use cwd as project root

        Parameters
        ----------
        target : str | None
            Target file, directory, or class identifier
        cwd : str | None
            Current working directory fallback

        Returns
        -------
        Path | None
            Resolved project root directory, or None if cannot determine
        """
        project_root = None

        # Try to determine project root from target
        if target:
            target_path = Path(target)
            if target_path.is_dir():
                project_root = target_path
            elif target_path.is_file() or (
                target_path.parent.exists() and ("/" in target or "\\" in target)
            ):
                # Target is a file path - use its parent directory
                project_root = target_path.parent

        # If target is an identifier (no path info), use cwd as project root
        if not project_root and cwd:
            cwd_path = Path(cwd)
            if cwd_path.exists() and cwd_path.is_dir():
                project_root = cwd_path

        return project_root
