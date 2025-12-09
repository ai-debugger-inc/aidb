"""MCP session context management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aidb_logging import get_mcp_logger as get_logger

from ..core.variable_tracker import VariableTracker

if TYPE_CHECKING:
    from aidb.models import AidbStackFrame, SessionInfo

    from ..core.types import BreakpointSpec, VariableValue

logger = get_logger(__name__)


@dataclass
class MCPSessionContext:
    """Maintains debugging context across MCP session operations."""

    # Session info
    session_info: SessionInfo | None = None
    session_started: bool = False

    # Current position
    current_thread_id: int | None = None
    current_frame_id: int | None = None
    current_file: str | None = None
    current_line: int | None = None

    # Execution state
    is_running: bool = False
    is_paused: bool = False
    is_terminated: bool = False
    at_breakpoint: bool = False
    last_operation: str | None = None

    # Collected data
    breakpoints_set: list[BreakpointSpec] = field(
        default_factory=list,
    )
    breakpoints_hit: list[BreakpointSpec] = field(
        default_factory=list,
    )
    variables_tracked: dict[str, list[VariableValue]] = field(default_factory=dict)
    # ExecutionHistoryEntry base structure, but accepts arbitrary extra fields
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    error_info: dict[str, str | int | None] | None = None

    # Init and start context tracking
    init_completed: bool = False  # Track if init was called for this session
    start_context_loaded: bool = False
    language_context: str | None = None
    framework_context: str | None = None
    mode_context: str | None = None

    # Stack info
    call_stack: list[AidbStackFrame] = field(default_factory=list)

    # Variable tracking
    last_locals: list[VariableValue] | dict[str, Any] | None = None
    last_globals: list[VariableValue] | dict[str, Any] | None = None
    variable_tracker: VariableTracker = field(default_factory=VariableTracker)

    # Restart context - stores launch params for session restart
    launch_params: dict[str, Any] = field(default_factory=dict)

    # Source path resolution for remote debugging
    source_paths: list[str] = field(default_factory=list)

    # Event bridge subscription IDs for cleanup
    event_subscription_ids: list[str] = field(default_factory=list)

    def reset(self):
        """Reset the context to initial state."""
        logger.debug(
            "Resetting MCP session context",
            extra={
                "had_session": self.session_info is not None,
                "history_size": len(self.execution_history),
                "breakpoints_set": len(self.breakpoints_set),
                "init_completed": self.init_completed,
            },
        )

        self.session_info = None
        self.session_started = False
        self.current_thread_id = None
        self.current_frame_id = None
        self.current_file = None
        self.current_line = None
        self.is_running = False
        self.is_paused = False
        self.is_terminated = False
        self.at_breakpoint = False
        self.breakpoints_set = []
        self.breakpoints_hit = []
        self.variables_tracked = {}
        self.execution_history = []
        self.error_info = None
        self.call_stack = []

        # Reset init context
        self.init_completed = False
        self.start_context_loaded = False
        self.language_context = None
        self.framework_context = None
        self.mode_context = None

        # Reset launch params
        self.launch_params = {}

        # Reset source paths
        self.source_paths = []

        # Reset event subscription IDs
        self.event_subscription_ids = []

    def update_position(self, frame: AidbStackFrame | None = None):
        """Update current position from a stack frame."""
        if frame:
            old_position = (self.current_file, self.current_line)
            self.current_frame_id = frame.id
            self.current_file = frame.source.path
            self.current_line = frame.source.line

            logger.debug(
                "Updated session position",
                extra={
                    "frame_id": frame.id,
                    "file": frame.source.path,
                    "line": frame.source.line,
                    "old_file": old_position[0],
                    "old_line": old_position[1],
                },
            )

    def record_execution_step(self, action: str, **details):
        """Record an execution step."""
        from datetime import datetime, timezone

        step_record = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": self.current_file,
            "line": self.current_line,
            "thread": self.current_thread_id,
            **details,
        }

        logger.info(
            "Recorded execution step",
            extra={
                "action": action,
                "file": self.current_file,
                "line": self.current_line,
                "thread_id": self.current_thread_id,
                "detail_count": len(details),
            },
        )

        self.execution_history.append(step_record)
