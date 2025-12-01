"""Unit tests for adapter lifecycle hooks.

Tests hook registration, execution, context management, and the AdapterHooksMixin.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.adapters.base.hooks import (
    AdapterHooksMixin,
    HookContext,
    LifecycleHook,
    LifecycleHooks,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_adapter(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock adapter for hook testing."""
    adapter = MagicMock()
    adapter.ctx = mock_ctx
    adapter.session = MagicMock()
    adapter.session.id = "test-session-123"
    return adapter


@pytest.fixture
def lifecycle_hooks(mock_adapter: MagicMock) -> LifecycleHooks:
    """Create a LifecycleHooks instance for testing."""
    return LifecycleHooks(mock_adapter)


@pytest.fixture
def hook_context(mock_adapter: MagicMock) -> HookContext:
    """Create a HookContext instance for testing."""
    return HookContext(
        adapter=mock_adapter,
        session=mock_adapter.session,
        data={"key": "value"},
    )


# =============================================================================
# TestLifecycleHook
# =============================================================================


class TestLifecycleHook:
    """Tests for LifecycleHook enum."""

    def test_pre_initialize_value(self) -> None:
        """Test PRE_INITIALIZE hook value."""
        assert LifecycleHook.PRE_INITIALIZE.value == "pre_initialize"

    def test_post_initialize_value(self) -> None:
        """Test POST_INITIALIZE hook value."""
        assert LifecycleHook.POST_INITIALIZE.value == "post_initialize"

    def test_pre_launch_value(self) -> None:
        """Test PRE_LAUNCH hook value."""
        assert LifecycleHook.PRE_LAUNCH.value == "pre_launch"

    def test_post_launch_value(self) -> None:
        """Test POST_LAUNCH hook value."""
        assert LifecycleHook.POST_LAUNCH.value == "post_launch"

    def test_pre_attach_value(self) -> None:
        """Test PRE_ATTACH hook value."""
        assert LifecycleHook.PRE_ATTACH.value == "pre_attach"

    def test_post_attach_value(self) -> None:
        """Test POST_ATTACH hook value."""
        assert LifecycleHook.POST_ATTACH.value == "post_attach"

    def test_pre_stop_value(self) -> None:
        """Test PRE_STOP hook value."""
        assert LifecycleHook.PRE_STOP.value == "pre_stop"

    def test_post_stop_value(self) -> None:
        """Test POST_STOP hook value."""
        assert LifecycleHook.POST_STOP.value == "post_stop"

    def test_custom_value(self) -> None:
        """Test CUSTOM hook value."""
        assert LifecycleHook.CUSTOM.value == "custom"


# =============================================================================
# TestHookContext
# =============================================================================


class TestHookContext:
    """Tests for HookContext class."""

    def test_init_with_defaults(self, mock_adapter: MagicMock) -> None:
        """Test HookContext initialization with defaults."""
        ctx = HookContext(
            adapter=mock_adapter,
            session=mock_adapter.session,
        )

        assert ctx.adapter is mock_adapter
        assert ctx.session is mock_adapter.session
        assert ctx.data == {}
        assert ctx.cancelled is False
        assert ctx.result is None

    def test_init_with_data(self, mock_adapter: MagicMock) -> None:
        """Test HookContext initialization with data."""
        data = {"target": "/path/to/file.py", "port": 5678}
        ctx = HookContext(
            adapter=mock_adapter,
            session=mock_adapter.session,
            data=data,
        )

        assert ctx.data == data
        assert ctx.data["target"] == "/path/to/file.py"

    def test_cancelled_can_be_set(self, hook_context: HookContext) -> None:
        """Test cancelled flag can be modified."""
        assert hook_context.cancelled is False

        hook_context.cancelled = True

        assert hook_context.cancelled is True

    def test_result_can_be_set(self, hook_context: HookContext) -> None:
        """Test result can be modified."""
        assert hook_context.result is None

        hook_context.result = "Operation cancelled: file not found"

        assert hook_context.result == "Operation cancelled: file not found"

    def test_data_can_be_modified(self, hook_context: HookContext) -> None:
        """Test data can be modified by hooks."""
        hook_context.data["new_key"] = "new_value"
        hook_context.data["key"] = "modified_value"

        assert hook_context.data["new_key"] == "new_value"
        assert hook_context.data["key"] == "modified_value"


