"""File creation and management helpers for tests."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional


class FileTestMixin:
    """Mixin providing file creation and management utilities for tests."""

    def create_test_file(
        self,
        path: Path,
        content: str | None = None,
        language: str = "python",
        scenario: str = "hello_world",
    ) -> Path:
        """Create a test file with content.

        Parameters
        ----------
        path : Path
            File path
        content : str, optional
            File content (if None, uses scenario)
        language : str
            Programming language
        scenario : str
            Scenario name for default content

        Returns
        -------
        Path
            Created file path
        """
        from tests._assets.test_content import get_test_content

        # Create parent directory
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get content
        if content is None:
            content = get_test_content(language, scenario)

        # Write file
        path.write_text(content)

        return path

    @asynccontextmanager
    async def create_test_file_context(
        self,
        temp_dir: Path,
        filename: str = "test.py",
        content: str | None = None,
        language: str = "python",
        scenario: str = "hello_world",
    ):
        """Context manager for test file creation.

        Parameters
        ----------
        temp_dir : Path
            Temporary directory
        filename : str
            File name
        content : str, optional
            File content
        language : str
            Programming language
        scenario : str
            Scenario for default content

        Yields
        ------
        Path
            Created file path
        """
        file_path = temp_dir / filename

        try:
            # Create file
            self.create_test_file(
                file_path,
                content=content,
                language=language,
                scenario=scenario,
            )

            yield file_path

        finally:
            # Cleanup is handled by temp directory fixture
            pass

    def create_project_structure(
        self,
        root_dir: Path,
        structure: dict,
        language: str = "python",
    ) -> dict:
        """Create a project directory structure with files.

        Parameters
        ----------
        root_dir : Path
            Root directory for the project
        structure : dict
            Dictionary describing the structure
            e.g., {"src": {"main.py": "content", "lib": {"utils.py": "content"}}}
        language : str
            Default language for files without content

        Returns
        -------
        dict
            Dictionary of created paths
        """
        created_paths = {}

        def create_recursive(base_path: Path, struct: dict, prefix: str = ""):
            for name, value in struct.items():
                path = base_path / name
                full_key = f"{prefix}/{name}" if prefix else name

                if isinstance(value, dict):
                    # Directory with subdirectories/files
                    path.mkdir(parents=True, exist_ok=True)
                    create_recursive(path, value, full_key)
                else:
                    # File with content
                    if value is None:
                        # Use default content based on file extension
                        ext = path.suffix[1:] if path.suffix else ""
                        if ext in ["py", "js", "java"]:
                            value = f"# {path.name} - auto generated"

                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(value or "")
                    created_paths[full_key] = path

        create_recursive(root_dir, structure)
        return created_paths
