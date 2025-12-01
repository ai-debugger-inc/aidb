"""Unit tests for PublicEventAPI and StubPublicEventAPI.

Tests the public event subscription interface including subscription management, event
filtering, and convenience methods.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from aidb.common.errors import AidbError
from aidb.dap.client.events import EventProcessor
from aidb.dap.client.public_events import (
    PublicEventAPI,
    StubPublicEventAPI,
    SubscriptionInfo,
)
from aidb.dap.client.state import SessionState
from tests._fixtures.unit.builders import DAPEventBuilder


class TestPublicEventAPIInit:
    """Tests for PublicEventAPI initialization."""

    def test_init_with_event_processor(self, mock_ctx):
        """PublicEventAPI initializes with event processor."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        assert api._event_processor == processor
        assert api._subscriptions == {}
        assert api._subscriptions_by_type == {}

    def test_init_statistics(self, mock_ctx):
        """PublicEventAPI initializes statistics."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        assert api._total_subscriptions_created == 0
        assert api._total_events_delivered == 0


class TestSubscribeToEvent:
    """Tests for subscribe_to_event method."""

    @pytest.mark.asyncio
    async def test_subscribe_returns_id(self, mock_ctx):
        """subscribe_to_event returns unique subscription ID."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.subscribe_to_event("stopped", handler)

        assert sub_id is not None
        assert isinstance(sub_id, str)

    @pytest.mark.asyncio
    async def test_subscribe_stores_subscription(self, mock_ctx):
        """subscribe_to_event stores subscription info."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.subscribe_to_event("stopped", handler)

        assert sub_id in api._subscriptions
        sub_info = api._subscriptions[sub_id]
        assert sub_info.event_type == "stopped"
        assert sub_info.handler == handler

    @pytest.mark.asyncio
    async def test_subscribe_tracks_by_type(self, mock_ctx):
        """subscribe_to_event tracks subscriptions by type."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.subscribe_to_event("stopped", handler)

        assert "stopped" in api._subscriptions_by_type
        assert sub_id in api._subscriptions_by_type["stopped"]

    @pytest.mark.asyncio
    async def test_subscribe_non_callable_raises(self, mock_ctx):
        """subscribe_to_event raises for non-callable handler."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        with pytest.raises(AidbError, match="callable"):
            await api.subscribe_to_event("stopped", "not a function")

    @pytest.mark.asyncio
    async def test_subscribe_with_filter(self, mock_ctx):
        """subscribe_to_event accepts optional filter."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        event_filter = MagicMock(return_value=True)
        sub_id = await api.subscribe_to_event("stopped", handler, event_filter)

        sub_info = api._subscriptions[sub_id]
        assert sub_info.filter == event_filter

    @pytest.mark.asyncio
    async def test_subscribe_increments_counter(self, mock_ctx):
        """subscribe_to_event increments subscription counter."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        await api.subscribe_to_event("stopped", handler)
        await api.subscribe_to_event("terminated", handler)

        assert api._total_subscriptions_created == 2


class TestUnsubscribeFromEvent:
    """Tests for unsubscribe_from_event method."""

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self, mock_ctx):
        """unsubscribe_from_event removes subscription."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.subscribe_to_event("stopped", handler)

        result = await api.unsubscribe_from_event(sub_id)

        assert result is True
        assert sub_id not in api._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_returns_false(self, mock_ctx):
        """unsubscribe_from_event returns False for unknown ID."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        result = await api.unsubscribe_from_event("unknown-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_from_type_tracking(self, mock_ctx):
        """unsubscribe_from_event removes from type tracking."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.subscribe_to_event("stopped", handler)
        await api.unsubscribe_from_event(sub_id)

        assert "stopped" not in api._subscriptions_by_type


class TestGetActiveSubscriptions:
    """Tests for get_active_subscriptions method."""

    @pytest.mark.asyncio
    async def test_get_active_subscriptions_empty(self, mock_ctx):
        """get_active_subscriptions returns empty list when none."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        subs = await api.get_active_subscriptions()

        assert subs == []

    @pytest.mark.asyncio
    async def test_get_active_subscriptions_returns_copies(self, mock_ctx):
        """get_active_subscriptions returns copies."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        await api.subscribe_to_event("stopped", handler)

        subs = await api.get_active_subscriptions()

        assert len(subs) == 1
        assert isinstance(subs[0], SubscriptionInfo)
        assert subs[0].event_type == "stopped"


