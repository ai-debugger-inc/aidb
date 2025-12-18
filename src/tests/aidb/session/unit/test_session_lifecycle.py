"""Unit tests for SessionLifecycleMixin.

Tests session lifecycle operations including start, destroy, attach modes, and DAP event
subscription management.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.common.errors import AidbError
from aidb.models import (
    SessionStatus,
    StartRequestType,
    StartResponse,
)


class TestableLifecycleMixin:
    """Testable wrapper for SessionLifecycleMixin.

    Provides all required attributes for the mixin to function without needing the full
    Session class.
    """

    # Type stubs for dynamically copied methods from SessionLifecycleMixin
    start: Any
    destroy: Any
    wait_for_stop: Any
    _handle_attach_mode: Any
    _handle_launch_mode: Any
    _subscribe_to_termination: Any
    _on_terminate_event: Any
    _on_terminated_event: Any
    _unsubscribe_all_events: Any
    _setup_dap_client: Any
    _disconnect_dap_client: Any
    _launch_adapter_process: Any
    _stop_debug_session: Any
    _cleanup_resources: Any
    _destroy_child_sessions: Any
    _setup_breakpoint_event_subscription: Any
    _on_breakpoint_event: Any
    _on_loaded_source_event: Any
    _breakpoint_update_tasks: set[Any]

    # Type stubs for attributes set by fixture
    ctx: Any
    _id: str
    id: str
    target: str
    language: str
    adapter_port: int | None
    start_request_type: Any
    breakpoints: list[Any]
    args: list[str]
    adapter_kwargs: dict[str, Any]
    child_session_ids: list[str]
    started: bool
    _initialized: bool
    _pending_subscriptions: list[Any]
    _attach_params: Any
    _event_subscriptions: dict[str, Any]
    status: Any
    state: Any
    connector: Any
    adapter: Any
    debug: Any
    resource_manager: Any
    registry: Any
    dap: Any

    def __init__(self) -> None:
        from aidb.session.session_lifecycle import SessionLifecycleMixin

        # Copy mixin methods to this instance
        for attr in dir(SessionLifecycleMixin):
            if not attr.startswith("__"):
                method = getattr(SessionLifecycleMixin, attr)
                if callable(method):
                    setattr(self, attr, method.__get__(self, type(self)))


@pytest.fixture
def lifecycle_mixin(mock_ctx: MagicMock) -> TestableLifecycleMixin:
    """Create a testable SessionLifecycleMixin instance."""
    mixin = TestableLifecycleMixin()

    # Core attributes
    mixin.ctx = mock_ctx
    mixin._id = "test-session-123"
    mixin.id = "test-session-123"  # Also set the property version
    mixin.target = "/path/to/script.py"
    mixin.language = "python"
    mixin.adapter_port = 5678
    mixin.start_request_type = StartRequestType.LAUNCH
    mixin.breakpoints = []
    mixin.args = []
    mixin.adapter_kwargs = {}
    mixin.child_session_ids = []
    mixin.started = False
    mixin._initialized = False
    mixin._pending_subscriptions = []
    mixin._attach_params = None
    mixin._event_subscriptions = {}
    mixin.status = SessionStatus.INITIALIZING  # Add status property

    # State mock
    mixin.state = MagicMock()
    mixin.state.is_initialized = MagicMock(return_value=False)
    mixin.state.set_initialized = MagicMock()

    # Connector mock
    mixin.connector = MagicMock()
    mixin.connector._dap = MagicMock()
    mixin.connector._dap.events = MagicMock()
    mixin.connector._dap.events.subscribe_to_event = AsyncMock(return_value="sub-id")
    mixin.connector._dap.events.unsubscribe_from_event = AsyncMock()
    mixin.connector._dap.connect = AsyncMock()
    mixin.connector._dap.disconnect = AsyncMock()
    mixin.connector._dap.wait_for_stopped = AsyncMock(return_value=True)

    # Adapter mock
    mixin.adapter = MagicMock()
    mixin.adapter.launch = AsyncMock(return_value=(MagicMock(), 5678))
    mixin.adapter.attach = AsyncMock(return_value=(MagicMock(), 5678))
    mixin.adapter.stop = AsyncMock()
    mixin.adapter.config = MagicMock()
    mixin.adapter.config.get_initialization_sequence = MagicMock(return_value=[])

    # Debug operations mock
    mixin.debug = MagicMock()
    mixin.debug.start = AsyncMock(return_value=StartResponse(success=True))
    mixin.debug.stop = AsyncMock()

    # Resource manager mock
    mixin.resource_manager = MagicMock()
    mixin.resource_manager.cleanup_all_resources = AsyncMock(
        return_value={"terminated_processes": 0, "released_ports": 1}
    )

    # Registry mock
    mixin.registry = MagicMock()
    mixin.registry.get_session = MagicMock(return_value=None)
    mixin.registry.unregister_session = MagicMock()

    # Property for dap access
    mixin.dap = mixin.connector._dap

    # Setup method stub
    mixin._setup_dap_client = MagicMock()

    return mixin


class TestSessionLifecycleStart:
    """Tests for SessionLifecycleMixin.start()."""

    @pytest.mark.asyncio
    async def test_start_raises_if_already_initialized(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When session is already initialized, raise AidbError."""
        lifecycle_mixin.state.is_initialized.return_value = True

        with pytest.raises(AidbError, match="already been started"):
            await lifecycle_mixin.start()

    @pytest.mark.asyncio
    async def test_start_acquires_deferred_port_when_none(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When adapter_port is None, acquire port via PortRegistry."""
        lifecycle_mixin.adapter_port = None

        mock_port_registry_instance = MagicMock()
        mock_port_registry_instance.acquire_port = AsyncMock(return_value=9999)
        mock_port_registry = MagicMock(return_value=mock_port_registry_instance)

        mock_adapter_config = MagicMock()
        mock_adapter_config.default_dap_port = 5678
        mock_adapter_config.fallback_port_ranges = [(5680, 5700)]
        mock_adapter_registry_instance = MagicMock()
        mock_adapter_registry_instance.__getitem__ = MagicMock(
            return_value=mock_adapter_config
        )
        mock_adapter_registry = MagicMock(return_value=mock_adapter_registry_instance)

        # Also patch _handle_launch_mode to prevent it from resetting the port
        with (
            patch(
                "aidb.resources.ports.PortRegistry",
                mock_port_registry,
            ),
            patch(
                "aidb.session.adapter_registry.AdapterRegistry",
                mock_adapter_registry,
            ),
            patch.object(
                lifecycle_mixin,
                "_handle_launch_mode",
                new_callable=AsyncMock,
                return_value=StartResponse(success=True),
            ),
        ):
            result = await lifecycle_mixin.start()

        assert result.success is True
        assert lifecycle_mixin.adapter_port == 9999
        mock_port_registry_instance.acquire_port.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_sets_up_dap_client_if_missing(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When connector._dap is None, call _setup_dap_client."""
        lifecycle_mixin.connector._dap = None

        await lifecycle_mixin.start()

        lifecycle_mixin._setup_dap_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_handles_attach_mode_when_attach_params_present(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When _attach_params is set, delegate to _handle_attach_mode."""
        lifecycle_mixin._attach_params = {"host": "localhost", "port": 5678}

        with patch.object(
            lifecycle_mixin,
            "_handle_attach_mode",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True),
        ) as mock_attach:
            result = await lifecycle_mixin.start()

        mock_attach.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_handles_launch_mode_as_default(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When no _attach_params, delegate to _handle_launch_mode."""
        lifecycle_mixin._attach_params = None

        with patch.object(
            lifecycle_mixin,
            "_handle_launch_mode",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True, message="launched"),
        ) as mock_launch:
            result = await lifecycle_mixin.start()

        mock_launch.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_start_returns_failure_on_exception(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When exception occurs during start, return StartResponse(success=False)."""
        with patch.object(
            lifecycle_mixin,
            "_handle_launch_mode",
            new_callable=AsyncMock,
            side_effect=RuntimeError("something failed"),
        ):
            result = await lifecycle_mixin.start()

        assert result.success is False
        assert "Failed to start" in result.message

    @pytest.mark.asyncio
    async def test_start_sets_initialized_state(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify state.set_initialized(True) is called."""
        await lifecycle_mixin.start()

        lifecycle_mixin.state.set_initialized.assert_called_once_with(True)


class TestSessionLifecycleHandleLaunchMode:
    """Tests for SessionLifecycleMixin._handle_launch_mode()."""

    @pytest.mark.asyncio
    async def test_handle_launch_mode_delegates_to_launch_initializer(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _handle_launch_mode delegates to LaunchInitializer."""
        with patch(
            "aidb.session.utils.launch_initializer.LaunchInitializer.handle_launch_mode",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True),
        ) as mock_launch:
            result = await lifecycle_mixin._handle_launch_mode()

        mock_launch.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_launch_mode_passes_auto_wait_params(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify auto_wait and wait_timeout are passed to LaunchInitializer."""
        with patch(
            "aidb.session.utils.launch_initializer.LaunchInitializer.handle_launch_mode",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True),
        ) as mock_launch:
            await lifecycle_mixin._handle_launch_mode(
                auto_wait=True,
                wait_timeout=10.0,
            )

        mock_launch.assert_awaited_once_with(True, 10.0)

    @pytest.mark.asyncio
    async def test_handle_launch_mode_returns_failure_response(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify failure response is returned from LaunchInitializer."""
        with patch(
            "aidb.session.utils.launch_initializer.LaunchInitializer.handle_launch_mode",
            new_callable=AsyncMock,
            return_value=StartResponse(success=False, message="Launch failed"),
        ):
            result = await lifecycle_mixin._handle_launch_mode()

        assert result.success is False
        assert "Launch failed" in result.message


class TestSessionLifecycleBreakpointEventSubscription:
    """Tests for SessionLifecycleMixin._setup_breakpoint_event_subscription()."""

    @pytest.mark.asyncio
    async def test_setup_breakpoint_event_subscription_subscribes_all_events(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Subscribe to breakpoint, loadedSource, and terminated events."""
        # Clear any existing subscriptions
        lifecycle_mixin._event_subscriptions = {}

        # Mock required event handlers
        lifecycle_mixin._on_breakpoint_event = MagicMock()
        lifecycle_mixin._on_loaded_source_event = MagicMock()
        lifecycle_mixin._on_terminated_event = MagicMock()

        await lifecycle_mixin._setup_breakpoint_event_subscription()

        # Should have subscribed to 3 events
        assert lifecycle_mixin.dap.events.subscribe_to_event.await_count == 3
        assert "breakpoint" in lifecycle_mixin._event_subscriptions
        assert "loadedSource" in lifecycle_mixin._event_subscriptions
        assert "terminated" in lifecycle_mixin._event_subscriptions

    @pytest.mark.asyncio
    async def test_setup_breakpoint_event_subscription_is_idempotent(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When already subscribed, skip setup."""
        lifecycle_mixin._event_subscriptions = {"breakpoint": "existing-id"}

        await lifecycle_mixin._setup_breakpoint_event_subscription()

        # Should not subscribe again
        lifecycle_mixin.dap.events.subscribe_to_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_setup_breakpoint_event_subscription_handles_no_dap(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When DAP is not available, skip without error."""
        lifecycle_mixin._event_subscriptions = {}
        lifecycle_mixin.dap = None

        # Should not raise
        await lifecycle_mixin._setup_breakpoint_event_subscription()

    @pytest.mark.asyncio
    async def test_setup_breakpoint_event_subscription_handles_subscription_failure(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When subscription fails, log warning but don't raise."""
        lifecycle_mixin._event_subscriptions = {}
        lifecycle_mixin._on_breakpoint_event = MagicMock()
        lifecycle_mixin.dap.events.subscribe_to_event.side_effect = RuntimeError(
            "subscription failed"
        )

        # Should not raise
        await lifecycle_mixin._setup_breakpoint_event_subscription()

        # Warning should be logged
        lifecycle_mixin.ctx.warning.assert_called()


class TestSessionLifecycleDestroy:
    """Tests for SessionLifecycleMixin.destroy()."""

    @pytest.mark.asyncio
    async def test_destroy_delegates_to_shutdown_orchestrator(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify destroy delegates to SessionShutdownOrchestrator."""
        with patch(
            "aidb.session.utils.shutdown_orchestrator.SessionShutdownOrchestrator",
        ) as mock_orchestrator:
            mock_instance = MagicMock()
            mock_instance.execute_full_shutdown = AsyncMock()
            mock_orchestrator.return_value = mock_instance

            await lifecycle_mixin.destroy()

        mock_orchestrator.assert_called_once()
        mock_instance.execute_full_shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_unregisters_from_registry(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify registry.unregister_session is called after shutdown."""
        with patch(
            "aidb.session.utils.shutdown_orchestrator.SessionShutdownOrchestrator",
        ) as mock_orchestrator:
            mock_instance = MagicMock()
            mock_instance.execute_full_shutdown = AsyncMock()
            mock_orchestrator.return_value = mock_instance

            await lifecycle_mixin.destroy()

        lifecycle_mixin.registry.unregister_session.assert_called_once_with(
            lifecycle_mixin._id
        )

    @pytest.mark.asyncio
    async def test_destroy_raises_aidb_error_on_failure(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When destroy fails, wrap in AidbError."""
        with patch(
            "aidb.session.utils.shutdown_orchestrator.SessionShutdownOrchestrator",
        ) as mock_orchestrator:
            mock_instance = MagicMock()
            mock_instance.execute_full_shutdown = AsyncMock(
                side_effect=RuntimeError("shutdown failed"),
            )
            mock_orchestrator.return_value = mock_instance

            with pytest.raises(AidbError, match="Failed to destroy session"):
                await lifecycle_mixin.destroy()


class TestSessionLifecycleWaitForStop:
    """Tests for SessionLifecycleMixin.wait_for_stop()."""

    @pytest.mark.asyncio
    async def test_wait_for_stop_uses_dap_client(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify wait_for_stopped is called on DAP client."""
        lifecycle_mixin.id = lifecycle_mixin._id

        await lifecycle_mixin.wait_for_stop(timeout=3.0)

        lifecycle_mixin.connector._dap.wait_for_stopped.assert_awaited_once_with(3.0)

    @pytest.mark.asyncio
    async def test_wait_for_stop_raises_runtime_error_without_dap(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When no DAP client, raise RuntimeError."""
        lifecycle_mixin.id = lifecycle_mixin._id
        lifecycle_mixin.connector._dap = None

        with pytest.raises(RuntimeError, match="no DAP client"):
            await lifecycle_mixin.wait_for_stop()

    @pytest.mark.asyncio
    async def test_wait_for_stop_raises_timeout_error_on_timeout(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When wait returns False, raise TimeoutError."""
        lifecycle_mixin.id = lifecycle_mixin._id
        lifecycle_mixin.connector._dap.wait_for_stopped.return_value = False

        with pytest.raises(TimeoutError, match="did not reach stopped state"):
            await lifecycle_mixin.wait_for_stop(timeout=1.0)


class TestSessionLifecycleHandleAttachMode:
    """Tests for SessionLifecycleMixin._handle_attach_mode()."""

    @pytest.mark.asyncio
    async def test_handle_attach_mode_raises_without_params(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When _attach_params is None, raise AidbError."""
        lifecycle_mixin._attach_params = None

        with pytest.raises(AidbError, match="No attach parameters"):
            await lifecycle_mixin._handle_attach_mode()

    @pytest.mark.asyncio
    async def test_handle_attach_mode_delegates_to_host_port(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When host and port provided, delegate to AttachInitializer."""
        lifecycle_mixin._attach_params = {"host": "localhost", "port": 5678}

        with patch(
            "aidb.session.utils.attach_initializer.AttachInitializer.attach_to_host_port",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True),
        ) as mock_attach:
            result = await lifecycle_mixin._handle_attach_mode()

        mock_attach.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_attach_mode_delegates_to_pid(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When pid provided, delegate to AttachInitializer."""
        lifecycle_mixin._attach_params = {"pid": 12345}

        with patch(
            "aidb.session.utils.attach_initializer.AttachInitializer.attach_to_pid",
            new_callable=AsyncMock,
            return_value=StartResponse(success=True),
        ) as mock_attach:
            result = await lifecycle_mixin._handle_attach_mode()

        mock_attach.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_attach_mode_returns_failure_without_host_port_or_pid(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When neither host:port nor pid, return failure response."""
        lifecycle_mixin._attach_params = {"timeout": 10000}

        result = await lifecycle_mixin._handle_attach_mode()

        assert result.success is False
        assert "Attach failed" in result.message
