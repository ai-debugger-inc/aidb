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
            # Extract class name from path, normalizing package separators
            return self.normalize_class_name(Path(target).stem)

        if target.endswith(".jar"):
            # Try to read main class from JAR manifest
            main_class = self.resolve_jar_manifest(target)
            if main_class:
                return main_class
            msg = (
                "For JAR files without Main-Class manifest attribute, "
                "please specify main_class parameter"
            )
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
        """
        import zipfile

        try:
            with zipfile.ZipFile(jar_path, "r") as jar:
                manifest = jar.read("META-INF/MANIFEST.MF").decode("utf-8")
                for line in manifest.split("\n"):
                    if line.startswith("Main-Class:"):
                        return line.split(":", 1)[1].strip()
        except (KeyError, zipfile.BadZipFile, FileNotFoundError):
            pass
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
        # Remove .class extension if present, then replace path separators with dots
        return class_name.removesuffix(".class").replace("/", ".").replace("\\", ".")

    @staticmethod
    def flatten_classpath(classpath: list) -> list[str]:
        """Flatten nested classpath lists from JDT LS.

        JDT LS resolveClasspath may return nested list structures. This method
        flattens them into a single-level list of classpath entries.

        Parameters
        ----------
        classpath : list
            Potentially nested list of classpath entries

        Returns
        -------
        list[str]
            Flat list of classpath entries (empty strings filtered out)
        """
        flat_classpath: list[str] = []
        for entry in classpath:
            if isinstance(entry, list):
                flat_classpath.extend(entry)
            elif entry:  # Skip empty strings
                flat_classpath.append(entry)
        return flat_classpath

    @staticmethod
    def add_target_classes(
        classpath: list[str],
        target_dir: Path,
    ) -> list[str]:
        """Add target/classes to classpath if missing.

        For Maven/Gradle projects, JDT LS may not include target/classes
        when resolving classpath. This method adds it at the beginning
        if it exists and isn't already present.

        Parameters
        ----------
        classpath : list[str]
            Current classpath entries
        target_dir : Path
            Target directory (project root or source directory)

        Returns
        -------
        list[str]
            Updated classpath with target/classes prepended if applicable
        """
        main_classes_dir = target_dir / "target" / "classes"
        if main_classes_dir.exists():
            main_classes_path = str(main_classes_dir)
            if main_classes_path not in classpath:
                # Insert at beginning of classpath
                classpath = [main_classes_path, *classpath]
        return classpath

    @staticmethod
    def add_test_classes(
        classpath: list[str],
        project_root: Path | None,
        main_class: str,
    ) -> list[str]:
        """Add target/test-classes for JUnit launchers.

        JDT LS resolves classpath for main classes only, missing test outputs.
        This method adds test-classes when running JUnit tests.

        Parameters
        ----------
        classpath : list[str]
            Current classpath entries
        project_root : Path | None
            Project root directory
        main_class : str
            Main class name to check for JUnit launcher

        Returns
        -------
        list[str]
            Updated classpath with test-classes added if applicable
        """
        # Check if this is a JUnit launcher
        is_junit_launcher = "junit" in main_class.lower()
        if not is_junit_launcher or not project_root:
            return classpath

        test_classes_dir = project_root / "target" / "test-classes"
        if not test_classes_dir.exists():
            return classpath

        test_classes_path = str(test_classes_dir)
        if test_classes_path in classpath:
            return classpath

        # Insert after target/classes if present, otherwise at start
        main_classes = str(project_root / "target" / "classes")
        try:
            idx = classpath.index(main_classes)
            classpath = [
                *classpath[: idx + 1],
                test_classes_path,
                *classpath[idx + 1 :],
            ]
        except ValueError:
            # target/classes not in classpath, add at beginning
            classpath = [test_classes_path, *classpath]

        return classpath
