"""Unit tests for PytestLoggingService."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from aidb_cli.services.test.pytest_logging_service import PytestLoggingService


class TestPytestLoggingService:
    """Test the PytestLoggingService session management."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def logging_service(self, tmp_path, mock_command_executor):
        """Create a PytestLoggingService instance with tmp_path."""
        return PytestLoggingService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    def test_generate_session_id_with_suite(self, logging_service):
        """Test session ID generation with suite name."""
        session_id = logging_service.generate_session_id("cli")

        # Format: cli-YYYYMMDD-HHMMSS
        assert session_id.startswith("cli-")
        parts = session_id.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS

    def test_generate_session_id_without_suite(self, logging_service):
        """Test session ID generation without suite (defaults to 'local')."""
        session_id = logging_service.generate_session_id(None)

        assert session_id.startswith("local-")
        parts = session_id.split("-")
        assert len(parts) == 3

    def test_create_session_directory(self, logging_service, tmp_path):
        """Test session directory creation."""
        session_id = "test-20251028-123456"
        session_dir = logging_service.create_session_directory(session_id)

        expected_dir = tmp_path / "pytest-logs" / session_id
        assert session_dir == expected_dir
        assert session_dir.exists()
        assert session_dir.is_dir()

    def test_create_session_directory_with_custom_base(self, logging_service, tmp_path):
        """Test session directory creation with custom base directory."""
        custom_base = tmp_path / "custom-logs"
        session_id = "test-20251028-123456"
        session_dir = logging_service.create_session_directory(session_id, custom_base)

        expected_dir = custom_base / session_id
        assert session_dir == expected_dir
        assert session_dir.exists()

    def test_get_pytest_log_file_path(self, logging_service, tmp_path):
        """Test pytest log file path generation."""
        session_dir = tmp_path / "session-dir"
        log_path = logging_service.get_pytest_log_file_path(session_dir)

        assert log_path == session_dir / "pytest-captured.log"

    def test_get_test_results_path(self, logging_service, tmp_path):
        """Test test results path generation."""
        session_dir = tmp_path / "session-dir"
        results_path = logging_service.get_test_results_path(session_dir)

        assert results_path == session_dir / "test-results.log"

    def test_cleanup_old_sessions_no_directory(self, logging_service, tmp_path):
        """Test cleanup when base directory doesn't exist."""
        non_existent = tmp_path / "non-existent"
        deleted = logging_service.cleanup_old_sessions(non_existent)

        assert deleted == 0

    def test_cleanup_old_sessions_keeps_recent(self, logging_service, tmp_path):
        """Test cleanup keeps most recent sessions."""
        base_dir = tmp_path / "pytest-logs"
        base_dir.mkdir()

        # Create 15 session directories with timestamps
        for i in range(15):
            timestamp = datetime(2025, 1, 1, 12, i, 0, tzinfo=timezone.utc)
            session_id = f"test-{timestamp.strftime('%Y%m%d-%H%M%S')}"
            (base_dir / session_id).mkdir()

        # Cleanup, keeping only 10
        deleted = logging_service.cleanup_old_sessions(base_dir, keep_count=10)

        assert deleted == 5
        remaining = list(base_dir.iterdir())
        assert len(remaining) == 10

        # Verify the most recent 10 are kept
        remaining_names = sorted([d.name for d in remaining])
        # Should keep test-20250101-120500 through test-20250101-121400
        assert "test-20250101-121400" in remaining_names  # Most recent
        assert "test-20250101-120500" in remaining_names  # 10th most recent
        assert "test-20250101-120000" not in remaining_names  # Should be deleted

    def test_cleanup_old_sessions_ignores_malformed(self, logging_service, tmp_path):
        """Test cleanup ignores directories with malformed names."""
        base_dir = tmp_path / "pytest-logs"
        base_dir.mkdir()

        # Create valid and invalid directories
        (base_dir / "test-20250101-120000").mkdir()
        (base_dir / "invalid-name").mkdir()
        (base_dir / "test-invalid-time").mkdir()
        (base_dir / "file.txt").touch()

        deleted = logging_service.cleanup_old_sessions(base_dir, keep_count=10)

        # Should not delete anything (only 1 valid session)
        assert deleted == 0
        assert (base_dir / "test-20250101-120000").exists()
        assert (base_dir / "invalid-name").exists()

    def test_cleanup_old_sessions_handles_permission_error(
        self,
        logging_service,
        tmp_path,
        monkeypatch,
    ):
        """Test cleanup continues on permission errors."""
        base_dir = tmp_path / "pytest-logs"
        base_dir.mkdir()

        # Create sessions
        for i in range(12):
            timestamp = datetime(2025, 1, 1, 12, i, 0, tzinfo=timezone.utc)
            session_id = f"test-{timestamp.strftime('%Y%m%d-%H%M%S')}"
            (base_dir / session_id).mkdir()

        # Mock shutil.rmtree to raise OSError for one directory
        import shutil

        original_rmtree = shutil.rmtree
        call_count = [0]

        def mock_rmtree(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                msg = "Permission denied"
                raise OSError(msg)
            original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr("shutil.rmtree", mock_rmtree)

        # Should continue despite error
        deleted = logging_service.cleanup_old_sessions(base_dir, keep_count=10)

        # Should have attempted to delete 2, but only 1 succeeded
        assert deleted == 1
        remaining = list(base_dir.iterdir())
        assert len(remaining) == 11  # 10 kept + 1 failed deletion

    def test_cleanup_all_locations(self, logging_service, tmp_path):
        """Test cleanup across all log locations with legacy pytest-logs structure."""
        # Create local pytest-logs with sessions
        local_logs = tmp_path / "pytest-logs"
        local_logs.mkdir()
        for i in range(12):
            (local_logs / f"test-{20250101 + i}-120000").mkdir()

        # Create container with old pytest-logs subdirectory structure
        # (Tests that cleanup handles non-session-id directories gracefully)
        container_base = tmp_path / ".cache" / "container-data"
        container1 = container_base / "container1"
        container1.mkdir(parents=True)

        # Add some non-session directories that should be skipped
        (container1 / "log").mkdir()
        (container1 / "pytest").mkdir()
        (container1 / "pytest-logs").mkdir()

        # Add session-scoped directories that should be cleaned
        for i in range(15):
            timestamp = 20250101 + i
            session_id = f"test-{timestamp}-120000"
            (container1 / session_id).mkdir()

        container2 = container_base / "container2"
        container2.mkdir(parents=True)
        (container2 / "log").mkdir()
        for i in range(8):
            timestamp = 20250101 + i
            session_id = f"test-{timestamp}-120000"
            (container2 / session_id).mkdir()

        # Cleanup all locations
        results = logging_service.cleanup_all_locations(keep_count=10)

        # Verify cleanup happened
        assert "local" in results
        assert results["local"] == 2  # 12 - 10
        assert "container:container1" in results
        assert results["container:container1"] == 5  # 15 - 10
        # container2 has only 8, so nothing deleted
        assert "container:container2" not in results

        # Verify non-session directories were not deleted
        assert (container1 / "log").exists()
        assert (container1 / "pytest").exists()
        assert (container1 / "pytest-logs").exists()

    def test_cleanup_all_locations_no_container_cache(self, logging_service, tmp_path):
        """Test cleanup when no container cache exists."""
        # Create only local pytest-logs
        local_logs = tmp_path / "pytest-logs"
        local_logs.mkdir()
        for i in range(12):
            (local_logs / f"test-{20250101 + i}-120000").mkdir()

        results = logging_service.cleanup_all_locations(keep_count=10)

        # Should only cleanup local
        assert "local" in results
        assert len(results) == 1

    def test_cleanup_all_locations_with_session_scoped_structure(
        self,
        logging_service,
        tmp_path,
    ):
        """Test cleanup with session-scoped container structure."""
        # Create local pytest-logs with sessions
        local_logs = tmp_path / "pytest-logs"
        local_logs.mkdir()
        for i in range(12):
            (local_logs / f"test-{20250101 + i}-120000").mkdir()

        # Create session-scoped container structure
        # New structure: .cache/container-data/{container}/{session-id}/
        container_base = tmp_path / ".cache" / "container-data"

        # Container 1: 12 sessions (should delete 2)
        container1 = container_base / "aidb-test-python"
        for i in range(12):
            timestamp = 20250101 + i
            session_id = f"python-{timestamp}-120000"
            session_dir = container1 / session_id
            session_dir.mkdir(parents=True)
            # Create log and pytest subdirectories
            (session_dir / "log").mkdir()
            (session_dir / "pytest").mkdir()

        # Container 2: 8 sessions (nothing to delete)
        container2 = container_base / "aidb-test-javascript"
        for i in range(8):
            timestamp = 20250101 + i
            session_id = f"javascript-{timestamp}-120000"
            session_dir = container2 / session_id
            session_dir.mkdir(parents=True)
            (session_dir / "log").mkdir()
            (session_dir / "pytest").mkdir()

        # Cleanup all locations
        results = logging_service.cleanup_all_locations(keep_count=10)

        # Verify cleanup happened
        assert "local" in results
        assert results["local"] == 2  # 12 - 10

        assert "container:aidb-test-python" in results
        assert results["container:aidb-test-python"] == 2  # 12 - 10

        # container2 has only 8, so nothing deleted
        assert "container:aidb-test-javascript" not in results

        # Verify the correct sessions remain
        remaining_python = sorted(container1.iterdir())
        assert len(remaining_python) == 10
        # Should keep the 10 most recent (20250103-120000 through 20250112-120000)
        assert remaining_python[0].name == "python-20250103-120000"
        assert remaining_python[-1].name == "python-20250112-120000"

        remaining_js = sorted(container2.iterdir())
        assert len(remaining_js) == 8
        assert remaining_js[0].name == "javascript-20250101-120000"
        assert remaining_js[-1].name == "javascript-20250108-120000"

    def test_session_directory_property(self, logging_service, tmp_path):
        """Test that base_log_dir is correctly set."""
        assert logging_service.base_log_dir == tmp_path / "pytest-logs"
        assert (
            logging_service.container_cache_dir
            == tmp_path / ".cache" / "container-data"
        )

    def test_skip_session_logging_no_subdirectory(self, tmp_path):
        """Test that skip_session_logging prevents session subdirectory creation."""
        service = PytestLoggingService(
            repo_root=tmp_path,
            skip_session_logging=True,
        )

        session_id = "test-20251028-123456"
        session_dir = service.create_session_directory(session_id)

        # Should return base dir, not session subdir
        assert session_dir == tmp_path / "pytest-logs"
        assert session_dir.exists()
        # Session subdirectory should NOT be created
        assert not (tmp_path / "pytest-logs" / session_id).exists()

    def test_skip_session_logging_no_cleanup(self, tmp_path):
        """Test that cleanup is skipped when session logging disabled."""
        service = PytestLoggingService(
            repo_root=tmp_path,
            skip_session_logging=True,
        )

        # Create some session directories manually
        base_dir = tmp_path / "pytest-logs"
        base_dir.mkdir()
        for i in range(12):
            (base_dir / f"test-{20250101 + i}-120000").mkdir()

        # Cleanup should skip when flag is set
        results = service.cleanup_all_locations()
        assert results == {}

        # All directories should still exist
        remaining = list(base_dir.iterdir())
        assert len(remaining) == 12

    def test_skip_session_logging_via_environment(self, tmp_path, monkeypatch):
        """Test that skip_session_logging can be enabled via env var."""
        monkeypatch.setenv("AIDB_SKIP_SESSION_LOGS", "1")

        service = PytestLoggingService(repo_root=tmp_path)

        # Service should have skip_session_logging enabled via env var
        assert service.skip_session_logging is True

        # Should not create session subdirectory
        session_id = "test-20251028-123456"
        session_dir = service.create_session_directory(session_id)
        assert session_dir == tmp_path / "pytest-logs"
        assert not (tmp_path / "pytest-logs" / session_id).exists()

    def test_skip_session_logging_env_var_variations(self, tmp_path, monkeypatch):
        """Test different environment variable values."""
        # Test "true"
        monkeypatch.setenv("AIDB_SKIP_SESSION_LOGS", "true")
        service = PytestLoggingService(repo_root=tmp_path)
        assert service.skip_session_logging is True

        # Test "yes"
        monkeypatch.setenv("AIDB_SKIP_SESSION_LOGS", "yes")
        service = PytestLoggingService(repo_root=tmp_path)
        assert service.skip_session_logging is True

        # Test "0" (should not enable)
        monkeypatch.setenv("AIDB_SKIP_SESSION_LOGS", "0")
        service = PytestLoggingService(repo_root=tmp_path)
        assert service.skip_session_logging is False

        # Test empty string (should not enable)
        monkeypatch.setenv("AIDB_SKIP_SESSION_LOGS", "")
        service = PytestLoggingService(repo_root=tmp_path)
        assert service.skip_session_logging is False
