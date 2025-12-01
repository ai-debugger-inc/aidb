"""Unit tests for SessionConnector.

Tests DAP connection management including client setup, child sessions, events API, and
reconnection logic.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.common.errors import DebugConnectionError, DebugSessionLostError


@pytest.fixture
def mock_session_for_connector() -> MagicMock:
    """Create a mock Session for connector tests."""
    session = MagicMock()
    session.id = "test-session-123"
    session.language = "python"
    session.is_child = False
    session.parent_session_id = None
    session._handle_child_session_request = MagicMock()

    # Registry for parent lookup
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


@pytest.fixture
def connector(mock_session_for_connector: MagicMock, mock_ctx: MagicMock):
    """Create a SessionConnector instance for testing."""
    from aidb.session.connector import SessionConnector

    return SessionConnector(session=mock_session_for_connector, ctx=mock_ctx)


class TestConnectorSetup:
    """Tests for DAP client setup."""

    def test_setup_dap_client_creates_client(
        self,
        connector,
        mock_ctx: MagicMock,
    ) -> None:
        """setup_dap_client creates a DAPClient instance."""
        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap = MagicMock()
            mock_dap_class.return_value = mock_dap

            result = connector.setup_dap_client("localhost", 5678)

            mock_dap_class.assert_called_once()
            call_kwargs = mock_dap_class.call_args.kwargs
            assert call_kwargs["adapter_host"] == "localhost"
            assert call_kwargs["adapter_port"] == 5678
            assert result is mock_dap

    def test_setup_dap_client_registers_callback(
        self,
        connector,
        mock_session_for_connector: MagicMock,
    ) -> None:
        """setup_dap_client registers child session callback."""
        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap = MagicMock()
            mock_dap_class.return_value = mock_dap

            connector.setup_dap_client("localhost", 5678)

            mock_dap.set_session_creation_callback.assert_called_once_with(
                mock_session_for_connector._handle_child_session_request,
            )

    def test_setup_dap_client_raises_on_error(
        self,
        connector,
    ) -> None:
        """setup_dap_client raises DebugConnectionError on failure."""
        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap_class.side_effect = OSError("Connection refused")

            with pytest.raises(DebugConnectionError) as exc_info:
                connector.setup_dap_client("localhost", 5678)

            assert "localhost:5678" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_setup_child_dap_client_connects(
        self,
        connector,
    ) -> None:
        """setup_child_dap_client creates and connects DAP client."""
        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap = MagicMock()
            mock_dap.connect = AsyncMock()
            mock_dap_class.return_value = mock_dap

            result = await connector.setup_child_dap_client("localhost", 5679)

            mock_dap.connect.assert_called_once()
            assert result is mock_dap

    @pytest.mark.asyncio
    async def test_setup_child_dap_client_raises_on_error(
        self,
        connector,
    ) -> None:
        """setup_child_dap_client raises DebugConnectionError on failure."""
        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap = MagicMock()
            mock_dap.connect = AsyncMock(side_effect=ConnectionRefusedError())
            mock_dap_class.return_value = mock_dap

            with pytest.raises(DebugConnectionError) as exc_info:
                await connector.setup_child_dap_client("localhost", 5679)

            assert "is_child" in exc_info.value.details


class TestConnectorGetDapClient:
    """Tests for get_dap_client and related methods."""

    def test_get_dap_client_returns_own_client(
        self,
        connector,
    ) -> None:
        """get_dap_client returns session's own DAP client."""
        mock_dap = MagicMock()
        connector._dap = mock_dap

        result = connector.get_dap_client()

        assert result is mock_dap

    def test_get_dap_client_uses_parent_for_child(
        self,
        connector,
        mock_session_for_connector: MagicMock,
    ) -> None:
        """get_dap_client uses parent's DAP client for child sessions."""
        connector._dap = None
        mock_session_for_connector.is_child = True
        mock_session_for_connector.parent_session_id = "parent-123"

        # Create mock parent with DAP client
        mock_parent = MagicMock()
        mock_parent.connector = MagicMock()
        mock_parent.connector._dap = MagicMock()
        mock_session_for_connector.registry.get_session.return_value = mock_parent

        result = connector.get_dap_client()

        assert result is mock_parent.connector._dap

    def test_get_dap_client_raises_when_missing(
        self,
        connector,
        mock_session_for_connector: MagicMock,
    ) -> None:
        """get_dap_client raises DebugSessionLostError when no client."""
        connector._dap = None
        mock_session_for_connector.is_child = False

        with pytest.raises(DebugSessionLostError) as exc_info:
            connector.get_dap_client()

        assert "has no DAP client" in str(exc_info.value)

    def test_get_dap_client_raises_when_child_parent_missing(
        self,
        connector,
        mock_session_for_connector: MagicMock,
    ) -> None:
        """get_dap_client raises when child can't access parent."""
        connector._dap = None
        mock_session_for_connector.is_child = True
        mock_session_for_connector.parent_session_id = "parent-123"

        # Parent doesn't have DAP client
        mock_parent = MagicMock()
        mock_parent.connector = MagicMock()
        mock_parent.connector._dap = None
        mock_session_for_connector.registry.get_session.return_value = mock_parent

        with pytest.raises(DebugSessionLostError) as exc_info:
            connector.get_dap_client()

        assert "child" in str(exc_info.value).lower()

    def test_has_dap_client_returns_true_when_available(
        self,
        connector,
    ) -> None:
        """has_dap_client returns True when DAP client exists."""
        connector._dap = MagicMock()

        assert connector.has_dap_client() is True

    def test_has_dap_client_returns_false_when_missing(
        self,
        connector,
        mock_session_for_connector: MagicMock,
    ) -> None:
        """has_dap_client returns False when no DAP client available."""
        connector._dap = None
        mock_session_for_connector.is_child = False

        assert connector.has_dap_client() is False

    def test_set_dap_client_updates_client(
        self,
        connector,
    ) -> None:
        """set_dap_client sets the internal DAP client."""
        mock_dap = MagicMock()

        connector.set_dap_client(mock_dap)

        assert connector._dap is mock_dap

    def test_set_dap_client_clears_with_none(
        self,
        connector,
    ) -> None:
        """set_dap_client(None) clears the DAP client."""
        connector._dap = MagicMock()

        connector.set_dap_client(None)

        assert connector._dap is None


