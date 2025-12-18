"""Public event API for DAP event subscriptions.

This module provides a clean public interface for event subscriptions that wraps the
internal EventProcessor without exposing implementation details. It enables
subscription-based event handling alongside the existing wait-based patterns, allowing
for a gradual migration path.
"""

import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

from aidb.common.constants import DEFAULT_WAIT_TIMEOUT_S, EVENT_QUEUE_POLL_TIMEOUT_S
from aidb.common.errors import AidbError
from aidb.dap.protocol.base import Event
from aidb.patterns import Obj

from .constants import EventType
from .events import EventProcessor


@dataclass
class SubscriptionInfo:
    """Information about an active event subscription.

    Attributes
    ----------
    id : str
        Unique subscription identifier (UUID)
    event_type : str
        The event type being subscribed to
    handler : Callable
        The callback function for this subscription
    filter : Optional[Callable]
        Optional filter function to apply before calling handler
    created_at : float
        Timestamp when subscription was created
    call_count : int
        Number of times the handler has been invoked
    _wrapper : Optional[Callable]
        Internal wrapper function used for unsubscribing
    """

    id: str
    event_type: str
    handler: Callable[[Event], None]
    filter: Callable[[Event], bool] | None = None
    created_at: float = field(default_factory=lambda: __import__("time").time())
    _wrapper: Callable | None = field(default=None, init=False)
    call_count: int = 0


