"""Unit tests for EventProcessor.

Tests the DAP event processing including event handlers, state updates, listener
management, and event synchronization.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from aidb.dap.client.events import EventProcessor
from aidb.dap.client.state import SessionState
from tests._fixtures.unit.builders import DAPEventBuilder


class TestEventProcessorInit:
    """Tests for EventProcessor initialization."""

    def test_init_with_state_and_ctx(self, mock_ctx):
        """EventProcessor initializes with state and context."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        assert processor._state == state
        assert processor._listeners == {}
        assert processor._last_events == {}

    def test_init_creates_internal_tracking(self, mock_ctx):
        """EventProcessor initializes internal tracking structures."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        assert processor._last_stopped_event is None
        assert processor._last_initialized_event is None
        assert processor._breakpoint_events == []
        assert processor._max_breakpoint_events == 100


class TestProcessEvent:
    """Tests for process_event method."""

    def test_process_event_stores_last_event(self, mock_ctx):
        """process_event stores the event by type."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert processor._last_events["stopped"] == event

    def test_process_event_signals_receipt(self, mock_ctx):
        """process_event signals event receipt via asyncio.Event."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert processor._event_received["stopped"].is_set()

    def test_process_event_unknown_type_logged(self, mock_ctx):
        """process_event logs unknown event types."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = MagicMock()
        event.event = "unknown_event_type"
        event.seq = 1

        processor.process_event(event)

        assert processor._last_events["unknown_event_type"] == event


class TestHandleInitialized:
    """Tests for initialized event handling."""

    def test_handle_initialized_updates_state(self, mock_ctx):
        """_handle_initialized sets state flags."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.initialized_event()
        processor.process_event(event)

        assert state.initialized is True
        assert state.ready_for_configuration is True
        assert processor._last_initialized_event == event


class TestHandleStopped:
    """Tests for stopped event handling."""

    def test_handle_stopped_updates_state(self, mock_ctx):
        """_handle_stopped sets stopped state."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert state.stopped is True
        assert state.stop_reason == "breakpoint"
        assert state.current_thread_id == 1
        assert processor._last_stopped_event == event

    def test_handle_stopped_tracks_breakpoint_events(self, mock_ctx):
        """_handle_stopped tracks breakpoint stop events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert len(processor._breakpoint_events) == 1
        assert processor._breakpoint_events[0] == event

    def test_handle_stopped_limits_breakpoint_events(self, mock_ctx):
        """_handle_stopped limits stored breakpoint events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        processor._max_breakpoint_events = 3

        for i in range(5):
            event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=i)
            processor.process_event(event)

        assert len(processor._breakpoint_events) == 3

    def test_handle_stopped_notifies_listeners(self, mock_ctx):
        """_handle_stopped notifies registered listeners."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        future: asyncio.Future = asyncio.Future()
        processor._stopped_listeners.append(future)

        event = DAPEventBuilder.stopped_event(reason="step", thread_id=1)
        processor.process_event(event)

        assert future.done()
        assert future.result() == event
        assert len(processor._stopped_listeners) == 0


class TestHandleContinued:
    """Tests for continued event handling."""

    def test_handle_continued_clears_stopped_state(self, mock_ctx):
        """_handle_continued clears stopped state."""
        state = SessionState()
        state.stopped = True
        state.stop_reason = "breakpoint"
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.continued_event(thread_id=1)
        processor.process_event(event)

        assert state.stopped is False
        assert state.stop_reason is None
        assert processor._last_stopped_event is None

    def test_handle_continued_ignores_spurious_after_stopped(self, mock_ctx):
        """_handle_continued ignores continued after stopped."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        stopped = DAPEventBuilder.stopped_event(
            reason="breakpoint", thread_id=1, seq=10
        )
        processor.process_event(stopped)

        continued = DAPEventBuilder.continued_event(thread_id=1, seq=15)
        processor.process_event(continued)

        assert state.stopped is True
        assert state.stop_reason == "breakpoint"


class TestHandleTerminated:
    """Tests for terminated event handling."""

    def test_handle_terminated_updates_state(self, mock_ctx):
        """_handle_terminated sets terminated state."""
        state = SessionState()
        state.session_established = True
        state.stopped = True
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.terminated_event()
        processor.process_event(event)

        assert state.terminated is True
        assert state.session_established is False
        assert state.stopped is False

    def test_handle_terminated_notifies_listeners(self, mock_ctx):
        """_handle_terminated notifies registered listeners."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        future: asyncio.Future = asyncio.Future()
        processor._terminated_listeners.append(future)

        event = DAPEventBuilder.terminated_event()
        processor.process_event(event)

        assert future.done()
        assert future.result() == event
        assert len(processor._terminated_listeners) == 0


class TestHandleThread:
    """Tests for thread event handling."""

    def test_handle_thread_event_logged(self, mock_ctx):
        """_handle_thread logs thread events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.thread_event(thread_id=1, reason="started")
        processor.process_event(event)

        assert processor._last_events["thread"] == event


