"""Path constants for AIDB CLI."""

from pathlib import Path

from aidb_common.path import (
    get_aidb_adapters_dir,
    get_aidb_cache_dir,
    get_aidb_home,
    get_aidb_log_dir,
)


class ProjectPaths:
    """Standard project paths relative to repo root."""

    VERSIONS_YAML = Path("versions.json")
    AIDB_CONFIG = Path(".aidb.yaml")
    TESTS_DIR = Path("src/tests")

    TEST_DOCKER_DIR = Path("src/tests/_docker")
    TEST_DOCKER_COMPOSE = Path("src/tests/_docker/docker-compose.yaml")
    TEST_DOCKER_BASE_COMPOSE = Path("src/tests/_docker/docker-compose.base.yaml")
    TEST_DOCKER_LANGUAGES = Path("src/tests/_docker/languages.yaml")
    TEST_DOCKER_TEMPLATES = Path("src/tests/_docker/templates")

    DOCS_DOCKER_COMPOSE = Path("scripts/install/docs/docker-compose.yaml")
    DOCS_ENV_FILE = Path("scripts/install/docs/.env")

    BUILD_SCRIPT = Path("scripts/build/build_aidb.sh")
    INSTALL_SCRIPT = Path("scripts/install/src/install.sh")

    SRC_DIR = Path("src")
    ADAPTERS_DIR = Path("src/aidb/adapters/lang")
    SCRIPTS_DIR = Path("scripts")

    @staticmethod
    def venv_python(repo_root: Path) -> Path:
        """Get path to venv Python executable.

        Parameters
        ----------
        repo_root : Path
            Repository root directory

        Returns
        -------
        Path
            Path to venv/bin/python
        """
        return repo_root / "venv" / "bin" / "python"


class CachePaths:
    """Cache directory paths."""

    @staticmethod
    def user_cache() -> Path:
        """Get user cache directory (~/.cache/aidb/adapters)."""
        return get_aidb_cache_dir()

    @staticmethod
    def user_aidb() -> Path:
        """Get user AIDB base directory (~/.aidb)."""
        return get_aidb_home()

    @staticmethod
    def adapters_dir() -> Path:
        """Get user adapters directory (~/.aidb/adapters)."""
        return get_aidb_adapters_dir()

    @staticmethod
    def log_dir() -> Path:
        """Get user log directory (~/.aidb/log)."""
        return get_aidb_log_dir()

    @staticmethod
    def repo_cache(repo_root: Path) -> Path:
        """Get repo cache directory (<repo>/.cache/adapters)."""
        return repo_root / ".cache" / "adapters"

    @staticmethod
    def container_data_dir(repo_root: Path) -> Path:
        """Get container data directory (<repo>/.cache/container-data).

        Parameters
        ----------
        repo_root : Path
            Repository root directory

        Returns
        -------
        Path
            Path to .cache/container-data directory
        """
        return repo_root / ".cache" / "container-data"

    @staticmethod
    def compose_cache_dir(repo_root: Path) -> Path:
        """Get compose generation cache directory (<repo>/.cache).

        Parameters
        ----------
        repo_root : Path
            Repository root directory

        Returns
        -------
        Path
            Path to .cache directory for compose generation
        """
        return repo_root / ".cache"

    @staticmethod
    def docker_build_cache_dir(repo_root: Path) -> Path:
        """Get Docker build cache directory (<repo>/.cache/docker-build).

        This directory stores hash checksums for Docker image rebuild detection.

        Parameters
        ----------
        repo_root : Path
            Repository root directory

        Returns
        -------
        Path
            Path to .cache/docker-build directory for image checksums
        """
        return repo_root / ".cache" / "docker-build"


class DockerConstants:
    """Docker-related constants."""

    DEFAULT_PROJECT = "aidb-tests"
    DOCS_PROJECT = "aidb-docs"

    DEFAULT_NETWORK = "aidb-network"

    DEFAULT_HEALTH_TIMEOUT = 60  # seconds
    DEFAULT_STARTUP_WAIT = 2  # seconds

    # Container lifecycle marker for dependency cache invalidation
    # Written by entrypoint.sh at container startup, read by checksum service
    # This is intentionally in /tmp/ as a well-known container-local path
    CONTAINER_MARKER_FILE = Path("/tmp/.container-id")  # noqa: S108

    # Container labels - use DockerLabels.MANAGED and
    # DockerLabelValues.MANAGED_TRUE from constants.py