class PublicEventAPI(Obj):
    """Public API for event subscriptions.

    This class provides a clean public interface for subscribing to DAP events without
    exposing the internal EventProcessor implementation. It manages subscription
    lifecycles, provides thread-safe operations, and supports both filtered and
    unfiltered event subscriptions.

    The API is designed to work alongside existing wait-based patterns, allowing for
    gradual migration without breaking changes.
    """

    def __init__(
        self,
        event_processor: EventProcessor,
        ctx: Optional["IContext"] = None,
    ):
        """Initialize the public event API.

        Parameters
        ----------
        event_processor : EventProcessor
            The internal event processor to wrap
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self._event_processor = event_processor
        self._subscriptions: dict[str, SubscriptionInfo] = {}

        # Track subscriptions by event type for efficient lookup
        self._subscriptions_by_type: dict[str, list[str]] = {}

        # Statistics for monitoring
        self._total_subscriptions_created = 0
        self._total_events_delivered = 0

    async def subscribe_to_event(
        self,
        event_type: str,
        handler: Callable[[Event], None],
        event_filter: Callable[[Event], bool] | None = None,
    ) -> str:
        """Subscribe to a specific event type.

        Creates a new subscription that will invoke the handler whenever an event
        of the specified type is received. An optional filter can be provided to
        only invoke the handler for events that match specific criteria.

        Parameters
        ----------
        event_type : str
            The DAP event type to subscribe to (e.g., 'stopped', 'terminated')
            Use '*' to subscribe to all event types
        handler : Callable[[Event], None]
            Callback function to invoke when matching events are received
        filter : Optional[Callable[[Event], bool]]
            Optional filter function. If provided, handler is only called when
            filter returns True for the event

        Returns
        -------
        str
            Unique subscription ID that can be used to unsubscribe

        Raises
        ------
        AidbError
            If handler is not callable
        """
        if not callable(handler):
            msg = "Handler must be callable"
            raise AidbError(msg)

        async with self.async_lock:
            # Generate unique subscription ID
            subscription_id = str(uuid.uuid4())

            # Create subscription info
            subscription = SubscriptionInfo(
                id=subscription_id,
                event_type=event_type,
                handler=handler,
                filter=event_filter,
            )

            # Store subscription
            self._subscriptions[subscription_id] = subscription

            # Track by event type
            if event_type not in self._subscriptions_by_type:
                self._subscriptions_by_type[event_type] = []
            self._subscriptions_by_type[event_type].append(subscription_id)

            # Create async function to update statistics
            async def update_stats() -> None:
                async with self.async_lock:
                    if subscription_id in self._subscriptions:
                        self._subscriptions[subscription_id].call_count += 1
                        self._total_events_delivered += 1

            # Create wrapper that includes filtering and statistics
            def wrapper(event: Event) -> None:
                self.ctx.debug(
                    f"[SUBSCRIPTION] Wrapper called for {event_type} with event "
                    f"{event.event}, subscription {subscription_id}",
                )

                # Apply filter if present
                if event_filter and not event_filter(event):
                    self.ctx.debug(
                        f"[SUBSCRIPTION] Event filtered out for {subscription_id}",
                    )
                    return

                # Update statistics (schedule async task)
                with contextlib.suppress(RuntimeError):
                    # Not in async context, skip stats update
                    asyncio.create_task(update_stats())

                # Call the actual handler
                try:
                    self.ctx.debug(
                        f"[SUBSCRIPTION] Calling handler for {subscription_id}",
                    )
                    handler(event)
                    self.ctx.debug(
                        f"[SUBSCRIPTION] Handler completed for {subscription_id}",
                    )
                except Exception as e:
                    self.ctx.error(
                        f"Error in subscription handler {subscription_id}: {e}",
                    )

            # Store the wrapper for cleanup (must be done before subscribing)
            # We need to keep a reference to the wrapper to unsubscribe later
            self._subscriptions[subscription_id]._wrapper = wrapper

            # Register with internal event processor
            self.ctx.debug(
                f"[SUBSCRIPTION] Registering wrapper with EventProcessor for "
                f"{event_type}, subscription {subscription_id}",
            )
            self._event_processor.subscribe(event_type, wrapper)

            self._total_subscriptions_created += 1

            self.ctx.debug(
                f"Created subscription {subscription_id} for event type '{event_type}'",
            )

            return subscription_id

    async def unsubscribe_from_event(self, subscription_id: str) -> bool:
        """Unsubscribe from event notifications.

        Removes an active subscription and stops invoking its handler.

        Parameters
        ----------
        subscription_id : str
            The subscription ID returned from subscribe_to_event

        Returns
        -------
        bool
            True if subscription was found and removed, False if not found
        """
        async with self.async_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                self.ctx.debug(f"Subscription {subscription_id} not found")
                return False

            # Unsubscribe from internal event processor using the wrapper
            wrapper = getattr(subscription, "_wrapper", subscription.handler)
            self._event_processor.unsubscribe(subscription.event_type, wrapper)

            # Remove from tracking
            del self._subscriptions[subscription_id]

            # Remove from type tracking
            if subscription.event_type in self._subscriptions_by_type:
                self._subscriptions_by_type[subscription.event_type].remove(
                    subscription_id,
                )
                if not self._subscriptions_by_type[subscription.event_type]:
                    del self._subscriptions_by_type[subscription.event_type]

            self.ctx.debug(
                f"Removed subscription {subscription_id} "
                f"(delivered {subscription.call_count} events)",
            )

            return True

    async def get_active_subscriptions(self) -> list[SubscriptionInfo]:
        """Get information about all active subscriptions.

        Returns
        -------
        List[SubscriptionInfo]
            List of active subscription information objects
        """
        async with self.async_lock:
            # Return copies to prevent external modification
            return [
                SubscriptionInfo(
                    id=sub.id,
                    event_type=sub.event_type,
                    handler=sub.handler,
                    filter=sub.filter,
                    created_at=sub.created_at,
                    call_count=sub.call_count,
                )
                for sub in self._subscriptions.values()
            ]

    async def clear_all_subscriptions(self) -> int:
        """Remove all active subscriptions.

        This is typically called during session teardown to ensure all
        subscriptions are properly cleaned up.

        Returns
        -------
        int
            Number of subscriptions that were cleared
        """
        async with self.async_lock:
            count = len(self._subscriptions)

            # Unsubscribe all from internal processor
            for subscription in self._subscriptions.values():
                wrapper = getattr(subscription, "_wrapper", subscription.handler)
                self._event_processor.unsubscribe(subscription.event_type, wrapper)

            # Clear all tracking
            self._subscriptions.clear()
            self._subscriptions_by_type.clear()

            self.ctx.debug(f"Cleared {count} active subscriptions")

            return count

    async def on_stopped(
        self,
        handler: Callable[[Event], None],
        event_filter: Callable[[Event], bool] | None = None,
    ) -> str:
        """Subscribe to 'stopped' events.

        Convenience method for subscribing to debugger stop events.

        Parameters
        ----------
        handler : Callable[[Event], None]
            Callback for stopped events
        filter : Optional[Callable[[Event], bool]]
            Optional filter for stopped events

        Returns
        -------
        str
            Subscription ID
        """
        return await self.subscribe_to_event(
            EventType.STOPPED.value,
            handler,
            event_filter,
        )

    async def on_terminated(
        self,
        handler: Callable[[Event], None],
    ) -> str:
        """Subscribe to 'terminated' events.

        Convenience method for subscribing to session termination events.

        Parameters
        ----------
        handler : Callable[[Event], None]
            Callback for terminated events

        Returns
        -------
        str
            Subscription ID
        """
        return await self.subscribe_to_event(EventType.TERMINATED.value, handler)

    async def on_continued(
        self,
        handler: Callable[[Event], None],
        event_filter: Callable[[Event], bool] | None = None,
    ) -> str:
        """Subscribe to 'continued' events.

        Convenience method for subscribing to execution continuation events.

        Parameters
        ----------
        handler : Callable[[Event], None]
            Callback for continued events
        filter : Optional[Callable[[Event], bool]]
            Optional filter for continued events

        Returns
        -------
        str
            Subscription ID
        """
        return await self.subscribe_to_event(
            EventType.CONTINUED.value,
            handler,
            event_filter,
        )

    async def on_output(
        self,
        handler: Callable[[Event], None],
        category: str | None = None,
    ) -> str:
        """Subscribe to 'output' events with optional category filtering.

        Parameters
        ----------
        handler : Callable[[Event], None]
            Callback for output events
        category : Optional[str]
            If provided, only output events with this category will trigger
            the handler (e.g., 'stdout', 'stderr', 'console')

        Returns
        -------
        str
            Subscription ID
        """
        filter_func = None
        if category:

            def category_filter(event: Event) -> bool:
                return (
                    hasattr(event, "body")
                    and event.body is not None
                    and getattr(event.body, "category", None) == category
                )

            filter_func = category_filter

        return await self.subscribe_to_event(
            EventType.OUTPUT.value,
            handler,
            filter_func,
        )

    async def get_subscription_stats(self) -> dict[str, Any]:
        """Get statistics about subscription usage.

        Returns
        -------
        Dict[str, Any]
            Statistics including total subscriptions created, active count,
            and events delivered
        """
        async with self.async_lock:
            return {
                "total_created": self._total_subscriptions_created,
                "active_count": len(self._subscriptions),
                "events_delivered": self._total_events_delivered,
                "subscriptions_by_type": {
                    event_type: len(subs)
                    for event_type, subs in self._subscriptions_by_type.items()
                },
            }

    async def wait_for_event_async(
        self,
        event_type: str,
        timeout: float | None = None,
    ) -> asyncio.Future[Event]:
        """Wait for an event asynchronously using a Future-like pattern.

        Creates a Future that will be resolved when the specified event occurs.
        This allows for Promise-like patterns and async/await usage.

        Parameters
        ----------
        event_type : str
            The event type to wait for
        timeout : Optional[float]
            Maximum time to wait in seconds. If None, waits indefinitely

        Returns
        -------
        asyncio.Future[Event]
            A Future that will be resolved with the event when it occurs

        Examples
        --------
        >>> future = session.events.wait_for_event_async("stopped")
        >>> # Do other work...
        >>> event = await future  # or future.result() in sync code
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Event] = loop.create_future()

        # Store sub_id reference for closure
        sub_id_ref: list[str | None] = [None]

        # Handler that resolves the future
        def resolve_future(event: Event) -> None:
            if not future.done():
                # Schedule the future resolution in the event loop
                loop.call_soon_threadsafe(future.set_result, event)
                # Unsubscribe after resolving
                if sub_id_ref[0]:
                    asyncio.create_task(self.unsubscribe_from_event(sub_id_ref[0]))

        # Subscribe to the event
        sub_id = await self.subscribe_to_event(event_type, resolve_future)
        sub_id_ref[0] = sub_id

        # Set up timeout if specified
        if timeout is not None:

            def timeout_handler() -> None:
                if not future.done():
                    loop.call_soon_threadsafe(
                        future.set_exception,
                        TimeoutError(f"Timeout waiting for {event_type}"),
                    )
                    if sub_id_ref[0]:
                        asyncio.create_task(self.unsubscribe_from_event(sub_id_ref[0]))

            asyncio.get_running_loop().call_later(timeout, timeout_handler)

        return future

    async def collect_events(
        self,
        event_type: str,
        count: int,
        timeout: float | None = None,
    ) -> list[Event]:
        """Collect a specified number of events then auto-unsubscribe.

        Subscribes to an event type, collects the specified number of events,
        then automatically unsubscribes. Useful for collecting a batch of events.

        Parameters
        ----------
        event_type : str
            The event type to collect
        count : int
            Number of events to collect before unsubscribing
        timeout : Optional[float]
            Maximum time to wait for all events. If timeout occurs, returns
            whatever events were collected so far

        Returns
        -------
        List[Event]
            List of collected events (may be less than count if timeout occurs)

        Examples
        --------
        >>> # Collect the next 5 output events
        >>> outputs = session.events.collect_events("output", 5, timeout=10.0)
        >>> for output in outputs:
        ...     print(output.body.output)
        """
        collected: list[Event] = []
        lock = asyncio.Lock()
        done_event = asyncio.Event()
        sub_id: str | None = None

        async def collector_wrapper(event: Event) -> None:
            async with lock:
                collected.append(event)
                if len(collected) >= count:
                    done_event.set()
                    if sub_id:
                        await self.unsubscribe_from_event(sub_id)

        # Need a sync wrapper for the callback since handlers are sync
        def collector(event: Event) -> None:
            asyncio.create_task(collector_wrapper(event))

        # Subscribe to collect events
        sub_id = await self.subscribe_to_event(event_type, collector)

        # Wait for collection to complete or timeout
        try:
            await asyncio.wait_for(done_event.wait(), timeout)
        except asyncio.TimeoutError:
            # Timeout occurred
            await self.unsubscribe_from_event(sub_id)

        return collected

    async def event_stream(
        self,
        event_type: str,
        buffer_size: int = 100,
    ) -> AsyncGenerator[Event, None]:
        """Create a generator that yields events as they arrive.

        Creates an iterator that yields events of the specified type as they
        occur. This allows for Pythonic iteration over events.

        Note: The generator will run indefinitely unless explicitly closed.
        Remember to unsubscribe when done to avoid memory leaks.

        Parameters
        ----------
        event_type : str
            The event type to stream
        buffer_size : int
            Maximum number of events to buffer (default: 100)

        Yields
        ------
        Event
            Events as they occur

        Examples
        --------
        >>> # Process output events as they arrive
        >>> for event in session.events.event_stream("output"):
        ...     print(f"Output: {event.body.output}")
        ...     if "Done" in event.body.output:
        ...         break
        """
        import queue

        # Create a queue for events
        event_queue: queue.Queue[Event | None] = queue.Queue(maxsize=buffer_size)
        sub_id: str | None = None

        def enqueue_event(event: Event) -> None:
            try:
                event_queue.put_nowait(event)
            except queue.Full:
                # Buffer full, drop oldest event
                try:
                    event_queue.get_nowait()
                    event_queue.put_nowait(event)
                except queue.Empty:
                    pass

        # Subscribe to events
        sub_id = await self.subscribe_to_event(event_type, enqueue_event)

        try:
            while True:
                # Yield events from queue
                try:
                    event = event_queue.get(timeout=EVENT_QUEUE_POLL_TIMEOUT_S)
                    if event is not None:
                        yield event
                except queue.Empty:
                    # No events available, continue waiting
                    continue
                except GeneratorExit:
                    # Generator closed, clean up
                    break
        finally:
            # Always unsubscribe when generator exits
            if sub_id:
                await self.unsubscribe_from_event(sub_id)

    async def wait_for_stopped_async(
        self,
        timeout: float | None = None,
    ) -> asyncio.Future[bool]:
        """Wait for a stopped event asynchronously.

        Creates a Future that resolves to True when a stopped event occurs,
        or False if timeout expires.

        Parameters
        ----------
        timeout : Optional[float]
            Maximum time to wait in seconds. If None, waits indefinitely

        Returns
        -------
        asyncio.Future[bool]
            A Future that resolves to True if stopped, False if timeout

        Examples
        --------
        >>> future = session.events.wait_for_stopped_async(timeout=5.0)
        >>> stopped = await future  # True if stopped, False if timeout
        """
        future = await self.wait_for_event_async(EventType.STOPPED.value, timeout)

        # Wrap to return bool instead of Event
        async def bool_wrapper() -> bool:
            try:
                await future
                return True
            except TimeoutError:
                return False

        loop = asyncio.get_running_loop()
        return loop.create_task(bool_wrapper())

    async def wait_for_terminated_async(
        self,
        timeout: float | None = None,
    ) -> asyncio.Future[bool]:
        """Wait for a terminated event asynchronously.

        Creates a Future that resolves to True when a terminated event occurs,
        or False if timeout expires.

        Parameters
        ----------
        timeout : Optional[float]
            Maximum time to wait in seconds. If None, waits indefinitely

        Returns
        -------
        asyncio.Future[bool]
            A Future that resolves to True if terminated, False if timeout

        Examples
        --------
        >>> future = session.events.wait_for_terminated_async(timeout=5.0)
        >>> terminated = await future  # True if terminated, False if timeout
        """
        future = await self.wait_for_event_async(EventType.TERMINATED.value, timeout)

        # Wrap to return bool instead of Event
        async def bool_wrapper() -> bool:
            try:
                await future
                return True
            except TimeoutError:
                return False

        loop = asyncio.get_running_loop()
        return loop.create_task(bool_wrapper())

    async def wait_for_stopped_or_terminated_async(
        self,
        timeout: float | None = None,
        edge_triggered: bool = False,
    ) -> str:
        """Wait for either a stopped or terminated event asynchronously.

        Waits for and returns "stopped", "terminated", or "timeout"
        depending on which event occurs first.

        This method uses future-based waiting which eliminates race conditions
        by registering for the NEXT occurrence of events before checking state.

        Parameters
        ----------
        timeout : Optional[float]
            Maximum time to wait in seconds. If None, defaults to 5.0
        edge_triggered : bool
            If True, wait for NEXT event (ignore current state).
            If False (default), return immediately if already stopped/terminated.

        Returns
        -------
        str
            "stopped", "terminated", or "timeout"

        Examples
        --------
        >>> # Level-triggered: check current state first
        >>> result = await session.events.wait_for_stopped_or_terminated_async(
        ...     timeout=5.0)

        >>> # Edge-triggered: wait for NEXT event only
        >>> result = await session.events.wait_for_stopped_or_terminated_async(
        ...     timeout=5.0, edge_triggered=True)
        """
        # Set default timeout if not specified
        if timeout is None:
            timeout = DEFAULT_WAIT_TIMEOUT_S

        # Register for NEXT occurrences BEFORE checking current state
        # This eliminates race conditions where events arrive between
        # state check and wait start
        stopped_future = self._event_processor.register_stopped_listener()
        terminated_future = self._event_processor.register_terminated_listener()

        self.ctx.debug(
            f"wait_for_stopped_or_terminated: registered futures, "
            f"edge_triggered={edge_triggered}, timeout={timeout}",
        )

        # Only check current state if level-triggered
        if not edge_triggered:
            # Level-triggered: Return immediately if already in target state
            if self._event_processor._state.stopped:
                stopped_future.cancel()
                terminated_future.cancel()
                self.ctx.debug(
                    "wait_for_stopped_or_terminated: already stopped, "
                    "returning immediately (level-triggered)",
                )
                return "stopped"

            if self._event_processor._state.terminated:
                stopped_future.cancel()
                terminated_future.cancel()
                self.ctx.debug(
                    "wait_for_stopped_or_terminated: already terminated, "
                    "returning immediately (level-triggered)",
                )
                return "terminated"

        # Edge-triggered OR not currently stopped/terminated - wait for next occurrence
        self.ctx.debug(
            f"wait_for_stopped_or_terminated: waiting for next event "
            f"({'edge-triggered' if edge_triggered else 'level-triggered'})",
        )

        try:
            # Wait for the first future to complete
            done, pending = await asyncio.wait(
                [stopped_future, terminated_future],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout,
            )

            # Cancel the pending future
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            # Check if we timed out (no tasks completed)
            if not done:
                self.ctx.debug(
                    f"wait_for_stopped_or_terminated: timeout after {timeout}s",
                )
                return "timeout"

            # Get the result from the completed task
            for task in done:
                if task == stopped_future and not task.cancelled():
                    self.ctx.debug(
                        "wait_for_stopped_or_terminated: stopped event received",
                    )
                    return "stopped"
                if task == terminated_future and not task.cancelled():
                    self.ctx.debug(
                        "wait_for_stopped_or_terminated: terminated event received",
                    )
                    return "terminated"

            # Shouldn't reach here, but handle gracefully
            self.ctx.debug(
                "wait_for_stopped_or_terminated: futures completed but no result",
            )
            return "timeout"

        except Exception as e:
            # Cancel both futures on error
            stopped_future.cancel()
            terminated_future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stopped_future
            with contextlib.suppress(asyncio.CancelledError):
                await terminated_future
            self.ctx.error(
                f"wait_for_stopped_or_terminated: error during wait: {e}",
            )
            raise

    async def cleanup(self) -> None:
        """Clean up all subscriptions and resources.

        This should be called when the session is being torn down.
        """
        cleared = await self.clear_all_subscriptions()
        if cleared > 0:
            self.ctx.info(f"Cleaned up {cleared} subscriptions during teardown")


