"""Unit tests for DebugService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.models import SessionStatus
from aidb.service.breakpoints import BreakpointService
from aidb.service.debug_service import DebugService
from aidb.service.execution import ExecutionControl, SteppingService
from aidb.service.stack import StackService
from aidb.service.variables import VariableService


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
    session._frame_cache = {"thread_id": 1, "frame_id": 0}

    # Mock DAP client
    session.dap = MagicMock()
    session.dap.send_request = AsyncMock()
    session.dap.get_next_seq = AsyncMock(return_value=1)

    # Mock capabilities
    session.has_capability = MagicMock(return_value=True)

    # Mock registry
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


class TestDebugServiceInit:
    """Test DebugService initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that DebugService can be initialized with a session."""
        service = DebugService(mock_service_session, mock_ctx)

        assert service._session is mock_service_session
        assert service.ctx is mock_ctx

    def test_init_uses_session_context_if_not_provided(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that DebugService uses session's context if none provided."""
        mock_service_session.ctx = mock_ctx

        service = DebugService(mock_service_session)

        assert service.ctx is mock_ctx

    def test_session_property(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that session property returns the underlying session."""
        service = DebugService(mock_service_session, mock_ctx)

        assert service.session is mock_service_session


class TestDebugServiceSubServices:
    """Test DebugService sub-service initialization."""

    def test_execution_service_initialized(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that execution service is properly initialized."""
        service = DebugService(mock_service_session, mock_ctx)

        assert isinstance(service.execution, ExecutionControl)
        assert service.execution._session is mock_service_session

    def test_stepping_service_initialized(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that stepping service is properly initialized."""
        service = DebugService(mock_service_session, mock_ctx)

        assert isinstance(service.stepping, SteppingService)
        assert service.stepping._session is mock_service_session

    def test_breakpoints_service_initialized(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that breakpoints service is properly initialized."""
        service = DebugService(mock_service_session, mock_ctx)

        assert isinstance(service.breakpoints, BreakpointService)
        assert service.breakpoints._session is mock_service_session

    def test_variables_service_initialized(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that variables service is properly initialized."""
        service = DebugService(mock_service_session, mock_ctx)

        assert isinstance(service.variables, VariableService)
        assert service.variables._session is mock_service_session

    def test_stack_service_initialized(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that stack service is properly initialized."""
        service = DebugService(mock_service_session, mock_ctx)

        assert isinstance(service.stack, StackService)
        assert service.stack._session is mock_service_session


class TestDebugServiceIntegration:
    """Test DebugService can access sub-service methods."""

    @pytest.mark.asyncio
    async def test_can_call_execution_continue(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that execution continue can be called through DebugService."""
        from aidb.dap.protocol.bodies import ContinueArguments
        from aidb.dap.protocol.requests import ContinueRequest

        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.allThreadsContinued = True
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = DebugService(mock_service_session, mock_ctx)

        # Create proper request
        request = ContinueRequest(seq=0, arguments=ContinueArguments(threadId=1))

        # Should not raise
        await service.execution.continue_(request)
        mock_service_session.dap.send_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_can_call_stepping_step_over(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that stepping operations can be called through DebugService."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = DebugService(mock_service_session, mock_ctx)

        await service.stepping.step_over(thread_id=1)
        mock_service_session.dap.send_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_can_call_breakpoints_list_all(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that breakpoint operations can be called through DebugService."""
        mock_service_session._breakpoint_store = {}

        service = DebugService(mock_service_session, mock_ctx)

        result = await service.breakpoints.list_all()
        assert result is not None

    @pytest.mark.asyncio
    async def test_can_call_variables_evaluate(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that variable operations can be called through DebugService."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.result = "42"
        mock_response.body.type = "int"
        mock_response.body.variablesReference = 0
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = DebugService(mock_service_session, mock_ctx)

        result = await service.variables.evaluate("2 + 40", frame_id=0)
        assert result.result == "42"

    @pytest.mark.asyncio
    async def test_can_call_stack_threads(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that stack operations can be called through DebugService."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.threads = []
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = DebugService(mock_service_session, mock_ctx)

        result = await service.stack.threads()
        assert result is not None