class TestClearAllSubscriptions:
    """Tests for clear_all_subscriptions method."""

    @pytest.mark.asyncio
    async def test_clear_all_subscriptions(self, mock_ctx):
        """clear_all_subscriptions removes all subscriptions."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        await api.subscribe_to_event("stopped", handler)
        await api.subscribe_to_event("terminated", handler)

        count = await api.clear_all_subscriptions()

        assert count == 2
        assert len(api._subscriptions) == 0
        assert len(api._subscriptions_by_type) == 0


class TestConvenienceMethods:
    """Tests for convenience subscription methods."""

    @pytest.mark.asyncio
    async def test_on_stopped(self, mock_ctx):
        """on_stopped subscribes to stopped events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.on_stopped(handler)

        assert api._subscriptions[sub_id].event_type == "stopped"

    @pytest.mark.asyncio
    async def test_on_terminated(self, mock_ctx):
        """on_terminated subscribes to terminated events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.on_terminated(handler)

        assert api._subscriptions[sub_id].event_type == "terminated"

    @pytest.mark.asyncio
    async def test_on_continued(self, mock_ctx):
        """on_continued subscribes to continued events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.on_continued(handler)

        assert api._subscriptions[sub_id].event_type == "continued"

    @pytest.mark.asyncio
    async def test_on_output(self, mock_ctx):
        """on_output subscribes to output events."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.on_output(handler)

        assert api._subscriptions[sub_id].event_type == "output"

    @pytest.mark.asyncio
    async def test_on_output_with_category_filter(self, mock_ctx):
        """on_output with category creates filter."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        sub_id = await api.on_output(handler, category="stderr")

        assert api._subscriptions[sub_id].filter is not None


class TestGetSubscriptionStats:
    """Tests for get_subscription_stats method."""

    @pytest.mark.asyncio
    async def test_get_subscription_stats(self, mock_ctx):
        """get_subscription_stats returns statistics."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        await api.subscribe_to_event("stopped", handler)
        await api.subscribe_to_event("stopped", handler)

        stats = await api.get_subscription_stats()

        assert stats["total_created"] == 2
        assert stats["active_count"] == 2
        assert stats["events_delivered"] == 0
        assert stats["subscriptions_by_type"]["stopped"] == 2


class TestWaitForEventAsync:
    """Tests for wait_for_event_async method."""

    @pytest.mark.asyncio
    async def test_wait_for_event_async_returns_future(self, mock_ctx):
        """wait_for_event_async returns a future."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        future = await api.wait_for_event_async("stopped")

        assert isinstance(future, asyncio.Future)

    @pytest.mark.asyncio
    async def test_wait_for_event_async_resolves_on_event(self, mock_ctx):
        """wait_for_event_async resolves when event occurs."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        future = await api.wait_for_event_async("stopped", timeout=1.0)

        event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
        processor.process_event(event)

        await asyncio.sleep(0.05)
        assert future.done()

    @pytest.mark.asyncio
    async def test_wait_for_event_async_timeout(self, mock_ctx):
        """wait_for_event_async raises TimeoutError on timeout."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        future = await api.wait_for_event_async("stopped", timeout=0.05)

        await asyncio.sleep(0.1)

        with pytest.raises(TimeoutError):
            future.result()


class TestCollectEvents:
    """Tests for collect_events method."""

    @pytest.mark.asyncio
    async def test_collect_events_collects_count(self, mock_ctx):
        """collect_events collects specified count."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        async def emit_events():
            for i in range(3):
                await asyncio.sleep(0.01)
                event = DAPEventBuilder.stopped_event(reason="step", thread_id=i)
                processor.process_event(event)

        asyncio.create_task(emit_events())
        events = await api.collect_events("stopped", count=3, timeout=1.0)

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_collect_events_timeout_partial(self, mock_ctx):
        """collect_events returns partial on timeout."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        event = DAPEventBuilder.stopped_event(reason="step", thread_id=1)
        processor.process_event(event)

        events = await api.collect_events("stopped", count=5, timeout=0.1)

        assert len(events) < 5


