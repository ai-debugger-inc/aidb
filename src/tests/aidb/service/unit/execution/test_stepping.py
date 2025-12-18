"""Unit tests for SteppingService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.models import ExecutionStateResponse, SessionStatus
from aidb.service.execution.stepping import (
    SteppingService,
    _convert_granularity,
)


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

    # Mock event processor
    session.dap._event_processor = MagicMock()
    session.dap._event_processor._state = MagicMock()
    session.dap._event_processor._state.current_thread_id = 1
    session.dap._event_processor._state.stop_reason = "step"

    # Mock has_capability
    session.has_capability = MagicMock(return_value=False)

    # Mock registry
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


class TestConvertGranularity:
    """Test _convert_granularity helper."""

    def test_returns_none_for_none(self) -> None:
        """Test that None input returns None."""
        assert _convert_granularity(None) is None

    def test_converts_valid_granularity(self) -> None:
        """Test that valid granularity strings are converted."""
        from aidb.dap.protocol.types import SteppingGranularity

        assert _convert_granularity("statement") == SteppingGranularity.STATEMENT
        assert _convert_granularity("line") == SteppingGranularity.LINE
        assert _convert_granularity("instruction") == SteppingGranularity.INSTRUCTION

    def test_defaults_to_statement_for_invalid(self) -> None:
        """Test that invalid values default to STATEMENT."""
        from aidb.dap.protocol.types import SteppingGranularity

        assert _convert_granularity("invalid") == SteppingGranularity.STATEMENT


class TestBuildTerminatedState:
    """Test _build_terminated_state method from BaseServiceComponent."""

    def test_builds_terminated_state(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that terminated state response is built correctly."""
        service = SteppingService(mock_service_session, mock_ctx)
        result = service._build_terminated_state()

        assert isinstance(result, ExecutionStateResponse)
        assert result.success is True
        assert result.execution_state is not None
        assert result.execution_state.terminated is True
        assert result.execution_state.status == SessionStatus.TERMINATED


class TestSteppingServiceInit:
    """Test SteppingService initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that SteppingService can be initialized with a session."""
        service = SteppingService(mock_service_session, mock_ctx)

        assert service._session is mock_service_session
        assert service.ctx is mock_ctx


class TestSteppingServiceStepInto:
    """Test SteppingService.step_into method."""

    @pytest.mark.asyncio
    async def test_step_into_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that step_into sends a StepInRequest to DAP."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)
        mock_service_session.dap.is_terminated = False

        service = SteppingService(mock_service_session, mock_ctx)

        result = await service.step_into(thread_id=1)

        # Verify stepping request was sent (first call)
        # Note: _build_stopped_execution_state sends additional requests (stackTrace)
        assert mock_service_session.dap.send_request.call_count >= 1
        first_call = mock_service_session.dap.send_request.call_args_list[0]
        assert first_call[0][0].command == "stepIn"

        assert isinstance(result, ExecutionStateResponse)


class TestSteppingServiceStepOver:
    """Test SteppingService.step_over method."""

    @pytest.mark.asyncio
    async def test_step_over_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that step_over sends a NextRequest to DAP."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)
        mock_service_session.dap.is_terminated = False

        service = SteppingService(mock_service_session, mock_ctx)

        result = await service.step_over(thread_id=1)

        # Verify stepping request was sent (first call)
        # Note: _build_stopped_execution_state sends additional requests (stackTrace)
        assert mock_service_session.dap.send_request.call_count >= 1
        first_call = mock_service_session.dap.send_request.call_args_list[0]
        assert first_call[0][0].command == "next"

        assert isinstance(result, ExecutionStateResponse)


class TestSteppingServiceStepOut:
    """Test SteppingService.step_out method."""

    @pytest.mark.asyncio
    async def test_step_out_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that step_out sends a StepOutRequest to DAP."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)
        mock_service_session.dap.is_terminated = False

        service = SteppingService(mock_service_session, mock_ctx)

        result = await service.step_out(thread_id=1)

        # Verify stepping request was sent (first call)
        # Note: _build_stopped_execution_state sends additional requests (stackTrace)
        assert mock_service_session.dap.send_request.call_count >= 1
        first_call = mock_service_session.dap.send_request.call_args_list[0]
        assert first_call[0][0].command == "stepOut"

        assert isinstance(result, ExecutionStateResponse)


class TestSteppingServiceTerminated:
    """Test stepping when session is terminated."""

    @pytest.mark.asyncio
    async def test_step_into_returns_terminated_when_session_terminated(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that step_into returns terminated state when session terminates."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)
        mock_service_session.dap.is_terminated = True

        service = SteppingService(mock_service_session, mock_ctx)

        result = await service.step_into(thread_id=1)

        assert result.success is True
        assert result.execution_state.terminated is True
        assert result.execution_state.status == SessionStatus.TERMINATED
