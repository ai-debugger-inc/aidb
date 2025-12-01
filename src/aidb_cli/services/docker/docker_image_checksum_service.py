"""Service for tracking Docker image checksums to detect rebuild requirements.

This service implements intelligent image rebuild detection by tracking file checksums
that affect Docker images. It prevents unnecessary rebuilds while ensuring images are
rebuilt when dependencies change.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from aidb_cli.core.paths import CachePaths, ProjectPaths
from aidb_common.constants import Language
from aidb_common.io import ChecksumServiceBase, compute_files_hash
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DockerImageType:
    """Docker image types that can be tracked for rebuild detection."""

    BASE = "base"
    PYTHON = Language.PYTHON.value
    JAVASCRIPT = Language.JAVASCRIPT.value
    JAVA = Language.JAVA.value

    @classmethod
    def all_language_images(cls) -> list[str]:
        """Get all language-specific image types.

        Returns
        -------
        list[str]
            List of language image type names
        """
        return [cls.PYTHON, cls.JAVASCRIPT, cls.JAVA]

    @classmethod
    def all_images(cls) -> list[str]:
        """Get all image types including base.

        Returns
        -------
        list[str]
            List of all image type names
        """
        return [cls.BASE] + cls.all_language_images()


class DockerImageChecksumService(ChecksumServiceBase):
    """Tracks file checksums to determine when Docker images need rebuilding.

    This service maintains hash caches similar to ComposeGeneratorService,
    tracking changes in:
    - Dependency files (pyproject.toml, package.json, pom.xml)
    - Dockerfiles
    - Build scripts
    - Version configuration files

    When any tracked file changes, the affected image is marked for rebuild.
    This prevents unnecessary rebuilds while ensuring images stay up-to-date.

    Examples
    --------
    >>> from pathlib import Path
    >>> service = DockerImageChecksumService(Path("/repo"))
    >>> needs_rebuild, reason = service.needs_rebuild("python")
    >>> if needs_rebuild:
    ...     print(f"Rebuild needed: {reason}")
    """

    # Files that affect each image type
    # When any of these files change, the image needs to be rebuilt
    IMAGE_DEPENDENCIES = {
        DockerImageType.BASE: [
            ProjectPaths.VERSIONS_YAML,
            Path("pyproject.toml"),
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.base",
            ProjectPaths.TEST_DOCKER_DIR / "scripts" / "entrypoint.sh",
            ProjectPaths.TEST_DOCKER_DIR / "scripts" / "install-framework-deps.sh",
        ],
        DockerImageType.PYTHON: [
            ProjectPaths.VERSIONS_YAML,
            Path("pyproject.toml"),
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.base",
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.python",
        ],
        DockerImageType.JAVASCRIPT: [
            ProjectPaths.VERSIONS_YAML,
            Path("pyproject.toml"),
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.base",
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.javascript",
        ],
        DockerImageType.JAVA: [
            ProjectPaths.VERSIONS_YAML,
            Path("pyproject.toml"),
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.base",
            ProjectPaths.TEST_DOCKER_DIR / "dockerfiles" / "Dockerfile.test.java",
        ],
    }

    def __init__(
        self,
        repo_root: Path,
        command_executor: "CommandExecutor | None" = None,
    ) -> None:
        """Initialize the checksum service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor for running Docker commands
        """
        cache_dir = CachePaths.docker_build_cache_dir(repo_root)
        super().__init__(cache_dir)
        self.repo_root = repo_root
        self.command_executor = command_executor

    def _get_hash_cache_file(self, image_type: str) -> Path:
        """Get hash cache file path for image type.

        Parameters
        ----------
        image_type : str
            Image type (e.g., "base", "python")

        Returns
        -------
        Path
            Path to cache file for this image type
        """
        return self.cache_dir / f"{image_type}-image-hash"

    def _compute_hash(self, image_type: str) -> str:
        """Compute hash of files affecting an image.

        Parameters
        ----------
        image_type : str
            Image type to compute hash for

        Returns
        -------
        str
            SHA256 hash of all dependency files
        """
        file_paths = self.IMAGE_DEPENDENCIES.get(image_type, [])
        absolute_paths = [self.repo_root / p for p in file_paths]
        return compute_files_hash(absolute_paths)

    def _exists(self, image_type: str) -> bool:
        """Check if Docker image exists locally.

        Parameters
        ----------
        image_type : str
            Image type (e.g., "python", "javascript")

        Returns
        -------
        bool
            True if image exists
        """
        if not self.command_executor:
            logger.debug("No command executor available, assuming image doesn't exist")
            return False

        image_name = self._get_image_name(image_type)
        result = self.command_executor.execute(
            ["docker", "image", "inspect", image_name],
            check=False,
            capture_output=True,
        )
        return result.returncode == 0

    def needs_rebuild(self, image_type: str) -> tuple[bool, str]:
        """Check if image needs rebuilding.

        Compares current file hashes against cached hashes to determine
        if the image needs to be rebuilt.

        Parameters
        ----------
        image_type : str
            Image type to check (e.g., "base", "python", "javascript", "java")

        Returns
        -------
        tuple[bool, str]
            (needs_rebuild, reason) where reason explains why rebuild is needed
            or why it's not needed

        Examples
        --------
        >>> service = DockerImageChecksumService(Path("/repo"))
        >>> needs_rebuild, reason = service.needs_rebuild("python")
        >>> print(f"Rebuild: {needs_rebuild}, Reason: {reason}")
        Rebuild: True, Reason: Source files changed (hash mismatch)
        """
        image_name = self._get_image_name(image_type)
        logger.debug("Checking rebuild for %s (image: %s)", image_type, image_name)
        return self.needs_update(image_type)

    def mark_built(self, image_type: str) -> None:
        """Mark image as built by saving current hash.

        Call this after successfully building an image to update the
        cached hash and prevent unnecessary future rebuilds.

        Parameters
        ----------
        image_type : str
            Image type that was built
        """
        self.mark_updated(image_type)
        current_hash = self._compute_hash(image_type)
        logger.debug(
            "Marked %s image as built (hash: %s)",
            image_type,
            current_hash[:8],
        )

    def _get_image_name(self, image_type: str) -> str:
        """Get Docker image name for type.

        Parameters
        ----------
        image_type : str
            Image type

        Returns
        -------
        str
            Full image name with tag
        """
        return f"aidb-test-{image_type}:latest"

    def check_all_images(self) -> dict[str, tuple[bool, str]]:
        """Check rebuild status for all images.

        Returns
        -------
        dict[str, tuple[bool, str]]
            Map of image_type -> (needs_rebuild, reason)

        Examples
        --------
        >>> service = DockerImageChecksumService(Path("/repo"))
        >>> status = service.check_all_images()
        >>> for img, (rebuild, reason) in status.items():
        ...     print(f"{img}: {rebuild} - {reason}")
        base: False - Up-to-date
        python: True - Source files changed (hash mismatch)
        javascript: False - Up-to-date
        java: False - Up-to-date
        """
        results = {}
        for image_type in DockerImageType.all_images():
            results[image_type] = self.needs_rebuild(image_type)
        return results