class TestWaitForStoppedOrTerminated:
    """Tests for wait_for_stopped_or_terminated_async method."""

    @pytest.mark.asyncio
    async def test_returns_stopped_if_already_stopped(self, mock_ctx):
        """wait_for_stopped_or_terminated returns 'stopped' if already stopped."""
        state = SessionState()
        state.stopped = True
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        result = await api.wait_for_stopped_or_terminated_async(timeout=1.0)

        assert result == "stopped"

    @pytest.mark.asyncio
    async def test_returns_terminated_if_already_terminated(self, mock_ctx):
        """wait_for_stopped_or_terminated returns 'terminated' if terminated."""
        state = SessionState()
        state.terminated = True
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        result = await api.wait_for_stopped_or_terminated_async(timeout=1.0)

        assert result == "terminated"

    @pytest.mark.asyncio
    async def test_returns_timeout_when_no_event(self, mock_ctx):
        """wait_for_stopped_or_terminated returns 'timeout' when no event."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        result = await api.wait_for_stopped_or_terminated_async(timeout=0.1)

        assert result == "timeout"

    @pytest.mark.asyncio
    async def test_edge_triggered_ignores_current_state(self, mock_ctx):
        """wait_for_stopped_or_terminated edge_triggered waits for next event."""
        state = SessionState()
        state.stopped = True
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        result = await api.wait_for_stopped_or_terminated_async(
            timeout=0.1,
            edge_triggered=True,
        )

        assert result == "timeout"


class TestCleanup:
    """Tests for cleanup method."""

    @pytest.mark.asyncio
    async def test_cleanup_clears_subscriptions(self, mock_ctx):
        """Cleanup clears all subscriptions."""
        state = SessionState()
        processor = EventProcessor(state=state, ctx=mock_ctx)
        api = PublicEventAPI(event_processor=processor, ctx=mock_ctx)

        handler = MagicMock()
        await api.subscribe_to_event("stopped", handler)

        await api.cleanup()

        assert len(api._subscriptions) == 0


class TestStubPublicEventAPI:
    """Tests for StubPublicEventAPI."""

    @pytest.mark.asyncio
    async def test_stub_subscribe_to_event(self):
        """StubPublicEventAPI stores subscriptions."""
        stub = StubPublicEventAPI()

        handler = MagicMock()
        sub_id = await stub.subscribe_to_event("stopped", handler)

        assert sub_id.startswith("stub_")
        assert "stopped" in stub._subscriptions
        assert len(stub._subscriptions["stopped"]) == 1

    @pytest.mark.asyncio
    async def test_stub_unsubscribe_from_event(self):
        """StubPublicEventAPI unsubscribes."""
        stub = StubPublicEventAPI()

        handler = MagicMock()
        sub_id = await stub.subscribe_to_event("stopped", handler)

        result = await stub.unsubscribe_from_event(sub_id)

        assert result is True
        assert "stopped" not in stub._subscriptions

    @pytest.mark.asyncio
    async def test_stub_clear_all_subscriptions(self):
        """StubPublicEventAPI clears all."""
        stub = StubPublicEventAPI()

        handler = MagicMock()
        await stub.subscribe_to_event("stopped", handler)
        await stub.subscribe_to_event("terminated", handler)

        count = await stub.clear_all_subscriptions()

        assert count == 2
        assert len(stub._subscriptions) == 0

    @pytest.mark.asyncio
    async def test_stub_get_subscriptions(self):
        """StubPublicEventAPI returns subscriptions for transfer."""
        stub = StubPublicEventAPI()

        handler = MagicMock()
        await stub.subscribe_to_event("stopped", handler)

        subs = await stub.get_subscriptions()

        assert "stopped" in subs
        assert len(subs["stopped"]) == 1

    @pytest.mark.asyncio
    async def test_stub_convenience_methods(self):
        """StubPublicEventAPI convenience methods work."""
        stub = StubPublicEventAPI()

        handler = MagicMock()

        await stub.on_stopped(handler)
        await stub.on_terminated(handler)
        await stub.on_continued(handler)

        subs = await stub.get_subscriptions()

        assert "stopped" in subs
        assert "terminated" in subs
        assert "continued" in subs
