"""Unit tests for StackService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aidb.models import (
    AidbCallStackResponse,
    AidbExceptionResponse,
    AidbModulesResponse,
    AidbThreadsResponse,
    ExecutionStateResponse,
    SessionStatus,
)
from aidb.service.stack.navigator import StackService


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


class TestStackServiceInit:
    """Test StackService initialization."""

    def test_init_with_session(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that StackService can be initialized with a session."""
        service = StackService(mock_service_session, mock_ctx)

        assert service._session is mock_service_session
        assert service.ctx is mock_ctx


class TestStackServiceCallstack:
    """Test StackService.callstack method."""

    @pytest.mark.asyncio
    async def test_callstack_returns_frames(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting call stack for a thread."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()

        mock_frame = MagicMock()
        mock_frame.id = 0
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.column = 0
        mock_frame.source = MagicMock()
        mock_frame.source.path = "/test/file.py"
        mock_frame.source.name = "file.py"
        mock_response.body.stackFrames = [mock_frame]

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.callstack(thread_id=1)

        assert isinstance(result, AidbCallStackResponse)
        mock_service_session.dap.send_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_callstack_empty_frames(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test call stack with no frames."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.stackFrames = []

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.callstack(thread_id=1)

        assert isinstance(result, AidbCallStackResponse)
        assert result.frames == []


class TestStackServiceThreads:
    """Test StackService.threads method."""

    @pytest.mark.asyncio
    async def test_threads_returns_threads(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting all threads."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()

        mock_thread = MagicMock()
        mock_thread.id = 1
        mock_thread.name = "MainThread"
        mock_response.body.threads = [mock_thread]

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.threads()

        assert isinstance(result, AidbThreadsResponse)
        mock_service_session.dap.send_request.assert_called_once()


class TestStackServiceFrame:
    """Test StackService.frame method."""

    @pytest.mark.asyncio
    async def test_frame_returns_frame_info(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting frame information."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()

        mock_frame = MagicMock()
        mock_frame.id = 0
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.column = 0
        mock_frame.source = MagicMock()
        mock_frame.source.path = "/test/file.py"
        mock_frame.source.name = "file.py"
        mock_response.body.stackFrames = [mock_frame]

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.frame(frame_id=0)

        assert result is not None
        assert result.id == 0
        mock_service_session.dap.send_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_frame_not_found_raises_error(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test that ValueError is raised when frame not found."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.stackFrames = []

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        with pytest.raises(ValueError, match="Frame with ID 99 not found"):
            await service.frame(frame_id=99)


class TestStackServiceGetScopes:
    """Test StackService.get_scopes method."""

    @pytest.mark.asyncio
    async def test_get_scopes_returns_scopes(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting scopes for a frame."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()

        mock_scope = MagicMock()
        mock_scope.name = "Locals"
        mock_scope.variablesReference = 1
        mock_response.body.scopes = [mock_scope]

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_scopes(frame_id=0)

        assert len(result) == 1
        assert result[0].name == "Locals"

    @pytest.mark.asyncio
    async def test_get_scopes_empty(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting scopes when none exist."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.scopes = []

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_scopes(frame_id=0)

        assert result == []


class TestStackServiceException:
    """Test StackService.exception method."""

    @pytest.mark.asyncio
    async def test_exception_returns_info(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting exception information."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()
        mock_response.body.exceptionId = "RuntimeError"
        mock_response.body.description = "Test error"
        mock_response.body.breakMode = "always"
        mock_response.body.details = None

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.exception(thread_id=1)

        assert isinstance(result, AidbExceptionResponse)
        mock_service_session.dap.send_request.assert_called_once()


class TestStackServiceGetModules:
    """Test StackService.get_modules method."""

    @pytest.mark.asyncio
    async def test_get_modules_returns_modules(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting loaded modules."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = MagicMock()

        mock_module = MagicMock()
        mock_module.id = 1
        mock_module.name = "test_module"
        mock_module.path = "/test/module.py"
        mock_response.body.modules = [mock_module]
        mock_response.body.totalModules = 1

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_modules()

        assert isinstance(result, AidbModulesResponse)
        assert result.success is True
        assert len(result.modules) == 1

    @pytest.mark.asyncio
    async def test_get_modules_empty(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting modules when none exist."""
        mock_response = MagicMock()
        mock_response.ensure_success = MagicMock()
        mock_response.body = None

        mock_service_session.dap.send_request = AsyncMock(return_value=mock_response)

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_modules()

        assert result.success is False
        assert result.modules == []


class TestStackServiceGetExecutionState:
    """Test StackService.get_execution_state method."""

    @pytest.mark.asyncio
    async def test_get_execution_state_paused(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting execution state when paused."""
        mock_service_session.status = SessionStatus.PAUSED

        # Mock event processor state
        mock_processor = MagicMock()
        mock_processor._state = MagicMock()
        mock_processor._state.stop_reason = None
        mock_service_session.dap._event_processor = mock_processor

        # Mock stack trace response
        mock_stack_response = MagicMock()
        mock_stack_response.ensure_success = MagicMock()
        mock_stack_response.body = MagicMock()
        mock_frame = MagicMock()
        mock_frame.id = 0
        mock_frame.name = "main"
        mock_frame.line = 10
        mock_frame.column = 0
        mock_frame.source = MagicMock()
        mock_frame.source.path = "/test/file.py"
        mock_frame.source.name = "file.py"
        mock_stack_response.body.stackFrames = [mock_frame]

        mock_service_session.dap.send_request = AsyncMock(
            return_value=mock_stack_response,
        )

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_execution_state()

        assert isinstance(result, ExecutionStateResponse)
        assert result.success is True
        assert result.execution_state.paused is True

    @pytest.mark.asyncio
    async def test_get_execution_state_terminated(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting execution state when terminated."""
        mock_service_session.status = SessionStatus.TERMINATED

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_execution_state()

        assert isinstance(result, ExecutionStateResponse)
        assert result.success is True
        assert result.execution_state.terminated is True

    @pytest.mark.asyncio
    async def test_get_execution_state_running(
        self,
        mock_service_session: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test getting execution state when running."""
        mock_service_session.status = SessionStatus.RUNNING

        service = StackService(mock_service_session, mock_ctx)

        result = await service.get_execution_state()

        assert isinstance(result, ExecutionStateResponse)
        assert result.success is True
        assert result.execution_state.running is True
