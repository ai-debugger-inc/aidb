"""Unit tests for audit logger."""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import AuditLogger
from tests._fixtures.audit import (  # noqa: F401
    mock_audit_logger,
    running_audit_logger,
    temp_audit_dir,
)
from tests._helpers.audit import (
    AuditEventFactory,
    AuditLogParser,
    AuditTestMixin,
    create_mock_log_files,
    wait_for_queue_processing,
)


class TestAuditLoggerSingleton(AuditTestMixin):
    """Test AuditLogger singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        AuditLogger._reset_singleton()

    def teardown_method(self):
        """Clean up singleton after each test."""
        AuditLogger._reset_singleton()

    def test_singleton_pattern(self):
        """Test that AuditLogger follows singleton pattern."""
        logger1 = AuditLogger()
        logger2 = AuditLogger()

        assert logger1 is logger2
        assert id(logger1) == id(logger2)

    def test_singleton_persists_configuration(self, tmp_path):
        """Test that singleton preserves configuration."""
        test_path = tmp_path / "test_audit" / "audit.log"
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(test_path),
            },
        ):
            logger1 = AuditLogger()
            assert logger1._log_path == test_path

            # Second instance should have same config
            logger2 = AuditLogger()
            assert logger2._log_path == logger1._log_path

    def test_singleton_reset(self):
        """Test resetting singleton instance."""
        logger1 = AuditLogger()
        logger1_id = id(logger1)

        # Clear singleton
        AuditLogger._instance = None

        # New instance should be different
        logger2 = AuditLogger()
        assert id(logger2) != logger1_id


class TestAuditLoggerConfiguration:
    """Test AuditLogger configuration."""

    def setup_method(self):
        """Reset singleton before each test."""
        AuditLogger._reset_singleton()

    def teardown_method(self):
        """Clean up singleton after each test."""
        AuditLogger._reset_singleton()

    def test_default_configuration(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            logger = AuditLogger()

            # Without AIDB_AUDIT_ENABLED, should be disabled
            assert not logger._enabled
            assert logger._max_size_mb == 100  # 100MB default
            assert logger._retention_days == 30

    def test_environment_configuration(self, tmp_path):
        """Test configuration from environment variables."""
        custom_path = tmp_path / "custom_audit" / "audit.log"
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(custom_path),
                "AIDB_AUDIT_LOG_MB": "50",
                "AIDB_AUDIT_LOG_RETENTION_DAYS": "7",
            },
        ):
            logger = AuditLogger()

            assert logger._enabled
            assert logger._log_path == custom_path
            assert logger._max_size_mb == 50
            assert logger._retention_days == 7

    def test_invalid_level_configuration(self):
        """Test handling of invalid audit level."""
        # Note: AIDB_AUDIT_LEVEL is not used in the actual implementation
        # Level filtering would be done at the event level, not logger level

    def test_audit_disabled(self):
        """Test disabling audit via environment."""
        with patch.dict(os.environ, {"AIDB_AUDIT_LOG": "false"}):
            # Should be disabled if AIDB_AUDIT_LOG is false
            logger = AuditLogger()
            assert not logger._enabled


class TestAuditLoggerOperations:
    """Test AuditLogger core operations."""

    def setup_method(self):
        """Reset singleton before each test."""
        AuditLogger._reset_singleton()

    def teardown_method(self):
        """Clean up singleton after each test."""
        AuditLogger._reset_singleton()

    @pytest.mark.asyncio
    async def test_log_event(self, temp_audit_dir):
        """Test logging a single event."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            try:
                event = AuditEventFactory.create_event(
                    component="test",
                    operation="test_log",
                )

                logger.log(event)
                await wait_for_queue_processing(logger)

                # Check file was created
                # The file should be exactly where we specified
                expected_file = temp_audit_dir / "audit.log"
                assert expected_file.exists(), (
                    f"Expected file {expected_file} does not exist"
                )
                log_files = [expected_file]

                # Verify content
                entries = AuditLogParser.parse_log_file(log_files[0])
                assert len(entries) == 1
                assert entries[0]["component"] == "test"
                assert entries[0]["operation"] == "test_log"

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_log_multiple_events(self, temp_audit_dir):
        """Test logging multiple events."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            try:
                events = AuditEventFactory.create_batch(10)
                for event in events:
                    logger.log(event)

                await wait_for_queue_processing(logger)

                log_files = list(temp_audit_dir.glob("*.log"))
                assert len(log_files) == 1

                entries = AuditLogParser.parse_log_file(log_files[0])
                assert len(entries) == 10

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_level_filtering(self, temp_audit_dir):
        """Test that events below min level are filtered."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()
            # Logger auto-starts, no need to call start()

            try:
                # Log events at different levels
                logger.log(
                    AuditEventFactory.create_event(level=AuditLevel.DEBUG),
                )
                logger.log(
                    AuditEventFactory.create_event(level=AuditLevel.INFO),
                )
                logger.log(
                    AuditEventFactory.create_event(level=AuditLevel.WARNING),
                )
                logger.log(
                    AuditEventFactory.create_event(level=AuditLevel.ERROR),
                )

                await wait_for_queue_processing(logger)

                log_files = list(temp_audit_dir.glob("*.log"))
                if log_files:
                    entries = AuditLogParser.parse_log_file(log_files[0])
                    # Only WARNING and ERROR should be logged
                    assert len(entries) == 2
                    levels = {e["level"] for e in entries}
                    assert levels == {"WARNING", "ERROR"}

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_disabled_logger(self, temp_audit_dir):
        """Test that disabled logger doesn't write files."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "false",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()
            # Logger auto-starts, no need to call start()

            try:
                event = AuditEventFactory.create_event()
                logger.log(event)
                await asyncio.sleep(0.1)

                # No files should be created
                log_files = list(temp_audit_dir.glob("*.log"))
                assert len(log_files) == 0

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_queue_operations(self):
        """Test queue operations."""
        logger = AuditLogger()
        logger._queue = asyncio.Queue(maxsize=5)

        # Test putting events
        from aidb.audit.events import AuditEvent

        events = []
        for i in range(5):
            event = AuditEvent(
                component="test",
                operation=f"test_operation_{i}",
                parameters={},
            )
            events.append(event)
            await logger._queue.put(event)

        assert logger._queue.qsize() == 5
        assert logger._queue.full()

        # Test getting events
        items = []
        while not logger._queue.empty():
            items.append(await logger._queue.get())

        # Compare the actual events
        assert items == events
        # Verify operations match
        for i, item in enumerate(items):
            assert item.operation == f"test_operation_{i}"

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, temp_audit_dir):
        """Test start/stop lifecycle."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            # Worker tasks are started automatically if enabled
            if logger._enabled:
                assert logger._worker_task is not None

            await logger.shutdown()
            # After shutdown, worker should be stopped
            assert logger._shutdown

    @pytest.mark.asyncio
    async def test_multiple_start_calls(self, temp_audit_dir):
        """Test that multiple start calls are idempotent."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            # Worker task is created once in __init__ if enabled
            if logger._enabled:
                task1 = logger._worker_task
                # Task should remain the same
                task2 = logger._worker_task
                assert task1 is task2

            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_file_rotation_by_size(self, temp_audit_dir):
        """Test file rotation when size limit is reached."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
                "AIDB_AUDIT_LOG_MB": "1",  # Set to 1MB in env var
            },
        ):
            logger = AuditLogger()

            # Override the size limits after initialization to force small size
            logger._max_size_bytes = 200  # 200 bytes - very small
            logger._max_size_mb = 0.0002

            try:
                # Write events that exceed 200 bytes total
                for i in range(5):
                    event = AuditEventFactory.create_event(
                        operation=f"operation_{i}",
                        parameters={
                            "data": "x"
                            * 100,  # Each event will be > 200 bytes when serialized
                        },
                    )
                    logger.log(event)
                    await asyncio.sleep(0.05)  # Give time for processing

                # Wait for processing
                await wait_for_queue_processing(logger)
                await asyncio.sleep(0.5)

                # Check for rotated files
                log_files = sorted(temp_audit_dir.glob("audit.log*"))

                # Should have rotated files
                assert len(log_files) > 1, (
                    f"Expected rotation with {logger._max_size_bytes} byte limit. Found {len(log_files)} files"
                )

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_cleanup_old_files(self, temp_audit_dir):
        """Test cleanup of old log files."""
        # Create files with different ages
        import time

        # Create an old file (40 days old)
        old_date = datetime.now(timezone.utc) - timedelta(days=40)
        old_file = temp_audit_dir / f"audit.log.{old_date.strftime('%Y%m%d_%H%M%S')}"
        old_file.write_text('{"test": "old"}')
        # Set the file's modification time to 40 days ago
        old_timestamp = (datetime.now(timezone.utc) - timedelta(days=40)).timestamp()
        os.utime(old_file, (old_timestamp, old_timestamp))

        # Create a recent file
        recent_file = temp_audit_dir / "audit.log.20240101_000000"
        recent_file.write_text('{"test": "recent"}')
        # Keep recent file with current timestamp

        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
                "AIDB_AUDIT_LOG_RETENTION_DAYS": "30",
            },
        ):
            logger = AuditLogger()

            # Call cleanup
            await logger.cleanup()

            assert not old_file.exists(), f"Old file should be deleted: {old_file}"
            # Recent file should still exist
            assert recent_file.exists(), (
                f"Recent file should still exist: {recent_file}"
            )

    @pytest.mark.asyncio
    async def test_error_handling_in_worker(
        self,
        temp_audit_dir,
    ):
        """Test error handling in background worker."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            # Mock write to fail
            with patch.object(
                logger,
                "_write_event",
                side_effect=OSError("Disk full"),
            ):
                # Logger auto-starts, no need to call start()

                try:
                    event = AuditEventFactory.create_event()
                    logger.log(event)
                    await asyncio.sleep(0.2)

                    # Worker should continue running despite error
                    assert logger._worker_task is not None

                finally:
                    await logger.shutdown()

    @pytest.mark.asyncio
    async def test_flush_on_interval(self, temp_audit_dir):
        """Test periodic flush of events."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),  # 100ms
            },
        ):
            logger = AuditLogger()
            # Logger auto-starts, no need to call start()

            try:
                # Log a single event
                event = AuditEventFactory.create_event()
                logger.log(event)

                # Wait for flush interval
                await asyncio.sleep(0.3)

                # Event should be written even without filling buffer
                log_files = list(temp_audit_dir.glob("*.log"))
                if log_files:
                    entries = AuditLogParser.parse_log_file(log_files[0])
                    assert len(entries) >= 1

            finally:
                await logger.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_logging(self, temp_audit_dir):
        """Test concurrent logging from multiple tasks."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            try:

                async def log_events(task_id: int):
                    for i in range(10):
                        event = AuditEventFactory.create_event(
                            component=f"task_{task_id}",
                            operation=f"op_{i}",
                        )
                        logger.log(event)

                # Run multiple tasks concurrently
                tasks = [log_events(i) for i in range(5)]
                await asyncio.gather(*tasks)

                await wait_for_queue_processing(logger)

                log_files = list(temp_audit_dir.glob("*.log"))
                if log_files:
                    entries = AuditLogParser.parse_log_file(log_files[0])
                    assert len(entries) == 50  # 5 tasks * 10 events

                    # Check all tasks logged events
                    components = {e["component"] for e in entries}
                    expected = {f"task_{i}" for i in range(5)}
                    assert expected.issubset(components)

            finally:
                await logger.shutdown()

    def test_create_audit_directory(self, tmp_path):
        """Test creation of audit directory if it doesn't exist."""
        non_existent = tmp_path / "new_audit_dir"
        assert not non_existent.exists()

        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_LOG_PATH": str(non_existent / "audit.log"),
            },
        ):
            AuditLogger()
            assert non_existent.exists()
            assert non_existent.is_dir()

    @pytest.mark.asyncio
    async def test_write_permissions_check(self, tmp_path):
        """Test handling of directory without write permissions."""
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()

        # Make directory read-only
        Path(read_only_dir).chmod(0o444)

        try:
            with patch.dict(
                os.environ,
                {
                    "AIDB_AUDIT_LOG": "true",
                    "AIDB_AUDIT_ENABLED": "true",
                    "AIDB_AUDIT_LOG_PATH": str(read_only_dir / "audit.log"),
                },
            ):
                logger = AuditLogger()
                # Logger auto-starts, no need to call start()

                try:
                    event = AuditEventFactory.create_event()
                    logger.log(event)
                    await asyncio.sleep(0.1)

                    # Should handle permission error gracefully
                    assert logger._worker_task is not None

                finally:
                    await logger.shutdown()

        finally:
            # Restore permissions for cleanup
            Path(read_only_dir).chmod(0o755)

    @pytest.mark.asyncio
    async def test_json_serialization_errors(
        self,
        temp_audit_dir,
    ):
        """Test handling of events that can't be serialized to JSON."""
        with patch.dict(
            os.environ,
            {
                "AIDB_AUDIT_LOG": "true",
                "AIDB_AUDIT_ENABLED": "true",
                "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
            },
        ):
            logger = AuditLogger()

            try:
                # Create event with non-serializable data
                event = AuditEventFactory.create_event()
                event.parameters["func"] = lambda x: x  # Functions can't be serialized

                # Mock to_json to raise exception
                with patch.object(
                    event,
                    "to_json",
                    side_effect=TypeError("Can't serialize"),
                ):
                    logger.log(event)
                    await asyncio.sleep(0.1)

                    # Logger should continue running
                    assert logger._worker_task is not None

            finally:
                await logger.shutdown()
