"""Tests for aidb_logging.utils module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from aidb_logging.utils import (
    LogOnce,
    clean_old_logs,
    format_bytes,
    get_file_size,
    get_log_file_path,
    get_log_level,
    is_debug_environment,
    is_test_environment,
    should_use_console_logging,
    should_use_file_logging,
)


class TestGetLogFilePath:
    """Tests for get_log_file_path function."""

    def test_returns_default_path(self):
        """Test that default path is returned."""
        path = get_log_file_path("test-container-output")
        assert "test-container-output.log" in path
        assert ".aidb" in path or "log" in path

    def test_uses_custom_filename(self):
        """Test that custom filename is used."""
        path = get_log_file_path("test", filename="custom.log")
        assert "custom.log" in path

    def test_uses_custom_directory(self, tmp_path: Path):
        """Test that custom directory is used."""
        custom_dir = str(tmp_path / "logs")
        path = get_log_file_path("test", log_dir=custom_dir)
        assert custom_dir in path

    def test_creates_directory_if_not_exists(self, tmp_path: Path):
        """Test that directory is created if it doesn't exist."""
        custom_dir = str(tmp_path / "newdir")
        get_log_file_path("test", log_dir=custom_dir)
        assert Path(custom_dir).exists()

    def test_respects_environment_variable(self, tmp_path: Path, monkeypatch):
        """Test that AIDB_LOG_DIR environment variable is respected."""
        custom_dir = str(tmp_path / "env_logs")
        monkeypatch.setenv("AIDB_LOG_DIR", custom_dir)
        path = get_log_file_path("test-container-output")
        assert custom_dir in path


class TestGetLogLevel:
    """Tests for get_log_level function."""

    def test_returns_default_when_not_set(self, monkeypatch):
        """Test that default is returned when not set."""
        monkeypatch.delenv("AIDB_LOG_LEVEL", raising=False)
        level = get_log_level("INFO")
        assert level == "INFO"

    def test_reads_from_environment(self, monkeypatch):
        """Test that log level is read from environment."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "DEBUG")
        level = get_log_level()
        assert level == "DEBUG"

    def test_validates_log_level(self, monkeypatch):
        """Test that invalid log levels are rejected."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "INVALID")
        level = get_log_level("WARNING")
        assert level == "WARNING"

    def test_normalizes_to_uppercase(self, monkeypatch):
        """Test that log level is normalized to uppercase."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "debug")
        level = get_log_level()
        assert level == "DEBUG"

    def test_accepts_trace_level(self, monkeypatch):
        """Test that TRACE level is accepted as valid."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "TRACE")
        level = get_log_level()
        assert level == "TRACE"


class TestShouldUseFileLogging:
    """Tests for should_use_file_logging function."""

    def test_returns_true_by_default(self, monkeypatch):
        """Test that True is returned by default."""
        monkeypatch.delenv("AIDB_NO_FILE_LOGGING", raising=False)
        assert should_use_file_logging() is True

    def test_returns_false_when_disabled(self, monkeypatch):
        """Test that False is returned when disabled."""
        monkeypatch.setenv("AIDB_NO_FILE_LOGGING", "1")
        assert should_use_file_logging() is False


class TestShouldUseConsoleLogging:
    """Tests for should_use_console_logging function."""

    def test_returns_false_by_default(self, monkeypatch):
        """Test that False is returned by default."""
        monkeypatch.delenv("AIDB_CONSOLE_LOGGING", raising=False)
        assert should_use_console_logging() is False

    def test_returns_true_when_enabled(self, monkeypatch):
        """Test that True is returned when enabled."""
        monkeypatch.setenv("AIDB_CONSOLE_LOGGING", "1")
        assert should_use_console_logging() is True


class TestIsTestEnvironment:
    """Tests for is_test_environment function."""

    def test_detects_pytest_in_modules(self):
        """Test that pytest in sys.modules is detected."""
        import sys

        assert "pytest" in sys.modules
        assert is_test_environment() is True

    def test_detects_test_mode_env_var(self, monkeypatch):
        """Test that AIDB_TEST_MODE is detected."""
        monkeypatch.setenv("AIDB_TEST_MODE", "1")
        assert is_test_environment() is True

    def test_detects_pytest_current_test(self, monkeypatch):
        """Test that PYTEST_CURRENT_TEST is detected."""
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_file::test_function")
        assert is_test_environment() is True


class TestIsDebugEnvironment:
    """Tests for is_debug_environment function."""

    def test_detects_debug_log_level(self, monkeypatch):
        """Test that DEBUG log level is detected."""
        monkeypatch.setenv("AIDB_LOG_LEVEL", "DEBUG")
        assert is_debug_environment() is True

    def test_detects_debug_flag(self, monkeypatch):
        """Test that AIDB_DEBUG flag is detected."""
        monkeypatch.setenv("AIDB_DEBUG", "1")
        assert is_debug_environment() is True

    def test_detects_adapter_trace(self, monkeypatch):
        """Test that AIDB_ADAPTER_TRACE is detected."""
        monkeypatch.setenv("AIDB_ADAPTER_TRACE", "1")
        assert is_debug_environment() is True

    def test_returns_false_when_not_debug(self, monkeypatch):
        """Test that False is returned when not in debug mode."""
        monkeypatch.delenv("AIDB_LOG_LEVEL", raising=False)
        monkeypatch.delenv("AIDB_DEBUG", raising=False)
        monkeypatch.delenv("AIDB_ADAPTER_TRACE", raising=False)

        with patch("aidb_logging.utils.get_log_level", return_value="INFO"):
            assert is_debug_environment() is False


