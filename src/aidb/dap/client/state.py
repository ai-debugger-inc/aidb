"""DAP session state tracking."""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aidb.dap.protocol.types import Source


@dataclass
class SessionState:
    """Tracks DAP session state.

    This class maintains the current state of a DAP debugging session, including
    connection status, initialization progress, and health metrics.
    """

    # Connection and initialization state
    connected: bool = False
    initialized: bool = False
    ready_for_configuration: bool = False
    configuration_done: bool = False
    session_established: bool = False

    # Handshake tracking (prevent duplicates)
    handshake_started: bool = False
    handshake_complete: bool = False

    # Execution state
    stopped: bool = False
    terminated: bool = False
    stop_reason: str | None = None
    current_thread_id: int | None = None

    # Location tracking
    current_file: str | None = None
    current_line: int | None = None
    current_column: int | None = None

    # Health monitoring (preserved from original)
    last_response_time: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3

    # Request/Response tracking
    last_command_sent: str | None = None
    total_requests_sent: int = 0
    total_responses_received: int = 0
    connection_start_time: float | None = None

    # Adapter information
    adapter_id: str | None = None
    capabilities: dict = field(default_factory=dict)

    # Instrumentation metrics
    last_message_received_wall: float | None = None
    last_message_received_mono_ns: int | None = None
    receiver_task_id: int | None = None
    receiver_task_name: str | None = None

    # Per-event instrumentation
    event_last_processed_wall: dict[str, float] = field(default_factory=dict)
    event_last_processed_mono_ns: dict[str, int] = field(default_factory=dict)
    event_last_signaled_wall: dict[str, float] = field(default_factory=dict)
    event_last_signaled_mono_ns: dict[str, int] = field(default_factory=dict)
    event_last_task_id: dict[str, int] = field(default_factory=dict)
    event_last_task_name: dict[str, str] = field(default_factory=dict)

    # Source tracking for debugging
    loaded_sources: dict[str, "Source"] = field(default_factory=dict)
    sources_needing_rebind: list = field(default_factory=list)

    # Module tracking for debugging
    loaded_modules: dict[str, Any] = field(default_factory=dict)

    # Invalidation tracking for refreshing state
    needs_refresh: dict[str, bool] = field(default_factory=dict)
    last_invalidation: dict[str, Any] = field(default_factory=dict)

    # Dynamic capabilities that can change during session
    dynamic_capabilities: dict[str, Any] = field(default_factory=dict)

    # Progress tracking for long-running operations
    active_progress: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Output collection (logpoints, stdout, stderr)
    output_buffer: list[dict[str, Any]] = field(default_factory=list)
    output_buffer_max_size: int = 100  # Prevent unbounded growth

    def is_healthy(self) -> bool:
        """Check if the session is in a healthy state."""
        if not self.connected:
            return False
        if self.terminated:
            return False
        if self.consecutive_failures >= self.max_consecutive_failures:
            return False
        # Consider unhealthy if no response in 30 seconds
        return not time.time() - self.last_response_time > 30

    def reset(self) -> None:
        """Reset state to initial values."""
        self.connected = False
        self.initialized = False
        self.ready_for_configuration = False
        self.configuration_done = False
        self.session_established = False
        self.handshake_started = False
        self.handshake_complete = False
        self.stopped = False
        self.terminated = False
        self.stop_reason = None
        self.current_thread_id = None
        self.current_file = None
        self.current_line = None
        self.current_column = None
        self.consecutive_failures = 0
        self.last_response_time = time.time()
        self.last_command_sent = None
        self.total_requests_sent = 0
        self.total_responses_received = 0
        self.connection_start_time = None

        # Reset instrumentation metrics
        self.last_message_received_wall = None
        self.last_message_received_mono_ns = None
        self.receiver_task_id = None
        self.receiver_task_name = None
        self.event_last_processed_wall.clear()
        self.event_last_processed_mono_ns.clear()
        self.event_last_signaled_wall.clear()
        self.event_last_signaled_mono_ns.clear()
        self.event_last_task_id.clear()
        self.event_last_task_name.clear()
        self.loaded_sources.clear()
        self.sources_needing_rebind.clear()
        self.loaded_modules.clear()
        self.needs_refresh.clear()
        self.last_invalidation.clear()
        self.dynamic_capabilities.clear()
        self.active_progress.clear()
        self.output_buffer.clear()

    def get_diagnostics(self) -> dict[str, Any]:
        """Get detailed diagnostics about the session state.

        Returns
        -------
        dict
            Dictionary containing diagnostic information
        """
        now = time.time()
        uptime = None
        if self.connection_start_time:
            uptime = now - self.connection_start_time

        # Build per-event metrics snapshot
        event_metrics: dict[str, dict[str, Any]] = {}
        for ev, t_wall in self.event_last_signaled_wall.items():
            event_metrics[ev] = {
                "signal_wall_time": t_wall,
                "signal_age": (now - t_wall) if t_wall else None,
                "signal_mono_ns": self.event_last_signaled_mono_ns.get(ev),
                "processed_wall_time": self.event_last_processed_wall.get(ev),
                "processed_mono_ns": self.event_last_processed_mono_ns.get(ev),
                "task_id": self.event_last_task_id.get(ev),
                "task_name": self.event_last_task_name.get(ev),
            }

        return {
            "connected": self.connected,
            "healthy": self.is_healthy(),
            "initialized": self.initialized,
            "configuration_done": self.configuration_done,
            "session_established": self.session_established,
            "handshake_complete": self.handshake_complete,
            "stopped": self.stopped,
            "terminated": self.terminated,
            "stop_reason": self.stop_reason,
            "current_thread_id": self.current_thread_id,
            "last_command": self.last_command_sent,
            "total_requests": self.total_requests_sent,
            "total_responses": self.total_responses_received,
            "consecutive_failures": self.consecutive_failures,
            "connection_uptime": uptime,
            "time_since_last_response": (
                now - self.last_response_time if self.last_response_time else None
            ),
            "adapter_id": self.adapter_id,
            # Receiver/thread instrumentation
            "receiver_task_id": self.receiver_task_id,
            "receiver_task_name": self.receiver_task_name,
            "last_message_wall_time": self.last_message_received_wall,
            "time_since_last_message": (
                (now - self.last_message_received_wall)
                if self.last_message_received_wall
                else None
            ),
            # Event instrumentation snapshot
            "event_metrics": event_metrics,
        }
