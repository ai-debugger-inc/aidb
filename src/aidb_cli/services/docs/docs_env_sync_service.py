"""Service for syncing versions.yaml to docs .env file."""

from datetime import datetime, timezone
from pathlib import Path

from aidb_cli.core.paths import CachePaths, ProjectPaths
from aidb_common.config import VersionManager
from aidb_common.io import compute_files_hash, read_cache_file, write_cache_file
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class DocsEnvSyncService:
    """Service for syncing versions from versions.yaml to docs .env file.

    This service ensures the docs Docker compose .env file stays in sync with
    versions.yaml by auto-generating it with hash-based change detection.
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialize the docs env sync service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        """
        self.repo_root = repo_root
        self.versions_file = repo_root / ProjectPaths.VERSIONS_YAML
        self.env_file = repo_root / ProjectPaths.DOCS_ENV_FILE
        self.hash_cache_file = CachePaths.compose_cache_dir(repo_root) / "docs-env-hash"
        self.version_manager = VersionManager(self.versions_file)

    def _compute_source_hash(self) -> str:
        """Compute hash of source files that affect .env generation.

        Returns
        -------
        str
            Hash of versions.yaml
        """
        return compute_files_hash([self.versions_file])

    def _get_cached_hash(self) -> str:
        """Get the cached hash value.

        Returns
        -------
        str
            Cached hash value, or empty string if not found
        """
        return read_cache_file(self.hash_cache_file) or ""

    def _save_hash(self, hash_value: str) -> None:
        """Save hash value to cache.

        Parameters
        ----------
        hash_value : str
            Hash to save
        """
        write_cache_file(self.hash_cache_file, hash_value)

    def needs_sync(self) -> bool:
        """Check if .env file needs regeneration.

        Returns
        -------
        bool
            True if sync is needed
        """
        if not self.env_file.exists():
            logger.debug("Docs .env file does not exist, sync needed")
            return True

        current_hash = self._compute_source_hash()
        cached_hash = self._get_cached_hash()

        if cached_hash != current_hash:
            logger.debug("versions.yaml changed (hash mismatch), sync needed")
            return True

        logger.debug("No changes detected, using existing docs .env file")
        return False

    def _generate_env_content(self) -> str:
        """Generate .env file content from versions.yaml.

        Returns
        -------
        str
            Generated .env file content
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Get all docker build args from versions.yaml
        build_args = self.version_manager.get_docker_build_args()

        # Extract needed values
        python_base_tag = build_args["PYTHON_BASE_TAG"]
        pip_version = build_args["PIP_VERSION"]
        setuptools_version = build_args["SETUPTOOLS_VERSION"]
        wheel_version = build_args["WHEEL_VERSION"]

        return f"""# Auto-generated from versions.yaml - DO NOT EDIT MANUALLY
# Generated: {now}
# This file is automatically synced before docs docker operations

PYTHON_TAG=python:{python_base_tag}

# Global package versions (from versions.yaml::global_packages)
PIP_VERSION={pip_version}
SETUPTOOLS_VERSION={setuptools_version}
WHEEL_VERSION={wheel_version}

# Performance optimizations for documentation builds
# SKIP_API_DOCS=1    # Set to skip expensive autoapi generation (useful for tests)
# SKIP_LINKCHECK=1   # Set to skip link checking (faster builds)
# FORCE_API_DOCS=1   # Set to force autoapi rebuild even if unchanged
"""

    def sync(self, force: bool = False) -> bool:
        """Sync versions.yaml to docs .env file.

        Parameters
        ----------
        force : bool, default=False
            Force regeneration even if not needed

        Returns
        -------
        bool
            True if file was regenerated, False if skipped
        """
        if not force and not self.needs_sync():
            return False

        logger.info("Syncing versions.yaml to docs .env file...")

        content = self._generate_env_content()
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text(content)
        self._save_hash(self._compute_source_hash())

        logger.info("Docs .env file generated: %s", self.env_file)
        return True

    def sync_if_needed(self) -> bool:
        """Sync .env file only if versions.yaml changed.

        Convenience method that always checks need before syncing.

        Returns
        -------
        bool
            True if file was regenerated, False if skipped
        """
        return self.sync(force=False)
