"""Unit tests for DockerImageChecksumService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.services.docker.docker_image_checksum_service import (
    DockerImageChecksumService,
    DockerImageType,
)


class TestDockerImageType:
    """Test DockerImageType constants and helpers."""

    def test_image_type_constants(self):
        """Test that image type constants are defined correctly."""
        assert DockerImageType.BASE == "base"
        assert DockerImageType.PYTHON == "python"
        assert DockerImageType.JAVASCRIPT == "javascript"
        assert DockerImageType.JAVA == "java"

    def test_all_language_images(self):
        """Test all_language_images returns language-specific images."""
        images = DockerImageType.all_language_images()
        assert images == ["python", "javascript", "java"]
        assert "base" not in images

    def test_all_images(self):
        """Test all_images returns all image types including base."""
        images = DockerImageType.all_images()
        assert images == ["base", "python", "javascript", "java"]


class TestDockerImageChecksumService:
    """Test the DockerImageChecksumService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create a DockerImageChecksumService instance with temp directory."""
        return DockerImageChecksumService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    @pytest.fixture
    def service_with_files(self, tmp_path, mock_command_executor):
        """Create service with sample dependency files."""
        # Create minimal dependency files
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "versions.yaml").write_text("python: '3.12'")

        # Create docker directory structure
        docker_dir = tmp_path / "src/tests/_docker"
        docker_dir.mkdir(parents=True, exist_ok=True)
        dockerfiles_dir = docker_dir / "dockerfiles"
        dockerfiles_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir = docker_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Create dockerfiles
        (dockerfiles_dir / "Dockerfile.test.base").write_text("FROM python:3.12")
        (dockerfiles_dir / "Dockerfile.test.python").write_text("FROM aidb-test-base")
        (dockerfiles_dir / "Dockerfile.test.javascript").write_text(
            "FROM aidb-test-base",
        )
        (dockerfiles_dir / "Dockerfile.test.java").write_text("FROM aidb-test-base")

        # Create scripts
        (scripts_dir / "entrypoint.sh").write_text("#!/bin/bash\necho 'test'")
        (scripts_dir / "install-framework-deps.sh").write_text(
            "#!/bin/bash\necho 'install'",
        )

        return DockerImageChecksumService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_service_initialization(self, tmp_path, mock_command_executor):
        """Test service initialization creates cache directory."""
        service = DockerImageChecksumService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.repo_root == tmp_path
        assert service.cache_dir == tmp_path / ".cache" / "docker-build"
        assert service.cache_dir.exists()
        assert service.command_executor == mock_command_executor

    def test_get_hash_cache_file(self, service):
        """Test hash cache file path generation."""
        cache_file = service._get_hash_cache_file("python")
        assert cache_file.name == "python-image-hash"
        assert cache_file.parent == service.cache_dir

    def test_compute_hash(self, service_with_files):
        """Test computing hash for image dependencies."""
        hash_value = service_with_files._compute_hash("base")

        # Should return a valid SHA256 hash
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA256 hex digest length

    def test_compute_hash_different_for_different_types(
        self,
        service_with_files,
    ):
        """Test that different image types have different hashes."""
        base_hash = service_with_files._compute_hash("base")
        python_hash = service_with_files._compute_hash("python")

        # Base and Python have different dependency files, so different hashes
        assert base_hash != python_hash

    def test_compute_hash_changes_with_file_content(self, service_with_files):
        """Test that hash changes when dependency file changes."""
        # Get initial hash
        initial_hash = service_with_files._compute_hash("base")

        # Modify a dependency file
        pyproject = service_with_files.repo_root / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'modified'")

        # Hash should be different
        new_hash = service_with_files._compute_hash("base")
        assert new_hash != initial_hash

    def test_get_cached_hash_when_not_exists(self, service):
        """Test getting cached hash when cache file doesn't exist."""
        cached_hash = service._get_cached_hash("python")
        assert cached_hash is None

    def test_save_and_get_cached_hash(self, service):
        """Test saving and retrieving cached hash."""
        test_hash = "abc123def456"

        # Save hash
        service._save_hash("python", test_hash)

        # Retrieve hash
        cached_hash = service._get_cached_hash("python")
        assert cached_hash == test_hash

    def test_image_exists_when_present(self, service, mock_command_executor):
        """Test _image_exists returns True when image exists."""
        # Mock docker inspect success
        mock_command_executor.execute.return_value = Mock(returncode=0)

        result = service._exists("python")

        assert result is True
        mock_command_executor.execute.assert_called_once()
        call_args = mock_command_executor.execute.call_args[0][0]
        assert call_args == [
            "docker",
            "image",
            "inspect",
            "aidb-test-python:latest",
        ]

    def test_image_exists_when_missing(self, service, mock_command_executor):
        """Test _image_exists returns False when image doesn't exist."""
        # Mock docker inspect failure
        mock_command_executor.execute.return_value = Mock(returncode=1)

        result = service._exists("python")

        assert result is False

    def test_image_exists_without_command_executor(self, tmp_path):
        """Test _image_exists returns False when no command executor."""
        service = DockerImageChecksumService(repo_root=tmp_path, command_executor=None)

        result = service._exists("python")

        assert result is False

    def test_get_image_name(self, service):
        """Test image name generation."""
        assert service._get_image_name("base") == "aidb-test-base:latest"
        assert service._get_image_name("python") == "aidb-test-python:latest"
        assert service._get_image_name("javascript") == "aidb-test-javascript:latest"
        assert service._get_image_name("java") == "aidb-test-java:latest"

    def test_needs_rebuild_when_image_missing(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test needs_rebuild returns True when image doesn't exist."""
        # Mock image doesn't exist
        mock_command_executor.execute.return_value = Mock(returncode=1)

        needs_rebuild, reason = service_with_files.needs_rebuild("python")

        assert needs_rebuild is True
        assert "not found" in reason

    def test_needs_rebuild_when_no_cached_hash(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test needs_rebuild returns True when no cached hash exists."""
        # Mock image exists
        mock_command_executor.execute.return_value = Mock(returncode=0)

        needs_rebuild, reason = service_with_files.needs_rebuild("python")

        assert needs_rebuild is True
        assert "No cached hash found" in reason

    def test_needs_rebuild_when_hash_mismatch(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test needs_rebuild returns True when hashes don't match."""
        # Mock image exists
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Save old hash
        service_with_files._save_hash("python", "old_hash_value")

        # Current hash will be different
        needs_rebuild, reason = service_with_files.needs_rebuild("python")

        assert needs_rebuild is True
        assert "hash mismatch" in reason

    def test_needs_rebuild_when_up_to_date(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test needs_rebuild returns False when image is up-to-date."""
        # Mock image exists
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Save current hash
        current_hash = service_with_files._compute_hash("python")
        service_with_files._save_hash("python", current_hash)

        needs_rebuild, reason = service_with_files.needs_rebuild("python")

        assert needs_rebuild is False
        assert reason == "Up-to-date"

    def test_mark_built(self, service_with_files):
        """Test marking an image as built saves current hash."""
        # Mark as built
        service_with_files.mark_built("python")

        # Verify hash was saved
        cached_hash = service_with_files._get_cached_hash("python")
        current_hash = service_with_files._compute_hash("python")
        assert cached_hash == current_hash

    def test_mark_built_prevents_rebuild(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test that marking as built prevents subsequent rebuild."""
        # Mock image exists
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Mark as built
        service_with_files.mark_built("python")

        # Should not need rebuild
        needs_rebuild, reason = service_with_files.needs_rebuild("python")
        assert needs_rebuild is False
        assert reason == "Up-to-date"

    def test_check_all_images(self, service_with_files, mock_command_executor):
        """Test checking rebuild status for all images."""
        # Mock all images exist
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Mark python as built
        service_with_files.mark_built("python")

        # Check all images
        results = service_with_files.check_all_images()

        # Should have results for all image types
        assert set(results.keys()) == {"base", "python", "javascript", "java"}

        # All should be tuples of (needs_rebuild, reason)
        for _image_type, (needs_rebuild, reason) in results.items():
            assert isinstance(needs_rebuild, bool)
            assert isinstance(reason, str)

        # Python should be up-to-date
        assert results["python"][0] is False
        assert results["python"][1] == "Up-to-date"

        # Others should need rebuild (no cached hash)
        for image_type in ["base", "javascript", "java"]:
            assert results[image_type][0] is True

    def test_image_dependencies_defined(self):
        """Test that image dependencies are defined for all image types."""
        from aidb_cli.services.docker.docker_image_checksum_service import (
            DockerImageChecksumService,
        )

        deps = DockerImageChecksumService.IMAGE_DEPENDENCIES

        # Should have dependencies for all image types
        for image_type in DockerImageType.all_images():
            assert image_type in deps
            assert isinstance(deps[image_type], list)
            assert len(deps[image_type]) > 0

    def test_image_dependencies_include_required_files(self):
        """Test that image dependencies include expected files."""
        from aidb_cli.services.docker.docker_image_checksum_service import (
            DockerImageChecksumService,
        )

        deps = DockerImageChecksumService.IMAGE_DEPENDENCIES

        # Base image should include pyproject.toml and Dockerfile
        base_deps = [str(p) for p in deps["base"]]
        assert any("pyproject.toml" in d for d in base_deps)
        assert any("Dockerfile.test.base" in d for d in base_deps)

        # Python image should include Python-specific Dockerfile
        python_deps = [str(p) for p in deps["python"]]
        assert any("Dockerfile.test.python" in d for d in python_deps)

        # JavaScript image should include JS-specific Dockerfile
        js_deps = [str(p) for p in deps["javascript"]]
        assert any("Dockerfile.test.javascript" in d for d in js_deps)

        # Java image should include Java-specific Dockerfile
        java_deps = [str(p) for p in deps["java"]]
        assert any("Dockerfile.test.java" in d for d in java_deps)

    def test_hash_stability(self, service_with_files):
        """Test that hash computation is stable across multiple calls."""
        hash1 = service_with_files._compute_hash("python")
        hash2 = service_with_files._compute_hash("python")
        hash3 = service_with_files._compute_hash("python")

        assert hash1 == hash2 == hash3

    def test_needs_rebuild_after_file_modification(
        self,
        service_with_files,
        mock_command_executor,
    ):
        """Test complete workflow: mark built, modify file, check rebuild."""
        # Mock image exists
        mock_command_executor.execute.return_value = Mock(returncode=0)

        # Mark as built (up-to-date)
        service_with_files.mark_built("python")
        needs_rebuild, _ = service_with_files.needs_rebuild("python")
        assert needs_rebuild is False

        # Modify a dependency file
        pyproject = service_with_files.repo_root / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'changed'")

        # Should now need rebuild
        needs_rebuild, reason = service_with_files.needs_rebuild("python")
        assert needs_rebuild is True
        assert "hash mismatch" in reason
