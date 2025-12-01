"""Lifecycle hooks system for debug adapters.

This module provides a hook-based extension system that allows adapters to customize
behavior at specific lifecycle points without overriding entire methods.
"""

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
)

from aidb.patterns.base import Obj

if TYPE_CHECKING:
    from aidb.adapters.base.adapter import DebugAdapter
    from aidb.interfaces import ISession


class LifecycleHook(Enum):
    """Predefined lifecycle hooks in the adapter lifecycle."""

    # Initialization hooks
    PRE_INITIALIZE = "pre_initialize"
    POST_INITIALIZE = "post_initialize"

    # Launch/Attach hooks
    PRE_LAUNCH = "pre_launch"
    POST_LAUNCH = "post_launch"
    PRE_ATTACH = "pre_attach"
    POST_ATTACH = "post_attach"

    # AidbBreakpoint hooks
    PRE_SET_BREAKPOINTS = "pre_set_breakpoints"
    POST_SET_BREAKPOINTS = "post_set_breakpoints"

    # Configuration hooks
    PRE_CONFIGURATION_DONE = "pre_configuration_done"
    POST_CONFIGURATION_DONE = "post_configuration_done"

    # Process lifecycle hooks
    PRE_STOP = "pre_stop"
    POST_STOP = "post_stop"
    PRE_CLEANUP = "pre_cleanup"
    POST_CLEANUP = "post_cleanup"

    # Custom adapter hooks
    CUSTOM = "custom"