class TestConnectorEventsAPI:
    """Tests for events API management."""

    def test_create_stub_events_api_creates_stub(
        self,
        connector,
    ) -> None:
        """create_stub_events_api creates a stub API."""
        result = connector.create_stub_events_api()

        assert result is not None
        assert connector._stub_events is not None

    def test_stub_captures_subscriptions(
        self,
        connector,
    ) -> None:
        """Stub events API captures subscriptions for replay."""
        stub = connector.create_stub_events_api()

        handler = MagicMock()
        stub.subscribe_to_event("stopped", handler)

        assert len(connector._pending_subscriptions) == 1
        assert connector._pending_subscriptions[0]["event_type"] == "stopped"
        assert connector._pending_subscriptions[0]["handler"] is handler

    def test_get_events_api_returns_dap_events(
        self,
        connector,
    ) -> None:
        """get_events_api returns DAP's events when connected."""
        mock_events = MagicMock()
        mock_dap = MagicMock()
        mock_dap.events = mock_events
        connector._dap = mock_dap

        result = connector.get_events_api()

        assert result is mock_events

    def test_get_events_api_returns_stub_events(
        self,
        connector,
    ) -> None:
        """get_events_api returns stub events when not connected."""
        connector._dap = None
        stub = connector.create_stub_events_api()

        result = connector.get_events_api()

        assert result is stub

    def test_get_events_api_raises_without_either(
        self,
        connector,
    ) -> None:
        """get_events_api raises RuntimeError when no API available."""
        connector._dap = None
        connector._stub_events = None

        with pytest.raises(RuntimeError, match="No event API available"):
            connector.get_events_api()

    def test_get_pending_subscriptions_returns_list(
        self,
        connector,
    ) -> None:
        """get_pending_subscriptions returns captured subscriptions."""
        stub = connector.create_stub_events_api()
        stub.subscribe_to_event("stopped", MagicMock())
        stub.subscribe_to_event("output", MagicMock())

        result = connector.get_pending_subscriptions()

        assert len(result) == 2


