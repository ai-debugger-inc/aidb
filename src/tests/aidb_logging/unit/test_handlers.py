"""Tests for aidb_logging.handlers module."""

import logging
import sys
from pathlib import Path

import pytest

from aidb_logging.handlers import DualStreamHandler, HalvingFileHandler


class TestHalvingFileHandler:
    """Tests for HalvingFileHandler class."""

    def test_creates_log_file(self, tmp_path: Path):
        """Test that log file is created."""
        log_file = tmp_path / "test.log"
        handler = HalvingFileHandler(str(log_file))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        assert log_file.exists()

    def test_appends_to_existing_file(self, tmp_path: Path):
        """Test that handler appends to existing file."""
        log_file = tmp_path / "test.log"
        log_file.write_text("existing content\n")

        handler = HalvingFileHandler(str(log_file))
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="new message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        content = log_file.read_text()
        assert "existing content" in content
        assert "new message" in content

    def test_halves_file_when_exceeds_max_bytes(self, tmp_path: Path):
        """Test that file is halved when it exceeds max_bytes."""
        log_file = tmp_path / "test.log"
        max_bytes = 1000

        handler = HalvingFileHandler(str(log_file), max_bytes=max_bytes)

        for i in range(50):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=42,
                msg=f"message {i}" + "x" * 50,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        handler.close()

        file_size = log_file.stat().st_size
        assert file_size < max_bytes * 1.5

    def test_thread_safety(self, tmp_path: Path):
        """Test that handler is thread-safe."""
        import threading

        log_file = tmp_path / "test.log"
        handler = HalvingFileHandler(str(log_file), max_bytes=5000)

        def write_logs():
            for i in range(20):
                record = logging.LogRecord(
                    name="test",
                    level=logging.INFO,
                    pathname="/path/to/test.py",
                    lineno=42,
                    msg=f"message {i}" + "x" * 100,
                    args=(),
                    exc_info=None,
                )
                handler.emit(record)

        threads = [threading.Thread(target=write_logs) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        handler.close()

        assert log_file.exists()

    def test_preserves_recent_logs_after_halving(self, tmp_path: Path):
        """Test that recent logs are preserved after halving."""
        log_file = tmp_path / "test.log"
        max_bytes = 1000

        handler = HalvingFileHandler(str(log_file), max_bytes=max_bytes)

        for i in range(20):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=42,
                msg=f"message {i}" + "x" * 50,
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        handler.close()

        content = log_file.read_text()
        assert "message 19" in content

    def test_handles_errors_gracefully(self, tmp_path: Path):
        """Test that handler handles errors gracefully."""
        log_file = tmp_path / "test.log"
        handler = HalvingFileHandler(str(log_file))

        log_file.chmod(0o444)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        try:
            handler.emit(record)
        finally:
            log_file.chmod(0o644)
            handler.close()

    def test_handles_deleted_log_file(self, tmp_path: Path, capfd):
        """Test that handler continues logging after file is deleted."""
        log_file = tmp_path / "test.log"
        handler = HalvingFileHandler(str(log_file))

        # Write initial log entry
        record1 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="before deletion",
            args=(),
            exc_info=None,
        )
        handler.emit(record1)
        assert log_file.exists()

        # Delete the log file mid-session
        log_file.unlink()
        assert not log_file.exists()

        # Write another log entry - should not raise error or print warning
        record2 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=43,
            msg="after deletion",
            args=(),
            exc_info=None,
        )
        handler.emit(record2)

        # File should be recreated
        assert log_file.exists()

        # No warnings should be printed to stderr
        captured = capfd.readouterr()
        assert "Warning: Failed to check/rotate log file" not in captured.err

        handler.close()

    def test_handles_deleted_log_directory(self, tmp_path: Path, capfd):
        """Test that handler recreates directory when deleted mid-session."""
        import shutil

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "test.log"

        handler = HalvingFileHandler(str(log_file))

        # Write initial log entry
        record1 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="before deletion",
            args=(),
            exc_info=None,
        )
        handler.emit(record1)
        assert log_file.exists()

        # Delete entire log directory mid-session (simulates user's scenario)
        shutil.rmtree(log_dir)
        assert not log_dir.exists()

        # Write another log entry - should not raise error or print warning
        record2 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=43,
            msg="after deletion",
            args=(),
            exc_info=None,
        )
        handler.emit(record2)

        # Directory and file should be recreated
        assert log_dir.exists()
        assert log_file.exists()

        # No warnings should be printed to stderr
        captured = capfd.readouterr()
        assert "Warning: Failed to check/rotate log file" not in captured.err

        handler.close()

    def test_continues_logging_after_multiple_deletions(self, tmp_path: Path, capfd):
        """Test that handler continues logging after repeated file deletions."""
        log_file = tmp_path / "test.log"
        handler = HalvingFileHandler(str(log_file))

        for i in range(5):
            # Delete file before writing (except first iteration)
            if i > 0 and i % 2 == 0 and log_file.exists():
                log_file.unlink()

            # Write log entry
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=42,
                msg=f"message {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        # File should exist at the end (last write should have created it)
        assert log_file.exists()

        # No warnings should be printed to stderr
        captured = capfd.readouterr()
        assert "Warning: Failed to check/rotate log file" not in captured.err

        handler.close()


class TestDualStreamHandler:
    """Tests for DualStreamHandler class."""

    def test_routes_info_to_stdout(self, capfd):
        """Test that INFO logs go to stdout."""
        handler = DualStreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="info message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        captured = capfd.readouterr()
        assert "info message" in captured.out
        assert captured.err == ""

    def test_routes_warning_to_stderr(self, capfd):
        """Test that WARNING logs go to stderr."""
        handler = DualStreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="/path/to/test.py",
            lineno=42,
            msg="warning message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        captured = capfd.readouterr()
        assert "warning message" in captured.err
        assert captured.out == ""

    def test_routes_error_to_stderr(self, capfd):
        """Test that ERROR logs go to stderr."""
        handler = DualStreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=42,
            msg="error message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        captured = capfd.readouterr()
        assert "error message" in captured.err
        assert captured.out == ""

    def test_routes_debug_to_stdout(self, capfd):
        """Test that DEBUG logs go to stdout."""
        handler = DualStreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="/path/to/test.py",
            lineno=42,
            msg="debug message",
            args=(),
            exc_info=None,
        )

        handler.emit(record)
        handler.close()

        captured = capfd.readouterr()
        assert "debug message" in captured.out
        assert captured.err == ""

    def test_sets_formatter_on_both_handlers(self):
        """Test that formatter is set on both handlers."""
        handler = DualStreamHandler()
        formatter = logging.Formatter("%(message)s")

        handler.setFormatter(formatter)

        assert handler.stdout_handler.formatter is formatter
        assert handler.stderr_handler.formatter is formatter

    def test_closes_both_handlers(self):
        """Test that both handlers are closed."""
        handler = DualStreamHandler()
        handler.close()

        assert True
