"""Tests for aidb_logging.formatters module."""

import json
import logging
import sys
from unittest.mock import patch

import pytest

from aidb_logging.context import set_log_context, set_request_id, set_session_id
from aidb_logging.formatters import (
    ColoredFormatter,
    JSONFormatter,
    SafeFormatter,
    SessionFormatter,
)


class TestSafeFormatter:
    """Tests for SafeFormatter class."""

    def test_adds_real_attributes_when_missing(self):
        """Test that real_* attributes are added when missing."""
        formatter = SafeFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        formatter.format(record)

        assert hasattr(record, "real_module")
        assert hasattr(record, "real_funcName")
        assert hasattr(record, "real_lineno")

    def test_preserves_existing_real_attributes(self):
        """Test that existing real_* attributes are preserved."""
        formatter = SafeFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        record.real_module = "custom_module"
        record.real_funcName = "custom_function"
        record.real_lineno = 100

        formatter.format(record)

        assert record.real_module == "custom_module"  # type: ignore[attr-defined]
        assert record.real_funcName == "custom_function"  # type: ignore[attr-defined]
        assert record.real_lineno == 100  # type: ignore[attr-defined]

    def test_normalizes_warning_to_warn(self):
        """Test that WARNING is normalized to WARN."""
        formatter = SafeFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        formatter.format(record)

        assert record.levelname == "WARN"


class TestSessionFormatter:
    """Tests for SessionFormatter class."""

    def test_includes_session_id_when_enabled(self):
        """Test that session ID is included when enabled."""
        set_session_id("test-session")
        formatter = SessionFormatter(include_session=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.session_id = "SID:test-ses"
        record.request_id = "test-request"

        result = formatter.format(record)

        assert "SID:test-ses" in result

    def test_excludes_session_id_when_disabled(self):
        """Test that session ID is excluded when disabled."""
        formatter = SessionFormatter(include_session=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "[SID:" not in result

    def test_adds_colors_when_enabled(self):
        """Test that colors are added when enabled."""
        with patch.object(SessionFormatter, "_should_use_colors", return_value=True):
            formatter = SessionFormatter(include_colors=True, include_session=False)
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=42,
                msg="test message",
                args=(),
                exc_info=None,
            )

            result = formatter.format(record)

            assert "\033[" in result

    def test_excludes_colors_when_disabled(self):
        """Test that colors are excluded when disabled."""
        formatter = SessionFormatter(include_colors=False, include_session=False)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "\033[" not in result

    def test_adds_fallback_session_context(self):
        """Test that fallback values are added when session context missing."""
        formatter = SessionFormatter(include_session=True, include_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        formatter.format(record)

        assert record.session_id == "NO_SESSION"  # type: ignore[attr-defined]
        assert record.request_id == "NO_REQUEST"  # type: ignore[attr-defined]


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_formats_as_valid_json(self):
        """Test that output is valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert isinstance(data, dict)
        assert data["message"] == "test message"

    def test_includes_base_log_data(self):
        """Test that base log data is included."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "test message"

    def test_includes_timestamp_when_enabled(self):
        """Test that timestamp is included when enabled."""
        formatter = JSONFormatter(include_timestamp=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "timestamp" in data

    def test_includes_service_metadata(self):
        """Test that service metadata is included."""
        formatter = JSONFormatter(
            service_name="test-service",
            environment="test-env",
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["service"] == "test-service"
        assert data["environment"] == "test-env"

    def test_includes_context_when_enabled(self):
        """Test that context is included when enabled."""
        set_session_id("test-session")
        set_request_id("test-request")
        set_log_context(custom_key="custom_value")

        formatter = JSONFormatter(include_context=True)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.session_id = "SID:test-ses"
        record.request_id = "test-request"

        result = formatter.format(record)
        data = json.loads(result)

        assert "session_id" in data
        assert "request_id" in data

    def test_includes_exception_info(self):
        """Test that exception info is included."""
        formatter = JSONFormatter()
        msg = "test error"

        try:
            raise ValueError(msg)
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=42,
                msg="test message",
                args=(),
                exc_info=exc_info,
            )

        result = formatter.format(record)
        data = json.loads(result)

        assert "exception" in data
        assert "ValueError" in data["exception"]

    def test_includes_extra_fields(self):
        """Test that extra fields are included."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.another_field = 123

        result = formatter.format(record)
        data = json.loads(result)

        assert "extra" in data
        assert data["extra"]["custom_field"] == "custom_value"
        assert data["extra"]["another_field"] == 123


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_adds_colors_when_enabled(self):
        """Test that colors are added when enabled."""
        with patch.object(ColoredFormatter, "_should_use_colors", return_value=True):
            formatter = ColoredFormatter(use_colors=True)
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=42,
                msg="test message",
                args=(),
                exc_info=None,
            )

            result = formatter.format(record)

            assert "\033[" in result

    def test_excludes_colors_when_disabled(self):
        """Test that colors are excluded when disabled."""
        formatter = ColoredFormatter(use_colors=False)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        assert "\033[" not in result

    def test_different_colors_for_different_levels(self):
        """Test that different colors are used for different levels."""
        with patch.object(ColoredFormatter, "_should_use_colors", return_value=True):
            formatter = ColoredFormatter(use_colors=True)

            error_record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=42,
                msg="error",
                args=(),
                exc_info=None,
            )
            info_record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=42,
                msg="info",
                args=(),
                exc_info=None,
            )

            error_result = formatter.format(error_record)
            info_result = formatter.format(info_record)

            assert "\033[31m" in error_result
            assert "\033[32m" in info_result

    def test_restores_original_levelname(self):
        """Test that original levelname is restored."""
        with patch.object(ColoredFormatter, "_should_use_colors", return_value=True):
            formatter = ColoredFormatter(use_colors=True)
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=42,
                msg="test message",
                args=(),
                exc_info=None,
            )

            original_levelname = record.levelname
            formatter.format(record)

            assert record.levelname == original_levelname
