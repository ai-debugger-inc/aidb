"""Helper utilities for audit subsystem testing."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from aidb.audit.events import AuditEvent, AuditLevel
from aidb_mcp.core.constants import ParamName


class AuditEventFactory:
    """Factory for creating test audit events."""

    @staticmethod
    def create_event(
        level: AuditLevel = AuditLevel.INFO,
        component: str = "test.component",
        operation: str = "test_operation",
        session_id: str | None = None,
        parameters: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
        timestamp: datetime | None = None,
    ) -> AuditEvent:
        """Create a custom audit event for testing.

        Parameters
        ----------
        level : AuditLevel
            Event severity level
        component : str
            Component name
        operation : str
            Operation name
        session_id : Optional[str]
            Session identifier
        parameters : Optional[Dict[str, Any]]
            Operation parameters
        result : Optional[Dict[str, Any]]
            Operation result
        metadata : Optional[Dict[str, Any]]
            Additional metadata
        error : Optional[str]
            Error message if failed
        timestamp : Optional[datetime]
            Event timestamp

        Returns
        -------
        AuditEvent
            Configured audit event
        """
        event = AuditEvent(
            level=level,
            component=component,
            operation=operation,
            session_id=session_id or f"test_{datetime.now(timezone.utc).timestamp()}",
            parameters=parameters or {},
            result=result or {"success": error is None},
            metadata=metadata or {},
            error=error,
        )

        if timestamp:
            event.timestamp = timestamp.isoformat()

        return event

    @staticmethod
    def create_batch(
        count: int,
        base_component: str = "test",
        time_delta: timedelta = timedelta(seconds=1),
    ) -> list[AuditEvent]:
        """Create a batch of audit events.

        Parameters
        ----------
        count : int
            Number of events to create
        base_component : str
            Base component name
        time_delta : timedelta
            Time between events

        Returns
        -------
        List[AuditEvent]
            List of audit events
        """
        events = []
        base_time = datetime.now(timezone.utc)

        for i in range(count):
            event = AuditEventFactory.create_event(
                level=AuditLevel.INFO if i % 3 != 2 else AuditLevel.WARNING,
                component=f"{base_component}.batch",
                operation=f"operation_{i}",
                session_id=f"batch_session_{i // 10}",
                parameters={"index": i, "batch": True},
                result={"success": i % 5 != 4, "duration_ms": 10 + i},
                timestamp=base_time + (time_delta * i),
            )
            events.append(event)

        return events


class AuditLogParser:
    """Parse and analyze audit log files."""

    @staticmethod
    def parse_log_file(log_path: Path) -> list[dict[str, Any]]:
        """Parse a JSON Lines audit log file.

        Parameters
        ----------
        log_path : Path
            Path to log file

        Returns
        -------
        List[Dict[str, Any]]
            List of parsed log entries
        """
        if not log_path.exists():
            return []

        entries = []
        with log_path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue

        return entries

    @staticmethod
    def filter_by_level(
        entries: list[dict[str, Any]],
        level: AuditLevel,
    ) -> list[dict[str, Any]]:
        """Filter log entries by level.

        Parameters
        ----------
        entries : List[Dict[str, Any]]
            Log entries to filter
        level : AuditLevel
            Minimum level to include

        Returns
        -------
        List[Dict[str, Any]]
            Filtered entries
        """
        level_order = {
            AuditLevel.DEBUG: 0,
            AuditLevel.INFO: 1,
            AuditLevel.WARNING: 2,
            AuditLevel.ERROR: 3,
            AuditLevel.CRITICAL: 4,
        }

        min_level = level_order[level]
        filtered = []

        for entry in entries:
            entry_level = AuditLevel(entry.get("level", "INFO"))
            if level_order[entry_level] >= min_level:
                filtered.append(entry)

        return filtered

    @staticmethod
    def get_session_events(
        entries: list[dict[str, Any]],
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Get all events for a specific session.

        Parameters
        ----------
        entries : List[Dict[str, Any]]
            Log entries
        session_id : str
            Session ID to filter by

        Returns
        -------
        List[Dict[str, Any]]
            Events for the session
        """
        return [e for e in entries if e.get(ParamName.SESSION_ID) == session_id]