class TestCleanOldLogs:
    """Tests for clean_old_logs function."""

    def test_keeps_most_recent_files(self, tmp_path: Path):
        """Test that most recent files are kept."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        for i in range(10):
            log_file = log_dir / f"test{i}.log"
            log_file.write_text(f"log {i}")

        clean_old_logs(str(log_dir), max_files=5)

        remaining_files = list(log_dir.glob("*.log"))
        assert len(remaining_files) == 5

    def test_removes_oldest_files(self, tmp_path: Path):
        """Test that oldest files are removed."""
        import time

        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        old_file = log_dir / "old.log"
        old_file.write_text("old")
        time.sleep(0.01)

        new_file = log_dir / "new.log"
        new_file.write_text("new")

        clean_old_logs(str(log_dir), max_files=1)

        assert new_file.exists()
        assert not old_file.exists()

    def test_handles_missing_directory(self, tmp_path: Path):
        """Test that missing directory is handled gracefully."""
        missing_dir = tmp_path / "missing"
        clean_old_logs(str(missing_dir))

    def test_respects_pattern(self, tmp_path: Path):
        """Test that glob pattern is respected."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        for i in range(5):
            (log_dir / f"test{i}.log").write_text("log")
            (log_dir / f"test{i}.txt").write_text("txt")

        clean_old_logs(str(log_dir), max_files=2, pattern="*.log")

        log_files = list(log_dir.glob("*.log"))
        txt_files = list(log_dir.glob("*.txt"))

        assert len(log_files) == 2
        assert len(txt_files) == 5


class TestFormatBytes:
    """Tests for format_bytes function."""

    def test_formats_bytes(self):
        """Test formatting of bytes."""
        assert format_bytes(100) == "100.0 B"

    def test_formats_kilobytes(self):
        """Test formatting of kilobytes."""
        assert "1.0 KB" in format_bytes(1024)

    def test_formats_megabytes(self):
        """Test formatting of megabytes."""
        assert "1.0 MB" in format_bytes(1024 * 1024)

    def test_formats_gigabytes(self):
        """Test formatting of gigabytes."""
        assert "1.0 GB" in format_bytes(1024 * 1024 * 1024)

    def test_rounds_to_one_decimal(self):
        """Test that values are rounded to one decimal place."""
        result = format_bytes(1536)
        assert "1.5 KB" in result


class TestGetFileSize:
    """Tests for get_file_size function."""

    def test_returns_file_size(self, tmp_path: Path):
        """Test that file size is returned."""
        test_file = tmp_path / "test.txt"
        content = "test content"
        test_file.write_text(content)

        size = get_file_size(str(test_file))
        assert size == len(content)

    def test_returns_zero_for_missing_file(self, tmp_path: Path):
        """Test that zero is returned for missing file."""
        missing_file = tmp_path / "missing.txt"
        size = get_file_size(str(missing_file))
        assert size == 0

    def test_returns_zero_for_empty_file(self, tmp_path: Path):
        """Test that zero is returned for empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        size = get_file_size(str(empty_file))
        assert size == 0


class TestLogOnce:
    """Tests for LogOnce utility class."""

    def setup_method(self):
        """Reset LogOnce state before each test."""
        LogOnce.reset()

    def test_debug_logs_first_call(self, mock_ctx):
        """Test that debug message is logged on first call."""
        LogOnce.debug(mock_ctx, "test_key", "Test message")

        mock_ctx.debug.assert_called_once_with("Test message")

    def test_debug_suppresses_second_call(self, mock_ctx):
        """Test that debug message is suppressed on second call with same key."""
        LogOnce.debug(mock_ctx, "test_key", "Test message")
        LogOnce.debug(mock_ctx, "test_key", "Test message")

        mock_ctx.debug.assert_called_once()

    def test_different_keys_both_log(self, mock_ctx):
        """Test that different keys both result in logging."""
        LogOnce.debug(mock_ctx, "key1", "Message 1")
        LogOnce.debug(mock_ctx, "key2", "Message 2")

        assert mock_ctx.debug.call_count == 2

    def test_info_logs_first_call(self, mock_ctx):
        """Test that info message is logged on first call."""
        LogOnce.info(mock_ctx, "test_key", "Test message")

        mock_ctx.info.assert_called_once_with("Test message")

    def test_info_suppresses_second_call(self, mock_ctx):
        """Test that info message is suppressed on second call with same key."""
        LogOnce.info(mock_ctx, "test_key", "Test message")
        LogOnce.info(mock_ctx, "test_key", "Test message")

        mock_ctx.info.assert_called_once()

    def test_warning_logs_first_call(self, mock_ctx):
        """Test that warning message is logged on first call."""
        LogOnce.warning(mock_ctx, "test_key", "Test message")

        mock_ctx.warning.assert_called_once_with("Test message")

    def test_warning_suppresses_second_call(self, mock_ctx):
        """Test that warning message is suppressed on second call with same key."""
        LogOnce.warning(mock_ctx, "test_key", "Test message")
        LogOnce.warning(mock_ctx, "test_key", "Test message")

        mock_ctx.warning.assert_called_once()

    def test_reset_clears_logged_keys(self, mock_ctx):
        """Test that reset() clears all logged keys."""
        LogOnce.debug(mock_ctx, "test_key", "Test message")
        LogOnce.reset()
        LogOnce.debug(mock_ctx, "test_key", "Test message")

        assert mock_ctx.debug.call_count == 2

    def test_thread_safety(self, mock_ctx):
        """Test that LogOnce is thread-safe."""
        import threading

        logged_count = [0]

        def log_once():
            LogOnce.debug(mock_ctx, "shared_key", "Test message")
            if mock_ctx.debug.called:
                logged_count[0] += 1

        threads = [threading.Thread(target=log_once) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should only log once despite multiple threads
        mock_ctx.debug.assert_called_once()
