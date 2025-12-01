"""Service for tracking framework app dependency checksums.

This service implements intelligent dependency installation detection by tracking
checksums of dependency files (package.json, requirements.txt, pom.xml). It prevents
unnecessary reinstallation while ensuring dependencies stay up-to-date.
"""

from pathlib import Path

from aidb_cli.core.paths import DockerConstants
from aidb_common.io import ChecksumServiceBase, compute_files_hash
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class FrameworkDepsChecksumService(ChecksumServiceBase):
    """Tracks framework app dependency file checksums for cache invalidation.

    This service provides per-app dependency tracking to determine when
    dependencies need reinstallation. It tracks language-specific dependency files:
    - JavaScript: package.json, package-lock.json
    - Python: requirements.txt
    - Java: pom.xml, build.gradle, build.gradle.kts

    When any tracked dependency file changes, the app is marked for reinstallation.
    This provides more granular caching than language-level markers.

    Examples
    --------
    >>> from pathlib import Path
    >>> service = FrameworkDepsChecksumService(Path("/framework_apps"))
    >>> needs_install, reason = service.needs_install("javascript", "express_app")
    >>> if needs_install:
    ...     print(f"Install needed: {reason}")
    """

    # Dependency file patterns per language
    DEPENDENCY_PATTERNS = {
        "javascript": ["package.json", "package-lock.json", "yarn.lock"],
        "python": ["requirements.txt", "pyproject.toml", "setup.py"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    }

    def __init__(self, framework_root: Path) -> None:
        """Initialize the framework deps checksum service.

        Parameters
        ----------
        framework_root : Path
            Root directory containing framework apps
            (e.g., /repo/src/tests/_assets/framework_apps)
        """
        cache_dir = framework_root / ".cache"
        super().__init__(cache_dir)
        self.framework_root = framework_root

    def _get_app_identifier(self, language: str, app_name: str) -> str:
        """Get unique identifier for an app.

        Parameters
        ----------
        language : str
            Programming language (e.g., "javascript", "python", "java")
        app_name : str
            Application name (e.g., "express_app", "django_app")

        Returns
        -------
        str
            Unique identifier (e.g., "javascript-express_app")
        """
        return f"{language}-{app_name}"

    def _get_hash_cache_file(self, identifier: str) -> Path:
        """Get hash cache file path for app.

        Parameters
        ----------
        identifier : str
            App identifier (e.g., "javascript-express_app")

        Returns
        -------
        Path
            Path to cache file
        """
        return self.cache_dir / f".deps-hash-{identifier}"

    def _compute_hash(self, identifier: str) -> str:
        """Compute hash of dependency files for an app.

        Parameters
        ----------
        identifier : str
            App identifier (e.g., "javascript-express_app")

        Returns
        -------
        str
            SHA256 hash of all dependency files
        """
        language, app_name = identifier.split("-", 1)
        app_dir = self.framework_root / language / app_name
        dep_files = self._get_dependency_files(app_dir, language)
        return compute_files_hash(dep_files)

    def _exists(self, identifier: str) -> bool:
        """Check if app dependencies exist.

        For dependency checking, we assume the app directory exists if we're
        checking it. The hash comparison will determine if dependencies need
        to be reinstalled.

        Parameters
        ----------
        identifier : str
            App identifier (e.g., "javascript-express_app")

        Returns
        -------
        bool
            Always returns True (we check hash changes, not artifact existence)
        """
        # For dependencies, we always return True because we want to check
        # hash changes rather than artifact existence (unlike Docker images).
        # If there's no cached hash, needs_update will return True anyway.
        logger.debug(
            "Checking existence for %s (always True for dependencies)",
            identifier,
        )
        return True

    def _get_artifact_context(self, identifier: str) -> dict[str, str]:
        """Get container lifecycle context for cache invalidation.

        Reads the container ID from container marker file created
        at container startup. If the container ID changes (container restart),
        the cache is invalidated even if dependency files haven't changed.

        This solves the problem where:
        - Hash files persist on host filesystem (via bind mount)
        - Installed packages don't persist (ephemeral container filesystem)
        - Service incorrectly reports "up-to-date" when packages are missing

        Parameters
        ----------
        identifier : str
            App identifier

        Returns
        -------
        dict[str, str]
            {"container_id": "<hostname>"} if marker exists, else {}
        """
        if DockerConstants.CONTAINER_MARKER_FILE.exists():
            try:
                container_id = DockerConstants.CONTAINER_MARKER_FILE.read_text().strip()
                logger.debug("Container ID for %s: %s", identifier, container_id)
                return {"container_id": container_id}
            except OSError as e:
                logger.warning("Failed to read container marker: %s", e)

        logger.debug("No container marker found for %s", identifier)
        return {}

    def _get_dependency_files(self, app_dir: Path, language: str) -> list[Path]:
        """Find dependency files for an app.

        Parameters
        ----------
        app_dir : Path
            Application directory
        language : str
            Programming language

        Returns
        -------
        list[Path]
            List of existing dependency file paths
        """
        patterns = self.DEPENDENCY_PATTERNS.get(language, [])
        files = []
        for pattern in patterns:
            file_path = app_dir / pattern
            if file_path.exists():
                files.append(file_path)
        return files

    def needs_install(self, language: str, app_name: str) -> tuple[bool, str]:
        """Check if app dependencies need installation.

        Parameters
        ----------
        language : str
            Programming language (e.g., "javascript", "python", "java")
        app_name : str
            Application name (e.g., "express_app", "django_app")

        Returns
        -------
        tuple[bool, str]
            (needs_install, reason) where reason explains why installation
            is needed or why it's not needed

        Examples
        --------
        >>> service = FrameworkDepsChecksumService(Path("/framework_apps"))
        >>> needs_install, reason = service.needs_install("javascript", "jest_suite")
        >>> print(f"Install: {needs_install}, Reason: {reason}")
        Install: True, Reason: No cached hash found (first run)
        """
        identifier = self._get_app_identifier(language, app_name)
        logger.debug("Checking %s dependencies", identifier)
        return self.needs_update(identifier)

    def mark_installed(self, language: str, app_name: str) -> None:
        """Mark app dependencies as installed.

        Call this after successfully installing dependencies to update
        the cached hash and prevent unnecessary future installations.

        Parameters
        ----------
        language : str
            Programming language
        app_name : str
            Application name
        """
        identifier = self._get_app_identifier(language, app_name)
        self.mark_updated(identifier)
        logger.debug("Marked %s dependencies as installed", identifier)

    def check_all_apps(self, language: str) -> dict[str, tuple[bool, str]]:
        """Check installation status for all apps of a language.

        Parameters
        ----------
        language : str
            Programming language to check

        Returns
        -------
        dict[str, tuple[bool, str]]
            Map of app_name -> (needs_install, reason)

        Examples
        --------
        >>> service = FrameworkDepsChecksumService(Path("/framework_apps"))
        >>> status = service.check_all_apps("javascript")
        >>> for app, (needs_install, reason) in status.items():
        ...     print(f"{app}: {needs_install} - {reason}")
        express_app: False - Up-to-date
        jest_suite: True - No cached hash found (first run)
        """
        language_dir = self.framework_root / language
        if not language_dir.exists():
            logger.warning("Language directory not found: %s", language_dir)
            return {}

        results = {}
        for app_dir in language_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("."):
                app_name = app_dir.name
                results[app_name] = self.needs_install(language, app_name)

        return results