class AuditTestMixin:
    """Mixin class with common audit test assertions."""

    def assert_event_valid(self, event: AuditEvent) -> None:
        """Assert that an audit event is valid.

        Parameters
        ----------
        event : AuditEvent
            Event to validate
        """
        assert event.timestamp
        assert event.level in AuditLevel
        assert event.component
        assert event.operation
        assert "pid" in event.metadata
        assert "user" in event.metadata

    def assert_event_masked(self, event_json: str) -> None:
        """Assert that sensitive data is masked in JSON.

        Parameters
        ----------
        event_json : str
            JSON string of event
        """
        sensitive_patterns = [
            "password",
            "secret",
            "token",
            "api_key",
            "license_key",
        ]

        for pattern in sensitive_patterns:
            assert pattern not in event_json.lower() or "***" in event_json

    def assert_log_file_valid(self, log_path: Path) -> None:
        """Assert that a log file is valid JSON Lines.

        Parameters
        ----------
        log_path : Path
            Path to log file
        """
        assert log_path.exists()
        assert log_path.stat().st_size > 0

        with log_path.open() as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        assert "timestamp" in data
                        assert "level" in data
                    except json.JSONDecodeError as e:
                        msg = f"Invalid JSON on line {line_num}: {e}"
                        raise AssertionError(
                            msg,
                        ) from e

    def assert_events_ordered(self, entries: list[dict[str, Any]]) -> None:
        """Assert that events are chronologically ordered.

        Parameters
        ----------
        entries : List[Dict[str, Any]]
            List of log entries
        """
        timestamps = [e["timestamp"] for e in entries if "timestamp" in e]
        assert timestamps == sorted(timestamps)


async def wait_for_queue_processing(
    logger: Any,
    timeout: float = 1.0,
) -> bool:
    """Wait for audit logger queue to be processed.

    Parameters
    ----------
    logger : Any
        AuditLogger instance
    timeout : float
        Maximum wait time in seconds

    Returns
    -------
    bool
        True if queue was processed, False if timeout
    """
    # Wait for queue to empty asynchronously
    if hasattr(logger, "_queue") and hasattr(logger, "_enabled") and logger._enabled:
        start_time = asyncio.get_event_loop().time()
        # Poll queue emptying with short sleep intervals
        while not logger._queue.empty():
            if asyncio.get_event_loop().time() - start_time > timeout:
                return False
            await asyncio.sleep(0.01)

        # Additional brief wait for file writing to complete
        await asyncio.sleep(0.05)
    else:
        # If no queue available or logger disabled, just wait briefly
        await asyncio.sleep(0.1)

    return True


def create_mock_log_files(
    audit_dir: Path,
    count: int = 3,
    size_kb: int = 10,
) -> list[Path]:
    """Create mock log files for testing.

    Parameters
    ----------
    audit_dir : Path
        Directory for log files
    count : int
        Number of files to create
    size_kb : int
        Approximate size of each file in KB

    Returns
    -------
    List[Path]
        Paths to created files
    """
    files = []
    base_time = datetime.now(timezone.utc)

    for i in range(count):
        timestamp = (base_time - timedelta(days=i)).strftime("%Y%m%d_%H%M%S")
        log_file = audit_dir / f"audit.log.{timestamp}"

        # Calculate events needed for target size
        sample_event = AuditEventFactory.create_event()
        event_size = len(sample_event.to_json())
        events_needed = (size_kb * 1024) // event_size

        with log_file.open("w") as f:
            for j in range(events_needed):
                event = AuditEventFactory.create_event(
                    operation=f"mock_op_{j}",
                    timestamp=base_time - timedelta(days=i, seconds=j),
                )
                f.write(event.to_json() + "\n")

        files.append(log_file)

    return files


def verify_sensitive_data_masked(data: dict[str, Any]) -> bool:
    """Verify that sensitive data is properly masked.

    Parameters
    ----------
    data : Dict[str, Any]
        Data dictionary to check

    Returns
    -------
    bool
        True if all sensitive data is masked
    """
    sensitive_keys = {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "license_key",
        "private_key",
        "access_token",
        "refresh_token",
    }

    def check_dict(d: dict[str, Any]) -> bool:
        for key, value in d.items():
            # Check if key contains sensitive pattern
            if any(s in key.lower() for s in sensitive_keys):
                if isinstance(value, str) and value != "***MASKED***":
                    return False
            # Recursively check nested dicts
            elif isinstance(value, dict):
                if not check_dict(value):
                    return False
            # Check lists of dicts
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and not check_dict(item):
                        return False
        return True

    return check_dict(data)
