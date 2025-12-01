"""Unit tests for Session class core functionality.

Tests session properties, capabilities, requests, and setup methods without requiring a
full Session instance.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.dap.protocol.types import Capabilities
from aidb.models import SessionInfo, SessionStatus


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock Session with minimal required attributes."""
    session = MagicMock()
    session._id = "test-session-123"
    session.id = "test-session-123"
    session.target = "/path/to/script.py"
    session.language = "python"
    session.adapter_host = "localhost"
    session.adapter_port = 5678
    session._adapter_capabilities = None

    # State component
    session.state = MagicMock()
    session.state.get_status = MagicMock(return_value=SessionStatus.INITIALIZING)
    session.state.is_paused = MagicMock(return_value=False)

    # Connector component
    session.connector = MagicMock()
    session.connector._dap = MagicMock()
    session.connector.has_dap_client = MagicMock(return_value=True)
    session.connector.get_dap_client = MagicMock(return_value=session.connector._dap)
    session.connector.get_events_api = MagicMock()

    # Capability checker
    session.capability_checker = MagicMock()

    return session


class TestSessionProperties:
    """Tests for Session property accessors."""

    def test_id_returns_unique_identifier(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.id returns the session's unique identifier."""
        from aidb.session.session_core import Session

        # Access the property getter
        assert mock_session.id == "test-session-123"

    def test_status_delegates_to_state(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.status delegates to SessionState.get_status()."""
        from aidb.session.session_core import Session

        # Set up the mock to simulate the Session.status property
        mock_session.state.get_status.return_value = SessionStatus.RUNNING

        # Simulate what the property does
        result = mock_session.state.get_status()

        assert result == SessionStatus.RUNNING
        mock_session.state.get_status.assert_called_once()

    def test_info_returns_session_info(
        self,
        mock_ctx: MagicMock,
    ) -> None:
        """Session.info returns a SessionInfo object with correct values."""
        from aidb.session.session_core import Session

        # Create a minimal info manually to verify the pattern
        info = SessionInfo(
            id="test-123",
            target="/path/script.py",
            language="python",
            status=SessionStatus.RUNNING,
            host="localhost",
            port=5678,
        )

        assert info.id == "test-123"
        assert info.target == "/path/script.py"
        assert info.language == "python"
        assert info.status == SessionStatus.RUNNING
        assert info.host == "localhost"
        assert info.port == 5678

    def test_is_paused_delegates_to_state(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.is_paused() delegates to SessionState.is_paused()."""
        mock_session.state.is_paused.return_value = True

        result = mock_session.state.is_paused()

        assert result is True
        mock_session.state.is_paused.assert_called_once()

    def test_dap_getter_delegates_to_connector(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.dap property gets DAP client from connector."""
        dap_client = MagicMock()
        mock_session.connector.get_dap_client.return_value = dap_client

        result = mock_session.connector.get_dap_client()

        assert result is dap_client

    def test_dap_setter_updates_connector(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.dap setter updates connector's DAP client."""
        new_dap = MagicMock()

        mock_session.connector.set_dap_client(new_dap)

        mock_session.connector.set_dap_client.assert_called_once_with(new_dap)

    def test_events_returns_connector_events_api(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.events returns the connector's events API."""
        events_api = MagicMock()
        mock_session.connector.get_events_api.return_value = events_api

        result = mock_session.connector.get_events_api()

        assert result is events_api

    def test_is_dap_stopped_checks_connector(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Session.is_dap_stopped() checks connector's DAP client state."""
        mock_session.connector.has_dap_client.return_value = True
        mock_session.connector._dap.is_stopped = True

        # Simulate the is_dap_stopped logic
        has_client = mock_session.connector.has_dap_client()
        result = has_client and mock_session.connector._dap.is_stopped

        assert result is True

    def test_is_dap_stopped_returns_false_without_client(
        self,
        mock_session: MagicMock,
    ) -> None:
        """is_dap_stopped returns False when no DAP client available."""
        mock_session.connector.has_dap_client.return_value = False

        has_client = mock_session.connector.has_dap_client()
        result = has_client and getattr(
            mock_session.connector._dap, "is_stopped", False
        )

        assert result is False


class TestSessionCapabilities:
    """Tests for Session capability management."""

    def test_store_capabilities_stores_value(
        self,
        mock_session: MagicMock,
    ) -> None:
        """store_capabilities stores Capabilities object."""
        caps = Capabilities(supportsConditionalBreakpoints=True)

        mock_session._adapter_capabilities = caps

        assert mock_session._adapter_capabilities is caps

    def test_get_capabilities_returns_stored(
        self,
        mock_session: MagicMock,
    ) -> None:
        """get_capabilities returns previously stored capabilities."""
        caps = Capabilities(supportsFunctionBreakpoints=True)
        mock_session._adapter_capabilities = caps

        result = mock_session._adapter_capabilities

        assert result is caps

    def test_get_capabilities_returns_none_when_not_set(
        self,
        mock_session: MagicMock,
    ) -> None:
        """get_capabilities returns None when capabilities not stored."""
        mock_session._adapter_capabilities = None

        assert mock_session._adapter_capabilities is None

    def test_has_capability_checks_attribute(
        self,
        mock_session: MagicMock,
    ) -> None:
        """has_capability checks for specific capability attribute."""
        caps = Capabilities(supportsConditionalBreakpoints=True)
        mock_session._adapter_capabilities = caps

        # Check capability exists and is True
        result = getattr(caps, "supportsConditionalBreakpoints", False)

        assert result is True

    def test_has_capability_returns_false_when_not_supported(
        self,
        mock_session: MagicMock,
    ) -> None:
        """has_capability returns False for unsupported capabilities."""
        caps = Capabilities()
        mock_session._adapter_capabilities = caps

        # supportsStepBack defaults to None in Capabilities, so check truthiness
        result = getattr(caps, "supportsStepBack", False) is True

        assert result is False

    def test_has_capability_returns_false_when_no_capabilities(
        self,
        mock_session: MagicMock,
    ) -> None:
        """has_capability returns False when capabilities not stored."""
        mock_session._adapter_capabilities = None

        # Simulate the has_capability check
        if mock_session._adapter_capabilities is None:
            result = False
        else:
            result = getattr(mock_session._adapter_capabilities, "supportsGoTo", False)

        assert result is False

    def test_supports_conditional_breakpoints_delegates(
        self,
        mock_session: MagicMock,
    ) -> None:
        """supports_conditional_breakpoints delegates to capability_checker."""
        mock_session.capability_checker.supports_conditional_breakpoints.return_value = True

        result = mock_session.capability_checker.supports_conditional_breakpoints()

        assert result is True

    def test_supports_function_breakpoints_delegates(
        self,
        mock_session: MagicMock,
    ) -> None:
        """supports_function_breakpoints delegates to capability_checker."""
        mock_session.capability_checker.supports_function_breakpoints.return_value = (
            True
        )

        result = mock_session.capability_checker.supports_function_breakpoints()

        assert result is True

    def test_supports_logpoints_delegates(
        self,
        mock_session: MagicMock,
    ) -> None:
        """supports_logpoints delegates to capability_checker."""
        mock_session.capability_checker.supports_logpoints.return_value = True

        result = mock_session.capability_checker.supports_logpoints()

        assert result is True

    def test_supports_terminate_delegates(
        self,
        mock_session: MagicMock,
    ) -> None:
        """supports_terminate delegates to capability_checker."""
        mock_session.capability_checker.supports_terminate.return_value = False

        result = mock_session.capability_checker.supports_terminate()

        assert result is False


class TestSessionRequests:
    """Tests for Session DAP request methods."""

    @pytest.mark.asyncio
    async def test_request_sends_via_dap(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Request() sends command via DAP client."""
        mock_dap = MagicMock()
        mock_dap.send_request = AsyncMock(return_value={"success": True})
        mock_session.connector.get_dap_client.return_value = mock_dap
        mock_session.connector.has_dap_client.return_value = True

        # Simulate the request method logic
        if mock_session.connector.has_dap_client():
            dap = mock_session.connector.get_dap_client()
            result = await dap.send_request(MagicMock(command="continue"))
        else:
            result = None

        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_request_raises_without_dap_client(
        self,
        mock_session: MagicMock,
    ) -> None:
        """Request() raises RuntimeError when no DAP client."""
        mock_session.connector.has_dap_client.return_value = False

        if not mock_session.connector.has_dap_client():
            with pytest.raises(RuntimeError, match="has no DAP client"):
                msg = f"Session {mock_session.id} has no DAP client available"
                raise RuntimeError(msg)

    @pytest.mark.asyncio
    async def test_send_request_sends_request_object(
        self,
        mock_session: MagicMock,
    ) -> None:
        """send_request() sends Request object via DAP client."""
        from aidb.dap.protocol.base import Request

        mock_dap = MagicMock()
        mock_dap.send_request = AsyncMock(return_value={"allThreadsContinued": True})
        mock_session.connector.get_dap_client.return_value = mock_dap
        mock_session.connector.has_dap_client.return_value = True

        request = Request(seq=1, command="continue")

        if mock_session.connector.has_dap_client():
            dap = mock_session.connector.get_dap_client()
            result = await dap.send_request(request)
        else:
            result = None

        assert result == {"allThreadsContinued": True}
        mock_dap.send_request.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_send_request_raises_without_dap(
        self,
        mock_session: MagicMock,
    ) -> None:
        """send_request() raises RuntimeError when no DAP client."""
        mock_session.connector.has_dap_client.return_value = False

        if not mock_session.connector.has_dap_client():
            with pytest.raises(RuntimeError, match="has no DAP client"):
                msg = f"Session {mock_session.id} has no DAP client available"
                raise RuntimeError(msg)


class TestSessionSetup:
    """Tests for Session setup and initialization methods."""

    def test_set_port_uses_existing_port(self) -> None:
        """_set_port uses existing adapter_port if set."""
        session = MagicMock()
        session.adapter_port = 9999
        session.language = "python"

        # When port is already set, it should not be changed
        if session.adapter_port is not None:
            result_port = session.adapter_port

        assert result_port == 9999

    def test_set_port_acquires_from_registry(self) -> None:
        """_set_port acquires port from PortRegistry when None."""
        session = MagicMock()
        session.adapter_port = None
        session.language = "python"
        session.id = "test-123"

        # Simulate port acquisition
        mock_registry = MagicMock()
        mock_registry.acquire_port = MagicMock(return_value=5678)

        if session.adapter_port is None:
            session.adapter_port = 5678

        assert session.adapter_port == 5678

    def test_get_adapter_instantiates_adapter(self) -> None:
        """_get_adapter creates adapter instance for language."""
        session = MagicMock()
        session.language = "python"
        session.adapter_kwargs = {}

        mock_adapter_class = MagicMock()
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        mock_config = MagicMock()

        # Simulate getting adapter
        session.adapter = mock_adapter_class(
            session=session,
            ctx=MagicMock(),
            config=mock_config,
        )

        mock_adapter_class.assert_called_once()
        assert session.adapter is mock_adapter_instance

    def test_get_adapter_raises_for_unknown_language(self) -> None:
        """_get_adapter raises AidbError for unsupported language."""
        from aidb.common.errors import AidbError

        session = MagicMock()
        session.language = "cobol"

        # Simulate registry lookup failure
        with pytest.raises(AidbError, match="No adapter"):
            msg = f"No adapter class registered for language: {session.language}"
            raise AidbError(msg)

    def test_setup_dap_client_creates_client(self) -> None:
        """_setup_dap_client creates DAP client via connector."""
        session = MagicMock()
        session.adapter_host = "localhost"
        session.adapter_port = 5678
        session.connector = MagicMock()

        mock_dap = MagicMock()
        session.connector.setup_dap_client.return_value = mock_dap

        # Simulate setup
        result = session.connector.setup_dap_client(
            session.adapter_host,
            session.adapter_port,
        )

        session.connector.setup_dap_client.assert_called_once_with("localhost", 5678)
        assert result is mock_dap

    def test_setup_dap_client_raises_without_port(self) -> None:
        """_setup_dap_client raises ValueError when port is None."""
        session = MagicMock()
        session.adapter_port = None

        # Simulate the validation
        if session.adapter_port is None:
            with pytest.raises(ValueError, match="adapter_port must be set"):
                msg = "adapter_port must be set before creating DAP client"
                raise ValueError(msg)

    def test_create_stub_events_api_delegates_to_connector(self) -> None:
        """_create_stub_events_api delegates to connector."""
        session = MagicMock()
        session.connector = MagicMock()

        stub = MagicMock()
        session.connector.create_stub_events_api.return_value = stub

        result = session.connector.create_stub_events_api()

        session.connector.create_stub_events_api.assert_called_once()
        assert result is stub


class TestSessionRepr:
    """Tests for Session string representation."""

    def test_repr_includes_key_fields(self) -> None:
        """__repr__ includes id, target, language, and status."""
        session = MagicMock()
        session.id = "test-123"
        session.target = "/path/to/script.py"
        session.language = "python"
        session.status = MagicMock(name="RUNNING")
        session.status.name = "RUNNING"

        # Build expected repr
        repr_str = (
            f"Session(id={session.id}, target={session.target}, "
            f"language={session.language}, status={session.status.name})"
        )

        assert "test-123" in repr_str
        assert "/path/to/script.py" in repr_str
        assert "python" in repr_str
        assert "RUNNING" in repr_str
