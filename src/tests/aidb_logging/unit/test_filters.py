"""Tests for aidb_logging.filters module."""

import logging

import pytest

from aidb_logging.context import set_request_id, set_session_id
from aidb_logging.filters import (
    CallerFilter,
    LevelFilter,
    ModuleFilter,
    SessionContextFilter,
)


class TestCallerFilter:
    """Tests for CallerFilter class."""

    def test_adds_real_caller_attributes(self):
        """Test that real caller attributes are added."""
        filter_obj = CallerFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert hasattr(record, "real_module")
        assert hasattr(record, "real_lineno")
        assert hasattr(record, "real_funcName")

    def test_skips_logging_infrastructure_frames(self):
        """Test that logging infrastructure frames are skipped."""
        filter_obj = CallerFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.real_module != "logging"  # type: ignore[attr-defined]
        assert record.real_module != "filters"  # type: ignore[attr-defined]

    def test_uses_custom_skip_modules(self):
        """Test that custom skip modules are honored."""
        filter_obj = CallerFilter(skip_modules={"custom_module"})
        assert "custom_module" in filter_obj.skip_modules
        assert "logging" in filter_obj.skip_modules

    def test_uses_custom_skip_functions(self):
        """Test that custom skip functions are honored."""
        filter_obj = CallerFilter(skip_functions={"custom_function"})
        assert "custom_function" in filter_obj.skip_functions
        assert "_log" in filter_obj.skip_functions

    def test_cache_improves_performance(self):
        """Test that cache improves performance."""
        filter_obj = CallerFilter(enable_cache=True, cache_size=10)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert filter_obj._cache is not None
        assert len(filter_obj._cache) > 0

    def test_cache_evicts_old_entries(self):
        """Test that cache evicts old entries when full."""
        filter_obj = CallerFilter(enable_cache=True, cache_size=2)

        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname=f"/path/to/test{i}.py",
                lineno=i,
                msg="test",
                args=(),
                exc_info=None,
            )
            filter_obj.filter(record)

        assert len(filter_obj._cache) <= 2

    def test_can_disable_cache(self):
        """Test that cache can be disabled."""
        filter_obj = CallerFilter(enable_cache=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert filter_obj._cache is None


class TestSessionContextFilter:
    """Tests for SessionContextFilter class."""

    def test_adds_session_id_when_set(self):
        """Test that session ID is added when set."""
        set_session_id("test-session-123")
        filter_obj = SessionContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert hasattr(record, "session_id")
        assert "SID:" in record.session_id

    def test_adds_no_session_when_not_set(self):
        """Test that NO_SESSION is added when not set."""
        set_session_id(None)
        filter_obj = SessionContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.session_id == "NO_SESSION"  # type: ignore[attr-defined]

    def test_adds_request_id_when_set(self):
        """Test that request ID is added when set."""
        set_request_id("test-request-456")
        filter_obj = SessionContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.request_id == "test-request-456"  # type: ignore[attr-defined]

    def test_adds_no_request_when_not_set(self):
        """Test that NO_REQUEST is added when not set."""
        set_request_id(None)
        filter_obj = SessionContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert record.request_id == "NO_REQUEST"  # type: ignore[attr-defined]

    def test_truncates_session_id(self):
        """Test that session ID is truncated."""
        long_session_id = "a" * 100
        set_session_id(long_session_id)
        filter_obj = SessionContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )

        filter_obj.filter(record)

        assert len(record.session_id) < len(long_session_id)  # type: ignore[attr-defined]
        assert "SID:" in record.session_id  # type: ignore[attr-defined]


class TestLevelFilter:
    """Tests for LevelFilter class."""

    def test_allows_records_within_range(self):
        """Test that records within range are allowed."""
        filter_obj = LevelFilter(min_level=logging.INFO, max_level=logging.ERROR)

        info_record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(info_record) is True

        warning_record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(warning_record) is True

    def test_blocks_records_below_minimum(self):
        """Test that records below minimum are blocked."""
        filter_obj = LevelFilter(min_level=logging.WARNING)

        debug_record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(debug_record) is False

    def test_blocks_records_above_maximum(self):
        """Test that records above maximum are blocked."""
        filter_obj = LevelFilter(max_level=logging.WARNING)

        error_record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(error_record) is False

    def test_uses_default_range_when_not_specified(self):
        """Test that default range is used when not specified."""
        filter_obj = LevelFilter()

        debug_record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(debug_record) is True

        critical_record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(critical_record) is True


class TestModuleFilter:
    """Tests for ModuleFilter class."""

    def test_includes_specified_modules(self):
        """Test that specified modules are included."""
        filter_obj = ModuleFilter(include_modules=["aidb", "test"])

        aidb_record = logging.LogRecord(
            name="aidb.core",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(aidb_record) is True

    def test_excludes_other_modules_when_include_list_specified(self):
        """Test that other modules are excluded when include list specified."""
        filter_obj = ModuleFilter(include_modules=["aidb"])

        other_record = logging.LogRecord(
            name="other.module",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(other_record) is False

    def test_excludes_specified_modules(self):
        """Test that specified modules are excluded."""
        filter_obj = ModuleFilter(exclude_modules=["aidb.logging", "test"])

        excluded_record = logging.LogRecord(
            name="aidb.logging.core",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(excluded_record) is False

    def test_includes_non_excluded_modules(self):
        """Test that non-excluded modules are included."""
        filter_obj = ModuleFilter(exclude_modules=["aidb.logging"])

        other_record = logging.LogRecord(
            name="aidb.core",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="test",
            args=(),
            exc_info=None,
        )
        assert filter_obj.filter(other_record) is True
