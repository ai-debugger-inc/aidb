"""Unit tests for BreakpointService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.models import AidbBreakpointsResponse, SessionStatus
from aidb.service.breakpoints.manager import BreakpointService


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
    session.dap.get_next_seq = AsyncMock(return_value=1)

    # Mock breakpoint store
    session._breakpoint_store = {}
    session._update_breakpoints_from_response = AsyncMock()
    session._clear_breakpoints_for_source = MagicMock()

    # Mock adapter config
    session.adapter_config = MagicMock()
    session.adapter_config.supports_hit_condition = MagicMock(return_value=True)
    session.adapter_config.language = "python"

    # Mock supports methods
    session.supports_logpoints = MagicMock(return_value=True)
    session.supports_hit_conditional_breakpoints = MagicMock(return_value=True)

    # Mock registry
    session.registry = MagicMock()
    session.registry.get_session = MagicMock(return_value=None)

    return session


class TestBreakpointServiceInit:
    """Test BreakpointService initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that BreakpointService can be initialized with a session."""
        service = BreakpointService(mock_service_session, mock_ctx)

        assert service._session is mock_service_session
        assert service.ctx is mock_ctx


class TestBreakpointServiceSet:
    """Test BreakpointService.set method."""

    @pytest.mark.asyncio
    async def test_set_sends_request(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that set sends a SetBreakpointsRequest to DAP."""
        from aidb.dap.protocol.bodies import SetBreakpointsArguments
        from aidb.dap.protocol.requests import SetBreakpointsRequest
        from aidb.dap.protocol.types import Source, SourceBreakpoint

        # Configure mock response
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = [
            MagicMock(id=1, line=10, verified=True, message=None),
        ]
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        source = Source(path="/test/file.py")
        breakpoints = [SourceBreakpoint(line=10)]
        args = SetBreakpointsArguments(source=source, breakpoints=breakpoints)
        request = SetBreakpointsRequest(seq=1, arguments=args)

        result = await service.set(request)

        mock_service_session.dap.send_request.assert_called_once_with(request)
        assert isinstance(result, AidbBreakpointsResponse)


class TestBreakpointServiceClear:
    """Test BreakpointService.clear method."""

    @pytest.mark.asyncio
    async def test_clear_single_file(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test clearing breakpoints for a single file."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = []
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.clear(source_path="/test/file.py")

        mock_service_session.dap.send_request.assert_called_once()
        assert isinstance(result, AidbBreakpointsResponse)

    @pytest.mark.asyncio
    async def test_clear_all(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test clearing all breakpoints."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.clear(clear_all=True)

        assert isinstance(result, AidbBreakpointsResponse)

    @pytest.mark.asyncio
    async def test_clear_requires_argument(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that clear raises error without arguments."""
        service = BreakpointService(mock_service_session, mock_ctx)

        with pytest.raises(ValueError, match="Either source_path or clear_all"):
            await service.clear()


class TestBreakpointServiceRemove:
    """Test BreakpointService.remove method."""

    @pytest.mark.asyncio
    async def test_remove_single_breakpoint(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test removing a single breakpoint."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = []
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.remove(source_path="/test/file.py", line=10)

        mock_service_session.dap.send_request.assert_called_once()
        assert isinstance(result, AidbBreakpointsResponse)


class TestBreakpointServiceListAll:
    """Test BreakpointService.list_all method."""

    @pytest.mark.asyncio
    async def test_list_all_returns_breakpoints(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test listing all breakpoints."""
        mock_bp = MagicMock()
        mock_bp.source_path = "/test/file.py"
        mock_bp.line = 10
        mock_service_session._breakpoint_store = {"bp-1": mock_bp}

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.list_all()

        assert isinstance(result, AidbBreakpointsResponse)
        assert "bp-1" in result.breakpoints


class TestBreakpointServiceDataBreakpoints:
    """Test data breakpoint operations."""

    @pytest.mark.asyncio
    async def test_set_data_breakpoint(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test setting data breakpoints."""
        from aidb.dap.protocol.bodies import SetDataBreakpointsArguments
        from aidb.dap.protocol.requests import SetDataBreakpointsRequest

        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = []
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        args = SetDataBreakpointsArguments(breakpoints=[])
        request = SetDataBreakpointsRequest(seq=1, arguments=args)

        result = await service.set_data(request)

        mock_service_session.dap.send_request.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_clear_data_breakpoints(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test clearing data breakpoints."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.clear_data()

        mock_service_session.dap.send_request.assert_called_once()
        assert result.success is True


class TestBreakpointServiceFunctionBreakpoints:
    """Test function breakpoint operations."""

    @pytest.mark.asyncio
    async def test_set_function_breakpoint(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test setting function breakpoints."""
        from aidb.dap.protocol.bodies import SetFunctionBreakpointsArguments
        from aidb.dap.protocol.requests import SetFunctionBreakpointsRequest

        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = []
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        args = SetFunctionBreakpointsArguments(breakpoints=[])
        request = SetFunctionBreakpointsRequest(seq=1, arguments=args)

        result = await service.set_function(request)

        mock_service_session.dap.send_request.assert_called_once()
        assert result is not None

    @pytest.mark.asyncio
    async def test_clear_function_breakpoints(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test clearing function breakpoints."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = BreakpointService(mock_service_session, mock_ctx)

        result = await service.clear_function()

        mock_service_session.dap.send_request.assert_called_once()
        assert result.success is True
