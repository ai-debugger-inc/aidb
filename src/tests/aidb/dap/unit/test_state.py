"""Unit tests for SessionState.

Tests the SessionState dataclass including defaults, health checks, state reset, and
diagnostics.
"""

import time
from unittest.mock import patch

import pytest

from aidb.dap.client.state import SessionState


class TestSessionStateDefaults:
    """Tests for SessionState default values."""

    def test_connection_defaults(self):
        """SessionState initializes with correct connection defaults."""
        state = SessionState()

        assert state.connected is False
        assert state.initialized is False
        assert state.ready_for_configuration is False
        assert state.configuration_done is False
        assert state.session_established is False

    def test_handshake_defaults(self):
        """SessionState initializes with correct handshake defaults."""
        state = SessionState()

        assert state.handshake_started is False
        assert state.handshake_complete is False

    def test_execution_defaults(self):
        """SessionState initializes with correct execution defaults."""
        state = SessionState()

        assert state.stopped is False
        assert state.terminated is False
        assert state.stop_reason is None
        assert state.current_thread_id is None

    def test_location_defaults(self):
        """SessionState initializes with correct location defaults."""
        state = SessionState()

        assert state.current_file is None
        assert state.current_line is None
        assert state.current_column is None

    def test_health_defaults(self):
        """SessionState initializes with correct health defaults."""
        state = SessionState()

        assert state.consecutive_failures == 0
        assert state.max_consecutive_failures == 3
        assert state.last_response_time is not None

    def test_request_tracking_defaults(self):
        """SessionState initializes with correct request tracking defaults."""
        state = SessionState()

        assert state.last_command_sent is None
        assert state.total_requests_sent == 0
        assert state.total_responses_received == 0
        assert state.connection_start_time is None

    def test_adapter_defaults(self):
        """SessionState initializes with correct adapter defaults."""
        state = SessionState()

        assert state.adapter_id is None
        assert state.capabilities == {}

    def test_instrumentation_defaults(self):
        """SessionState initializes with correct instrumentation defaults."""
        state = SessionState()

        assert state.last_message_received_wall is None
        assert state.last_message_received_mono_ns is None
        assert state.receiver_task_id is None
        assert state.receiver_task_name is None

    def test_tracking_dict_defaults(self):
        """SessionState initializes tracking dicts as empty."""
        state = SessionState()

        assert state.event_last_processed_wall == {}
        assert state.event_last_processed_mono_ns == {}
        assert state.loaded_sources == {}
        assert state.loaded_modules == {}
        assert state.needs_refresh == {}


class TestIsHealthy:
    """Tests for is_healthy method."""

    def test_healthy_when_connected_and_responsive(self):
        """is_healthy returns True when connected and responsive."""
        state = SessionState()
        state.connected = True
        state.last_response_time = time.time()

        assert state.is_healthy() is True

    def test_unhealthy_when_not_connected(self):
        """is_healthy returns False when not connected."""
        state = SessionState()
        state.connected = False

        assert state.is_healthy() is False

    def test_unhealthy_when_terminated(self):
        """is_healthy returns False when terminated."""
        state = SessionState()
        state.connected = True
        state.terminated = True

        assert state.is_healthy() is False

    def test_unhealthy_too_many_failures(self):
        """is_healthy returns False with too many consecutive failures."""
        state = SessionState()
        state.connected = True
        state.consecutive_failures = 3
        state.max_consecutive_failures = 3

        assert state.is_healthy() is False

    def test_unhealthy_no_response_timeout(self):
        """is_healthy returns False with no response for 30+ seconds."""
        state = SessionState()
        state.connected = True
        state.last_response_time = time.time() - 31

        assert state.is_healthy() is False

    def test_healthy_recent_response(self):
        """is_healthy returns True with recent response."""
        state = SessionState()
        state.connected = True
        state.last_response_time = time.time() - 10

        assert state.is_healthy() is True