class TestHandleOutput:
    """Tests for output event handling."""

    def test_handle_output_event_logged(self, mock_ctx):
        """_handle_output logs output events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.output_event(output="Hello, World!", category="stdout")
        processor.process_event(event)

        assert processor._last_events["output"] == event


class TestHandleProcess:
    """Tests for process event handling."""

    def test_handle_process_event_logged(self, mock_ctx):
        """_handle_process logs process events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.process_event(
            name="test_program",
            system_process_id=12345,
        )
        processor.process_event(event)

        assert processor._last_events["process"] == event


class TestHandleModule:
    """Tests for module event handling."""

    def test_handle_module_tracks_modules(self, mock_ctx):
        """_handle_module tracks loaded modules."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.module_event(
            module_id=1,
            module_name="test_module",
            reason="new",
        )
        processor.process_event(event)

        assert processor._last_events["module"] == event
        assert "1" in state.loaded_modules


class TestSubscribe:
    """Tests for subscription management."""

    def test_subscribe_adds_listener(self, mock_ctx):
        """Subscribe adds listener for event type."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("stopped", listener)

        assert listener in processor._listeners["stopped"]

    def test_subscribe_same_listener_once(self, mock_ctx):
        """Subscribe only adds same listener once."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("stopped", listener)
        processor.subscribe("stopped", listener)

        assert processor._listeners["stopped"].count(listener) == 1

    def test_subscribe_wildcard(self, mock_ctx):
        """Subscribe with '*' receives all events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("*", listener)

        assert listener in processor._listeners["*"]


class TestUnsubscribe:
    """Tests for unsubscription."""

    def test_unsubscribe_removes_listener(self, mock_ctx):
        """Unsubscribe removes listener."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("stopped", listener)
        processor.unsubscribe("stopped", listener)

        assert listener not in processor._listeners["stopped"]

    def test_unsubscribe_nonexistent_noop(self, mock_ctx):
        """Unsubscribe with nonexistent listener is safe."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.unsubscribe("stopped", listener)


class TestNotifyListeners:
    """Tests for listener notification."""

    def test_notify_specific_listeners(self, mock_ctx):
        """_notify_listeners calls specific event listeners."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("stopped", listener)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        listener.assert_called_once_with(event)

    def test_notify_wildcard_listeners(self, mock_ctx):
        """_notify_listeners calls wildcard listeners."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        listener = MagicMock()
        processor.subscribe("*", listener)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        listener.assert_called_once_with(event)

    def test_listener_error_caught(self, mock_ctx):
        """_notify_listeners catches listener errors."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        error_listener = MagicMock(side_effect=RuntimeError("test error"))
        processor.subscribe("stopped", error_listener)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)


class TestRegisterListeners:
    """Tests for one-time listener registration."""

    def test_register_stopped_listener(self, mock_ctx):
        """register_stopped_listener returns future."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        future = processor.register_stopped_listener()

        assert isinstance(future, asyncio.Future)
        assert future in processor._stopped_listeners

    def test_register_terminated_listener(self, mock_ctx):
        """register_terminated_listener returns future."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        future = processor.register_terminated_listener()

        assert isinstance(future, asyncio.Future)
        assert future in processor._terminated_listeners


class TestWaitForEvent:
    """Tests for wait_for_event method."""

    @pytest.mark.asyncio
    async def test_wait_for_event_immediate_if_set(self, mock_ctx):
        """wait_for_event returns immediately if event already set."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        processor._event_received["stopped"].set()

        result = await processor.wait_for_event("stopped", timeout=0.1)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_event_waits_for_signal(self, mock_ctx):
        """wait_for_event waits for event signal."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        async def signal_event():
            await asyncio.sleep(0.01)
            processor._event_received["stopped"].set()

        asyncio.create_task(signal_event())
        result = await processor.wait_for_event("stopped", timeout=1.0)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_event_timeout(self, mock_ctx):
        """wait_for_event returns False on timeout."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        result = await processor.wait_for_event("stopped", timeout=0.05)

        assert result is False


class TestHasEvent:
    """Tests for has_event method."""

    def test_has_event_true_when_set(self, mock_ctx):
        """has_event returns True when event received."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert processor.has_event("stopped") is True

    def test_has_event_false_when_not_set(self, mock_ctx):
        """has_event returns False when no event."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        assert processor.has_event("stopped") is False


class TestGetLastEvent:
    """Tests for get_last_event method."""

    def test_get_last_event_returns_event(self, mock_ctx):
        """get_last_event returns last event of type."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        assert processor.get_last_event("stopped") == event

    def test_get_last_event_none_if_no_event(self, mock_ctx):
        """get_last_event returns None if no event."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        assert processor.get_last_event("stopped") is None


class TestGetBreakpointEvents:
    """Tests for get_breakpoint_events method."""

    def test_get_breakpoint_events_returns_copy(self, mock_ctx):
        """get_breakpoint_events returns a copy."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        events = processor.get_breakpoint_events()
        events.clear()

        assert len(processor._breakpoint_events) == 1


class TestClearEvents:
    """Tests for clear_events method."""

    def test_clear_events_clears_all(self, mock_ctx):
        """clear_events clears all stored events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        processor.clear_events()

        assert processor._last_events == {}
        assert processor._breakpoint_events == []
        assert processor._last_stopped_event is None
        assert processor._last_initialized_event is None
        assert not processor._event_received["stopped"].is_set()
