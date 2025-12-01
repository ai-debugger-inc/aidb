"""Comprehensive logging capture utilities for AIDB tests.

This module provides utilities to capture logs from multiple sources (pytest, aidb core,
MCP server) and make them available for assertions in tests.
"""

import logging
import re
import threading
from collections import defaultdict, deque
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from re import Pattern
from typing import Any, Optional, Union


@dataclass
class LogRecord:
    """Captured log record with metadata."""

    timestamp: datetime
    logger_name: str
    level: int
    level_name: str
    message: str
    thread_id: int
    thread_name: str
    session_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def matches(self, pattern: str | Pattern) -> bool:
        """Check if log message matches a pattern.

        Parameters
        ----------
        pattern : Union[str, Pattern]
            String or regex pattern to match

        Returns
        -------
        bool
            True if message matches pattern
        """
        if isinstance(pattern, str):
            return pattern in self.message
        return bool(pattern.search(self.message))


class LogCapture:
    """Captures logs from specified loggers for testing.

    This class provides thread-safe log capture with filtering, searching, and assertion
    capabilities.
    """

    def __init__(
        self,
        logger_names: list[str] | None = None,
        level: int = logging.DEBUG,
        capture_root: bool = False,
        max_records: int = 10000,
    ):
        """Initialize log capture.

        Parameters
        ----------
        logger_names : List[str], optional
            Specific logger names to capture. If None, captures based on capture_root
        level : int
            Minimum log level to capture
        capture_root : bool
            Whether to capture from root logger
        max_records : int
            Maximum number of records to keep (prevents memory issues)
        """
        self.logger_names = logger_names or []
        self.level = level
        self.capture_root = capture_root
        self.max_records = max_records

        # Thread-safe storage
        self._lock = threading.RLock()
        self._records: deque[LogRecord] = deque(maxlen=max_records)
        self._records_by_logger: dict[str, list[LogRecord]] = defaultdict(list)

        # Handler management
        self._handlers: dict[logging.Logger, logging.Handler] = {}
        self._original_levels: dict[logging.Logger, int] = {}

    def start(self) -> None:
        """Start capturing logs."""
        with self._lock:
            # Clear any existing records
            self._records.clear()
            self._records_by_logger.clear()

            # Set up handlers
            if self.capture_root:
                self._attach_to_logger(logging.getLogger())

            for name in self.logger_names:
                logger = logging.getLogger(name)
                self._attach_to_logger(logger)

    def _attach_to_logger(self, logger: logging.Logger) -> None:
        """Attach capture handler to a logger.

        Parameters
        ----------
        logger : logging.Logger
            Logger to attach to
        """
        # Store original level
        self._original_levels[logger] = logger.level

        # Create custom handler
        handler = LogCaptureHandler(self)
        handler.setLevel(self.level)

        # Add formatter to capture all details
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        handler.setFormatter(formatter)

        # Attach handler
        logger.addHandler(handler)
        self._handlers[logger] = handler

        # Ensure logger level allows our captures
        if logger.level > self.level:
            logger.setLevel(self.level)

    def stop(self) -> None:
        """Stop capturing logs and restore original configuration."""
        with self._lock:
            for logger, handler in self._handlers.items():
                logger.removeHandler(handler)
                # Restore original level
                if logger in self._original_levels:
                    logger.setLevel(self._original_levels[logger])

            self._handlers.clear()
            self._original_levels.clear()

    def add_record(self, record: logging.LogRecord) -> None:
        """Add a log record to capture.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to capture
        """
        with self._lock:
            # Convert to our LogRecord format
            log_record = LogRecord(
                timestamp=datetime.fromtimestamp(record.created, timezone.utc),
                logger_name=record.name,
                level=record.levelno,
                level_name=record.levelname,
                message=record.getMessage(),
                thread_id=record.thread or 0,
                thread_name=record.threadName or "Unknown",
                session_id=getattr(record, "session_id", None),
                extras={
                    k: v
                    for k, v in record.__dict__.items()
                    if k
                    not in ["name", "msg", "args", "created", "levelno", "levelname"]
                },
            )

            self._records.append(log_record)
            self._records_by_logger[record.name].append(log_record)

    def clear(self) -> None:
        """Clear all captured records."""
        with self._lock:
            self._records.clear()
            self._records_by_logger.clear()

    @property
    def records(self) -> list[LogRecord]:
        """Get all captured records.

        Returns
        -------
        List[LogRecord]
            All captured log records
        """
        with self._lock:
            return list(self._records)

    def get_logger_records(self, logger_name: str) -> list[LogRecord]:
        """Get records for a specific logger.

        Parameters
        ----------
        logger_name : str
            Logger name to filter by

        Returns
        -------
        List[LogRecord]
            Records from specified logger
        """
        with self._lock:
            return list(self._records_by_logger.get(logger_name, []))

    def filter_level(self, level: int | str) -> list[LogRecord]:
        """Filter records by log level.

        Parameters
        ----------
        level : Union[int, str]
            Log level (e.g., logging.ERROR or "ERROR")

        Returns
        -------
        List[LogRecord]
            Records matching the level
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper())

        with self._lock:
            return [r for r in self._records if r.level >= int(level)]

    def search(self, pattern: str | Pattern) -> list[LogRecord]:
        """Search for records matching a pattern.

        Parameters
        ----------
        pattern : Union[str, Pattern]
            String or regex pattern to search for

        Returns
        -------
        List[LogRecord]
            Records with messages matching the pattern
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern, re.IGNORECASE)

        with self._lock:
            return [r for r in self._records if r.matches(pattern)]

    def contains(self, message: str, logger: str | None = None) -> bool:
        """Check if a message was logged.

        Parameters
        ----------
        message : str
            Message to search for
        logger : str, optional
            Specific logger to search in

        Returns
        -------
        bool
            True if message was logged
        """
        records = self.get_logger_records(logger) if logger else self.records
        return any(message in r.message for r in records)

    def count_level(self, level: int | str) -> int:
        """Count records at or above a log level.

        Parameters
        ----------
        level : Union[int, str]
            Log level to count

        Returns
        -------
        int
            Number of records at or above the level
        """
        return len(self.filter_level(level))

    def has_errors(self) -> bool:
        """Check if any errors were logged.

        Returns
        -------
        bool
            True if ERROR or CRITICAL logs exist
        """
        return self.count_level(logging.ERROR) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were logged.

        Returns
        -------
        bool
            True if WARNING logs exist
        """
        return self.count_level(logging.WARNING) > 0

    def get_messages(
        self,
        level: int | str | None = None,
        logger: str | None = None,
    ) -> list[str]:
        """Get just the message strings.

        Parameters
        ----------
        level : Union[int, str], optional
            Filter by log level
        logger : str, optional
            Filter by logger name

        Returns
        -------
        List[str]
            Log messages
        """
        records = self.records

        if logger:
            records = self.get_logger_records(logger)

        if level:
            if isinstance(level, str):
                level = getattr(logging, level.upper())
            records = [r for r in records if r.level >= int(level)]

        return [r.message for r in records]

    def assert_sequence(self, *expected_messages: str) -> None:
        """Assert that messages appear in order.

        Parameters
        ----------
        *expected_messages : str
            Expected messages in order

        Raises
        ------
        AssertionError
            If messages don't appear in order
        """
        messages = self.get_messages()
        message_iter = iter(messages)

        for expected in expected_messages:
            found = False
            for actual in message_iter:
                if expected in actual:
                    found = True
                    break

            if not found:
                msg = (
                    f"Expected message '{expected}' not found in sequence. "
                    f"Messages: {messages}"
                )
                raise AssertionError(
                    msg,
                )

    def print_logs(self, level: int | str | None = None) -> None:
        """Print captured logs for debugging.

        Parameters
        ----------
        level : Union[int, str], optional
            Minimum level to print
        """
        records = self.filter_level(level) if level else self.records

        for record in records:
            print(
                f"[{record.timestamp:%H:%M:%S.%f}] "
                f"[{record.level_name:8s}] "
                f"[{record.logger_name}] "
                f"{record.message}",
            )

    def __enter__(self) -> "LogCapture":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

    def __len__(self) -> int:
        """Get number of captured records."""
        return len(self._records)

    def __bool__(self) -> bool:
        """Check if any records were captured."""
        return len(self._records) > 0


class LogCaptureHandler(logging.Handler):
    """Custom logging handler that captures to LogCapture."""

    def __init__(self, capture: LogCapture):
        """Initialize handler.

        Parameters
        ----------
        capture : LogCapture
            LogCapture instance to send records to
        """
        super().__init__()
        self.capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to capture.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to capture
        """
        with suppress(Exception):
            # Ignore errors in logging
            self.capture.add_record(record)


