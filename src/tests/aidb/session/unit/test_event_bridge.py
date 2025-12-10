"""Unit tests for EventBridge.

Tests parent-child event synchronization, event forwarding, and subscription management
for DAP events between debug sessions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.session.event_bridge import EventBridge


@pytest.fixture
def event_bridge(mock_ctx):
    """Create a fresh EventBridge instance for testing."""
    return EventBridge(ctx=mock_ctx)


@pytest.fixture
def mock_parent_session():
    """Create a mock parent session."""
    session = MagicMock()
    session.id = "parent-session-id"
    session.events = MagicMock()
    session.events.subscribe_to_event = AsyncMock(return_value="sub-id-1")
    session.events.unsubscribe_from_event = AsyncMock()
    return session


@pytest.fixture
def mock_child_session():
    """Create a mock child session."""
    session = MagicMock()
    session.id = "child-session-id"
    session.connector = MagicMock()
    session.connector._dap = MagicMock()
    session.connector._dap._event_processor = MagicMock()
    session.dap = MagicMock()
    session.dap.ingest_synthetic_event = MagicMock()
    return session


@pytest.fixture
def mock_stopped_event():
    """Create a mock stopped event."""
    event = MagicMock()
    event.event = "stopped"
    return event


@pytest.fixture
def mock_continued_event():
    """Create a mock continued event."""
    event = MagicMock()
    event.event = "continued"
    return event


class TestEventBridgeInit:
    """Tests for EventBridge initialization."""

    def test_init_creates_empty_mappings(self, event_bridge):
        """EventBridge initializes with empty parent-child mappings."""
        assert event_bridge._parent_to_children == {}
        assert event_bridge._child_to_parent == {}

    def test_init_sets_forwarded_event_types(self, event_bridge):
        """EventBridge initializes with correct forwarded event types."""
        assert event_bridge._forwarded_event_types == {"stopped", "continued"}

    def test_init_creates_empty_subscriptions(self, event_bridge):
        """EventBridge initializes with empty subscriptions dict."""
        assert event_bridge._subscriptions == {}

    def test_init_creates_locks(self, event_bridge):
        """EventBridge creates async and sync locks."""
        assert event_bridge._async_lock is not None
        assert event_bridge._sync_lock is not None


class TestEventBridgeChildRegistration:
    """Tests for child session registration."""

    @pytest.mark.asyncio
    async def test_register_child_adds_to_parent_mapping(
        self, event_bridge, mock_parent_session
    ):
        """register_child adds child to parent's children set."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-id")

            assert "parent-id" in event_bridge._parent_to_children
            assert "child-id" in event_bridge._parent_to_children["parent-id"]

    @pytest.mark.asyncio
    async def test_register_child_creates_reverse_lookup(
        self, event_bridge, mock_parent_session
    ):
        """register_child creates child-to-parent reverse lookup."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-id")

            assert event_bridge._child_to_parent["child-id"] == "parent-id"

    @pytest.mark.asyncio
    async def test_register_multiple_children_same_parent(
        self, event_bridge, mock_parent_session
    ):
        """Multiple children can be registered to the same parent."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-1")
            await event_bridge.register_child("parent-id", "child-2")

            assert len(event_bridge._parent_to_children["parent-id"]) == 2
            assert "child-1" in event_bridge._parent_to_children["parent-id"]
            assert "child-2" in event_bridge._parent_to_children["parent-id"]

    @pytest.mark.asyncio
    async def test_unregister_child_removes_from_mappings(
        self, event_bridge, mock_parent_session
    ):
        """unregister_child removes child from all mappings."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-id")
            await event_bridge.unregister_child("child-id")

            assert "child-id" not in event_bridge._child_to_parent
            assert "parent-id" not in event_bridge._parent_to_children

    @pytest.mark.asyncio
    async def test_unregister_child_cleans_empty_parent(
        self, event_bridge, mock_parent_session
    ):
        """unregister_child removes parent entry when no children left."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-id")
            await event_bridge.unregister_child("child-id")

            assert "parent-id" not in event_bridge._parent_to_children

    @pytest.mark.asyncio
    async def test_unregister_child_keeps_sibling(
        self, event_bridge, mock_parent_session
    ):
        """unregister_child keeps sibling children registered."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.register_child("parent-id", "child-1")
            await event_bridge.register_child("parent-id", "child-2")
            await event_bridge.unregister_child("child-1")

            assert "child-2" in event_bridge._parent_to_children["parent-id"]
            assert "child-1" not in event_bridge._child_to_parent


class TestEventBridgeEventForwarding:
    """Tests for event forwarding from parent to children."""

    def test_forward_event_skips_non_forwarded_types(
        self, event_bridge, mock_parent_session
    ):
        """forward_event_to_children skips non-forwarded event types."""
        event_bridge._parent_to_children["parent-session-id"] = {"child-id"}

        non_forwarded_event = MagicMock()
        non_forwarded_event.event = "output"

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, non_forwarded_event
            )

            mock_registry.get_session.assert_not_called()

    def test_forward_event_skips_when_no_children(
        self, event_bridge, mock_parent_session, mock_stopped_event
    ):
        """forward_event_to_children skips when parent has no children."""
        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, mock_stopped_event
            )

            mock_registry.get_session.assert_not_called()

    def test_forward_stopped_event_to_child(
        self,
        event_bridge,
        mock_parent_session,
        mock_child_session,
        mock_stopped_event,
    ):
        """forward_event_to_children forwards stopped event to child."""
        event_bridge._parent_to_children["parent-session-id"] = {"child-session-id"}

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_child_session
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, mock_stopped_event
            )

            mock_child_session.dap.ingest_synthetic_event.assert_called_once_with(
                mock_stopped_event
            )

    def test_forward_continued_event_to_child(
        self,
        event_bridge,
        mock_parent_session,
        mock_child_session,
        mock_continued_event,
    ):
        """forward_event_to_children forwards continued event to child."""
        event_bridge._parent_to_children["parent-session-id"] = {"child-session-id"}

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_child_session
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, mock_continued_event
            )

            mock_child_session.dap.ingest_synthetic_event.assert_called_once_with(
                mock_continued_event
            )

    def test_forward_event_handles_missing_child(
        self,
        event_bridge,
        mock_parent_session,
        mock_stopped_event,
        mock_ctx,
    ):
        """forward_event_to_children handles missing child gracefully."""
        event_bridge._parent_to_children["parent-session-id"] = {"missing-child"}

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = None
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, mock_stopped_event
            )

            mock_ctx.warning.assert_called()

    def test_forward_event_to_multiple_children(
        self,
        event_bridge,
        mock_parent_session,
        mock_stopped_event,
    ):
        """forward_event_to_children forwards to all children."""
        child1 = MagicMock()
        child1.id = "child-1"
        child1.connector._dap = MagicMock()
        child1.connector._dap._event_processor = MagicMock()
        child1.dap = MagicMock()

        child2 = MagicMock()
        child2.id = "child-2"
        child2.connector._dap = MagicMock()
        child2.connector._dap._event_processor = MagicMock()
        child2.dap = MagicMock()

        event_bridge._parent_to_children["parent-session-id"] = {"child-1", "child-2"}

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.side_effect = lambda session_id: (
                child1 if session_id == "child-1" else child2
            )
            mock_registry_cls.return_value = mock_registry

            event_bridge.forward_event_to_children(
                mock_parent_session, mock_stopped_event
            )

            child1.dap.ingest_synthetic_event.assert_called_once()
            child2.dap.ingest_synthetic_event.assert_called_once()


class TestEventBridgeSubscriptions:
    """Tests for event subscription management."""

    @pytest.mark.asyncio
    async def test_setup_parent_subscriptions_creates_handlers(
        self, event_bridge, mock_parent_session
    ):
        """setup_parent_subscriptions creates handlers for forwarded events."""
        await event_bridge.setup_parent_subscriptions(mock_parent_session)

        assert mock_parent_session.events.subscribe_to_event.call_count == 2
        assert "parent-session-id" in event_bridge._subscriptions

    @pytest.mark.asyncio
    async def test_setup_parent_subscriptions_skips_without_events_api(
        self, event_bridge, mock_ctx
    ):
        """setup_parent_subscriptions skips session without events API."""
        session = MagicMock()
        session.id = "no-events-session"
        session.events = None

        await event_bridge.setup_parent_subscriptions(session)

        mock_ctx.warning.assert_called()
        assert "no-events-session" not in event_bridge._subscriptions

    @pytest.mark.asyncio
    async def test_cleanup_parent_subscriptions_removes_all(
        self, event_bridge, mock_parent_session
    ):
        """cleanup_parent_subscriptions removes all subscriptions."""
        event_bridge._subscriptions["parent-session-id"] = {"sub-1", "sub-2"}

        with patch("aidb.session.registry.SessionRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.get_session.return_value = mock_parent_session
            mock_registry_cls.return_value = mock_registry

            await event_bridge.cleanup_parent_subscriptions("parent-session-id")

            assert "parent-session-id" not in event_bridge._subscriptions
            assert mock_parent_session.events.unsubscribe_from_event.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_parent_subscriptions_handles_unknown(self, event_bridge):
        """cleanup_parent_subscriptions handles unknown parent gracefully."""
        await event_bridge.cleanup_parent_subscriptions("unknown-parent")


class TestEventBridgeForwardToChild:
    """Tests for _forward_event_to_child internal method."""

    def test_forward_event_to_child_calls_ingest(
        self, event_bridge, mock_child_session, mock_stopped_event
    ):
        """_forward_event_to_child calls ingest_synthetic_event."""
        event_bridge._forward_event_to_child(mock_child_session, mock_stopped_event)

        mock_child_session.dap.ingest_synthetic_event.assert_called_once_with(
            mock_stopped_event
        )

    def test_forward_event_to_child_handles_error(
        self, event_bridge, mock_child_session, mock_stopped_event, mock_ctx
    ):
        """_forward_event_to_child handles errors gracefully."""
        mock_child_session.dap.ingest_synthetic_event.side_effect = Exception(
            "Test error"
        )

        event_bridge._forward_event_to_child(mock_child_session, mock_stopped_event)

        mock_ctx.error.assert_called()
