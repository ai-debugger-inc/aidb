"""Unit tests for ExecutionControl service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.models import ExecutionStateResponse, SessionStatus
from aidb.service.execution.control import ExecutionControl


@pytest.fixture
def mock_service_session(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock session for service tests.

    Returns
    -------
    MagicMock
        Mock session with DAP client and required attributes
    """
    session = MagicMock()
    session.id = "test-session-id"
    session.language = "python"
    session.is_child = False
    session.started = True
    session.ctx = mock_ctx
    session.child_session_ids = []
    session.status = SessionStatus.PAUSED

    # Mock DAP client
    session.dap = MagicMock()
    session.dap.send_request = AsyncMock()
    session.dap.is_terminated = False
    session.dap.get_next_seq = AsyncMock(return_value=1)
    session.dap.DEFAULT_WAIT_TIMEOUT = 30

    # Mock event processor
    session.dap._event_processor = MagicMock()
    session.dap._event_processor._state = MagicMock()
    session.dap._event_processor._state.current_thread_id = 1
    session.dap._event_processor._state.stop_reason = "breakpoint"

    # Mock events
    session.events = MagicMock()
    session.events.wait_for_stopped_or_terminated_async = AsyncMock(
        return_value="stopped",
    )

    # Mock adapter
    session.adapter = MagicMock()
    session.adapter.requires_child_session_wait = False
    session.adapter.config = MagicMock()
    session.adapter.config.terminate_request_timeout = 5

    # Mock info property
    session.info = MagicMock()

    # Mock registry
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


class TestExecutionControlInit:
    """Test ExecutionControl initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that ExecutionControl can be initialized with a session."""
        control = ExecutionControl(mock_service_session, mock_ctx)

        assert control._session is mock_service_session
        assert control.ctx is mock_ctx

    def test_init_uses_session_ctx_if_none_provided(
        self,
        mock_service_session: MagicMock,
    ) -> None:
        """Test that ExecutionControl uses session's context if none provided."""
        control = ExecutionControl(mock_service_session)

        assert control._session is mock_service_session
        assert control.ctx is mock_service_session.ctx


class TestExecutionControlSessionProperty:
    """Test ExecutionControl.session property."""

    def test_session_returns_session_when_not_child(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that session property returns the session when not a child."""
        mock_service_session.is_child = False
        mock_service_session.adapter.requires_child_session_wait = False

        control = ExecutionControl(mock_service_session, mock_ctx)

        assert control.session is mock_service_session

    def test_session_returns_session_when_is_child(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that session property returns self when session is already a child."""
        mock_service_session.is_child = True

        control = ExecutionControl(mock_service_session, mock_ctx)

        assert control.session is mock_service_session


class TestExecutionControlBuildTerminatedState:
    """Test ExecutionControl._build_terminated_state method."""

    def test_builds_terminated_state(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that _build_terminated_state returns proper terminated response."""
        control = ExecutionControl(mock_service_session, mock_ctx)

        result = control._build_terminated_state()

        assert isinstance(result, ExecutionStateResponse)
        assert result.success is True
        assert result.execution_state is not None
        assert result.execution_state.terminated is True
        assert result.execution_state.status == SessionStatus.TERMINATED


class TestExecutionControlContinue:
    """Test ExecutionControl.continue_ method."""

    @pytest.mark.asyncio
    async def test_continue_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that continue_ sends a continue request to DAP."""
        from aidb.dap.protocol.bodies import ContinueArguments
        from aidb.dap.protocol.requests import ContinueRequest

        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.success = True
        mock_response.body = MagicMock(allThreadsContinued=True)
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        control = ExecutionControl(mock_service_session, mock_ctx)

        request = ContinueRequest(
            seq=1,
            arguments=ContinueArguments(threadId=1),
        )

        # Mock from_dap class method
        with patch.object(
            ExecutionStateResponse,
            "from_dap",
            return_value=ExecutionStateResponse(success=True),
        ):
            result = await control.continue_(request, wait_for_stop=False)

        # Verify request was sent
        mock_service_session.dap.send_request.assert_called_once_with(request)
        assert result.success is True


class TestExecutionControlPause:
    """Test ExecutionControl.pause method."""

    @pytest.mark.asyncio
    async def test_pause_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that pause sends a pause request to DAP."""
        from aidb.dap.protocol.bodies import PauseArguments
        from aidb.dap.protocol.requests import PauseRequest

        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        control = ExecutionControl(mock_service_session, mock_ctx)

        request = PauseRequest(
            seq=1,
            arguments=PauseArguments(threadId=1),
        )

        # Mock from_dap
        with patch.object(
            ExecutionStateResponse,
            "from_dap",
            return_value=ExecutionStateResponse(success=True),
        ):
            result = await control.pause(request)

        mock_service_session.dap.send_request.assert_called_once_with(request)
        assert result.success is True