class TestReset:
    """Tests for reset method."""

    def test_reset_connection_state(self):
        """Reset clears connection state."""
        state = SessionState()
        state.connected = True
        state.initialized = True
        state.ready_for_configuration = True
        state.configuration_done = True
        state.session_established = True

        state.reset()

        assert state.connected is False
        assert state.initialized is False
        assert state.ready_for_configuration is False
        assert state.configuration_done is False
        assert state.session_established is False

    def test_reset_handshake_state(self):
        """Reset clears handshake state."""
        state = SessionState()
        state.handshake_started = True
        state.handshake_complete = True

        state.reset()

        assert state.handshake_started is False
        assert state.handshake_complete is False

    def test_reset_execution_state(self):
        """Reset clears execution state."""
        state = SessionState()
        state.stopped = True
        state.terminated = True
        state.stop_reason = "breakpoint"
        state.current_thread_id = 1

        state.reset()

        assert state.stopped is False
        assert state.terminated is False
        assert state.stop_reason is None
        assert state.current_thread_id is None

    def test_reset_location_state(self):
        """Reset clears location state."""
        state = SessionState()
        state.current_file = "/path/to/file.py"
        state.current_line = 42
        state.current_column = 10

        state.reset()

        assert state.current_file is None
        assert state.current_line is None
        assert state.current_column is None

    def test_reset_failure_count(self):
        """Reset clears failure count."""
        state = SessionState()
        state.consecutive_failures = 5

        state.reset()

        assert state.consecutive_failures == 0

    def test_reset_updates_response_time(self):
        """Reset updates last_response_time."""
        state = SessionState()

        with patch("aidb.dap.client.state.time.time", return_value=1000.0):
            state.reset()

        assert state.last_response_time == 1000.0

    def test_reset_request_tracking(self):
        """Reset clears request tracking."""
        state = SessionState()
        state.last_command_sent = "continue"
        state.total_requests_sent = 100
        state.total_responses_received = 98
        state.connection_start_time = time.time()

        state.reset()

        assert state.last_command_sent is None
        assert state.total_requests_sent == 0
        assert state.total_responses_received == 0
        assert state.connection_start_time is None

    def test_reset_clears_dicts(self):
        """Reset clears tracking dictionaries."""
        state = SessionState()
        state.loaded_sources["test.py"] = {}
        state.loaded_modules["mod1"] = {}
        state.needs_refresh["threads"] = True

        state.reset()

        assert state.loaded_sources == {}
        assert state.loaded_modules == {}
        assert state.needs_refresh == {}


class TestGetDiagnostics:
    """Tests for get_diagnostics method."""

    def test_diagnostics_basic_fields(self):
        """get_diagnostics includes basic fields."""
        state = SessionState()
        state.connected = True
        state.initialized = True

        diag = state.get_diagnostics()

        assert "connected" in diag
        assert "healthy" in diag
        assert "initialized" in diag
        assert diag["connected"] is True
        assert diag["initialized"] is True

    def test_diagnostics_execution_state(self):
        """get_diagnostics includes execution state."""
        state = SessionState()
        state.stopped = True
        state.stop_reason = "breakpoint"
        state.current_thread_id = 5

        diag = state.get_diagnostics()

        assert diag["stopped"] is True
        assert diag["stop_reason"] == "breakpoint"
        assert diag["current_thread_id"] == 5

    def test_diagnostics_request_counts(self):
        """get_diagnostics includes request counts."""
        state = SessionState()
        state.total_requests_sent = 50
        state.total_responses_received = 48

        diag = state.get_diagnostics()

        assert diag["total_requests"] == 50
        assert diag["total_responses"] == 48

    def test_diagnostics_uptime_calculation(self):
        """get_diagnostics calculates uptime."""
        state = SessionState()
        state.connection_start_time = time.time() - 100

        diag = state.get_diagnostics()

        assert diag["connection_uptime"] is not None
        assert diag["connection_uptime"] >= 99

    def test_diagnostics_uptime_none_when_not_started(self):
        """get_diagnostics returns None uptime when not started."""
        state = SessionState()
        state.connection_start_time = None

        diag = state.get_diagnostics()

        assert diag["connection_uptime"] is None

    def test_diagnostics_time_since_response(self):
        """get_diagnostics calculates time since last response."""
        state = SessionState()
        state.last_response_time = time.time() - 5

        diag = state.get_diagnostics()

        assert diag["time_since_last_response"] is not None
        assert diag["time_since_last_response"] >= 4

    def test_diagnostics_event_metrics(self):
        """get_diagnostics includes event metrics."""
        state = SessionState()
        state.event_last_signaled_wall["stopped"] = time.time()
        state.event_last_signaled_mono_ns["stopped"] = 12345

        diag = state.get_diagnostics()

        assert "event_metrics" in diag
        assert "stopped" in diag["event_metrics"]
        assert diag["event_metrics"]["stopped"]["signal_mono_ns"] == 12345


class TestStateMutations:
    """Tests for state mutations."""

    def test_track_request_sent(self):
        """State tracks request sent."""
        state = SessionState()
        state.last_command_sent = "threads"
        state.total_requests_sent = 1

        assert state.last_command_sent == "threads"
        assert state.total_requests_sent == 1

    def test_track_response_received(self):
        """State tracks response received."""
        state = SessionState()
        state.total_responses_received = 5
        state.last_response_time = time.time()

        assert state.total_responses_received == 5
        assert state.last_response_time is not None

    def test_update_location(self):
        """State updates location."""
        state = SessionState()
        state.current_file = "/path/test.py"
        state.current_line = 10
        state.current_column = 5

        assert state.current_file == "/path/test.py"
        assert state.current_line == 10
        assert state.current_column == 5

    def test_store_capabilities(self):
        """State stores capabilities."""
        state = SessionState()
        state.capabilities = {
            "supportsConfigurationDoneRequest": True,
            "supportsEvaluateForHovers": True,
        }

        assert state.capabilities["supportsConfigurationDoneRequest"] is True
        assert state.capabilities["supportsEvaluateForHovers"] is True
