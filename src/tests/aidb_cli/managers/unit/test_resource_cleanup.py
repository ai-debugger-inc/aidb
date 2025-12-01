"""Unit tests for ResourceCleaner."""

from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from aidb_cli.core.cleanup import ResourceCleaner


class TestResourceCleaner:
    """Test the ResourceCleaner."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def cleaner(self, tmp_path, mock_command_executor):
        """Create cleaner instance with mocks."""
        return ResourceCleaner(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
            ctx=None,
        )

    def test_initialization(self, tmp_path, mock_command_executor):
        """Test cleaner initialization."""
        cleaner = ResourceCleaner(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert cleaner.repo_root == tmp_path
        assert cleaner.docker_compose_file == (
            tmp_path / "src" / "tests" / "_docker" / "docker-compose.yaml"
        )
        assert cleaner.cleanup_actions == []

    def test_command_executor_lazy_creation(self, tmp_path):
        """Test command executor is lazily created if not provided."""
        cleaner = ResourceCleaner(repo_root=tmp_path, command_executor=None)

        # Access property - should create executor
        executor = cleaner.command_executor

        assert executor is not None
        assert cleaner._command_executor is executor

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_cleanup_docker_resources_success(
        self,
        mock_formatter,
        cleaner,
        mock_command_executor,
    ):
        """Test successful Docker resource cleanup."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        result = cleaner.cleanup_docker_resources(
            profile="test",
            remove_volumes=True,
            remove_networks=True,
            remove_images=False,
        )

        assert result is True
        assert "Stopped and removed containers" in cleaner.cleanup_actions

        # Verify docker compose down was called
        calls = mock_command_executor.execute.call_args_list
        down_call = calls[0]
        assert "docker" in down_call[0][0]
        assert "compose" in down_call[0][0]
        assert "down" in down_call[0][0]
        assert "--profile" in down_call[0][0]
        assert "test" in down_call[0][0]
        assert "-v" in down_call[0][0]

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_cleanup_docker_resources_failure(
        self,
        mock_formatter,
        cleaner,
        mock_command_executor,
    ):
        """Test failed Docker resource cleanup."""
        mock_command_executor.execute.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Error stopping containers",
        )

        result = cleaner.cleanup_docker_resources()

        assert result is False

    def test_cleanup_dangling_volumes(self, cleaner, mock_command_executor):
        """Test cleanup of dangling volumes."""
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="aidb-test-vol1\naidb-test-vol2\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        cleaner._cleanup_dangling_volumes()

        # Verify volume list was queried
        calls = mock_command_executor.execute.call_args_list
        assert "volume" in calls[0][0][0]
        assert "ls" in calls[0][0][0]

        # Verify volumes were removed
        assert len([c for c in calls if "rm" in c[0][0]]) == 2
        assert "Removed 2 dangling volumes" in cleaner.cleanup_actions

    def test_cleanup_test_networks(self, cleaner, mock_command_executor):
        """Test cleanup of test networks."""
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="aidb-test-net1\naidb-test-net2\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        cleaner._cleanup_test_networks()

        # Verify network list was queried
        calls = mock_command_executor.execute.call_args_list
        assert "network" in calls[0][0][0]
        assert "ls" in calls[0][0][0]

        # Verify networks were removed
        rm_calls = [c for c in calls if "rm" in c[0][0]]
        assert len(rm_calls) == 2

    def test_cleanup_test_networks_with_errors(self, cleaner, mock_command_executor):
        """Test network cleanup handles errors gracefully."""
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="aidb-test-net1\n", stderr=""),
            Mock(returncode=1, stdout="", stderr="network has active endpoints"),
        ]

        # Should not raise exception
        cleaner._cleanup_test_networks()

    def test_stop_aidb_containers(self, cleaner, mock_command_executor):
        """Test force stopping AIDB containers."""
        mock_command_executor.execute.side_effect = [
            Mock(returncode=0, stdout="abc123\ndef456\n", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        cleaner._stop_aidb_containers()

        # Verify ps was called
        calls = mock_command_executor.execute.call_args_list
        assert "ps" in calls[0][0][0]
        assert "--filter" in calls[0][0][0]

        # Verify stop and rm were called for each container
        stop_calls = [c for c in calls if "stop" in c[0][0]]
        rm_calls = [c for c in calls if "rm" in c[0][0]]
        assert len(stop_calls) == 2
        assert len(rm_calls) == 2

    def test_cleanup_test_images(self, cleaner, mock_command_executor):
        """Test cleanup of test images."""
        mock_command_executor.execute.side_effect = [
            Mock(
                returncode=0,
                stdout="aidb-test:latest\naidb-runtime:test\n",
                stderr="",
            ),
            Mock(returncode=0, stdout="", stderr=""),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        cleaner._cleanup_test_images()

        # Verify images list was queried
        calls = mock_command_executor.execute.call_args_list
        assert "images" in calls[0][0][0]

        # Verify images were removed
        rmi_calls = [c for c in calls if "rmi" in c[0][0]]
        assert len(rmi_calls) == 2
        assert "Removed 2 test images" in cleaner.cleanup_actions

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    @patch("shutil.rmtree")
    def test_cleanup_test_artifacts(
        self,
        mock_rmtree,
        mock_formatter,
        cleaner,
        tmp_path,
    ):
        """Test cleanup of test artifacts."""
        pytest_cache = tmp_path / ".pytest_cache"
        pytest_cache.mkdir()

        coverage_file = tmp_path / ".coverage"
        coverage_file.touch()

        htmlcov = tmp_path / "htmlcov"
        htmlcov.mkdir()

        result = cleaner.cleanup_test_artifacts(
            clean_cache=True,
            clean_coverage=True,
            clean_logs=False,
        )

        assert result is True
        assert "Removed pytest cache" in cleaner.cleanup_actions
        assert "Removed coverage data" in cleaner.cleanup_actions
        assert "Removed HTML coverage report" in cleaner.cleanup_actions

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_cleanup_test_artifacts_with_logs(
        self,
        mock_formatter,
        cleaner,
        tmp_path,
    ):
        """Test cleanup of log files."""
        # Create test log files
        (tmp_path / "test.log").touch()
        (tmp_path / "test-output.txt").touch()
        (tmp_path / "aidb-test-123.log").touch()

        result = cleaner.cleanup_test_artifacts(
            clean_cache=False,
            clean_coverage=False,
            clean_logs=True,
        )

        assert result is True
        assert "Removed log files" in cleaner.cleanup_actions

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    @patch("shutil.rmtree")
    def test_cleanup_temp_files(self, mock_rmtree, mock_formatter, cleaner, tmp_path):
        """Test cleanup of temporary files."""
        tmp_dir = tmp_path / "tmp"
        tmp_dir.mkdir()

        dot_tmp = tmp_path / ".tmp"
        dot_tmp.mkdir()

        result = cleaner.cleanup_temp_files()

        assert result is True

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    def test_full_cleanup_with_running_tests(
        self,
        mock_formatter,
        cleaner,
        mock_command_executor,
    ):
        """Test full cleanup aborts when tests are running without force."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="abc123\n",
            stderr="",
        )

        result = cleaner.full_cleanup(force=False)

        assert result is False

    @patch("aidb_cli.core.formatting.HeadingFormatter")
    @patch("shutil.rmtree")
    def test_full_cleanup_with_force(
        self,
        mock_rmtree,
        mock_formatter,
        cleaner,
        mock_command_executor,
        tmp_path,
    ):
        """Test full cleanup with force flag."""
        mock_command_executor.execute.return_value = Mock(
            returncode=0,
            stdout="",
            stderr="",
        )

        # Create test artifacts
        pytest_cache = tmp_path / ".pytest_cache"
        pytest_cache.mkdir()

        result = cleaner.full_cleanup(force=True)

        assert result is True

    @patch("signal.signal")
    @patch("atexit.register")
    def test_register_cleanup_handler(self, mock_atexit, mock_signal, cleaner):
        """Test cleanup handler registration."""
        cleaner.register_cleanup_handler()

        mock_atexit.assert_called_once()
        assert mock_signal.call_count == 2  # SIGTERM and SIGINT
