"""Java classpath management utilities.

This module provides utilities for building classpaths, extracting main classes, and
managing JAR manifest files.
"""

from pathlib import Path

from aidb.common.errors import AidbError


class JavaClasspathBuilder:
    """Manages Java classpath construction and main class resolution.

    This class provides methods for building classpaths from various sources and
    extracting main class information from Java files and JARs.
    """

    def __init__(self, base_classpath: list[str] | None = None):
        """Initialize classpath builder.

        Parameters
        ----------
        base_classpath : Optional[List[str]]
            Base classpath entries to include in all builds
        """
        self._base_classpath = base_classpath or []

    def build_classpath(
        self,
        target: str,
        additional_entries: list[str] | None = None,
        temp_compile_dir: str | None = None,
    ) -> list[str]:
        """Build classpath for the debug session.

        Parameters
        ----------
        target : str
            The target file being debugged (.class, .jar, or .java)
        additional_entries : Optional[List[str]]
            Additional classpath entries to include
        temp_compile_dir : Optional[str]
            Temporary compilation directory if source was compiled

        Returns
        -------
        List[str]
            Complete classpath entries
        """
        classpath = list(self._base_classpath)

        # Add additional entries if provided
        if additional_entries:
            classpath.extend(additional_entries)

        # Add target directory or JAR
        if target.endswith(".jar"):
            classpath.append(target)
        else:
            # Add parent directory of class file
            classpath.append(str(Path(target).parent))

        # Add temp compile directory if we compiled
        if temp_compile_dir:
            classpath.append(temp_compile_dir)

        # Add current directory if not already present
        if "." not in classpath:
            classpath.append(".")

        return classpath

    def extract_main_class(
        self,
        target: str,
        explicit_main_class: str | None = None,
    ) -> str:
        """Extract main class name from target.

        Parameters
        ----------
        target : str
            Path to .class file, .jar file, or .java file
        explicit_main_class : Optional[str]
            Explicitly provided main class name (takes precedence)

        Returns
        -------
        str
            Fully qualified main class name

        Raises
        ------
        AidbError
            If main class cannot be determined for JAR files
        """
        # Use explicit main class if provided
        if explicit_main_class:
            return explicit_main_class

        if target.endswith(".class"):
            # Extract class name from path
            # This is simplified - real implementation would need to handle packages
            return Path(target).stem

        if target.endswith(".jar"):
            # For JARs, we'd need to read the manifest or require main_class
            # In a full implementation, this would parse META-INF/MANIFEST.MF
            msg = "For JAR files, please specify main_class parameter"
            raise AidbError(msg)

        # For .java files (that we compiled or will compile)
        return Path(target).stem

    def resolve_jar_manifest(self, jar_path: str) -> str | None:
        """Extract main class from JAR manifest.

        Parameters
        ----------
        jar_path : str
            Path to JAR file

        Returns
        -------
        Optional[str]
            Main class name from manifest, or None if not found

        Notes
        -----
        This is a placeholder for future implementation. A complete version
        would use zipfile to read META-INF/MANIFEST.MF and parse Main-Class attribute.
        """
        # TODO: Implement JAR manifest parsing
        # import zipfile
        # with zipfile.ZipFile(jar_path, 'r') as jar:
        #     try:
        #         manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8')
        #         for line in manifest.split('\n'):
        #             if line.startswith('Main-Class:'):
        #                 return line.split(':', 1)[1].strip()
        #     except KeyError:
        #         pass
        return None

    def normalize_class_name(self, class_name: str) -> str:
        """Normalize a class name to fully qualified format.

        Parameters
        ----------
        class_name : str
            Class name (may be simple or fully qualified)

        Returns
        -------
        str
            Normalized class name
        """
        # Remove .class extension if present
        class_name = class_name.removesuffix(".class")

        # Replace path separators with dots for package names
        class_name = class_name.replace("/", ".").replace("\\", ".")

        return class_name
