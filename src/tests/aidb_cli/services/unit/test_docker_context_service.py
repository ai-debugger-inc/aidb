"""Unit tests for DockerContextService."""

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from aidb_cli.services.docker.docker_context_service import DockerContextService


class TestDockerContextService:
    """Test the DockerContextService."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create service instance.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory

        Returns
        -------
        DockerContextService
            Service instance for testing
        """
        return DockerContextService(repo_root=tmp_path)

    @pytest.fixture
    def service_with_executor(self, tmp_path):
        """Create service instance with command executor.

        Parameters
        ----------
        tmp_path : Path
            Pytest temporary directory

        Returns
        -------
        DockerContextService
            Service instance with mock executor
        """
        executor = Mock()
        return DockerContextService(repo_root=tmp_path, command_executor=executor)

    def test_initialization_without_executor(self, tmp_path):
        """Test service initialization without command executor."""
        service = DockerContextService(repo_root=tmp_path)

        assert service.repo_root == tmp_path
        assert service._temp_context is None
        assert service._version_manager is None

    def test_initialization_with_executor(self, tmp_path):
        """Test service initialization with command executor."""
        executor = Mock()
        service = DockerContextService(repo_root=tmp_path, command_executor=executor)

        assert service.repo_root == tmp_path
        assert service._command_executor is executor
        assert service._temp_context is None

    def test_version_manager_lazy_loading(self, service):
        """Test version_manager property creates instance on first access."""
        assert service._version_manager is None

        with patch(
            "aidb_cli.services.docker.docker_context_service.VersionManager",
        ) as mock_vm:
            mock_instance = Mock()
            mock_vm.return_value = mock_instance

            manager = service.version_manager

            mock_vm.assert_called_once_with()
            assert manager is mock_instance
            assert service._version_manager is mock_instance

    def test_version_manager_returns_cached_instance(self, service):
        """Test version_manager returns same instance on subsequent calls."""
        with patch(
            "aidb_cli.services.docker.docker_context_service.VersionManager",
        ) as mock_vm:
            mock_instance = Mock()
            mock_vm.return_value = mock_instance

            manager1 = service.version_manager
            manager2 = service.version_manager

            mock_vm.assert_called_once()
            assert manager1 is manager2

    def test_get_build_args_happy_path(self, service):
        """Test get_build_args returns correct structure."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {
            "PYTHON_VERSION": "3.11",
            "NODE_VERSION": "20",
        }
        mock_vm.versions = {"version": "1.2.3"}
        service._version_manager = mock_vm

        args = service.get_build_args()

        assert isinstance(args, dict)
        assert args["PACKAGE_VERSION"] == "1.2.3"
        assert args["PYTHON_VERSION"] == "3.11"
        assert args["BASE_IMAGE"] == "python:3.12-slim"

    def test_get_build_args_with_default_python_version(self, service):
        """Test get_build_args uses default Python version when not provided."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {}
        mock_vm.versions = {"version": "1.0.0"}
        service._version_manager = mock_vm

        args = service.get_build_args()

        assert args["PYTHON_VERSION"] == "3.12"
        assert args["BASE_IMAGE"] == "python:3.12-slim"

    def test_get_build_args_with_none_python_version(self, service):
        """Test get_build_args handles None Python version."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {"PYTHON_VERSION": None}
        mock_vm.versions = {"version": "1.0.0"}
        service._version_manager = mock_vm

        args = service.get_build_args()

        assert args["PYTHON_VERSION"] == "3.12"

    def test_get_build_args_version_manager_exception(self, service):
        """Test get_build_args fallback on VersionManager exception."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.side_effect = Exception("Version error")
        mock_vm.versions = {"version": "0.0.0"}
        service._version_manager = mock_vm

        args = service.get_build_args()

        assert args["PYTHON_VERSION"] == "3.12"
        assert args["PACKAGE_VERSION"] == "0.0.0"
        assert args["BASE_IMAGE"] == "python:3.12-slim"

    def test_get_build_args_missing_version_key(self, service):
        """Test get_build_args handles missing version key."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {"PYTHON_VERSION": "3.11"}
        mock_vm.versions = {}
        service._version_manager = mock_vm

        args = service.get_build_args()

        assert args["PACKAGE_VERSION"] == "0.0.0"

    def test_generate_env_file_default_path(self, service):
        """Test generate_env_file with default output path."""
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {"PYTHON_VERSION": "3.11"}
        mock_vm.versions = {"version": "1.5.0"}
        service._version_manager = mock_vm

        mock_dt = datetime(2025, 9, 30, 14, 30, 45, tzinfo=timezone.utc)
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt

            with patch("tempfile.mkstemp") as mock_mkstemp:
                temp_path = Path("/tmp/aidb_test.env")  # noqa: S108
                mock_mkstemp.return_value = (99, str(temp_path))

                with patch("os.close") as mock_close:
                    with patch.object(Path, "write_text") as mock_write:
                        result = service.generate_env_file()

                        mock_mkstemp.assert_called_once()
                        mock_close.assert_called_once_with(99)
                        assert result == temp_path
                    mock_write.assert_called_once()
                    content = mock_write.call_args[0][0]
                    assert "PACKAGE_VERSION=1.5.0" in content
                    assert "PYTHON_VERSION=3.11" in content
                    assert "BUILD_DATE=2025-09-30T14:30:45Z" in content

    def test_generate_env_file_custom_path(self, service, tmp_path):
        """Test generate_env_file with custom output path."""
        output_path = tmp_path / "custom.env"
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {"PYTHON_VERSION": "3.12"}
        mock_vm.versions = {"version": "2.0.0"}
        service._version_manager = mock_vm

        mock_dt = datetime(2025, 1, 15, 10, 20, 30, tzinfo=timezone.utc)
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt

            result = service.generate_env_file(output_path=output_path)

            assert result == output_path
            assert output_path.exists()
            content = output_path.read_text()
            assert "# AIDB Docker Environment" in content
            assert "PACKAGE_VERSION=2.0.0" in content
            assert "PYTHON_VERSION=3.12" in content
            assert "BUILD_DATE=2025-01-15T10:20:30Z" in content

    def test_generate_env_file_timestamp_format(self, service, tmp_path):
        """Test generate_env_file uses correct UTC timestamp format."""
        output_path = tmp_path / "test.env"
        mock_vm = Mock()
        mock_vm.get_docker_build_args.return_value = {}
        mock_vm.versions = {"version": "1.0.0"}
        service._version_manager = mock_vm

        mock_dt = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_dt

            service.generate_env_file(output_path=output_path)

            content = output_path.read_text()
            assert "BUILD_DATE=2025-12-31T23:59:59Z" in content

    def test_prepare_docker_context_success_all_defaults(self, service, tmp_path):
        """Test prepare_docker_context with all default options."""
        # Create source files
        (tmp_path / "pyproject.toml").write_text("test")
        (tmp_path / "README.md").write_text("readme")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "test.py").write_text("code")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "run.sh").write_text("#!/bin/bash")

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            result = service.prepare_docker_context()

            assert result == temp_dir
            assert (temp_dir / "pyproject.toml").exists()
            assert (temp_dir / "README.md").exists()
            assert (temp_dir / "src").exists()
            assert (temp_dir / "scripts").exists()
            assert (temp_dir / ".env").exists()

    def test_prepare_docker_context_include_src_false(self, service, tmp_path):
        """Test prepare_docker_context excludes src when include_src=False."""
        (tmp_path / "pyproject.toml").write_text("test")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "test.py").write_text("code")

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            result = service.prepare_docker_context(include_src=False)

            assert result == temp_dir
            assert (temp_dir / "pyproject.toml").exists()
            assert not (temp_dir / "src").exists()

    def test_prepare_docker_context_include_scripts_false(self, service, tmp_path):
        """Test prepare_docker_context excludes scripts when include_scripts=False."""
        (tmp_path / "pyproject.toml").write_text("test")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "run.sh").write_text("#!/bin/bash")

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            result = service.prepare_docker_context(include_scripts=False)

            assert result == temp_dir
            assert (temp_dir / "pyproject.toml").exists()
            assert not (temp_dir / "scripts").exists()

    def test_prepare_docker_context_missing_source_files(self, service, tmp_path):
        """Test prepare_docker_context handles missing source files gracefully."""
        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            result = service.prepare_docker_context()

            assert result == temp_dir
            assert not (temp_dir / "pyproject.toml").exists()
            assert not (temp_dir / "README.md").exists()
            assert not (temp_dir / "src").exists()

    def test_prepare_docker_context_verbose_output(self, service, tmp_path, capsys):
        """Test prepare_docker_context verbose mode outputs via CliOutput."""
        (tmp_path / "pyproject.toml").write_text("test")
        (tmp_path / "README.md").write_text("readme")

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            result = service.prepare_docker_context(verbose=True)

            assert result == temp_dir
            captured = capsys.readouterr()
            assert "Preparing Docker context" in captured.out
            assert "Copied pyproject.toml" in captured.out
            assert "Copied README.md" in captured.out
            assert "Generated .env file" in captured.out
            assert "Docker context prepared" in captured.out

    def test_prepare_docker_context_oserror_handling(self, service, tmp_path):
        """Test prepare_docker_context handles OSError and returns None."""
        with patch("tempfile.mkdtemp", side_effect=OSError("Permission denied")):
            result = service.prepare_docker_context()

            assert result is None
            assert service._temp_context is None

    def test_prepare_docker_context_shutil_error_handling(self, service, tmp_path):
        """Test prepare_docker_context handles shutil.Error and returns None."""
        (tmp_path / "pyproject.toml").write_text("test")

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            with patch("shutil.copy2", side_effect=shutil.Error("Copy error")):
                result = service.prepare_docker_context()

                assert result is None

    def test_prepare_docker_context_cleanup_on_error(self, service, tmp_path):
        """Test prepare_docker_context calls cleanup_context on error."""
        with patch("tempfile.mkdtemp", side_effect=OSError("Error")):
            with patch.object(service, "cleanup_context") as mock_cleanup:
                result = service.prepare_docker_context()

                assert result is None
                mock_cleanup.assert_called_once()

    def test_cleanup_context_removes_temp_directory(self, service, tmp_path):
        """Test cleanup_context removes temp context successfully."""
        temp_dir = tmp_path / "temp_context"
        temp_dir.mkdir()
        (temp_dir / "test.txt").write_text("test")
        service._temp_context = temp_dir

        service.cleanup_context()

        assert not temp_dir.exists()
        assert service._temp_context is None

    def test_cleanup_context_handles_oserror(self, service, tmp_path):
        """Test cleanup_context handles OSError during removal."""
        temp_dir = tmp_path / "temp_context"
        temp_dir.mkdir()
        service._temp_context = temp_dir

        with patch("shutil.rmtree", side_effect=OSError("Permission denied")):
            service.cleanup_context()

            assert service._temp_context is None

    def test_cleanup_context_handles_shutil_error(self, service, tmp_path):
        """Test cleanup_context handles shutil.Error during removal."""
        temp_dir = tmp_path / "temp_context"
        temp_dir.mkdir()
        service._temp_context = temp_dir

        with patch("shutil.rmtree", side_effect=shutil.Error("Removal error")):
            service.cleanup_context()

            assert service._temp_context is None

    def test_cleanup_context_noop_when_none(self, service):
        """Test cleanup_context is no-op when _temp_context is None."""
        service._temp_context = None

        with patch("shutil.rmtree") as mock_rmtree:
            service.cleanup_context()

            mock_rmtree.assert_not_called()

    def test_cleanup_context_skips_when_path_not_exists(self, service, tmp_path):
        """Test cleanup_context skips cleanup when path doesn't exist."""
        temp_dir = tmp_path / "nonexistent"
        service._temp_context = temp_dir

        with patch("shutil.rmtree") as mock_rmtree:
            service.cleanup_context()

            mock_rmtree.assert_not_called()
            # _temp_context is not reset when path doesn't exist
            assert service._temp_context == temp_dir

    def test_cleanup_method_calls_cleanup_context(self, service):
        """Test cleanup() calls cleanup_context()."""
        with patch.object(service, "cleanup_context") as mock_cleanup_context:
            service.cleanup()

            mock_cleanup_context.assert_called_once()

    def test_multiple_prepare_cleanup_cycles(self, service, tmp_path):
        """Test multiple prepare/cleanup cycles work correctly."""
        (tmp_path / "pyproject.toml").write_text("test")

        for i in range(3):
            with patch("tempfile.mkdtemp") as mock_mkdtemp:
                temp_dir = tmp_path / f"temp_context_{i}"
                temp_dir.mkdir()
                mock_mkdtemp.return_value = str(temp_dir)

                result = service.prepare_docker_context()
                assert result == temp_dir
                assert service._temp_context == temp_dir

                service.cleanup_context()
                assert service._temp_context is None

    def test_prepare_docker_context_creates_tempdir(self, service, tmp_path):
        """Test prepare_docker_context creates temporary directory."""
        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            temp_dir = tmp_path / "temp_context"
            temp_dir.mkdir()
            mock_mkdtemp.return_value = str(temp_dir)

            service.prepare_docker_context()

            mock_mkdtemp.assert_called_once()
            call_kwargs = mock_mkdtemp.call_args[1]
            assert call_kwargs["prefix"] == "aidb_docker_"

    def test_context_already_cleaned(self, service, tmp_path):
        """Test cleanup when context already cleaned."""
        temp_dir = tmp_path / "temp_context"
        temp_dir.mkdir()
        service._temp_context = temp_dir

        service.cleanup_context()
        assert service._temp_context is None

        service.cleanup_context()
        assert service._temp_context is None
