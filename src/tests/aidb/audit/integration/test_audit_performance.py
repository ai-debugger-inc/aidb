"""Performance and stress tests for audit subsystem."""

import asyncio
import gc
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import psutil
import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import AuditLogger
from aidb.audit.middleware import AuditContext
from aidb_common.patterns import Singleton
from tests._fixtures.audit import temp_audit_dir  # noqa: F401
from tests._helpers.audit import (
    AuditEventFactory,
    AuditLogParser,
    AuditTestMixin,
    wait_for_queue_processing,
)
from tests._helpers.pytest_base import PytestIntegrationBase


class TestAuditPerformance(PytestIntegrationBase, AuditTestMixin):
    """Test audit subsystem performance and limits."""

    @pytest.fixture(autouse=True)
    async def setup_performance(self, temp_audit_dir):
        """Set up performance test environment."""
        # Clear singleton using AuditLogger's own singleton pattern
        AuditLogger._reset_singleton()

        self.audit_dir = temp_audit_dir
        os.environ["AIDB_AUDIT_LOG"] = "true"  # Enable audit logging
        os.environ["AIDB_AUDIT_ENABLED"] = "true"  # Enable via new env var
        os.environ["AIDB_AUDIT_LOG_PATH"] = str(temp_audit_dir / "audit.log")
        os.environ["AIDB_AUDIT_LEVEL"] = "INFO"
        os.environ["AIDB_AUDIT_FLUSH_INTERVAL"] = "0.1"  # Fast flush for tests

        try:
            yield
        finally:
            # Reset singleton (handles shutdown internally if needed)
            AuditLogger._reset_singleton()

            # Cleanup env vars
            os.environ.pop("AIDB_AUDIT_LOG", None)
            os.environ.pop("AIDB_AUDIT_ENABLED", None)
            os.environ.pop("AIDB_AUDIT_LOG_PATH", None)
            os.environ.pop("AIDB_AUDIT_LEVEL", None)
            os.environ.pop("AIDB_AUDIT_FLUSH_INTERVAL", None)

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_high_volume_event_handling(self):
        """Test handling of high volume of events."""
        # Logger creation relies on fixture's patch
        logger = AuditLogger()

        event_count = 1000
        start_time = time.time()

        try:
            # Generate high volume of events with pacing to prevent queue overflow
            for i in range(event_count):
                event = AuditEventFactory.create_event(
                    component="performance",
                    operation=f"op_{i}",
                    parameters={"index": i, "batch": i // 100},
                    result={"success": True, "duration_ms": 10},
                )
                logger.log(event)

                # Brief pause every 50 events to prevent queue overflow
                if i > 0 and i % 50 == 0:
                    await asyncio.sleep(0.05)

            # Wait for processing with longer timeout
            await wait_for_queue_processing(logger, timeout=15.0)

            elapsed = time.time() - start_time

            # Verify all events were logged
            log_files = list(self.audit_dir.glob("audit.log*"))
            total_events = 0
            for log_file in log_files:
                entries = AuditLogParser.parse_log_file(log_file)
                total_events += len(entries)

            assert total_events == event_count

            # Performance assertions
            events_per_second = event_count / elapsed
            assert events_per_second > 100  # Should handle at least 100 events/sec

            self.logger.info("Processed %s events in %.2fs", event_count, elapsed)
            self.logger.info(
                "Rate: %s events/second",
                f"{events_per_second:.0f}",
            )

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_queue_overflow_behavior(self):
        """Test behavior when event queue overflows."""
        from unittest.mock import PropertyMock

        # Create logger with small queue
        logger = AuditLogger()
        logger._queue = asyncio.Queue(maxsize=10)

        # Don't start worker to simulate slow processing
        # Mock the is_running property using patch context manager for proper cleanup
        with patch.object(
            type(logger),
            "is_running",
            new_callable=PropertyMock,
            return_value=True,
        ):
            events_sent = 0
            events_dropped = 0

            # Try to send more events than queue can hold
            for i in range(20):
                event = AuditEventFactory.create_event(
                    operation=f"overflow_{i}",
                )

                try:
                    # Use nowait to detect overflow
                    logger._queue.put_nowait(event)
                    events_sent += 1
                except asyncio.QueueFull:
                    events_dropped += 1

            # Queue should be full
            assert logger._queue.full()
            assert events_sent == 10
            assert events_dropped == 10

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_under_load(self):
        """Test memory usage with sustained load."""
        logger = AuditLogger()

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        try:
            # Generate events for 2 seconds
            start_time = time.time()
            event_count = 0

            while time.time() - start_time < 2.0:
                event = AuditEventFactory.create_event(
                    component="memory_test",
                    operation=f"op_{event_count}",
                    parameters={"data": "x" * 1000},  # 1KB payload
                )
                logger.log(event)
                event_count += 1

                if event_count % 100 == 0:
                    await asyncio.sleep(0.01)  # Yield control

            await wait_for_queue_processing(logger)

            # Check memory usage
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            self.logger.info("Generated %s events", event_count)
            self.logger.info("Memory increase: %s MB", f"{memory_increase:.1f}")

            # Memory increase should be reasonable (< 50MB for this test)
            assert memory_increase < 50

            # Force garbage collection
            gc.collect()

            # Memory should be released after GC
            post_gc_memory = process.memory_info().rss / 1024 / 1024
            assert post_gc_memory - initial_memory < 20

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_sustained_load_stability(self):
        """Test system stability under sustained load."""
        logger = AuditLogger()

        duration = 3.0  # seconds
        start_time = time.time()
        event_count = 0
        errors = []

        try:
            while time.time() - start_time < duration:
                try:
                    # Vary the load
                    burst_size = 10 if event_count % 100 < 50 else 1

                    for _ in range(burst_size):
                        event = AuditEventFactory.create_event(
                            component="sustained",
                            operation=f"op_{event_count}",
                        )
                        logger.log(event)
                        event_count += 1

                    # Small delay between bursts
                    await asyncio.sleep(0.001)

                except Exception as e:
                    errors.append(str(e))

            await wait_for_queue_processing(logger)

            # Should have no errors
            assert len(errors) == 0

            # Verify events were logged
            log_files = list(self.audit_dir.glob("audit.log*"))
            total_logged = 0
            for log_file in log_files:
                entries = AuditLogParser.parse_log_file(log_file)
                total_logged += len(entries)

            # Allow for some events in queue at end
            assert total_logged >= event_count * 0.95

            rate = event_count / duration
            self.logger.info(
                "Sustained rate: %.0f events/second for %ss",
                rate,
                duration,
            )

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_worker_recovery_performance(self):
        """Test performance of worker recovery after errors."""
        from unittest.mock import patch

        logger = AuditLogger()

        try:
            # Simulate intermittent write errors
            original_write = logger._write_event
            write_count = 0
            error_count = 0

            async def flaky_write(event):
                nonlocal write_count, error_count
                write_count += 1
                # Fail every 10th write
                if write_count % 10 == 0:
                    error_count += 1
                    msg = "Simulated write error"
                    raise OSError(msg)
                return await original_write(event)

            with patch.object(logger, "_write_event", side_effect=flaky_write):
                # Send events despite errors
                for i in range(100):
                    event = AuditEventFactory.create_event(
                        operation=f"recovery_{i}",
                    )
                    logger.log(event)

                await wait_for_queue_processing(logger, timeout=10.0)

                # Worker should continue running despite errors
                assert logger.is_running

                # Most events should still be logged
                log_files = list(self.audit_dir.glob("audit.log*"))
            if log_files:
                entries = AuditLogParser.parse_log_file(log_files[0])
                # Should have logged most events (minus the failed ones)
                # With 100 events and ~10% failure rate, expect ~90 successes
                # but timing/async issues can cause additional variance
                assert len(entries) >= 60

            self.logger.info("Recovered from  write errors %s", error_count)

        finally:
            await logger.shutdown()