class MultiLoggerCapture:
    """Captures logs from multiple named loggers simultaneously."""

    def __init__(
        self,
        logger_mapping: dict[str, list[str]],
        level: int = logging.DEBUG,
    ):
        """Initialize multi-logger capture.

        Parameters
        ----------
        logger_mapping : Dict[str, List[str]]
            Mapping of capture name to logger names
        level : int
            Minimum log level to capture
        """
        self.captures: dict[str, LogCapture] = {}

        for name, loggers in logger_mapping.items():
            self.captures[name] = LogCapture(logger_names=loggers, level=level)

    def start(self) -> None:
        """Start all captures."""
        for capture in self.captures.values():
            capture.start()

    def stop(self) -> None:
        """Stop all captures."""
        for capture in self.captures.values():
            capture.stop()

    def __enter__(self) -> "MultiLoggerCapture":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

    def __getitem__(self, name: str) -> LogCapture:
        """Get a specific capture by name."""
        return self.captures[name]


@contextmanager
def capture_logs(
    *logger_names: str,
    level: int = logging.DEBUG,
    capture_root: bool = False,
):
    """Context manager for capturing logs.

    Parameters
    ----------
    *logger_names : str
        Logger names to capture
    level : int
        Minimum log level
    capture_root : bool
        Whether to capture root logger

    Yields
    ------
    LogCapture
        Log capture instance
    """
    capture = LogCapture(
        logger_names=list(logger_names),
        level=level,
        capture_root=capture_root,
    )

    try:
        capture.start()
        yield capture
    finally:
        capture.stop()


