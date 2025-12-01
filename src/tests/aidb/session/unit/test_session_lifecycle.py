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
    async def test_handle_launch_mode_launches_adapter_process(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _launch_adapter_process is called."""
        with patch.object(
            lifecycle_mixin,
            "_launch_adapter_process",
            new_callable=AsyncMock,
        ) as mock_launch:
            await lifecycle_mixin._handle_launch_mode()

        mock_launch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_launch_mode_connects_dap(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify dap.connect() is called."""
        with patch.object(
            lifecycle_mixin,
            "_launch_adapter_process",
            new_callable=AsyncMock,
        ):
            await lifecycle_mixin._handle_launch_mode()

        lifecycle_mixin.dap.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_launch_mode_subscribes_to_breakpoint_events(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _setup_breakpoint_event_subscription is called."""
        with (
            patch.object(
                lifecycle_mixin,
                "_launch_adapter_process",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_setup_breakpoint_event_subscription",
                new_callable=AsyncMock,
            ) as mock_subscribe,
        ):
            await lifecycle_mixin._handle_launch_mode()

        mock_subscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_launch_mode_executes_init_sequence(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _execute_initialization_sequence is called with adapter sequence."""
        lifecycle_mixin.adapter.config.get_initialization_sequence.return_value = [
            "step1",
            "step2",
        ]

        with (
            patch.object(
                lifecycle_mixin,
                "_launch_adapter_process",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_execute_initialization_sequence",
                new_callable=AsyncMock,
            ) as mock_init,
        ):
            await lifecycle_mixin._handle_launch_mode()

        mock_init.assert_awaited_once_with(["step1", "step2"])

    @pytest.mark.asyncio
    async def test_handle_launch_mode_calls_debug_start_and_sets_started(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify debug.start() is called and started=True on success."""
        lifecycle_mixin.debug.start.return_value = StartResponse(success=True)

        with (
            patch.object(
                lifecycle_mixin,
                "_launch_adapter_process",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_execute_initialization_sequence",
                new_callable=AsyncMock,
            ),
        ):
            result = await lifecycle_mixin._handle_launch_mode()

        lifecycle_mixin.debug.start.assert_awaited_once()
        assert lifecycle_mixin.started is True
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_launch_mode_does_not_set_started_on_failure(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When debug.start() fails, started remains False."""
        lifecycle_mixin.debug.start.return_value = StartResponse(
            success=False,
            message="failed",
        )

        with (
            patch.object(
                lifecycle_mixin,
                "_launch_adapter_process",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_execute_initialization_sequence",
                new_callable=AsyncMock,
            ),
        ):
            result = await lifecycle_mixin._handle_launch_mode()

        assert lifecycle_mixin.started is False
        assert result.success is False


class TestSessionLifecycleLaunchAdapterProcess:
    """Tests for SessionLifecycleMixin._launch_adapter_process()."""

    @pytest.mark.asyncio
    async def test_launch_adapter_process_calls_adapter_launch(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """For launch request type, call adapter.launch()."""
        lifecycle_mixin.start_request_type = StartRequestType.LAUNCH
        lifecycle_mixin.adapter.launch.return_value = (MagicMock(), 5678)

        await lifecycle_mixin._launch_adapter_process()

        lifecycle_mixin.adapter.launch.assert_awaited_once_with(
            lifecycle_mixin.target,
            port=lifecycle_mixin.adapter_port,
            args=lifecycle_mixin.args,
            env=None,
            cwd=None,
        )

    @pytest.mark.asyncio
    async def test_launch_adapter_process_calls_adapter_attach(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """For attach request type, call adapter.attach()."""
        lifecycle_mixin.start_request_type = StartRequestType.ATTACH

        await lifecycle_mixin._launch_adapter_process()

        lifecycle_mixin.adapter.attach.assert_awaited_once_with(
            lifecycle_mixin.target,
        )

    @pytest.mark.asyncio
    async def test_launch_adapter_process_raises_on_unknown_request_type(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """For unknown request type, raise ValueError."""
        # Create a mock with an unknown value
        lifecycle_mixin.start_request_type = MagicMock()
        lifecycle_mixin.start_request_type.value = "unknown"

        with pytest.raises(ValueError, match="Unknown start request type"):
            await lifecycle_mixin._launch_adapter_process()

    @pytest.mark.asyncio
    async def test_launch_adapter_process_updates_port_if_changed(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When adapter returns different port, update adapter_port and recreate DAP."""
        lifecycle_mixin.adapter_port = 5678
        lifecycle_mixin.adapter.launch.return_value = (
            MagicMock(),
            9999,
        )  # Different port

        await lifecycle_mixin._launch_adapter_process()

        assert lifecycle_mixin.adapter_port == 9999
        assert lifecycle_mixin.connector._dap is None
        lifecycle_mixin._setup_dap_client.assert_called_once()


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
    async def test_destroy_cleans_up_child_sessions(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _destroy_child_sessions is called."""
        # Patch all the helper methods to isolate _destroy_child_sessions
        with (
            patch.object(
                lifecycle_mixin,
                "_destroy_child_sessions",
                new_callable=AsyncMock,
            ) as mock_destroy_children,
            patch.object(
                lifecycle_mixin,
                "_stop_debug_session",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_disconnect_dap_client",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_adapter",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_cleanup_resources",
                new_callable=AsyncMock,
            ),
        ):
            await lifecycle_mixin.destroy()

        mock_destroy_children.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_stops_debug_session(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _stop_debug_session is called."""
        with (
            patch.object(
                lifecycle_mixin,
                "_destroy_child_sessions",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_debug_session",
                new_callable=AsyncMock,
            ) as mock_stop,
            patch.object(
                lifecycle_mixin,
                "_disconnect_dap_client",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_adapter",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_cleanup_resources",
                new_callable=AsyncMock,
            ),
        ):
            await lifecycle_mixin.destroy()

        mock_stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_disconnects_dap_client(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify _disconnect_dap_client is called."""
        with (
            patch.object(
                lifecycle_mixin,
                "_destroy_child_sessions",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_debug_session",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_disconnect_dap_client",
                new_callable=AsyncMock,
            ) as mock_disconnect,
            patch.object(
                lifecycle_mixin,
                "_stop_adapter",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_cleanup_resources",
                new_callable=AsyncMock,
            ),
        ):
            await lifecycle_mixin.destroy()

        mock_disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_unregisters_from_registry(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify registry.unregister_session is called."""
        with (
            patch.object(
                lifecycle_mixin,
                "_destroy_child_sessions",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_debug_session",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_disconnect_dap_client",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_stop_adapter",
                new_callable=AsyncMock,
            ),
            patch.object(
                lifecycle_mixin,
                "_cleanup_resources",
                new_callable=AsyncMock,
            ),
        ):
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
        with patch.object(
            lifecycle_mixin,
            "_destroy_child_sessions",
            new_callable=AsyncMock,
            side_effect=RuntimeError("child cleanup failed"),
        ):
            with pytest.raises(AidbError, match="Failed to destroy session"):
                await lifecycle_mixin.destroy()


class TestSessionLifecycleDestroyChildSessions:
    """Tests for SessionLifecycleMixin._destroy_child_sessions()."""

    @pytest.mark.asyncio
    async def test_destroy_child_sessions_destroys_all_children(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When child sessions exist, destroy each one."""
        child1 = MagicMock()
        child1.destroy = AsyncMock()
        child2 = MagicMock()
        child2.destroy = AsyncMock()

        lifecycle_mixin.child_session_ids = ["child-1", "child-2"]
        lifecycle_mixin.registry.get_session.side_effect = [child1, child2]

        await lifecycle_mixin._destroy_child_sessions()

        child1.destroy.assert_awaited_once()
        child2.destroy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destroy_child_sessions_skips_missing_children(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When child is not in registry, skip it."""
        lifecycle_mixin.child_session_ids = ["child-1"]
        lifecycle_mixin.registry.get_session.return_value = None

        # Should not raise
        await lifecycle_mixin._destroy_child_sessions()


class TestSessionLifecycleStopDebugSession:
    """Tests for SessionLifecycleMixin._stop_debug_session()."""

    @pytest.mark.asyncio
    async def test_stop_debug_session_stops_when_running(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When session status is RUNNING, call debug.stop()."""
        session = MagicMock()
        session.status = SessionStatus.RUNNING

        await lifecycle_mixin._stop_debug_session(session)

        lifecycle_mixin.debug.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_debug_session_skips_when_not_running(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When session status is not RUNNING, skip stop."""
        session = MagicMock()
        session.status = SessionStatus.TERMINATED

        await lifecycle_mixin._stop_debug_session(session)

        lifecycle_mixin.debug.stop.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_debug_session_handles_stop_error(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When stop fails, log and continue."""
        session = MagicMock()
        session.status = SessionStatus.RUNNING
        lifecycle_mixin.debug.stop.side_effect = RuntimeError("stop failed")

        # Should not raise
        await lifecycle_mixin._stop_debug_session(session)

        lifecycle_mixin.ctx.debug.assert_called()


class TestSessionLifecycleDisconnectDapClient:
    """Tests for SessionLifecycleMixin._disconnect_dap_client()."""

    @pytest.mark.asyncio
    async def test_disconnect_dap_client_disconnects(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When DAP client exists, disconnect it."""
        await lifecycle_mixin._disconnect_dap_client()

        lifecycle_mixin.connector._dap.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_dap_client_handles_no_connector(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When connector is missing, skip without error."""
        del lifecycle_mixin.connector

        # Should not raise
        await lifecycle_mixin._disconnect_dap_client()

    @pytest.mark.asyncio
    async def test_disconnect_dap_client_handles_disconnect_error(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When disconnect fails, log and continue."""
        lifecycle_mixin.connector._dap.disconnect.side_effect = RuntimeError(
            "disconnect failed"
        )

        # Should not raise
        await lifecycle_mixin._disconnect_dap_client()

        lifecycle_mixin.ctx.debug.assert_called()


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


class TestSessionLifecycleCleanupResources:
    """Tests for SessionLifecycleMixin._cleanup_resources()."""

    @pytest.mark.asyncio
    async def test_cleanup_resources_awaits_pending_tasks(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify pending breakpoint tasks are awaited."""
        task = asyncio.create_task(asyncio.sleep(0))
        lifecycle_mixin._breakpoint_update_tasks = {task}

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = []
            await lifecycle_mixin._cleanup_resources()

        mock_gather.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_unsubscribes_from_events(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify event subscriptions are cleaned up."""
        lifecycle_mixin._breakpoint_update_tasks = set()
        lifecycle_mixin._event_subscriptions = {
            "breakpoint": "sub-1",
            "loadedSource": "sub-2",
        }

        await lifecycle_mixin._cleanup_resources()

        assert (
            lifecycle_mixin.connector._dap.events.unsubscribe_from_event.await_count
            == 2
        )
        assert lifecycle_mixin._event_subscriptions == {}

    @pytest.mark.asyncio
    async def test_cleanup_resources_uses_resource_manager(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """Verify resource_manager.cleanup_all_resources is called."""
        lifecycle_mixin._breakpoint_update_tasks = set()
        lifecycle_mixin._event_subscriptions = {}

        await lifecycle_mixin._cleanup_resources()

        lifecycle_mixin.resource_manager.cleanup_all_resources.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_resources_falls_back_to_port_registry(
        self,
        lifecycle_mixin: TestableLifecycleMixin,
    ) -> None:
        """When no resource_manager, use PortRegistry fallback."""
        lifecycle_mixin._breakpoint_update_tasks = set()
        lifecycle_mixin._event_subscriptions = {}
        lifecycle_mixin.resource_manager = None

        mock_port_registry = MagicMock()
        mock_port_registry.return_value.release_session_ports.return_value = [5678]

        # Patch in aidb.resources.ports since it's imported dynamically in the function
        with patch(
            "aidb.resources.ports.PortRegistry",
            mock_port_registry,
        ):
            await lifecycle_mixin._cleanup_resources()

        mock_port_registry.return_value.release_session_ports.assert_called_once_with(
            lifecycle_mixin._id
        )


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
        """When host and port provided, delegate to _attach_to_host_port."""
        lifecycle_mixin._attach_params = {"host": "localhost", "port": 5678}

        with patch.object(
            lifecycle_mixin,
            "_attach_to_host_port",
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
        """When pid provided, delegate to _attach_to_pid."""
        lifecycle_mixin._attach_params = {"pid": 12345}

        with patch.object(
            lifecycle_mixin,
            "_attach_to_pid",
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