class HookContext:
    """Context object passed to hook callbacks.

    Provides access to adapter state and allows hooks to modify behavior.

    Attributes
    ----------
    adapter : DebugAdapter
        The adapter instance
    session : ISession
        The debug session
    data : Dict[str, Any]
        Hook-specific data that can be read/modified
    cancelled : bool
        If set to True, cancels the operation
    result : Any
        Can be set to override the operation result. When `cancelled` is True,
        this should contain a descriptive error message string explaining why
        the operation was cancelled. This message will be shown to the user
        instead of a generic "cancelled by hook" message.
    """

    def __init__(
        self,
        adapter: "DebugAdapter",
        session: "ISession",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Initialize hook context.

        Parameters
        ----------
        adapter : DebugAdapter
            The adapter instance
        session : ISession
            The debug session
        data : Dict[str, Any], optional
            Initial context data
        """
        self.adapter = adapter
        self.session = session
        self.data = data or {}
        self.cancelled: bool = False
        self.result: Any = None


class LifecycleHooks(Obj):
    """Manages lifecycle hooks for debug adapters.

    This class provides a centralized hook registry and execution system that
    allows adapters to register callbacks for specific lifecycle events.

    Parameters
    ----------
    adapter : DebugAdapter
        The adapter instance
    """

    def __init__(self, adapter: "DebugAdapter") -> None:
        """Initialize the lifecycle hooks manager.

        Parameters
        ----------
        adapter : DebugAdapter
            The adapter instance to manage hooks for
        """
        super().__init__(ctx=adapter.ctx)
        self.adapter = adapter
        self.session = adapter.session
        self._hooks: dict[
            str,
            list[
                tuple[
                    int,
                    Callable[[HookContext], None]
                    | Callable[[HookContext], Awaitable[None]],
                ]
            ],
        ] = {}
        self._enabled = True

    def register(
        self,
        hook_point: LifecycleHook,
        callback: Callable[[HookContext], None]
        | Callable[[HookContext], Awaitable[None]],
        priority: int = 50,
    ) -> None:
        """Register a hook callback for a specific lifecycle point.

        Callbacks are executed in priority order (lower values first).

        Parameters
        ----------
        hook_point : LifecycleHook
            The lifecycle point to hook into
        callback : Callable[[HookContext], None] |
            Callable[[HookContext], Awaitable[None]]
            Function to call at the hook point (sync or async)
        priority : int, optional
            Execution priority (0-100, default 50)
        """
        hook_name = (
            hook_point.value
            if isinstance(hook_point, LifecycleHook)
            else str(hook_point)
        )

        if hook_name not in self._hooks:
            self._hooks[hook_name] = []

        # Add callback with priority
        self._hooks[hook_name].append((priority, callback))
        # Sort by priority
        self._hooks[hook_name].sort(key=lambda x: x[0])

        self.ctx.debug(f"Registered hook '{hook_name}' with priority {priority}")

    async def execute(
        self,
        hook_point: LifecycleHook,
        data: dict[str, Any] | None = None,
    ) -> HookContext:
        """Execute all callbacks registered for a hook point.

        Parameters
        ----------
        hook_point : LifecycleHook
            The hook point to execute
        data : Dict[str, Any], optional
            Data to pass to hook callbacks

        Returns
        -------
        HookContext
            The context after all hooks have executed
        """
        if not self._enabled:
            return HookContext(self.adapter, self.session, data)

        hook_name = (
            hook_point.value
            if isinstance(hook_point, LifecycleHook)
            else str(hook_point)
        )
        context = HookContext(self.adapter, self.session, data)

        if hook_name not in self._hooks:
            return context

        self.ctx.debug(f"Executing hooks for '{hook_name}'")

        for priority, callback in self._hooks[hook_name]:
            if context.cancelled:
                self.ctx.debug(f"Hook execution cancelled at '{hook_name}'")
                break

            try:
                # Check if callback is async (coroutine function) or sync
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as e:
                self.ctx.warning(f"Hook callback failed for '{hook_name}': {e}")
                # Continue with other hooks unless critical
                if priority < 10:  # Critical priority hooks (0-9)
                    raise

        return context

    def clear(self, hook_point: LifecycleHook | None = None) -> None:
        """Clear registered hooks.

        Parameters
        ----------
        hook_point : LifecycleHook, optional
            Specific hook point to clear, or None to clear all
        """
        if hook_point:
            hook_name = (
                hook_point.value
                if isinstance(hook_point, LifecycleHook)
                else str(hook_point)
            )
            if hook_name in self._hooks:
                del self._hooks[hook_name]
                self.ctx.debug(f"Cleared hooks for '{hook_name}'")
        else:
            self._hooks.clear()
            self.ctx.debug("Cleared all hooks")

    def disable(self) -> None:
        """Disable hook execution temporarily."""
        self._enabled = False
        self.ctx.debug("Hook execution disabled")

    def enable(self) -> None:
        """Re-enable hook execution."""
        self._enabled = True
        self.ctx.debug("Hook execution enabled")

    def has_hooks(self, hook_point: LifecycleHook) -> bool:
        """Check if any hooks are registered for a hook point.

        Parameters
        ----------
        hook_point : LifecycleHook
            The hook point to check

        Returns
        -------
        bool
            True if hooks are registered
        """
        hook_name = (
            hook_point.value
            if isinstance(hook_point, LifecycleHook)
            else str(hook_point)
        )
        return hook_name in self._hooks and len(self._hooks[hook_name]) > 0


class AdapterHooksMixin:
    """Mixin class that adds hook support to debug adapters.

    This mixin can be added to adapter classes to provide built-in hook support with
    minimal code changes.
    """

    # Type annotation for mypy - this mixin expects the class to have ctx
    if TYPE_CHECKING:
        from aidb.interfaces import IContext

        ctx: "IContext"

    def __init__(self, *args, **kwargs):
        """Initialize the hooks mixin."""
        super().__init__(*args, **kwargs)
        # Cast self to DebugAdapter since this mixin is intended for adapters
        from typing import cast

        self.hooks = LifecycleHooks(cast("DebugAdapter", self))

    def register_hook(
        self,
        hook_point: LifecycleHook,
        callback: Callable[[HookContext], None]
        | Callable[[HookContext], Awaitable[None]],
        priority: int = 50,
    ) -> None:
        """Register a lifecycle hook.

        Parameters
        ----------
        hook_point : LifecycleHook
            The lifecycle point to hook into
        callback : Callable[[HookContext], None] |
            Callable[[HookContext], Awaitable[None]]
            Function to call at the hook point (sync or async)
        priority : int, optional
            Execution priority (0-100, default 50)
        """
        self.hooks.register(hook_point, callback, priority)

    async def execute_hook(
        self,
        hook_point: LifecycleHook,
        data: dict[str, Any] | None = None,
    ) -> HookContext:
        """Execute hooks for a lifecycle point.

        Parameters
        ----------
        hook_point : LifecycleHook
            The hook point to execute
        data : Dict[str, Any], optional
            Data to pass to hook callbacks

        Returns
        -------
        HookContext
            The context after all hooks have executed
        """
        return await self.hooks.execute(hook_point, data)

    async def post_launch_hook(
        self,
        proc: "asyncio.subprocess.Process",
        port: int,
    ) -> None:
        """Execute post-launch hook operations.

        Can be overridden by subclasses for adapter-specific behavior.

        Parameters
        ----------
        proc : asyncio.subprocess.Process
            The launched async process
        port : int
            The port the adapter is listening on
        """
        context = await self.execute_hook(
            LifecycleHook.POST_LAUNCH,
            data={"process": proc, "port": port},
        )

        # Allow hooks to modify behavior
        if context.cancelled:
            msg = (
                context.result
                if context.result
                else "Post-launch hook cancelled operation"
            )
            raise RuntimeError(msg)

    async def pre_stop_hook(self) -> None:
        """Execute pre-stop hook operations.

        Can be overridden by subclasses for adapter-specific cleanup.
        """
        context = await self.execute_hook(LifecycleHook.PRE_STOP)

        # Allow hooks to cancel stop
        if context.cancelled:
            self.ctx.warning("Stop operation cancelled by hook")
            return

    async def on_attach_hook(self, pid: int) -> None:
        """Execute attach hook operations.

        Can be overridden by subclasses for adapter-specific attach logic.

        Parameters
        ----------
        pid : int
            Process ID being attached to
        """
        await self.execute_hook(LifecycleHook.POST_ATTACH, data={"pid": pid})
