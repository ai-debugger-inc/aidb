"""DAP event processing."""

import asyncio
import contextlib
import time
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional, cast

from aidb.dap.protocol.base import Event
from aidb.patterns import Obj

from .constants import EventType, StopReason
from .state import SessionState

if TYPE_CHECKING:
    from aidb.dap.protocol.events import (
        BreakpointEvent,
        CapabilitiesEvent,
        ContinuedEvent,
        ExitedEvent,
        InitializedEvent,
        InvalidatedEvent,
        LoadedSourceEvent,
        MemoryEvent,
        ModuleEvent,
        OutputEvent,
        ProcessEvent,
        ProgressEndEvent,
        ProgressStartEvent,
        ProgressUpdateEvent,
        StoppedEvent,
        TerminatedEvent,
        ThreadEvent,
    )
    from aidb.interfaces.context import IContext


class EventProcessor(Obj):
    """Process DAP events and maintain session state.

    This class is responsible for:
        - Processing incoming DAP events
        - Updating session state based on events
        - Managing event listeners
        - Providing event synchronization primitives

    The event detection mechanism uses counters instead of boolean flags to ensure
    that wait_for_event only returns True for NEW events, not stale events from
    previous operations. This prevents race conditions in parallel test execution.
    """

    def __init__(
        self,
        state: SessionState,
        ctx: Optional["IContext"] = None,
        session_id: str | None = None,
    ):
        """Initialize event processor.

        Parameters
        ----------
        state : SessionState
            Shared session state to update
        ctx : IContext, optional
            Application context for logging
        session_id : str, optional
            Session ID for logging and debugging
        """
        super().__init__(ctx)
        self._state = state
        self._session_id = session_id
        self._listeners: dict[str, list[Callable[[Event], None]]] = defaultdict(list)
        self._last_events: dict[str, Event] = {}

        # Counter-based event detection for reliable wait_for_event
        # Each event type has a counter that increments on each event receipt
        # This allows wait_for_event to detect NEW events vs stale state
        self._event_counter: dict[str, int] = defaultdict(int)
        # Signal for waking up waiters (set on event, cleared before wait)
        self._event_signal: dict[str, asyncio.Event] = defaultdict(asyncio.Event)

        # Legacy alias for backward compatibility with clear_event() calls
        self._event_received = self._event_signal

        # Track specific important events
        self._last_stopped_event: Event | None = None
        self._last_initialized_event: Event | None = None
        self._breakpoint_events: list[Event] = []
        self._max_breakpoint_events = 100

        # One-time listeners for terminated events (used by request handler)
        self._terminated_listeners: list[asyncio.Future] = []

        # One-time listeners for stopped events (used by request handler)
        self._stopped_listeners: list[asyncio.Future] = []

    def _capture_event_timing(self) -> tuple[float, int, str]:
        """Capture timing and task info for event processing.

        Returns
        -------
        tuple[float, int, str]
            Wall time, monotonic time in ns, and task name
        """
        t_start_wall = time.time()
        t_start_mono_ns = time.perf_counter_ns()

        # Get task info if in async context
        try:
            current_task = asyncio.current_task()
            task_name = current_task.get_name() if current_task else "sync-context"
        except RuntimeError:
            task_name = "sync-context"

        return t_start_wall, t_start_mono_ns, task_name

    def _compute_time_since_receipt(self, t_start_mono_ns: int) -> float | None:
        """Compute time since last message receipt.

        Parameters
        ----------
        t_start_mono_ns : int
            Start time in nanoseconds

        Returns
        -------
        float | None
            Time in milliseconds or None if not available
        """
        try:
            last_recv_ns = getattr(self._state, "last_message_received_mono_ns", None)
            if last_recv_ns is not None:
                return (t_start_mono_ns - last_recv_ns) / 1_000_000.0
        except Exception as e:
            msg = f"Failed to compute time since last message receipt: {e}"
            self.ctx.debug(msg)
        return None

    def _get_event_handlers(self) -> dict[str, Callable]:
        """Get mapping of event types to handler methods."""
        return {
            EventType.INITIALIZED.value: self._handle_initialized,
            EventType.STOPPED.value: self._handle_stopped,
            EventType.CONTINUED.value: self._handle_continued,
            EventType.TERMINATED.value: self._handle_terminated,
            EventType.EXITED.value: self._handle_exited,
            EventType.THREAD.value: self._handle_thread,
            EventType.BREAKPOINT.value: self._handle_breakpoint,
            EventType.OUTPUT.value: self._handle_output,
            EventType.PROCESS.value: self._handle_process,
            EventType.LOADED_SOURCE.value: self._handle_loaded_source,
            EventType.MEMORY.value: self._handle_memory,
            EventType.MODULE.value: self._handle_module,
            EventType.PROGRESSSTART.value: self._handle_progress_start,
            EventType.PROGRESSUPDATE.value: self._handle_progress_update,
            EventType.PROGRESSEND.value: self._handle_progress_end,
            EventType.INVALIDATED.value: self._handle_invalidated,
            EventType.CAPABILITIES.value: self._handle_capabilities,
        }

    def _record_event_timing(
        self,
        event: Event,
        t_start_wall: float,
        t_start_mono_ns: int,
        task_name: str,
    ) -> None:
        """Record event processing timing information.

        Parameters
        ----------
        event : Event
            The DAP event
        t_start_wall : float
            Wall clock start time
        t_start_mono_ns : int
            Monotonic start time in nanoseconds
        task_name : str
            Name of the processing task
        """
        try:
            self._state.event_last_processed_wall[event.event] = t_start_wall
            self._state.event_last_processed_mono_ns[event.event] = t_start_mono_ns
            self._state.event_last_task_name[event.event] = task_name
        except Exception as e:
            msg = f"Failed to record event processing timing for {event.event}: {e}"
            self.ctx.debug(msg)

    def _signal_event_receipt(self, event: Event) -> None:
        """Signal that an event was received and record signal time.

        Increments the event counter for reliable detection by wait_for_event,
        and sets the signal to wake any waiters.

        Parameters
        ----------
        event : Event
            The DAP event
        """
        try:
            t_signal_wall = time.time()
            t_signal_mono_ns = time.perf_counter_ns()
            self._state.event_last_signaled_wall[event.event] = t_signal_wall
            self._state.event_last_signaled_mono_ns[event.event] = t_signal_mono_ns
        except Exception as e:
            msg = f"Failed to record event signal timing for {event.event}: {e}"
            self.ctx.debug(msg)

        # Increment counter for reliable event detection
        self._event_counter[event.event] += 1
        # Signal to wake up any waiters
        self._event_signal[event.event].set()

    def process_event(self, event: Event) -> None:
        """Process a DAP event and update state.

        Parameters
        ----------
        event : Event
            The DAP event to process
        """
        # Capture timing and task info
        t_start_wall, t_start_mono_ns, task_name = self._capture_event_timing()

        # Compute time since last message receipt
        since_recv_ms = self._compute_time_since_receipt(t_start_mono_ns)

        self.ctx.debug(
            f"Processing event: {event.event} in task={task_name} "
            f"t_wall={t_start_wall:.6f}"
            + (
                f" since_recv_ms={since_recv_ms:.3f}"
                if since_recv_ms is not None
                else ""
            ),
        )

        # Store last event of this type
        self._last_events[event.event] = event

        # Update state based on event type using dispatch table
        handlers = self._get_event_handlers()
        handler = handlers.get(event.event)

        if handler:
            # Log stopped events specifically for debugging
            if event.event == EventType.STOPPED.value:
                self.ctx.debug(
                    f"Dispatching stopped event (seq={event.seq}) to handler, "
                    f"{len(self._stopped_listeners)} listeners waiting",
                )
            handler(event)
        else:
            # Unknown event, just log it
            self.ctx.debug(f"Unhandled event type: {event.event}")

        # Record processed timing/task
        self._record_event_timing(event, t_start_wall, t_start_mono_ns, task_name)

        # Signal that this event was received
        self._signal_event_receipt(event)

        # Notify listeners
        self._notify_listeners(event)

    def _handle_initialized(self, event: Event) -> None:
        """Handle initialized event."""
        initialized_event = cast("InitializedEvent", event)
        self._last_initialized_event = initialized_event
        self._state.initialized = True
        self._state.ready_for_configuration = True
        self.ctx.info("Debug adapter initialized and ready for configuration")
        # NOTE: We do NOT send configurationDone here. That's the responsibility
        # of the session orchestrator.

    def _handle_stopped(self, event: Event) -> None:
        """Handle stopped event."""
        stopped_event = cast("StoppedEvent", event)
        self._last_stopped_event = stopped_event
        self._state.stopped = True

        if stopped_event.body:
            self._state.stop_reason = stopped_event.body.reason
            self._state.current_thread_id = stopped_event.body.threadId
        else:
            self._state.stop_reason = "unknown"
            self._state.current_thread_id = None

        # Track breakpoint events
        if self._state.stop_reason == StopReason.BREAKPOINT.value:
            self._breakpoint_events.append(stopped_event)
            # Limit stored breakpoint events
            if len(self._breakpoint_events) > self._max_breakpoint_events:
                self._breakpoint_events.pop(0)

        self.ctx.info(
            f"Stopped: reason={self._state.stop_reason}, "
            f"thread={self._state.current_thread_id}",
        )

        # Notify any waiting futures for stopped events
        num_listeners = len(self._stopped_listeners)
        if num_listeners > 0:
            self.ctx.debug(
                f"Notifying {num_listeners} stopped listener(s) "
                f"(reason={self._state.stop_reason}, seq={event.seq})",
            )
            for future in self._stopped_listeners:
                if not future.done():
                    future.set_result(event)
                    self.ctx.debug("Stopped future signaled successfully")
            self._stopped_listeners.clear()
        else:
            self.ctx.debug(
                f"No stopped listeners registered for this event "
                f"(reason={self._state.stop_reason}, seq={event.seq})",
            )

    def _handle_continued(self, event: Event) -> None:
        """Handle continued event."""
        continued_event = cast("ContinuedEvent", event)

        # If there's a recent stopped event, only clear stopped state if this
        # continued event came BEFORE the stop. If the continued event came
        # AFTER the stopped event (higher seq), it's spurious and should be ignored.
        if (
            self._last_stopped_event
            and continued_event.seq > self._last_stopped_event.seq
        ):
            self.ctx.debug(
                f"Ignoring spurious continued event (seq={continued_event.seq}) - "
                f"came after stopped (seq={self._last_stopped_event.seq})",
            )
            return

        self._state.stopped = False
        self._state.stop_reason = None
        # Clear last stopped event since we're continuing
        self._last_stopped_event = None

        if continued_event.body:
            if continued_event.body.allThreadsContinued:
                self.ctx.debug("All threads continued")
            else:
                self.ctx.debug(f"AidbThread {continued_event.body.threadId} continued")
        else:
            self.ctx.debug("Continued event with no body")

    def _handle_terminated(self, event: Event) -> None:
        """Handle terminated event."""
        terminated_event = cast("TerminatedEvent", event)
        self._state.terminated = True
        self._state.session_established = False
        self._state.stopped = False  # Clear stopped state on termination

        if terminated_event.body and terminated_event.body.restart is not None:
            self.ctx.info(
                f"Debug session terminated (restart={terminated_event.body.restart})",
            )
        else:
            self.ctx.info("Debug session terminated")

        # Notify any waiting futures for terminated events
        for future in self._terminated_listeners:
            if not future.done():
                future.set_result(event)
        self._terminated_listeners.clear()

    def _handle_exited(self, event: Event) -> None:
        """Handle exited event."""
        exited_event = cast("ExitedEvent", event)
        exit_code = exited_event.body.exitCode if exited_event.body else None
        self.ctx.info(f"Process exited with code: {exit_code}")
        self._state.terminated = True
        self._state.stopped = False  # Clear stopped state on exit

    def _handle_thread(self, event: Event) -> None:
        """Handle thread event."""
        thread_event = cast("ThreadEvent", event)
        if thread_event.body:
            self.ctx.debug(
                f"AidbThread {thread_event.body.threadId} {thread_event.body.reason}",
            )
        else:
            self.ctx.debug("AidbThread event with no body")

    def _handle_breakpoint(self, event: Event) -> None:
        """Handle breakpoint event."""
        breakpoint_event = cast("BreakpointEvent", event)
        if breakpoint_event.body:
            self.ctx.debug(
                f"AidbBreakpoint {breakpoint_event.body.reason}: "
                f"{breakpoint_event.body.breakpoint}",
            )
        else:
            self.ctx.debug("AidbBreakpoint event with no body")

    def _handle_output(self, event: Event) -> None:
        """Handle output event.

        Stores output in state buffer for retrieval by MCP handlers (logpoints, etc.)
        and logs the output for debugging purposes.
        """
        output_event = cast("OutputEvent", event)
        if output_event.body:
            category = output_event.body.category or "console"
            output = output_event.body.output or ""

            # Store in state buffer with rotation
            entry = {
                "category": category,
                "output": output.rstrip(),
                "timestamp": time.time(),
            }
            if len(self._state.output_buffer) >= self._state.output_buffer_max_size:
                self._state.output_buffer.pop(0)
            self._state.output_buffer.append(entry)

            # Log based on category
            if category == "stderr":
                self.ctx.debug(f"Program stderr: {output.rstrip()}")
            elif category == "stdout":
                self.ctx.debug(f"Program stdout: {output.rstrip()}")
            elif category == "console":
                self.ctx.debug(f"Console: {output.rstrip()}")
            else:
                self.ctx.debug(f"Output ({category}): {output.rstrip()}")
        else:
            self.ctx.debug("Output event with no body")

    def _handle_process(self, event: Event) -> None:
        """Handle process event."""
        process_event = cast("ProcessEvent", event)
        if process_event.body:
            self.ctx.info(
                f"Process {process_event.body.startMethod}: {process_event.body.name} "
                f"(PID: {process_event.body.systemProcessId}, "
                f"local: {process_event.body.isLocalProcess})",
            )
        else:
            self.ctx.debug("Process event with no body")

    def _handle_loaded_source(self, event: Event) -> None:
        """Handle loadedSource event.

        This event is fired when a new source is loaded or the same source is loaded
        with a different path (common with symlinks). We track these to help with
        breakpoint re-binding if needed.
        """
        loaded_event = cast("LoadedSourceEvent", event)
        if loaded_event.body:
            source = loaded_event.body.source
            reason = loaded_event.body.reason

            # Filter node_internals from INFO level (too noisy)
            # Keep user code at INFO, move internals to DEBUG
            if source.path and source.path.startswith("<node_internals>"):
                self.ctx.debug(
                    f"Source loaded (internal): {source.name} path={source.path}",
                )
            else:
                self.ctx.info(
                    f"Source loaded ({reason}): {source.name} "
                    f"path={source.path}, id={source.sourceReference}",
                )

            # Store loaded source info for potential breakpoint rebinding. Note:
            # The session may need to react to this event if the path differs
            # from expected breakpoint paths
            if not hasattr(self._state, "loaded_sources"):
                self._state.loaded_sources = {}

            if source.path:
                self._state.loaded_sources[source.path] = source

                # Check if this might be an alternate path for existing breakpoints
                # (e.g., symlinks, relocated sources)
                if reason in ["new", "changed"]:
                    # Flag that breakpoint re-binding might be needed
                    # The session can check this flag and re-bind if necessary
                    if not hasattr(self._state, "sources_needing_rebind"):
                        self._state.sources_needing_rebind = []

                    # Store info about the loaded source that might need rebinding
                    rebind_info = {
                        "path": source.path,
                        "name": source.name,
                        "sourceReference": source.sourceReference,
                        "reason": reason,
                        "timestamp": time.time(),
                    }
                    self._state.sources_needing_rebind.append(rebind_info)

                    self.ctx.debug(
                        f"Source loaded that may need breakpoint re-binding: "
                        f"{source.path}",
                    )
        else:
            self.ctx.debug("LoadedSource event with no body")

    def _handle_memory(self, event: Event) -> None:
        """Handle memory event.

        Memory events indicate changes in memory state that might affect debugging
        operations.
        """
        memory_event = cast("MemoryEvent", event)
        if memory_event.body:
            self.ctx.info(
                f"Memory event: address={memory_event.body.memoryReference}, "
                f"offset={memory_event.body.offset}, count={memory_event.body.count}",
            )
        else:
            self.ctx.debug("Memory event with no body")

    def _handle_module(self, event: Event) -> None:
        """Handle module event.

        Module events indicate when modules are loaded or unloaded during debugging.
        """
        module_event = cast("ModuleEvent", event)
        if module_event.body:
            reason = module_event.body.reason
            module = module_event.body.module
            self.ctx.info(
                f"Module {reason}: {module.name} (id={module.id}, path={module.path})",
            )

            # Track loaded modules
            if not hasattr(self._state, "loaded_modules"):
                self._state.loaded_modules = {}

            if reason in ["new", "changed"]:
                self._state.loaded_modules[str(module.id)] = module
            elif reason == "removed":
                self._state.loaded_modules.pop(str(module.id), None)
        else:
            self.ctx.debug("Module event with no body")

    def _handle_progress_start(self, event: Event) -> None:
        """Handle progress start event.

        Progress events allow tracking of long-running operations.
        """
        progress_event = cast("ProgressStartEvent", event)
        if progress_event.body:
            self.ctx.info(
                f"Progress started: {progress_event.body.title} "
                f"(id={progress_event.body.progressId})",
            )

            # Track active progress operations
            progress_id = progress_event.body.progressId
            self._state.active_progress[progress_id] = {
                "title": progress_event.body.title,
                "started": time.time(),
                "cancellable": getattr(progress_event.body, "cancellable", False),
            }
        else:
            self.ctx.debug("Progress start event with no body")

    def _handle_progress_update(self, event: Event) -> None:
        """Handle progress update event."""
        progress_event = cast("ProgressUpdateEvent", event)
        if progress_event.body:
            percentage = getattr(progress_event.body, "percentage", None)
            message = getattr(progress_event.body, "message", "")

            self.ctx.debug(
                f"Progress update: id={progress_event.body.progressId} "
                f"percentage={percentage}, message={message}",
            )
        else:
            self.ctx.debug("Progress update event with no body")

    def _handle_progress_end(self, event: Event) -> None:
        """Handle progress end event."""
        progress_event = cast("ProgressEndEvent", event)
        if progress_event.body:
            self.ctx.info(
                f"Progress ended: id={progress_event.body.progressId}, "
                f"message={getattr(progress_event.body, 'message', '')}",
            )

            # Remove from active progress
            self._state.active_progress.pop(progress_event.body.progressId, None)
        else:
            self.ctx.debug("Progress end event with no body")

    def _handle_invalidated(self, event: Event) -> None:
        """Handle invalidated event.

        This event signals that some state in the debug adapter has changed and the
        client should refresh its data views.
        """
        invalidated_event = cast("InvalidatedEvent", event)
        if invalidated_event.body:
            areas = getattr(invalidated_event.body, "areas", None) or []
            thread_id = getattr(invalidated_event.body, "threadId", None)
            stack_frame_id = getattr(invalidated_event.body, "stackFrameId", None)

            self.ctx.info(
                f"State invalidated: areas={areas}, "
                f"thread={thread_id}, frame={stack_frame_id}",
            )

            # Mark state as needing refresh
            if not hasattr(self._state, "needs_refresh"):
                self._state.needs_refresh = {}

            for area in areas:
                self._state.needs_refresh[area] = True

            # Store invalidation details for potential refresh operations
            self._state.last_invalidation = {
                "areas": areas,
                "threadId": thread_id,
                "stackFrameId": stack_frame_id,
                "timestamp": time.time(),
            }
        else:
            self.ctx.debug("Invalidated event with no body")

    def _handle_capabilities(self, event: Event) -> None:
        """Handle capabilities event.

        This event indicates that one or more capabilities have changed dynamically
        during the debug session.
        """
        capabilities_event = cast("CapabilitiesEvent", event)
        if capabilities_event.body:
            capabilities = capabilities_event.body.capabilities

            self.ctx.info("Adapter capabilities changed dynamically during session")

            # Store the updated capabilities
            # The session should merge these with existing capabilities
            if not hasattr(self._state, "dynamic_capabilities"):
                self._state.dynamic_capabilities = {}

            # Convert capabilities object to dict and merge
            if capabilities:
                cap_dict = {}
                for attr_name in dir(capabilities):
                    if not attr_name.startswith("_"):
                        value = getattr(capabilities, attr_name, None)
                        if value is not None:
                            cap_dict[attr_name] = value

                self._state.dynamic_capabilities.update(cap_dict)

                self.ctx.debug(f"Updated capabilities: {list(cap_dict.keys())}")
        else:
            self.ctx.debug("Capabilities event with no body")

    def register_terminated_listener(self) -> asyncio.Future:
        """Register a one-time listener for terminated event.

        Returns
        -------
        asyncio.Future
            A future that will be resolved when a terminated event occurs
        """
        future: asyncio.Future = asyncio.Future()
        self._terminated_listeners.append(future)
        return future

    def register_stopped_listener(self) -> asyncio.Future:
        """Register a one-time listener for stopped event.

        Returns
        -------
        asyncio.Future
            A future that will be resolved when a stopped event occurs
        """
        future: asyncio.Future = asyncio.Future()
        self._stopped_listeners.append(future)
        self.ctx.debug(
            f"Registered stopped listener "
            f"(total listeners: {len(self._stopped_listeners)})",
        )
        return future

    def _notify_listeners(self, event: Event) -> None:
        """Notify all registered listeners about an event.

        Parameters
        ----------
        event : Event
            The event to notify about
        """
        # Notify specific event type listeners
        specific_listeners = self._listeners[event.event]
        self.ctx.debug(
            f"[EVENT] Notifying {len(specific_listeners)} listeners for event "
            f"{event.event}",
        )

        for i, listener in enumerate(specific_listeners):
            try:
                self.ctx.debug(
                    f"[EVENT] Calling listener {i} for {event.event}: {listener}",
                )
                listener(event)
                self.ctx.debug(f"[EVENT] Listener {i} completed for {event.event}")
            except Exception as e:
                self.ctx.error(f"Event listener error for {event.event}: {e}")

        # Notify wildcard listeners
        wildcard_listeners = self._listeners["*"]
        if wildcard_listeners:
            self.ctx.debug(
                f"[EVENT] Notifying {len(wildcard_listeners)} wildcard listeners",
            )

        for i, listener in enumerate(wildcard_listeners):
            try:
                self.ctx.debug(f"[EVENT] Calling wildcard listener {i}: {listener}")
                listener(event)
                self.ctx.debug(f"[EVENT] Wildcard listener {i} completed")
            except Exception as e:
                self.ctx.error(f"Wildcard event listener error: {e}")

    def subscribe(self, event_type: str, listener: Callable[[Event], None]) -> None:
        """Subscribe to a specific event type.

        Parameters
        ----------
        event_type : str
            Event type to subscribe to (or '*' for all)
        listener : callable
            Function to call when event occurs
        """
        if listener not in self._listeners[event_type]:
            self._listeners[event_type].append(listener)
            self.ctx.debug(
                f"[SUBSCRIBE] Added listener for {event_type} events. "
                f"Total listeners for {event_type}: {len(self._listeners[event_type])}",
            )
        else:
            self.ctx.debug(f"[SUBSCRIBE] Listener already exists for {event_type}")

    def unsubscribe(self, event_type: str, listener: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type.

        Parameters
        ----------
        event_type : str
            Event type to unsubscribe from
        listener : callable
            Listener to remove
        """
        if listener in self._listeners[event_type]:
            self._listeners[event_type].remove(listener)
            self.ctx.debug(f"Unsubscribed from {event_type} events")

    def has_event(self, event_type: str) -> bool:
        """Check if an event has been received without waiting.

        Parameters
        ----------
        event_type : str
            Event type to check

        Returns
        -------
        bool
            True if at least one event of this type has been received
        """
        return self._event_counter[event_type] > 0

    async def wait_for_event(self, event_type: str, timeout: float = 2.0) -> bool:
        """Wait for a specific event type to occur.

        Parameters
        ----------
        event_type : str
            Event type to wait for
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if event occurred, False if timeout
        """
        # Session prefix for log messages
        sid_prefix = f"[{self._session_id[:8]}] " if self._session_id else ""

        # Log wait start with current metrics
        now_wall = time.time()
        last_sig = self._state.event_last_signaled_wall.get(event_type)
        last_proc = self._state.event_last_processed_wall.get(event_type)
        age_sig = (now_wall - last_sig) if last_sig else None
        age_proc = (now_wall - last_proc) if last_proc else None
        with contextlib.suppress(Exception):
            self.ctx.debug(
                f"{sid_prefix}Waiting for event '{event_type}' "
                f"timeout={timeout:.2f}s "
                f"flag_set={self._event_received[event_type].is_set()} "
                + (
                    f"age_sig={age_sig:.3f} age_proc={age_proc:.3f}"
                    if (age_sig is not None and age_proc is not None)
                    else ""
                ),
            )

        # If event already occurred, return immediately (avoid clearing to
        # prevent missed signals)
        if self._event_received[event_type].is_set():
            self.ctx.debug(
                f"{sid_prefix}Event {event_type} already set; returning immediately",
            )
            return True

        # Otherwise wait w/out clearing to avoid a race where the signal is lost
        try:
            await asyncio.wait_for(
                self._event_received[event_type].wait(),
                timeout=timeout,
            )
            result = True
        except asyncio.TimeoutError:
            result = False

        if result:
            try:
                recv_age = None
                last_sig2 = self._state.event_last_signaled_wall.get(event_type)
                if last_sig2:
                    recv_age = time.time() - last_sig2
                self.ctx.debug(
                    f"{sid_prefix}Event {event_type} received"
                    + (f"; age_since_signal={recv_age:.3f}s" if recv_age else ""),
                )
            except Exception as e:
                msg = f"Failed to log event receipt timing for {event_type}: {e}"
                self.ctx.debug(msg)
        else:
            try:
                # On timeout, log richer diagnostics
                last_sig3 = self._state.event_last_signaled_wall.get(event_type)
                last_proc3 = self._state.event_last_processed_wall.get(event_type)
                self.ctx.debug(
                    f"{sid_prefix}Timeout waiting for {event_type}; "
                    f"last_signal={last_sig3} last_processed={last_proc3}",
                )
            except Exception as e:
                msg = f"Failed to log timeout diagnostics for {event_type}: {e}"
                self.ctx.debug(msg)

        return result

    def get_last_event(self, event_type: str) -> Event | None:
        """Get the last event of a specific type.

        Parameters
        ----------
        event_type : str
            Event type to get

        Returns
        -------
        Event or None
            Last event of that type, if any
        """
        return self._last_events.get(event_type)

    def get_breakpoint_events(self) -> list[Event]:
        """Get recent breakpoint events.

        Returns
        -------
        list
            List of recent breakpoint stopped events
        """
        return self._breakpoint_events.copy()

    def clear_events(self) -> None:
        """Clear all stored events and reset counters."""
        self._last_events.clear()
        self._breakpoint_events.clear()
        self._last_stopped_event = None
        self._last_initialized_event = None

        # Clear all event signals and reset counters
        for event in self._event_signal.values():
            event.clear()
        self._event_counter.clear()
