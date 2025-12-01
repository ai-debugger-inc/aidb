"""Unit tests for ChildSessionManager.

Tests child session creation, parent-child relationships, and session initialization for
multi-phase debugging scenarios.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.models import StartRequestType


@pytest.fixture
def mock_parent_session() -> MagicMock:
    """Create a mock parent session for child manager tests."""
    session = MagicMock()
    session.id = "parent-session-123"
    session.target = "/path/to/script.js"
    session.language = "javascript"
    session.breakpoints = []
    session.adapter = MagicMock()
    session.adapter.initialize_child_dap = AsyncMock()
    session.adapter_host = "localhost"
    session.adapter_port = 5678
    session.adapter_kwargs = {}
    session.child_session_ids = []
    session.ctx = MagicMock()
    session.connector = MagicMock()
    session.connector._dap = MagicMock()
    session.connector._dap._reverse_request_handler = MagicMock()
    session.connector._dap.set_session_creation_callback = MagicMock()

    return session


@pytest.fixture
def mock_event_bridge() -> MagicMock:
    """Create a mock event bridge."""
    bridge = MagicMock()
    bridge.register_child = AsyncMock()
    bridge.unregister_child = MagicMock()
    return bridge


@pytest.fixture
def child_manager(
    mock_event_bridge: MagicMock,
    mock_ctx: MagicMock,
):
    """Create a ChildSessionManager instance for testing."""
    from aidb.session.child_manager import ChildSessionManager

    return ChildSessionManager(
        event_bridge=mock_event_bridge,
        ctx=mock_ctx,
    )


class TestChildSessionCreation:
    """Tests for child session creation."""

    @pytest.mark.asyncio
    async def test_create_child_session_returns_id(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """create_child_session returns child session ID."""
        config = {
            "__pendingTargetId": "pending-123",
            "request": "attach",
            "name": "Child Session",
        }

        with patch.object(child_manager, "_create_session_instance") as mock_create:
            mock_child = MagicMock()
            mock_child.id = "child-session-456"
            mock_child.parent_session_id = mock_parent_session.id
            mock_child.language = "javascript"
            mock_create.return_value = mock_child

            with patch.object(
                child_manager, "_start_child_session", new_callable=AsyncMock
            ):
                with patch.object(child_manager, "_setup_parent_child_relationship"):
                    with patch.object(child_manager, "_register_with_registry"):
                        result = await child_manager.create_child_session(
                            mock_parent_session, config
                        )

        assert result == "child-session-456"

    @pytest.mark.asyncio
    async def test_create_child_session_sets_relationships(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """create_child_session sets up parent-child relationships."""
        config = {"__pendingTargetId": "pending-123"}

        with patch.object(child_manager, "_create_session_instance") as mock_create:
            mock_child = MagicMock()
            mock_child.id = "child-session-456"
            mock_child.parent_session_id = mock_parent_session.id
            mock_create.return_value = mock_child

            with patch.object(
                child_manager, "_start_child_session", new_callable=AsyncMock
            ):
                with patch.object(
                    child_manager, "_setup_parent_child_relationship"
                ) as mock_setup:
                    with patch.object(child_manager, "_register_with_registry"):
                        await child_manager.create_child_session(
                            mock_parent_session, config
                        )

        mock_setup.assert_called_once_with(mock_parent_session, mock_child)

    @pytest.mark.asyncio
    async def test_create_child_session_registers_with_bridge(
        self,
        child_manager,
        mock_parent_session: MagicMock,
        mock_event_bridge: MagicMock,
    ) -> None:
        """create_child_session registers child with event bridge."""
        config = {"__pendingTargetId": "pending-123"}

        with patch.object(child_manager, "_create_session_instance") as mock_create:
            mock_child = MagicMock()
            mock_child.id = "child-session-456"
            mock_child.parent_session_id = mock_parent_session.id
            mock_create.return_value = mock_child

            with patch.object(
                child_manager, "_start_child_session", new_callable=AsyncMock
            ):
                with patch.object(child_manager, "_setup_parent_child_relationship"):
                    with patch.object(child_manager, "_register_with_registry"):
                        await child_manager.create_child_session(
                            mock_parent_session, config
                        )

        mock_event_bridge.register_child.assert_called_once_with(
            mock_parent_session.id, "child-session-456"
        )

    @pytest.mark.asyncio
    async def test_create_child_session_raises_on_error(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """create_child_session raises RuntimeError on failure."""
        config = {"__pendingTargetId": "pending-123"}

        with patch.object(child_manager, "_create_session_instance") as mock_create:
            mock_create.side_effect = RuntimeError("Creation failed")

            with pytest.raises(RuntimeError, match="Child session creation failed"):
                await child_manager.create_child_session(mock_parent_session, config)


class TestChildSessionInstance:
    """Tests for _create_session_instance."""

    def test_create_session_instance_copies_target(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """_create_session_instance copies target from parent."""
        config = {"__pendingTargetId": "pending-123"}

        with patch("aidb.session.Session") as mock_session_class:
            mock_child = MagicMock()
            mock_session_class.return_value = mock_child

            child_manager._create_session_instance(mock_parent_session, config)

            call_kwargs = mock_session_class.call_args.kwargs
            assert call_kwargs["target"] == mock_parent_session.target

    def test_create_session_instance_copies_language(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """_create_session_instance copies language from parent."""
        config = {"__pendingTargetId": "pending-123"}

        with patch("aidb.session.Session") as mock_session_class:
            mock_child = MagicMock()
            mock_session_class.return_value = mock_child

            child_manager._create_session_instance(mock_parent_session, config)

            call_kwargs = mock_session_class.call_args.kwargs
            assert call_kwargs["language"] == mock_parent_session.language

    def test_create_session_instance_stores_pending_id(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """_create_session_instance stores __pendingTargetId."""
        config = {"__pendingTargetId": "pending-123"}

        with patch("aidb.session.Session") as mock_session_class:
            mock_child = MagicMock()
            mock_session_class.return_value = mock_child

            result = child_manager._create_session_instance(mock_parent_session, config)

            assert result._pending_target_id == "pending-123"

    def test_create_session_instance_copies_pending_breakpoints(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """_create_session_instance copies parent's pending breakpoints."""
        mock_parent_session._pending_child_breakpoints = [
            MagicMock(source="/file.js", line=10),
            MagicMock(source="/file.js", line=20),
        ]

        config = {"__pendingTargetId": "pending-123"}

        with patch("aidb.session.Session") as mock_session_class:
            mock_child = MagicMock()
            mock_session_class.return_value = mock_child

            child_manager._create_session_instance(mock_parent_session, config)

            call_kwargs = mock_session_class.call_args.kwargs
            assert len(call_kwargs["breakpoints"]) == 2

    def test_create_session_instance_sets_parent_id(
        self,
        child_manager,
        mock_parent_session: MagicMock,
    ) -> None:
        """_create_session_instance sets parent_session_id on child."""
        config = {"__pendingTargetId": "pending-123"}

        with patch("aidb.session.Session") as mock_session_class:
            mock_child = MagicMock()
            mock_session_class.return_value = mock_child

            child_manager._create_session_instance(mock_parent_session, config)

            call_kwargs = mock_session_class.call_args.kwargs
            assert call_kwargs["parent_session_id"] == mock_parent_session.id


