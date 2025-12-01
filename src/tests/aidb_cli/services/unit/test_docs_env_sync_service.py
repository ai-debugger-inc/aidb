"""Unit tests for DocsEnvSyncService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.docs.docs_env_sync_service import DocsEnvSyncService


class TestDocsEnvSyncService:
    """Test the DocsEnvSyncService."""

    @pytest.fixture
    def versions_yaml_content(self):
        """Sample versions.json content."""
        return """{
  "infrastructure": {
    "python": {
      "docker_tag": "3.12-slim"
    }
  },
  "global_packages": {
    "pip": {
      "pip": {"version": "25.3"},
      "setuptools": {"version": "80.9.0"},
      "wheel": {"version": "0.45.1"}
    }
  }
}"""

    @pytest.fixture
    def service_with_files(self, tmp_path, versions_yaml_content):
        """Create service with versions.json and env file paths."""
        # Create versions.json
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_yaml_content)

        # Create docs directory structure
        docs_dir = tmp_path / "scripts" / "install" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch(
                "aidb_cli.core.paths.ProjectPaths.VERSIONS_YAML",
                Path("versions.json"),
            ),
            patch(
                "aidb_cli.core.paths.ProjectPaths.DOCS_ENV_FILE",
                Path("scripts/install/docs/.env"),
            ),
        ):
            return DocsEnvSyncService(tmp_path)

    @pytest.fixture
    def service_without_env(self, tmp_path, versions_yaml_content):
        """Create service without existing .env file."""
        # Create versions.json only
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_yaml_content)

        # Create docs directory but no .env file
        docs_dir = tmp_path / "scripts" / "install" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch(
                "aidb_cli.core.paths.ProjectPaths.VERSIONS_YAML",
                Path("versions.json"),
            ),
            patch(
                "aidb_cli.core.paths.ProjectPaths.DOCS_ENV_FILE",
                Path("scripts/install/docs/.env"),
            ),
        ):
            return DocsEnvSyncService(tmp_path)

    def test_service_initialization(self, tmp_path, versions_yaml_content):
        """Test service initialization sets up paths correctly."""
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_yaml_content)

        with (
            patch(
                "aidb_cli.core.paths.ProjectPaths.VERSIONS_YAML",
                Path("versions.json"),
            ),
            patch(
                "aidb_cli.core.paths.ProjectPaths.DOCS_ENV_FILE",
                Path("scripts/install/docs/.env"),
            ),
        ):
            service = DocsEnvSyncService(tmp_path)

            assert service.repo_root == tmp_path
            assert service.versions_file == tmp_path / "versions.json"
            assert (
                service.env_file == tmp_path / "scripts" / "install" / "docs" / ".env"
            )
            assert service.hash_cache_file == tmp_path / ".cache" / "docs-env-hash"

    def test_compute_source_hash(self, service_with_files):
        """Test computing hash of versions.json."""
        hash_value = service_with_files._compute_source_hash()

        # Should return a valid hash string
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0

    def test_hash_stability(self, service_with_files):
        """Test that hash computation is stable across multiple calls."""
        hash1 = service_with_files._compute_source_hash()
        hash2 = service_with_files._compute_source_hash()
        hash3 = service_with_files._compute_source_hash()

        assert hash1 == hash2 == hash3

    def test_hash_changes_with_file_modification(
        self,
        service_with_files,
        versions_yaml_content,
    ):
        """Test that hash changes when versions.json is modified."""
        initial_hash = service_with_files._compute_source_hash()

        # Modify versions.json
        modified_content = versions_yaml_content.replace("3.12-slim", "3.13-slim")
        service_with_files.versions_file.write_text(modified_content)

        new_hash = service_with_files._compute_source_hash()
        assert new_hash != initial_hash

    def test_get_cached_hash_when_not_exists(self, service_with_files):
        """Test getting cached hash when cache file doesn't exist."""
        # Ensure cache file doesn't exist
        if service_with_files.hash_cache_file.exists():
            service_with_files.hash_cache_file.unlink()

        cached_hash = service_with_files._get_cached_hash()
        assert cached_hash == ""

    def test_save_and_get_cached_hash(self, service_with_files):
        """Test saving and retrieving cached hash."""
        test_hash = "abc123def456"

        service_with_files._save_hash(test_hash)

        cached_hash = service_with_files._get_cached_hash()
        assert cached_hash == test_hash

    def test_needs_sync_when_env_missing(self, service_without_env):
        """Test needs_sync returns True when .env file doesn't exist."""
        assert service_without_env.needs_sync() is True

    def test_needs_sync_when_hash_mismatch(self, service_with_files):
        """Test needs_sync returns True when hashes don't match."""
        # Create .env file
        service_with_files.env_file.parent.mkdir(parents=True, exist_ok=True)
        service_with_files.env_file.write_text("# old content")

        # Save old hash
        service_with_files._save_hash("old_hash_value")

        # Current hash will be different
        assert service_with_files.needs_sync() is True

    def test_needs_sync_when_up_to_date(self, service_with_files):
        """Test needs_sync returns False when .env is up-to-date."""
        # Create .env file
        service_with_files.env_file.parent.mkdir(parents=True, exist_ok=True)
        service_with_files.env_file.write_text("# content")

        # Save current hash
        current_hash = service_with_files._compute_source_hash()
        service_with_files._save_hash(current_hash)

        assert service_with_files.needs_sync() is False

    def test_generate_env_content(self, service_with_files):
        """Test generating .env file content from versions.json."""
        content = service_with_files._generate_env_content()

        # Verify header
        assert "Auto-generated from versions.json" in content
        assert "DO NOT EDIT MANUALLY" in content

        # Verify Python tag
        assert "PYTHON_TAG=python:3.12-slim" in content

        # Verify package versions
        assert "PIP_VERSION=25.3" in content
        assert "SETUPTOOLS_VERSION=80.9.0" in content
        assert "WHEEL_VERSION=0.45.1" in content

        # Verify performance optimizations section
        assert "# SKIP_API_DOCS=1" in content
        assert "# SKIP_LINKCHECK=1" in content
        assert "# FORCE_API_DOCS=1" in content

    def test_sync_when_needed(self, service_without_env):
        """Test sync generates .env file when needed."""
        result = service_without_env.sync()

        assert result is True
        assert service_without_env.env_file.exists()

        # Verify content
        content = service_without_env.env_file.read_text()
        assert "PYTHON_TAG=python:3.12-slim" in content
        assert "PIP_VERSION=25.3" in content

        # Verify hash was saved
        cached_hash = service_without_env._get_cached_hash()
        assert cached_hash != ""

    def test_sync_when_not_needed(self, service_with_files):
        """Test sync skips generation when not needed."""
        # Create .env file
        service_with_files.env_file.parent.mkdir(parents=True, exist_ok=True)
        service_with_files.env_file.write_text("# existing content")

        # Save current hash
        current_hash = service_with_files._compute_source_hash()
        service_with_files._save_hash(current_hash)

        result = service_with_files.sync()

        assert result is False
        # .env should still have old content
        assert service_with_files.env_file.read_text() == "# existing content"

    def test_sync_with_force(self, service_with_files):
        """Test sync with force=True regenerates even when not needed."""
        # Create .env file
        service_with_files.env_file.parent.mkdir(parents=True, exist_ok=True)
        service_with_files.env_file.write_text("# existing content")

        # Save current hash
        current_hash = service_with_files._compute_source_hash()
        service_with_files._save_hash(current_hash)

        result = service_with_files.sync(force=True)

        assert result is True
        # .env should have new content
        content = service_with_files.env_file.read_text()
        assert "PYTHON_TAG=python:3.12-slim" in content

    def test_sync_if_needed(self, service_without_env):
        """Test sync_if_needed convenience method."""
        result = service_without_env.sync_if_needed()

        assert result is True
        assert service_without_env.env_file.exists()

    def test_sync_if_needed_when_not_needed(self, service_with_files):
        """Test sync_if_needed skips when not needed."""
        # Create .env file
        service_with_files.env_file.parent.mkdir(parents=True, exist_ok=True)
        service_with_files.env_file.write_text("# existing")

        # Save current hash
        current_hash = service_with_files._compute_source_hash()
        service_with_files._save_hash(current_hash)

        result = service_with_files.sync_if_needed()

        assert result is False

    def test_sync_after_versions_change(
        self,
        service_with_files,
        versions_yaml_content,
    ):
        """Test complete workflow: sync, modify versions, sync again."""
        # Initial sync
        service_with_files.sync()
        initial_content = service_with_files.env_file.read_text()
        assert "PYTHON_TAG=python:3.12-slim" in initial_content

        # Should not need sync
        assert service_with_files.needs_sync() is False

        # Modify versions.json
        modified_content = versions_yaml_content.replace("3.12-slim", "3.13-slim")
        service_with_files.versions_file.write_text(modified_content)

        # Create a new service instance to force reload of versions.json
        from aidb_cli.services.docs.docs_env_sync_service import DocsEnvSyncService

        new_service = DocsEnvSyncService(service_with_files.repo_root)

        # Should now need sync
        assert new_service.needs_sync() is True

        # Sync again
        result = new_service.sync()
        assert result is True

        # Verify new content
        new_content = new_service.env_file.read_text()
        assert "PYTHON_TAG=python:3.13-slim" in new_content

    def test_env_content_includes_timestamp(self, service_with_files):
        """Test that generated .env content includes timestamp."""
        content = service_with_files._generate_env_content()

        # Should include "Generated: YYYY-MM-DD HH:MM:SS UTC"
        assert "Generated:" in content
        assert "UTC" in content

    def test_env_content_format(self, service_with_files):
        """Test that generated .env content has correct format."""
        content = service_with_files._generate_env_content()

        # Should start with comment block
        lines = content.strip().split("\n")
        assert lines[0].startswith("#")
        assert lines[1].startswith("#")
        assert lines[2].startswith("#")

        # Should have empty line after header
        assert lines[3] == ""

        # Should have PYTHON_TAG
        assert any(line.startswith("PYTHON_TAG=") for line in lines)

        # Should have comment section for global packages
        assert any("Global package versions" in line for line in lines)

    def test_hash_cache_directory_creation(self, tmp_path, versions_yaml_content):
        """Test that hash cache directory is created if needed."""
        versions_file = tmp_path / "versions.json"
        versions_file.write_text(versions_yaml_content)

        with (
            patch(
                "aidb_cli.core.paths.ProjectPaths.VERSIONS_YAML",
                Path("versions.json"),
            ),
            patch(
                "aidb_cli.core.paths.ProjectPaths.DOCS_ENV_FILE",
                Path("scripts/install/docs/.env"),
            ),
        ):
            service = DocsEnvSyncService(tmp_path)

            # Cache directory should not exist yet
            assert not service.hash_cache_file.exists()

            # Save hash should create directory
            service._save_hash("test_hash")

            assert service.hash_cache_file.parent.exists()
            assert service.hash_cache_file.exists()

    def test_env_file_directory_creation(self, service_without_env):
        """Test that .env file directory is created during sync."""
        # Ensure docs directory doesn't exist
        if service_without_env.env_file.exists():
            service_without_env.env_file.unlink()
        if service_without_env.env_file.parent.exists():
            service_without_env.env_file.parent.rmdir()

        service_without_env.sync()

        assert service_without_env.env_file.parent.exists()
        assert service_without_env.env_file.exists()
