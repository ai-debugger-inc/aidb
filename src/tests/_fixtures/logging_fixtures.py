"""Logging capture fixtures for AIDB test suite.

This module provides fixtures for capturing, filtering, and asserting on log output
during tests. Extracted from base.py for focused maintainability.
"""

__all__ = [
    "aidb_logs",
    "all_logs",
    "assert_logs",
    "captured_logs",
    "isolated_logger",
    "log_context",
    "mcp_logs",
    "multi_logger_capture",
    "suppress_logs",
]

import logging
import time
from collections.abc import Callable, Generator

import pytest

from tests._helpers.logging_capture import (
    LogCapture,
    MultiLoggerCapture,
    capture_logs,
)


@pytest.fixture
def captured_logs() -> Generator[LogCapture, None, None]:
    """Capture all logs during a test.

    Yields
    ------
    LogCapture
        Log capture instance for assertions
    """
    capture = LogCapture(
        logger_names=["aidb", "aidb_mcp", "tests"],
        level=logging.DEBUG,
        capture_root=False,  # Don't capture root to avoid noise
    )

    capture.start()
    yield capture
    capture.stop()


@pytest.fixture
def isolated_logger(
    test_logger: logging.Logger,
) -> Generator[logging.Logger, None, None]:
    """Provide an isolated logger with captured output.

    Parameters
    ----------
    test_logger : logging.Logger
        Base test logger

    Yields
    ------
    logging.Logger
        Isolated logger instance
    """
    # Create a child logger with unique name
    isolated = test_logger.getChild(f"isolated_{time.time()}")
    isolated.setLevel(logging.DEBUG)

    # Add memory handler to capture logs
    from logging.handlers import MemoryHandler

    memory_handler = MemoryHandler(capacity=1000)
    memory_handler.setLevel(logging.DEBUG)
    isolated.addHandler(memory_handler)

    # Store logs for access
    isolated.memory_handler = memory_handler  # type: ignore

    yield isolated

    # Cleanup
    isolated.removeHandler(memory_handler)
    memory_handler.close()


@pytest.fixture
def log_context() -> Generator[LogCapture, None, None]:
    """Capture logs with session context support.

    Yields
    ------
    LogCapture
        Log capture with session awareness
    """
    # Import session context utilities
    from aidb_mcp.core.logging import _session_context

    capture = LogCapture(logger_names=["aidb", "aidb_mcp"], level=logging.DEBUG)

    capture.start()

    # Optionally set a test session ID
    test_session_id = f"test_{time.time()}"
    token = _session_context.set(test_session_id)

    try:
        yield capture
    finally:
        _session_context.reset(token)
        capture.stop()


@pytest.fixture
def multi_logger_capture() -> Callable:
    """Capture multiple named loggers for testing.

    Returns
    -------
    callable
        Function to create multi-logger capture
    """

    def _create_multi_capture(
        logger_mapping: dict[str, list[str]],
    ) -> MultiLoggerCapture:
        """Create a multi-logger capture.

        Parameters
        ----------
        logger_mapping : Dict[str, List[str]]
            Mapping of capture names to logger names

        Returns
        -------
        MultiLoggerCapture
            Multi-logger capture instance
        """
        return MultiLoggerCapture(logger_mapping, level=logging.DEBUG)

    return _create_multi_capture


@pytest.fixture
def aidb_logs() -> Generator[LogCapture, None, None]:
    """Capture only AIDB core logs.

    Yields
    ------
    LogCapture
        Capture for aidb.* loggers
    """
    with capture_logs("aidb", level=logging.DEBUG) as capture:
        yield capture


@pytest.fixture
def mcp_logs() -> Generator[LogCapture, None, None]:
    """Capture only MCP server logs.

    Yields
    ------
    LogCapture
        Capture for aidb_mcp.* loggers
    """
    with capture_logs("aidb_mcp", level=logging.DEBUG) as capture:
        yield capture


@pytest.fixture
def all_logs() -> Generator[LogCapture, None, None]:
    """Capture all logs including root logger.

    Yields
    ------
    LogCapture
        Capture for all loggers
    """
    capture = LogCapture(
        logger_names=["aidb", "aidb_mcp", "tests", "asyncio"],
        level=logging.DEBUG,
        capture_root=True,
    )

    capture.start()
    yield capture
    capture.stop()


@pytest.fixture
def suppress_logs():
    """Suppress all logs during a test.

    Useful for tests that generate expected warnings/errors.
    """
    # Store original levels
    loggers_to_suppress = [
        "aidb",
        "aidb_mcp",
        "tests",
    ]

    original_levels = {}
    for name in loggers_to_suppress:
        logger = logging.getLogger(name)
        original_levels[logger] = logger.level
        logger.setLevel(logging.CRITICAL + 1)  # Above all levels

    # Also suppress root if it's configured
    root = logging.getLogger()
    original_levels[root] = root.level
    root.setLevel(logging.CRITICAL + 1)

    yield

    # Restore levels
    for logger, level in original_levels.items():
        logger.setLevel(level)


@pytest.fixture
def assert_logs():
    """Provide log assertion helpers.

    Returns
    -------
    object
        Object with log assertion methods
    """
    from tests._helpers.logging_capture import (
        assert_log_contains,
        assert_no_errors,
        get_session_logs,
    )

    class LogAssertions:
        """Log assertion helpers."""

        @staticmethod
        def contains(capture: LogCapture, message: str, **kwargs):
            """Assert log contains message."""
            assert_log_contains(capture, message, **kwargs)

        @staticmethod
        def no_errors(capture: LogCapture, message: str | None = None):
            """Assert no errors logged."""
            assert_no_errors(capture, message or "Unexpected errors in logs")

        @staticmethod
        def has_session_logs(capture: LogCapture, session_id: str):
            """Assert session has logs."""
            logs = get_session_logs(capture, session_id)
            assert logs, f"No logs found for session {session_id}"
            return logs

        @staticmethod
        def level_count(capture: LogCapture, level: str) -> int:
            """Count logs at level."""
            return capture.count_level(level)

    return LogAssertions()
