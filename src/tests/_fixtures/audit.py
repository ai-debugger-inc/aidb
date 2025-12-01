"""Fixtures for audit subsystem testing."""

__all__ = [
    # Mock fixtures
    "mock_audit_logger",
    "mock_aidb_context",
    "mock_async_queue",
    # Directory fixtures
    "temp_audit_dir",
    # Event fixtures
    "sample_audit_event",
    "error_audit_event",
    "sensitive_audit_event",
    # Context fixtures
    "audit_context",
    # Data fixtures
    "audit_log_content",
    # Running logger
    "running_audit_logger",
]

import asyncio
import tempfile
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.logger import AuditLogger
from aidb.audit.middleware import AuditContext
from aidb.common.context import AidbContext
from tests._helpers.constants import TestData


@pytest.fixture
def mock_audit_logger() -> Generator[Mock, None, None]:
    """Provide a mock AuditLogger instance.

    Yields
    ------
    Mock
        Mock AuditLogger with common methods stubbed
    """
    logger = Mock(spec=AuditLogger)
    logger.log = Mock()  # log is synchronous
    logger.shutdown = AsyncMock()
    logger.is_enabled = Mock(return_value=True)
    logger._enabled = True
    logger._queue = asyncio.Queue()

    # Mock singleton behavior
    with patch("aidb.audit.logger.AuditLogger.__new__", return_value=logger):
        yield logger


@pytest.fixture
def temp_audit_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for audit logs.

    Yields
    ------
    Path
        Path to temporary audit directory
    """
    with tempfile.TemporaryDirectory(prefix="aidb_audit_test_") as tmpdir:
        audit_dir = Path(tmpdir) / "audit"
        audit_dir.mkdir()
        yield audit_dir


@pytest.fixture
def sample_audit_event() -> AuditEvent:
    """Provide a sample audit event.

    Returns
    -------
    AuditEvent
        Pre-configured audit event for testing
    """
    return AuditEvent(
        level=AuditLevel.INFO,
        component="test.component",
        operation="test_operation",
        session_id="test_session_123",
        parameters={"param1": "value1", "param2": 42},
        result={"success": True, "duration_ms": 100},
        metadata={"language": "python", "adapter": "debugpy"},
    )


@pytest.fixture
def error_audit_event() -> AuditEvent:
    """Provide an error audit event.

    Returns
    -------
    AuditEvent
        Pre-configured error audit event for testing
    """
    return AuditEvent(
        level=AuditLevel.ERROR,
        component="test.error",
        operation="failed_operation",
        session_id="error_session_456",
        parameters={"input": "bad_data"},
        result={"success": False},
        error="Something went wrong",
        metadata={"traceback": "stack trace here"},
    )


@pytest.fixture
def sensitive_audit_event() -> AuditEvent:
    """Provide an audit event with sensitive data.

    Returns
    -------
    AuditEvent
        Audit event containing sensitive information for masking tests
    """
    return AuditEvent(
        level=AuditLevel.WARNING,
        component="auth.system",
        operation="login",
        parameters={
            "username": "testuser",
            "password": "secret123",
            "api_key": "sk-1234567890",
            "token": "bearer_token_xyz",
        },
        metadata={
            "secret": "sensitive_value",
        },
    )


@pytest.fixture
def mock_aidb_context() -> Mock:
    """Provide a mock AidbContext.

    Returns
    -------
    Mock
        Mock AidbContext for testing
    """
    ctx = Mock(spec=AidbContext)
    temp_base = Path(tempfile.gettempdir()) / "aidb"
    ctx.storage_dir = temp_base
    ctx.audit_dir = temp_base / "audit"
    ctx.debug = Mock()
    ctx.info = Mock()
    ctx.warning = Mock()
    ctx.error = Mock()
    return ctx


@pytest.fixture
async def audit_context(
    mock_audit_logger: Mock,
) -> AsyncGenerator[AuditContext, None]:
    """Provide an AuditContext for testing.

    Parameters
    ----------
    mock_audit_logger : Mock
        Mock audit logger

    Yields
    ------
    AuditContext
        Configured audit context
    """
    context = AuditContext(
        component="test.context",
        operation="test_op",
        session_id="ctx_session_789",
    )

    # Patch the logger singleton
    with patch("aidb.audit.middleware.AuditLogger", return_value=mock_audit_logger):
        yield context


@pytest.fixture
def mock_async_queue() -> AsyncMock:
    """Provide a mock async queue.

    Returns
    -------
    AsyncMock
        Mock asyncio.Queue for testing
    """
    queue = AsyncMock(spec=asyncio.Queue)
    queue.put = AsyncMock()
    queue.get = AsyncMock()
    queue.qsize = Mock(return_value=0)
    queue.empty = Mock(return_value=True)
    return queue


@pytest.fixture
def audit_log_content() -> list[str]:
    """Provide sample audit log lines.

    Returns
    -------
    List[str]
        Sample JSON log lines for testing
    """
    return [
        '{"timestamp":"2024-01-01T00:00:00Z","level":"INFO","component":"api","operation":"start"}',
        '{"timestamp":"2024-01-01T00:00:01Z","level":"DEBUG","component":"api","operation":"init"}',
        '{"timestamp":"2024-01-01T00:00:02Z","level":"ERROR","component":"api","operation":"fail","error":"test error"}',
    ]


@pytest.fixture
async def running_audit_logger(
    temp_audit_dir: Path,
) -> AsyncGenerator[AuditLogger, None]:
    """Provide a running AuditLogger instance.

    Parameters
    ----------
    temp_audit_dir : Path
        Temporary audit directory

    Yields
    ------
    AuditLogger
        Running logger instance
    """
    # Clear singleton instance
    AuditLogger._instance = None

    # Create logger with proper environment (audit enabled via env var)
    with patch.dict(
        "os.environ",
        {
            "AIDB_AUDIT_ENABLED": "true",
            "AIDB_AUDIT_LOG_PATH": str(temp_audit_dir / "audit.log"),
        },
    ):
        logger = AuditLogger()

        yield logger

        # Cleanup
        await logger.shutdown()

        # Clear singleton again
        AuditLogger._instance = None