# =============================================================================
# TestLifecycleHooksInit
# =============================================================================


class TestLifecycleHooksInit:
    """Tests for LifecycleHooks initialization."""

    def test_init_sets_adapter(self, mock_adapter: MagicMock) -> None:
        """Test initialization sets adapter reference."""
        hooks = LifecycleHooks(mock_adapter)

        assert hooks.adapter is mock_adapter

    def test_init_sets_session(self, mock_adapter: MagicMock) -> None:
        """Test initialization sets session reference."""
        hooks = LifecycleHooks(mock_adapter)

        assert hooks.session is mock_adapter.session

    def test_init_hooks_empty(self, mock_adapter: MagicMock) -> None:
        """Test initialization creates empty hooks dict."""
        hooks = LifecycleHooks(mock_adapter)

        assert hooks._hooks == {}

    def test_init_enabled_by_default(self, mock_adapter: MagicMock) -> None:
        """Test hooks are enabled by default."""
        hooks = LifecycleHooks(mock_adapter)

        assert hooks._enabled is True


# =============================================================================
# TestLifecycleHooksRegister
# =============================================================================


class TestLifecycleHooksRegister:
    """Tests for hook registration."""

    def test_register_sync_callback(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test registering a synchronous callback."""

        def sync_callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, sync_callback)

        assert LifecycleHook.PRE_LAUNCH.value in lifecycle_hooks._hooks
        assert len(lifecycle_hooks._hooks[LifecycleHook.PRE_LAUNCH.value]) == 1

    def test_register_async_callback(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test registering an async callback."""

        async def async_callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.POST_LAUNCH, async_callback)

        assert LifecycleHook.POST_LAUNCH.value in lifecycle_hooks._hooks
        assert len(lifecycle_hooks._hooks[LifecycleHook.POST_LAUNCH.value]) == 1

    def test_register_with_priority(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test registering with custom priority."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback, priority=10)

        hook_entry = lifecycle_hooks._hooks[LifecycleHook.PRE_LAUNCH.value][0]
        assert hook_entry[0] == 10  # Priority

    def test_register_multiple_callbacks_sorted_by_priority(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test multiple callbacks are sorted by priority."""

        def low_priority(ctx: HookContext) -> None:
            pass

        def high_priority(ctx: HookContext) -> None:
            pass

        def medium_priority(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, low_priority, priority=80)
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, high_priority, priority=10)
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, medium_priority, priority=50)

        hooks = lifecycle_hooks._hooks[LifecycleHook.PRE_LAUNCH.value]
        priorities = [h[0] for h in hooks]

        assert priorities == [10, 50, 80]

    def test_register_default_priority_is_50(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test default priority is 50."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)

        hook_entry = lifecycle_hooks._hooks[LifecycleHook.PRE_LAUNCH.value][0]
        assert hook_entry[0] == 50


# =============================================================================
# TestLifecycleHooksExecute
# =============================================================================


class TestLifecycleHooksExecute:
    """Tests for hook execution."""

    @pytest.mark.asyncio
    async def test_execute_returns_context(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute returns HookContext."""
        context = await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert isinstance(context, HookContext)

    @pytest.mark.asyncio
    async def test_execute_passes_data_to_context(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute passes data to context."""
        data = {"target": "test.py"}

        context = await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH, data=data)

        assert context.data == data

    @pytest.mark.asyncio
    async def test_execute_calls_sync_callback(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute calls synchronous callbacks."""
        called = []

        def callback(ctx: HookContext) -> None:
            called.append("sync")

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)

        await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert called == ["sync"]

    @pytest.mark.asyncio
    async def test_execute_calls_async_callback(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute calls async callbacks."""
        called = []

        async def callback(ctx: HookContext) -> None:
            called.append("async")

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)

        await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert called == ["async"]

    @pytest.mark.asyncio
    async def test_execute_respects_priority_order(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test callbacks are executed in priority order."""
        order = []

        def first(ctx: HookContext) -> None:
            order.append("first")

        def second(ctx: HookContext) -> None:
            order.append("second")

        def third(ctx: HookContext) -> None:
            order.append("third")

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, third, priority=90)
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, first, priority=10)
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, second, priority=50)

        await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_execute_stops_when_cancelled(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute stops when context is cancelled."""
        order = []

        def first(ctx: HookContext) -> None:
            order.append("first")
            ctx.cancelled = True

        def second(ctx: HookContext) -> None:
            order.append("second")

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, first, priority=10)
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, second, priority=50)

        context = await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert order == ["first"]
        assert context.cancelled is True

    @pytest.mark.asyncio
    async def test_execute_skips_when_disabled(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute skips hooks when disabled."""
        called = []

        def callback(ctx: HookContext) -> None:
            called.append("called")

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)
        lifecycle_hooks.disable()

        await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert called == []

    @pytest.mark.asyncio
    async def test_execute_returns_context_when_no_hooks(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute returns context even when no hooks registered."""
        context = await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        assert isinstance(context, HookContext)
        assert context.cancelled is False

    @pytest.mark.asyncio
    async def test_execute_handles_callback_exception(
        self,
        lifecycle_hooks: LifecycleHooks,
        mock_ctx: MagicMock,
    ) -> None:
        """Test execute handles callback exceptions gracefully."""

        def failing_callback(ctx: HookContext) -> None:
            msg = "Test error"
            raise ValueError(msg)

        def second_callback(ctx: HookContext) -> None:
            ctx.data["reached"] = True

        lifecycle_hooks.register(
            LifecycleHook.PRE_LAUNCH, failing_callback, priority=50
        )
        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, second_callback, priority=60)

        context = await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)

        mock_ctx.warning.assert_called()
        assert context.data.get("reached") is True

    @pytest.mark.asyncio
    async def test_execute_raises_on_critical_hook_exception(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test execute raises when critical priority hook fails."""

        def critical_callback(ctx: HookContext) -> None:
            msg = "Critical error"
            raise ValueError(msg)

        lifecycle_hooks.register(
            LifecycleHook.PRE_LAUNCH,
            critical_callback,
            priority=5,  # Critical priority (< 10)
        )

        with pytest.raises(ValueError, match="Critical error"):
            await lifecycle_hooks.execute(LifecycleHook.PRE_LAUNCH)


# =============================================================================
# TestLifecycleHooksClear
# =============================================================================


class TestLifecycleHooksClear:
    """Tests for clearing hooks."""

    def test_clear_specific_hook(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test clearing a specific hook point."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)
        lifecycle_hooks.register(LifecycleHook.POST_LAUNCH, callback)

        lifecycle_hooks.clear(LifecycleHook.PRE_LAUNCH)

        assert LifecycleHook.PRE_LAUNCH.value not in lifecycle_hooks._hooks
        assert LifecycleHook.POST_LAUNCH.value in lifecycle_hooks._hooks

    def test_clear_all_hooks(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test clearing all hooks."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)
        lifecycle_hooks.register(LifecycleHook.POST_LAUNCH, callback)

        lifecycle_hooks.clear()

        assert lifecycle_hooks._hooks == {}

    def test_clear_nonexistent_hook(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test clearing a hook that doesn't exist."""
        lifecycle_hooks.clear(LifecycleHook.PRE_LAUNCH)


# =============================================================================
# TestLifecycleHooksEnableDisable
# =============================================================================


class TestLifecycleHooksEnableDisable:
    """Tests for enable/disable functionality."""

    def test_disable_sets_enabled_false(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test disable sets _enabled to False."""
        lifecycle_hooks.disable()

        assert lifecycle_hooks._enabled is False

    def test_enable_sets_enabled_true(self, lifecycle_hooks: LifecycleHooks) -> None:
        """Test enable sets _enabled to True."""
        lifecycle_hooks.disable()
        lifecycle_hooks.enable()

        assert lifecycle_hooks._enabled is True


# =============================================================================
# TestLifecycleHooksHasHooks
# =============================================================================


class TestLifecycleHooksHasHooks:
    """Tests for has_hooks method."""

    def test_has_hooks_returns_false_when_empty(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test has_hooks returns False when no hooks registered."""
        assert lifecycle_hooks.has_hooks(LifecycleHook.PRE_LAUNCH) is False

    def test_has_hooks_returns_true_when_registered(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test has_hooks returns True when hooks are registered."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)

        assert lifecycle_hooks.has_hooks(LifecycleHook.PRE_LAUNCH) is True

    def test_has_hooks_false_after_clear(
        self,
        lifecycle_hooks: LifecycleHooks,
    ) -> None:
        """Test has_hooks returns False after clearing."""

        def callback(ctx: HookContext) -> None:
            pass

        lifecycle_hooks.register(LifecycleHook.PRE_LAUNCH, callback)
        lifecycle_hooks.clear(LifecycleHook.PRE_LAUNCH)

        assert lifecycle_hooks.has_hooks(LifecycleHook.PRE_LAUNCH) is False


# =============================================================================
# TestAdapterHooksMixin
# =============================================================================


class TestableHooksMixin(AdapterHooksMixin):
    """Testable wrapper for AdapterHooksMixin."""

    def __init__(self, mock_adapter: MagicMock) -> None:
        # Set required attributes before calling super().__init__
        self.ctx = mock_adapter.ctx
        self.session = mock_adapter.session
        # Call mixin init
        super().__init__()


class TestAdapterHooksMixin:
    """Tests for AdapterHooksMixin."""

    def test_mixin_creates_hooks_instance(self, mock_adapter: MagicMock) -> None:
        """Test mixin creates LifecycleHooks instance."""
        mixin = TestableHooksMixin(mock_adapter)

        assert hasattr(mixin, "hooks")
        assert isinstance(mixin.hooks, LifecycleHooks)

    def test_register_hook_delegates_to_hooks(self, mock_adapter: MagicMock) -> None:
        """Test register_hook delegates to hooks.register."""
        mixin = TestableHooksMixin(mock_adapter)

        def callback(ctx: HookContext) -> None:
            pass

        mixin.register_hook(LifecycleHook.PRE_LAUNCH, callback, priority=25)

        assert mixin.hooks.has_hooks(LifecycleHook.PRE_LAUNCH)

    @pytest.mark.asyncio
    async def test_execute_hook_delegates_to_hooks(
        self,
        mock_adapter: MagicMock,
    ) -> None:
        """Test execute_hook delegates to hooks.execute."""
        mixin = TestableHooksMixin(mock_adapter)

        context = await mixin.execute_hook(LifecycleHook.PRE_LAUNCH, {"key": "value"})

        assert isinstance(context, HookContext)
        assert context.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_post_launch_hook_raises_on_cancel(
        self,
        mock_adapter: MagicMock,
    ) -> None:
        """Test post_launch_hook raises when cancelled."""
        mixin = TestableHooksMixin(mock_adapter)

        def cancel_hook(ctx: HookContext) -> None:
            ctx.cancelled = True
            ctx.result = "Cancelled for testing"

        mixin.register_hook(LifecycleHook.POST_LAUNCH, cancel_hook)

        with pytest.raises(RuntimeError, match="Cancelled for testing"):
            await mixin.post_launch_hook(MagicMock(), 5678)

    @pytest.mark.asyncio
    async def test_pre_stop_hook_logs_on_cancel(
        self,
        mock_adapter: MagicMock,
    ) -> None:
        """Test pre_stop_hook logs warning when cancelled."""
        mixin = TestableHooksMixin(mock_adapter)

        def cancel_hook(ctx: HookContext) -> None:
            ctx.cancelled = True

        mixin.register_hook(LifecycleHook.PRE_STOP, cancel_hook)

        await mixin.pre_stop_hook()

        mock_adapter.ctx.warning.assert_called()

    @pytest.mark.asyncio
    async def test_on_attach_hook_executes(self, mock_adapter: MagicMock) -> None:
        """Test on_attach_hook executes POST_ATTACH hooks."""
        mixin = TestableHooksMixin(mock_adapter)
        called = []

        def attach_hook(ctx: HookContext) -> None:
            called.append(ctx.data.get("pid"))

        mixin.register_hook(LifecycleHook.POST_ATTACH, attach_hook)

        await mixin.on_attach_hook(9999)

        assert called == [9999]