class TestChildSessionRelationships:
    """Tests for parent-child relationship setup."""

    def test_setup_parent_child_relationship_sets_parent_id(
        self,
        child_manager,
    ) -> None:
        """_setup_parent_child_relationship sets parent_session_id on child."""
        mock_parent = MagicMock()
        mock_parent.id = "parent-123"
        mock_parent.child_session_ids = []

        mock_child = MagicMock()
        mock_child.id = "child-456"

        child_manager._setup_parent_child_relationship(mock_parent, mock_child)

        assert mock_child.parent_session_id == "parent-123"

    def test_setup_parent_child_relationship_adds_child_id(
        self,
        child_manager,
    ) -> None:
        """_setup_parent_child_relationship adds child ID to parent's list."""
        mock_parent = MagicMock()
        mock_parent.id = "parent-123"
        mock_parent.child_session_ids = []

        mock_child = MagicMock()
        mock_child.id = "child-456"

        child_manager._setup_parent_child_relationship(mock_parent, mock_child)

        assert "child-456" in mock_parent.child_session_ids


class TestChildSessionStart:
    """Tests for child session startup."""

    @pytest.mark.asyncio
    async def test_start_child_session_calls_language_handler(
        self,
        child_manager,
    ) -> None:
        """_start_child_session calls language-specific handler if available."""
        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"
        mock_child.language = "javascript"
        mock_child.state = MagicMock()
        mock_child.adapter = MagicMock()
        mock_child.adapter.initialize_child_dap = AsyncMock()

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)
        child_manager._handle_javascript_child = MagicMock()

        config = {"request": "attach"}

        await child_manager._start_child_session(
            mock_child, StartRequestType.ATTACH, config
        )

        child_manager._handle_javascript_child.assert_called_once_with(
            mock_child, mock_parent, config
        )

    @pytest.mark.asyncio
    async def test_start_child_session_uses_default_handler(
        self,
        child_manager,
    ) -> None:
        """_start_child_session uses default handler for unknown languages."""
        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"
        mock_child.language = "unknown"
        mock_child.state = MagicMock()
        mock_child.adapter = MagicMock()

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)

        config = {"request": "launch"}

        with patch.object(
            child_manager, "_handle_default_child"
        ) as mock_default_handler:
            with patch.object(
                child_manager, "_initialize_child_dap", new_callable=AsyncMock
            ):
                await child_manager._start_child_session(
                    mock_child, StartRequestType.LAUNCH, config
                )

        mock_default_handler.assert_called_once_with(mock_child, mock_parent, config)

    @pytest.mark.asyncio
    async def test_start_child_session_marks_initialized(
        self,
        child_manager,
    ) -> None:
        """_start_child_session marks child as initialized."""
        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"
        mock_child.language = "python"
        mock_child.state = MagicMock()

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)

        config = {"request": "attach"}

        with patch.object(child_manager, "_handle_default_child"):
            with patch.object(
                child_manager, "_initialize_child_dap", new_callable=AsyncMock
            ):
                await child_manager._start_child_session(
                    mock_child, StartRequestType.ATTACH, config
                )

        mock_child.state.set_initialized.assert_called_once_with(True)