class TestConnectorReconnect:
    """Tests for reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_creates_new_client(
        self,
        connector,
    ) -> None:
        """Reconnect creates a new DAP client."""
        # Set up existing client
        old_dap = MagicMock()
        old_dap._transport = MagicMock()
        old_dap._transport._host = "localhost"
        old_dap._transport._port = 5678
        old_dap.disconnect = AsyncMock()
        connector._dap = old_dap

        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            new_dap = MagicMock()
            new_dap.connect = AsyncMock()
            mock_dap_class.return_value = new_dap

            result = await connector.reconnect()

            assert result is True
            assert connector._dap is new_dap
            old_dap.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_replays_subscriptions(
        self,
        connector,
    ) -> None:
        """Reconnect replays pending event subscriptions."""
        # Set up existing client
        old_dap = MagicMock()
        old_dap._transport = MagicMock()
        old_dap._transport._host = "localhost"
        old_dap._transport._port = 5678
        old_dap.disconnect = AsyncMock()
        connector._dap = old_dap

        # Add pending subscriptions
        handler = MagicMock()
        connector._pending_subscriptions = [
            {"event_type": "stopped", "handler": handler, "filter": None},
        ]

        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            new_dap = MagicMock()
            new_dap.connect = AsyncMock()
            new_dap.events = MagicMock()
            new_dap.events.subscribe_to_event = AsyncMock()
            mock_dap_class.return_value = new_dap

            await connector.reconnect()

            new_dap.events.subscribe_to_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_fails_without_dap(
        self,
        connector,
    ) -> None:
        """Reconnect returns False when no existing DAP client."""
        connector._dap = None

        result = await connector.reconnect()

        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_fails_without_transport(
        self,
        connector,
    ) -> None:
        """Reconnect returns False when no transport layer."""
        old_dap = MagicMock(spec=[])  # Empty spec means no _transport attribute
        connector._dap = old_dap

        result = await connector.reconnect()

        assert result is False

    @pytest.mark.asyncio
    async def test_reconnect_retries_with_backoff(
        self,
        connector,
    ) -> None:
        """Reconnect uses exponential backoff between attempts."""
        old_dap = MagicMock()
        old_dap._transport = MagicMock()
        old_dap._transport._host = "localhost"
        old_dap._transport._port = 5678
        connector._dap = old_dap

        attempt_delays = []

        async def mock_sleep(delay):
            attempt_delays.append(delay)

        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap_class.side_effect = ConnectionError("Failed")

            with patch("asyncio.sleep", side_effect=mock_sleep):
                result = await connector.reconnect(max_attempts=3, delay=1.0)

        assert result is False
        # Should have 2 sleep calls (between 3 attempts)
        assert len(attempt_delays) == 2
        # Exponential backoff
        assert attempt_delays[0] == 1.0
        assert attempt_delays[1] == 1.5

    @pytest.mark.asyncio
    async def test_reconnect_returns_false_after_max_attempts(
        self,
        connector,
    ) -> None:
        """Reconnect returns False after max attempts exhausted."""
        old_dap = MagicMock()
        old_dap._transport = MagicMock()
        old_dap._transport._host = "localhost"
        old_dap._transport._port = 5678
        connector._dap = old_dap

        with patch("aidb.session.connector.DAPClient") as mock_dap_class:
            mock_dap_class.side_effect = ConnectionError("Failed")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await connector.reconnect(max_attempts=2)

        assert result is False
        assert mock_dap_class.call_count == 2


class TestConnectorVerifyConnection:
    """Tests for connection verification."""

    @pytest.mark.asyncio
    async def test_verify_connection_returns_true_when_connected(
        self,
        connector,
    ) -> None:
        """verify_connection returns True when connection is active."""
        mock_dap = MagicMock()
        mock_dap.is_connected = True
        connector._dap = mock_dap

        result = await connector.verify_connection()

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_connection_returns_false_without_client(
        self,
        connector,
    ) -> None:
        """verify_connection returns False when no DAP client."""
        connector._dap = None

        result = await connector.verify_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_connection_calls_method_if_callable(
        self,
        connector,
    ) -> None:
        """verify_connection calls is_connected if it's a method."""
        mock_dap = MagicMock()
        mock_dap.is_connected = MagicMock(return_value=True)
        connector._dap = mock_dap

        result = await connector.verify_connection()

        assert result is True
        mock_dap.is_connected.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connection_handles_exception(
        self,
        connector,
    ) -> None:
        """verify_connection returns False on exception."""
        mock_dap = MagicMock()
        mock_dap.is_connected = MagicMock(side_effect=Exception("Error"))
        connector._dap = mock_dap

        result = await connector.verify_connection()

        assert result is False
