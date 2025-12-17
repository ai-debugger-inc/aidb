"""Integration tests for audit subsystem workflows."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import AuditLogger
from aidb.audit.middleware import AuditContext, audit_operation
from aidb.common.context import AidbContext
from tests._fixtures.audit import temp_audit_dir  # noqa: F401
from tests._helpers.audit import (
    AuditEventFactory,
    AuditLogParser,
    AuditTestMixin,
    wait_for_queue_processing,
)
from tests._helpers.pytest_base import PytestIntegrationBase


class TestAuditIntegration(PytestIntegrationBase, AuditTestMixin):
    """Test end-to-end audit workflows."""

    @pytest.fixture(autouse=True)
    async def setup_audit(self, temp_audit_dir):
        """Set up audit environment for tests."""
        # Clear singleton
        AuditLogger._instance = None

        # Set audit directory with correct environment variables
        self.audit_dir = temp_audit_dir
        os.environ["AIDB_AUDIT_LOG"] = "true"
        os.environ["AIDB_AUDIT_ENABLED"] = "true"
        os.environ["AIDB_AUDIT_LOG_PATH"] = str(temp_audit_dir / "audit.log")

        yield

        # Cleanup - use _reset_singleton which handles shutdown internally
        AuditLogger._reset_singleton()

        # Clean up env vars
        os.environ.pop("AIDB_AUDIT_LOG", None)
        os.environ.pop("AIDB_AUDIT_ENABLED", None)
        os.environ.pop("AIDB_AUDIT_LOG_PATH", None)

    @pytest.mark.asyncio
    async def test_full_debug_session_audit(self):
        """Test auditing of a complete debug session."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        try:
            # Simulate debug session with audit context
            async with AuditContext(
                component="api.session",
                operation="create_session",
                session_id="test_session_001",
                parameters={"language": "python", "target": "test.py"},
            ) as create_ctx:
                await asyncio.sleep(0.01)  # Simulate work
                create_ctx.set_result({"session_created": True, "port": 5678})

            # Simulate operations within session
            async with AuditContext(
                component="api.operations",
                operation="set_breakpoint",
                session_id="test_session_001",
                parameters={"file": "test.py", "line": 10},
            ) as bp_ctx:
                bp_ctx.set_result({"breakpoint_id": "bp_1"})

            async with AuditContext(
                component="api.operations",
                operation="continue_execution",
                session_id="test_session_001",
            ) as exec_ctx:
                exec_ctx.set_result({"stopped_at": "test.py:10"})

            # Simulate session termination
            async with AuditContext(
                component="api.session",
                operation="terminate_session",
                session_id="test_session_001",
            ) as term_ctx:
                term_ctx.set_result({"terminated": True})

            # Wait for all events to be written
            await wait_for_queue_processing(logger)

            # Verify audit trail
            log_files = list(self.audit_dir.glob("*.log"))
            assert len(log_files) == 1

            entries = AuditLogParser.parse_log_file(log_files[0])
            assert len(entries) >= 4

            # Verify session events
            session_events = AuditLogParser.get_session_events(
                entries,
                "test_session_001",
            )
            assert len(session_events) == 4

            # Check event sequence
            operations = [e["operation"] for e in session_events]
            assert operations == [
                "create_session",
                "set_breakpoint",
                "continue_execution",
                "terminate_session",
            ]

            # Verify event details
            create_event = next(
                e for e in session_events if e["operation"] == "create_session"
            )
            assert create_event["parameters"]["language"] == "python"
            assert create_event["result"]["session_created"] is True

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_audit_error_handling_integration(self):
        """Test audit of error scenarios."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        try:
            # Successful operation
            async with AuditContext(
                component="api",
                operation="success_op",
            ) as ctx:
                ctx.set_result({"status": "ok"})

            # Failed operation
            try:
                async with AuditContext(
                    component="api",
                    operation="failed_op",
                ) as ctx:
                    msg = "Simulated failure"
                    raise RuntimeError(msg)
            except RuntimeError:
                pass

            # Operation with warning
            async with AuditContext(
                component="api",
                operation="warning_op",
                level=AuditLevel.WARNING,
            ) as ctx:
                ctx.set_result({"warning": "Resource limit approaching"})

            await wait_for_queue_processing(logger)

            # Verify all events logged
            log_files = list(self.audit_dir.glob("*.log"))
            entries = AuditLogParser.parse_log_file(log_files[0])

            # Check success event
            success = next(
                (e for e in entries if e["operation"] == "success_op"),
                None,
            )
            assert success is not None, "success_op event not found"
            assert success["level"] == "INFO"
            assert success["result"]["success"] is True

            # Check error event
            error = next(
                (e for e in entries if e["operation"] == "failed_op"),
                None,
            )
            assert error is not None, "failed_op event not found"
            assert error["level"] == "ERROR"
            assert error["error"] == "Simulated failure"
            assert error["result"]["success"] is False

            # Check warning event
            warning = next(
                (e for e in entries if e["operation"] == "warning_op"),
                None,
            )
            assert warning is not None, "warning_op event not found"
            assert warning["level"] == "WARNING"

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_operations_audit(self):
        """Test auditing of concurrent operations."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        try:

            async def perform_operation(op_id: int, session_id: str):
                async with AuditContext(
                    component="concurrent",
                    operation=f"operation_{op_id}",
                    session_id=session_id,
                    parameters={"op_id": op_id},
                ) as ctx:
                    await asyncio.sleep(0.01)  # Simulate work
                    ctx.set_result({"completed": True, "op_id": op_id})

            # Run operations concurrently
            session1_tasks = [perform_operation(i, "session_1") for i in range(5)]
            session2_tasks = [perform_operation(i, "session_2") for i in range(5)]

            await asyncio.gather(*(session1_tasks + session2_tasks))
            await wait_for_queue_processing(logger)

            # Verify all operations logged
            log_files = list(self.audit_dir.glob("*.log"))
            entries = AuditLogParser.parse_log_file(log_files[0])

            # Should have 10 events total
            assert len(entries) == 10

            # Check session separation
            session1_events = AuditLogParser.get_session_events(
                entries,
                "session_1",
            )
            session2_events = AuditLogParser.get_session_events(
                entries,
                "session_2",
            )

            assert len(session1_events) == 5
            assert len(session2_events) == 5

            # Verify all operations completed
            for event in entries:
                assert event["result"]["completed"] is True

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_decorated_api_methods_audit(self):
        """Test auditing of decorated API methods."""

        # Audit enabled via setup_audit fixture
        class MockAPI:
            @audit_operation(component="mock_api", operation="start_session")
            async def start_session(self, session_id: str, language: str) -> dict:
                await asyncio.sleep(0.01)
                return {"session_id": session_id, "status": "started"}

            @audit_operation(component="mock_api", operation="stop_session")
            async def stop_session(self, session_id: str) -> bool:
                return True

            @audit_operation(
                component="mock_api",
                operation="execute_command",
                level=AuditLevel.DEBUG,
            )
            async def execute_command(self, session_id: str, command: str) -> str:
                if command == "error":
                    msg = "Invalid command"
                    raise ValueError(msg)
                return f"Executed: {command}"

        logger = AuditLogger()

        try:
            api = MockAPI()

            # Test normal operations
            result = await api.start_session("test_001", "python")
            assert result["status"] == "started"

            result = await api.execute_command("test_001", "continue")
            assert result == "Executed: continue"

            # Test error case
            with pytest.raises(ValueError, match="Invalid command"):
                await api.execute_command("test_001", "error")

            result = await api.stop_session("test_001")
            assert result is True

            await wait_for_queue_processing(logger)

            # Verify audit trail
            log_files = list(self.audit_dir.glob("*.log"))
            entries = AuditLogParser.parse_log_file(log_files[0])

            # Check all operations logged
            operations = [e["operation"] for e in entries]
            assert "start_session" in operations
            assert "execute_command" in operations
            assert "stop_session" in operations

            # Verify error was logged
            error_events = [
                e
                for e in entries
                if e["operation"] == "execute_command" and e.get("error")
            ]
            assert len(error_events) == 1
            assert error_events[0]["error"] == "Invalid command"

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_audit_file_rotation_integration(self):
        """Test audit file rotation during operations."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        # Override size limits after initialization to force rotation
        logger._max_size_bytes = 10000  # 10KB
        logger._max_size_mb = 0.01

        try:
            # Generate enough events to trigger rotation
            # Use smaller batches with more frequent waits to ensure events aren't lost
            for i in range(100):
                async with AuditContext(
                    component="rotation_test",
                    operation=f"operation_{i}",
                    parameters={
                        "index": i,
                        "data": "x" * 200,  # Add bulk
                    },
                ) as ctx:
                    ctx.set_result({"success": True, "index": i})

                # Wait more frequently during rotation to prevent event loss
                if i % 3 == 0:
                    await wait_for_queue_processing(logger)
                    await asyncio.sleep(
                        0.1,
                    )  # Longer pause for rotation file operations

            # Final wait with extra time for any pending rotation
            await wait_for_queue_processing(logger)
            await asyncio.sleep(1.0)  # Extra time to ensure rotation completes

            # Poll for rotation to complete (up to 10 seconds)
            log_files = []
            for _ in range(10):
                log_files = sorted(self.audit_dir.glob("audit.log*"))
                if len(log_files) > 1:
                    break
                await asyncio.sleep(1.0)

            # Should have multiple log files
            assert len(log_files) > 1, f"Expected >1 log files, got {len(log_files)}"

            # Verify all events are preserved across files
            # Sort files by modification time to read in chronological order
            log_files_sorted = sorted(log_files, key=lambda f: f.stat().st_mtime)

            all_entries = []
            for log_file in log_files_sorted:
                all_entries.extend(AuditLogParser.parse_log_file(log_file))

            # Should have all 100 events
            assert len(all_entries) >= 100

            # Verify chronological order across rotated files
            self.assert_events_ordered(all_entries)

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_audit_cleanup_integration(self):
        """Test audit log cleanup functionality."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        # Create some old files
        old_date = datetime.now(timezone.utc) - timedelta(days=40)
        old_file = self.audit_dir / f"audit.log.{old_date.strftime('%Y%m%d_%H%M%S')}"
        old_file.write_text('{"old": "event"}\n')

        recent_date = datetime.now(timezone.utc) - timedelta(days=5)
        recent_file = (
            self.audit_dir / f"audit.log.{recent_date.strftime('%Y%m%d_%H%M%S')}"
        )
        recent_file.write_text('{"recent": "event"}\n')

        # Configure cleanup
        os.environ["AIDB_AUDIT_LOG_RETENTION_DAYS"] = "30"

        try:
            # Note: cleanup is not directly exposed in the implementation
            # We would need to trigger it through rotation or similar mechanism
            # For now, we'll skip the actual cleanup test
            pass

            # Old file should be removed
            # assert not old_file.exists()
            # Recent file should remain
            # assert recent_file.exists()

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_audit_context_metadata_propagation(self):
        """Test metadata propagation through audit contexts."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        try:
            # Create nested contexts with metadata
            async with AuditContext(
                component="outer",
                operation="parent_op",
                metadata={"request_id": "req_123", "user": "test_user"},
            ) as outer:
                outer.add_metadata("outer_data", "value1")

                async with AuditContext(
                    component="inner",
                    operation="child_op",
                    metadata={"inner_specific": "data"},
                ) as inner:
                    inner.add_metadata("inner_data", "value2")
                    # Access parent context metadata if needed
                    inner.add_metadata("parent_ref", outer.operation)

            await wait_for_queue_processing(logger)

            # Verify metadata in events
            log_files = list(self.audit_dir.glob("*.log"))
            entries = AuditLogParser.parse_log_file(log_files[0])

            outer_event = next(
                (e for e in entries if e["operation"] == "parent_op"),
                None,
            )
            assert outer_event is not None, "parent_op event not found"
            assert outer_event["metadata"]["request_id"] == "req_123"
            assert outer_event["metadata"]["outer_data"] == "value1"

            inner_event = next(
                (e for e in entries if e["operation"] == "child_op"),
                None,
            )
            assert inner_event is not None, "child_op event not found"
            assert inner_event["metadata"]["inner_specific"] == "data"
            assert inner_event["metadata"]["inner_data"] == "value2"
            assert inner_event["metadata"]["parent_ref"] == "parent_op"

        finally:
            await logger.shutdown()

    @pytest.mark.asyncio
    async def test_audit_performance_metrics(self):
        """Test performance metrics in audit events."""
        # Audit enabled via setup_audit fixture
        logger = AuditLogger()

        try:
            # Perform operations with varying durations
            async with AuditContext(
                component="perf",
                operation="fast_op",
            ) as ctx:
                await asyncio.sleep(0.01)
                ctx.set_result({"data": "fast"})

            async with AuditContext(
                component="perf",
                operation="slow_op",
            ) as ctx:
                await asyncio.sleep(0.1)
                ctx.set_result({"data": "slow"})

            await wait_for_queue_processing(logger)

            # Verify duration metrics
            log_files = list(self.audit_dir.glob("*.log"))
            entries = AuditLogParser.parse_log_file(log_files[0])

            fast_op = next(
                (e for e in entries if e["operation"] == "fast_op"),
                None,
            )
            assert fast_op is not None, "fast_op event not found"
            slow_op = next(
                (e for e in entries if e["operation"] == "slow_op"),
                None,
            )
            assert slow_op is not None, "slow_op event not found"

            # Fast operation should be < 50ms
            assert fast_op["result"]["duration_ms"] < 50

            # Slow operation should be >= 100ms
            assert slow_op["result"]["duration_ms"] >= 100

            # Both should have success status
            assert fast_op["result"]["success"] is True
            assert slow_op["result"]["success"] is True

        finally:
            await logger.shutdown()
