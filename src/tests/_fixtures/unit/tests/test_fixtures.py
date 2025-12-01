"""Tests for unit test fixture infrastructure.

These tests validate that the shared fixtures, builders, and mocks work correctly before
using them in actual unit tests.
"""

from unittest.mock import MagicMock

import pytest

from tests._fixtures.unit.assertions import UnitAssertions
from tests._fixtures.unit.builders.dap_builders import (
    DAPEventBuilder,
    DAPResponseBuilder,
)
from tests._fixtures.unit.context import (
    assert_error_logged,
    assert_warning_logged,
)
from tests._fixtures.unit.dap.events import MockEventProcessor
from tests._fixtures.unit.dap.transport import MockTransportRecorder


class TestContextFixtures:
    """Tests for context mock fixtures."""

    def test_mock_ctx_has_logging_methods(self, mock_ctx: MagicMock) -> None:
        """Test that mock_ctx has all logging methods."""
        mock_ctx.debug("test debug")
        mock_ctx.info("test info")
        mock_ctx.warning("test warning")
        mock_ctx.error("test error")
        mock_ctx.critical("test critical")

        mock_ctx.debug.assert_called()
        mock_ctx.info.assert_called()
        mock_ctx.warning.assert_called()
        mock_ctx.error.assert_called()
        mock_ctx.critical.assert_called()

    def test_mock_ctx_storage_path(self, mock_ctx: MagicMock) -> None:
        """Test that mock_ctx provides storage paths."""
        path = mock_ctx.get_storage_path("session", "state.json")
        assert "session" in path
        assert "state.json" in path

    def test_null_ctx_does_nothing(self, null_ctx: MagicMock) -> None:
        """Test that null_ctx can be used without errors."""
        null_ctx.debug("ignored")
        null_ctx.any_method()  # Should not raise

    def test_tmp_storage_creates_directory(self, tmp_storage) -> None:
        """Test that tmp_storage creates a real directory."""
        assert tmp_storage.exists()
        assert tmp_storage.is_dir()