class StubPublicEventAPI:
    """Stub of PublicEventAPI for deferred session initialization.

    This stub collects subscriptions before the real DAP client is available, allowing
    the session to be created in a deferred state and initialized later.
    """

    def __init__(self) -> None:
        """Initialize the stub event API."""
        self._subscriptions: dict[str, list[SubscriptionInfo]] = {}
        self._subscription_counter = 0
        self._lock = asyncio.Lock()

    async def subscribe_to_event(
        self,
        event_type: str,
        handler: Callable[[Event], None],
        event_filter: Callable[[Event], bool] | None = None,
    ) -> str:
        """Subscribe to a DAP event type (stub implementation).

        Parameters
        ----------
        event_type : str
            The DAP event type to subscribe to
        handler : Callable[[Event], None]
            Callback function to handle the event
        filter : Optional[Callable[[Event], bool]]
            Optional filter function to apply before calling handler

        Returns
        -------
        str
            Subscription ID that can be used to unsubscribe
        """
        async with self._lock:
            self._subscription_counter += 1
            sub_id = f"stub_{self._subscription_counter}"

            sub = SubscriptionInfo(
                id=sub_id,
                event_type=event_type,
                handler=handler,
                filter=event_filter,
            )

            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(sub)

            return sub_id

    async def unsubscribe_from_event(self, subscription_id: str) -> bool:
        """Unsubscribe from a DAP event (stub implementation).

        Parameters
        ----------
        subscription_id : str
            The subscription ID returned from subscribe_to_event

        Returns
        -------
        bool
            True if subscription was found and removed, False otherwise
        """
        async with self._lock:
            for event_type, subs in self._subscriptions.items():
                for i, sub in enumerate(subs):
                    if sub.id == subscription_id:
                        subs.pop(i)
                        if not subs:
                            del self._subscriptions[event_type]
                        return True
            return False

    async def clear_all_subscriptions(self) -> int:
        """Clear all active subscriptions (stub implementation).

        Returns
        -------
        int
            Number of subscriptions that were cleared
        """
        async with self._lock:
            count = sum(len(subs) for subs in self._subscriptions.values())
            self._subscriptions.clear()
            return count

    async def get_subscriptions(self) -> dict[str, list[SubscriptionInfo]]:
        """Get all current subscriptions (for transfer to real API).

        Returns
        -------
        Dict[str, List[SubscriptionInfo]]
            Dictionary mapping event types to subscription info
        """
        async with self._lock:
            return dict(self._subscriptions)

    async def on_stopped(self, handler: Callable[[Event], None]) -> str:
        """Subscribe to 'stopped' events (stub convenience method).

        Parameters
        ----------
        handler : Callable[[Event], None]
            Function to call when event occurs

        Returns
        -------
        str
            Subscription ID for unsubscribing
        """
        return await self.subscribe_to_event(EventType.STOPPED.value, handler)

    async def on_terminated(self, handler: Callable[[Event], None]) -> str:
        """Subscribe to 'terminated' events (stub convenience method).

        Parameters
        ----------
        handler : Callable[[Event], None]
            Function to call when event occurs

        Returns
        -------
        str
            Subscription ID for unsubscribing
        """
        return await self.subscribe_to_event(EventType.TERMINATED.value, handler)

    async def on_continued(self, handler: Callable[[Event], None]) -> str:
        """Subscribe to 'continued' events (stub convenience method).

        Parameters
        ----------
        handler : Callable[[Event], None]
            Function to call when event occurs

        Returns
        -------
        str
            Subscription ID for unsubscribing
        """
        return await self.subscribe_to_event(EventType.CONTINUED.value, handler)