# Utility functions for common patterns


def assert_no_errors(
    capture: LogCapture,
    message: str = "Unexpected errors in logs",
) -> None:
    """Assert that no errors were logged.

    Parameters
    ----------
    capture : LogCapture
        Log capture to check
    message : str
        Assertion message

    Raises
    ------
    AssertionError
        If errors were logged
    """
    errors = capture.filter_level(logging.ERROR)
    if errors:
        error_messages = "\n".join(f"  - {r.message}" for r in errors)
        msg = f"{message}:\n{error_messages}"
        raise AssertionError(msg)


def assert_log_contains(
    capture: LogCapture,
    expected: str,
    level: int | str | None = None,
    logger: str | None = None,
) -> None:
    """Assert that a log message was captured.

    Parameters
    ----------
    capture : LogCapture
        Log capture to check
    expected : str
        Expected message substring
    level : Union[int, str], optional
        Required log level
    logger : str, optional
        Required logger name

    Raises
    ------
    AssertionError
        If message not found
    """
    messages = capture.get_messages(level=level, logger=logger)

    if not any(expected in msg for msg in messages):
        msg = (
            f"Expected log message '{expected}' not found. "
            f"Captured messages: {messages}"
        )
        raise AssertionError(
            msg,
        )


def get_session_logs(capture: LogCapture, session_id: str) -> list[LogRecord]:
    """Get logs for a specific session ID.

    Parameters
    ----------
    capture : LogCapture
        Log capture to search
    session_id : str
        Session ID to filter by

    Returns
    -------
    List[LogRecord]
        Records with matching session ID
    """
    return [r for r in capture.records if r.session_id and session_id in r.session_id]