class TestChildDefaultStart:
    """Tests for default child session start handler."""

    def test_handle_default_child_shares_adapter(
        self,
        child_manager,
    ) -> None:
        """_handle_default_child shares parent's adapter."""
        mock_child = MagicMock()
        mock_child.connector = MagicMock()
        mock_child.connector._dap = MagicMock()

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.connector = MagicMock()
        mock_parent.connector._dap = MagicMock()
        mock_parent.connector._dap._reverse_request_handler = MagicMock()

        config: dict[str, str] = {}

        child_manager._handle_default_child(mock_child, mock_parent, config)

        assert mock_child.adapter is mock_parent.adapter

    def test_handle_default_child_clears_adapter_process(
        self,
        child_manager,
    ) -> None:
        """_handle_default_child clears _adapter_process on child."""
        mock_child = MagicMock()

        mock_parent = MagicMock()
        mock_parent.connector = MagicMock()
        mock_parent.connector._dap = MagicMock()
        mock_parent.connector._dap._reverse_request_handler = None

        config: dict[str, str] = {}

        child_manager._handle_default_child(mock_child, mock_parent, config)

        assert mock_child._adapter_process is None


class TestChildLaunchArgs:
    """Tests for child launch argument building."""

    def test_build_child_launch_args_copies_config(
        self,
        child_manager,
    ) -> None:
        """_build_child_launch_args copies launch config."""
        mock_child = MagicMock()
        mock_child.adapter = None

        config = {
            "name": "Test",
            "request": "launch",
            "__pendingTargetId": "pending-123",
        }

        result = child_manager._build_child_launch_args(mock_child, config)

        assert "name" in result
        assert result["request"] == "launch"

    def test_build_child_attach_args_sets_request(
        self,
        child_manager,
    ) -> None:
        """_build_child_attach_args sets attach request type."""
        mock_child = MagicMock()

        config = {
            "request": "attach",
            "__pendingTargetId": "pending-123",
        }

        result = child_manager._build_child_attach_args(mock_child, config)

        assert result["request"] == "attach"

    def test_build_child_launch_args_calls_adapter_configure(
        self,
        child_manager,
    ) -> None:
        """_build_child_launch_args calls adapter.configure_child_launch."""
        mock_child = MagicMock()
        mock_child.adapter = MagicMock()
        mock_child.adapter.configure_child_launch = MagicMock()

        config = {"request": "launch"}

        child_manager._build_child_launch_args(mock_child, config)

        mock_child.adapter.configure_child_launch.assert_called_once()


class TestChildDapInitialization:
    """Tests for child DAP initialization."""

    @pytest.mark.asyncio
    async def test_initialize_child_dap_delegates_to_adapter(
        self,
        child_manager,
    ) -> None:
        """_initialize_child_dap delegates to parent's adapter."""
        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)

        config = {"request": "attach"}

        await child_manager._initialize_child_dap(
            mock_child, StartRequestType.ATTACH, config
        )

        mock_parent.adapter.initialize_child_dap.assert_called_once_with(
            mock_child, StartRequestType.ATTACH, config
        )

    @pytest.mark.asyncio
    async def test_initialize_child_dap_invokes_callback(
        self,
        child_manager,
    ) -> None:
        """_initialize_child_dap invokes on_child_created callback."""
        callback = MagicMock()
        child_manager._on_child_created_callback = callback

        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)

        await child_manager._initialize_child_dap(
            mock_child, StartRequestType.ATTACH, {}
        )

        callback.assert_called_once_with(mock_child)

    @pytest.mark.asyncio
    async def test_initialize_child_dap_handles_callback_error(
        self,
        child_manager,
        mock_ctx: MagicMock,
    ) -> None:
        """_initialize_child_dap handles callback errors gracefully."""
        callback = MagicMock(side_effect=RuntimeError("Callback failed"))
        child_manager._on_child_created_callback = callback

        mock_child = MagicMock()
        mock_child.id = "child-456"
        mock_child.parent_session_id = "parent-123"

        mock_parent = MagicMock()
        mock_parent.adapter = MagicMock()
        mock_parent.adapter.initialize_child_dap = AsyncMock()

        child_manager.registry.get_session = MagicMock(return_value=mock_parent)

        # Should not raise
        await child_manager._initialize_child_dap(
            mock_child, StartRequestType.ATTACH, {}
        )

        callback.assert_called_once_with(mock_child)
