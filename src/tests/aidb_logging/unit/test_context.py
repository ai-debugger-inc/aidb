"""Tests for aidb_logging.context module."""

import time

import pytest

from aidb_logging.context import (
    LogContext,
    RequestContext,
    SessionContext,
    clear_all_context,
    clear_log_context,
    clear_request_id,
    clear_request_timing,
    clear_session_id,
    get_log_context,
    get_request_duration,
    get_request_id,
    get_session_id,
    set_log_context,
    set_request_id,
    set_request_id_with_ttl,
    set_session_id,
    set_session_id_with_ttl,
    start_request_timing,
)


@pytest.fixture(autouse=True)
def cleanup_context():
    """Clean up context after each test."""
    yield
    clear_all_context()


class TestSessionIdContext:
    """Tests for session ID context functions."""

    def test_sets_and_gets_session_id(self):
        """Test setting and getting session ID."""
        set_session_id("test-session-123")
        assert get_session_id() == "test-session-123"

    def test_returns_none_when_not_set(self):
        """Test that None is returned when not set."""
        clear_session_id()
        assert get_session_id() is None

    def test_clears_session_id(self):
        """Test clearing session ID."""
        set_session_id("test-session")
        clear_session_id()
        assert get_session_id() is None


class TestRequestIdContext:
    """Tests for request ID context functions."""

    def test_sets_and_gets_request_id(self):
        """Test setting and getting request ID."""
        set_request_id("test-request-456")
        assert get_request_id() == "test-request-456"

    def test_returns_none_when_not_set(self):
        """Test that None is returned when not set."""
        clear_request_id()
        assert get_request_id() is None

    def test_clears_request_id(self):
        """Test clearing request ID."""
        set_request_id("test-request")
        clear_request_id()
        assert get_request_id() is None


class TestRequestTiming:
    """Tests for request timing functions."""

    def test_starts_timing(self):
        """Test starting request timing."""
        start_request_timing()
        duration = get_request_duration()
        assert duration is not None
        assert duration >= 0

    def test_returns_none_when_not_started(self):
        """Test that None is returned when not started."""
        clear_request_timing()
        assert get_request_duration() is None

    def test_duration_increases_over_time(self):
        """Test that duration increases over time."""
        start_request_timing()
        duration1 = get_request_duration()
        time.sleep(0.01)
        duration2 = get_request_duration()

        assert duration2 is not None
        assert duration1 is not None
        assert duration2 > duration1

    def test_clears_timing(self):
        """Test clearing request timing."""
        start_request_timing()
        clear_request_timing()
        assert get_request_duration() is None


class TestLogContext:
    """Tests for log context functions."""

    def test_sets_and_gets_log_context(self):
        """Test setting and getting log context."""
        set_log_context(key1="value1", key2="value2")
        context = get_log_context()
        assert context["key1"] == "value1"
        assert context["key2"] == "value2"

    def test_merges_context_updates(self):
        """Test that context updates are merged."""
        set_log_context(key1="value1")
        set_log_context(key2="value2")
        context = get_log_context()
        assert context["key1"] == "value1"
        assert context["key2"] == "value2"

    def test_overwrites_existing_keys(self):
        """Test that existing keys are overwritten."""
        set_log_context(key="old_value")
        set_log_context(key="new_value")
        context = get_log_context()
        assert context["key"] == "new_value"

    def test_returns_empty_dict_when_not_set(self):
        """Test that empty dict is returned when not set."""
        clear_log_context()
        assert get_log_context() == {}

    def test_clears_log_context(self):
        """Test clearing log context."""
        set_log_context(key="value")
        clear_log_context()
        assert get_log_context() == {}


class TestClearAllContext:
    """Tests for clear_all_context function."""

    def test_clears_all_context_variables(self):
        """Test that all context variables are cleared."""
        set_session_id("session")
        set_request_id("request")
        start_request_timing()
        set_log_context(key="value")

        clear_all_context()

        assert get_session_id() is None
        assert get_request_id() is None
        assert get_request_duration() is None
        assert get_log_context() == {}


class TestSessionContextManager:
    """Tests for SessionContext context manager."""

    def test_sets_session_id_in_context(self):
        """Test that session ID is set in context."""
        with SessionContext("test-session"):
            assert get_session_id() == "test-session"

    def test_restores_previous_session_id(self):
        """Test that previous session ID is restored."""
        set_session_id("original")

        with SessionContext("temporary"):
            assert get_session_id() == "temporary"

        assert get_session_id() == "original"

    def test_restores_none_when_no_previous(self):
        """Test that None is restored when no previous session ID."""
        clear_session_id()

        with SessionContext("temporary"):
            assert get_session_id() == "temporary"

        assert get_session_id() is None


class TestRequestContextManager:
    """Tests for RequestContext context manager."""

    def test_sets_request_id_in_context(self):
        """Test that request ID is set in context."""
        with RequestContext("test-request"):
            assert get_request_id() == "test-request"

    def test_starts_timing_by_default(self):
        """Test that timing is started by default."""
        with RequestContext("test-request"):
            duration = get_request_duration()
            assert duration is not None
            assert duration >= 0

    def test_skips_timing_when_requested(self):
        """Test that timing can be skipped."""
        with RequestContext("test-request", start_timing=False):
            assert get_request_duration() is None

    def test_restores_previous_request_id(self):
        """Test that previous request ID is restored."""
        set_request_id("original")

        with RequestContext("temporary"):
            assert get_request_id() == "temporary"

        assert get_request_id() == "original"


class TestLogContextManager:
    """Tests for LogContext context manager."""

    def test_adds_context_in_scope(self):
        """Test that context is added in scope."""
        with LogContext(key1="value1", key2="value2"):
            context = get_log_context()
            assert context["key1"] == "value1"
            assert context["key2"] == "value2"

    def test_merges_with_existing_context(self):
        """Test that new context is merged with existing."""
        set_log_context(existing="value")

        with LogContext(new="value2"):
            context = get_log_context()
            assert context["existing"] == "value"
            assert context["new"] == "value2"

    def test_restores_previous_context(self):
        """Test that previous context is restored."""
        set_log_context(original="value")

        with LogContext(temporary="value2"):
            assert get_log_context()["temporary"] == "value2"

        context = get_log_context()
        assert "temporary" not in context
        assert context["original"] == "value"


class TestContextManagerSingleton:
    """Tests for ContextManager singleton."""

    def test_is_singleton(self):
        """Test that ContextManager is a singleton."""
        from aidb_logging.context import ContextManager

        manager1 = ContextManager()
        manager2 = ContextManager()
        assert manager1 is manager2

    def test_registers_context_with_ttl(self):
        """Test registering context with TTL."""
        set_session_id_with_ttl("test-session", ttl_seconds=1)
        assert get_session_id() == "test-session"

    def test_registers_request_with_ttl(self):
        """Test registering request with TTL."""
        set_request_id_with_ttl("test-request", ttl_seconds=1)
        assert get_request_id() == "test-request"