class TestAssertErrorLogged:
    """Tests for assert_error_logged helper."""

    def test_passes_when_error_logged(self, mock_ctx: MagicMock) -> None:
        """Test assertion passes when error was logged."""
        mock_ctx.error("Something went wrong")
        assert_error_logged(mock_ctx, "wrong")

    def test_fails_when_no_error_logged(self, mock_ctx: MagicMock) -> None:
        """Test assertion fails when no error was logged."""
        with pytest.raises(AssertionError):
            assert_error_logged(mock_ctx, "not found")

    def test_fails_when_different_error_logged(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """Test assertion fails when different error logged."""
        mock_ctx.error("Different error")
        with pytest.raises(AssertionError):
            assert_error_logged(mock_ctx, "expected message")


class TestAssertWarningLogged:
    """Tests for assert_warning_logged helper."""

    def test_passes_when_warning_logged(self, mock_ctx: MagicMock) -> None:
        """Test assertion passes when warning was logged."""
        mock_ctx.warning("Be careful")
        assert_warning_logged(mock_ctx, "careful")


class TestDAPResponseBuilder:
    """Tests for DAPResponseBuilder."""

    def test_build_basic_response(self) -> None:
        """Test building a basic response."""
        builder = DAPResponseBuilder()
        response = builder.with_command("test").with_success(True).build()

        assert response.command == "test"
        assert response.success is True

    def test_build_error_response(self) -> None:
        """Test building an error response."""
        builder = DAPResponseBuilder()
        response = builder.with_command("launch").with_error("Failed").build()

        assert response.success is False
        assert response.message == "Failed"

    def test_build_initialize_response(self) -> None:
        """Test building an InitializeResponse with capabilities."""
        builder = DAPResponseBuilder()
        response = builder.build_initialize(
            supports_configuration_done=True,
            supports_conditional_breakpoints=True,
        )

        assert response.command == "initialize"
        assert response.success is True
        assert response.body is not None
        assert response.body.supportsConfigurationDoneRequest is True

    def test_build_set_breakpoints_response(self) -> None:
        """Test building a SetBreakpointsResponse."""
        builder = DAPResponseBuilder()
        response = builder.build_set_breakpoints()

        assert response.command == "setBreakpoints"
        assert response.body is not None
        assert len(response.body.breakpoints) == 1
        assert response.body.breakpoints[0].verified is True


class TestDAPEventBuilder:
    """Tests for DAPEventBuilder."""

    def test_stopped_event_default(self) -> None:
        """Test creating stopped event with defaults."""
        event = DAPEventBuilder.stopped_event()

        assert event.event == "stopped"
        assert event.body is not None
        assert event.body.reason == "breakpoint"
        assert event.body.threadId == 1

    def test_stopped_event_custom(self) -> None:
        """Test creating stopped event with custom values."""
        event = DAPEventBuilder.stopped_event(
            reason="step",
            thread_id=5,
            all_threads_stopped=False,
        )

        assert event.body.reason == "step"
        assert event.body.threadId == 5
        assert event.body.allThreadsStopped is False

    def test_breakpoint_event(self) -> None:
        """Test creating breakpoint event."""
        event = DAPEventBuilder.breakpoint_event(
            breakpoint_id=42,
            verified=True,
            line=100,
        )

        assert event.event == "breakpoint"
        assert event.body is not None
        assert event.body.breakpoint.id == 42
        assert event.body.breakpoint.line == 100

    def test_initialized_event(self) -> None:
        """Test creating initialized event."""
        event = DAPEventBuilder.initialized_event()
        assert event.event == "initialized"

    def test_terminated_event(self) -> None:
        """Test creating terminated event."""
        event = DAPEventBuilder.terminated_event()
        assert event.event == "terminated"

    def test_seq_counter_increments(self) -> None:
        """Test that sequence numbers increment."""
        DAPEventBuilder.reset_seq()
        event1 = DAPEventBuilder.stopped_event()
        event2 = DAPEventBuilder.stopped_event()
        assert event2.seq > event1.seq


class TestMockTransportRecorder:
    """Tests for MockTransportRecorder."""

    @pytest.mark.asyncio
    async def test_records_sent_messages(self) -> None:
        """Test that recorder captures sent messages."""
        recorder = MockTransportRecorder()
        await recorder.send_message({"command": "initialize"})
        await recorder.send_message({"command": "launch"})

        assert len(recorder.sent_messages) == 2
        assert recorder.sent_messages[0]["command"] == "initialize"

    @pytest.mark.asyncio
    async def test_get_messages_by_command(self) -> None:
        """Test filtering messages by command."""
        recorder = MockTransportRecorder()
        await recorder.send_message({"command": "setBreakpoints"})
        await recorder.send_message({"command": "launch"})
        await recorder.send_message({"command": "setBreakpoints"})

        bp_messages = recorder.get_messages_by_command("setBreakpoints")
        assert len(bp_messages) == 2

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        """Test async connect and disconnect."""
        recorder = MockTransportRecorder()
        await recorder.connect()
        assert recorder.is_connected() is True

        await recorder.disconnect()
        assert recorder.is_connected() is False


class TestMockEventProcessor:
    """Tests for MockEventProcessor."""

    def test_subscribe_and_emit(self) -> None:
        """Test subscribing to events and receiving them."""
        processor = MockEventProcessor()
        received = []

        def handler(event):
            received.append(event)

        processor.subscribe("stopped", handler)
        processor.emit_stopped(reason="breakpoint")

        assert len(received) == 1
        assert received[0].event == "stopped"

    def test_get_last_event(self) -> None:
        """Test retrieving last event of type."""
        processor = MockEventProcessor()
        processor.emit_stopped(reason="step")
        processor.emit_stopped(reason="breakpoint")

        last = processor.get_last_event("stopped")
        assert last is not None
        assert last.body.reason == "breakpoint"

    def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        processor = MockEventProcessor()
        received = []

        def handler(event):
            received.append(event)

        processor.subscribe("stopped", handler)
        processor.unsubscribe("stopped", handler)
        processor.emit_stopped()

        assert len(received) == 0


class TestUnitAssertions:
    """Tests for UnitAssertions class."""

    def test_assert_no_errors_logged_passes(self, mock_ctx: MagicMock) -> None:
        """Test passes when no errors logged."""
        mock_ctx.debug("just debug")
        UnitAssertions.assert_no_errors_logged(mock_ctx)

    def test_assert_no_errors_logged_fails(self, mock_ctx: MagicMock) -> None:
        """Test fails when errors logged."""
        mock_ctx.error("oops")
        with pytest.raises(AssertionError):
            UnitAssertions.assert_no_errors_logged(mock_ctx)

    def test_assert_dap_response_success(self) -> None:
        """Test success assertion with response object."""
        response = DAPResponseBuilder().with_success(True).build()
        UnitAssertions.assert_dap_response_success(response)

    def test_assert_dap_response_success_fails(self) -> None:
        """Test success assertion fails on error response."""
        response = DAPResponseBuilder().with_error("failed").build()
        with pytest.raises(AssertionError):
            UnitAssertions.assert_dap_response_success(response)

    def test_assert_dap_response_failure(self) -> None:
        """Test failure assertion with error response."""
        response = DAPResponseBuilder().with_error("expected error").build()
        UnitAssertions.assert_dap_response_failure(response, "expected")

    def test_assert_error_logged(self, mock_ctx: MagicMock) -> None:
        """Test error logged assertion."""
        mock_ctx.error("Database connection failed")
        UnitAssertions.assert_error_logged(mock_ctx, "connection")

    def test_assert_debug_logged(self, mock_ctx: MagicMock) -> None:
        """Test debug logged assertion."""
        mock_ctx.debug("Processing request")
        UnitAssertions.assert_debug_logged(mock_ctx, "Processing")
