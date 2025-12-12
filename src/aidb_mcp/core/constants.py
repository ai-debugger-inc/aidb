"""Constants and enums for MCP tools.

This module provides standardized constants and enums to replace string literals
throughout the MCP codebase.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class DebugAdapter(Enum):
    """Debug adapter types."""

    DEBUGPY = "debugpy"
    NODE = "node"
    NODE2 = "node2"
    CHROME = "chrome"
    JAVA = "java"


class ToolName:
    """Standard tool names."""

    INSPECT = "inspect"
    STEP = "step"
    EXECUTE = "execute"
    BREAKPOINT = "breakpoint"
    VARIABLE = "variable"
    SESSION = "session"
    SESSION_START = "session_start"
    CONFIG = "config"
    CONTEXT = "context"
    RUN_UNTIL = "run_until"
    INIT = "init"
    ADAPTER = "adapter"


class ResponseStatus:
    """Response status codes."""

    OK = "OK"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class EventType(Enum):
    """Event types for debugging events."""

    BREAKPOINT_HIT = "breakpoint_hit"
    STEP_COMPLETE = "step_complete"
    EXCEPTION = "exception"
    THREAD_STARTED = "thread_started"
    THREAD_EXITED = "thread_exited"
    SESSION_STATE_CHANGED = "session_state_changed"
    WATCH_CHANGED = "watch_changed"  # DAP data breakpoint (watchpoint) events
    THREAD_EVENT = "thread_event"
    TERMINATED = "terminated"  # Program ended


class NotificationEventType(Enum):
    """Simplified event types for agent subscriptions.

    Keep this list minimal to reduce cognitive load.
    """

    BREAKPOINT = "breakpoint"  # Any breakpoint hit
    EXCEPTION = "exception"  # Any exception occurred
    TERMINATED = "terminated"  # Program ended (auto-subscribed)


class ExecutionState(Enum):
    """Execution state of debug session."""

    RUNNING = "running"
    PAUSED = "paused"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


class DetailedExecutionStatus(Enum):
    """Combines execution state with stop reason for clearer status messaging.

    This enum provides more specific status values that help agents understand both the
    current state and the reason for that state, enabling better next-step guidance and
    error handling.
    """

    STOPPED_AT_BREAKPOINT = "stopped_at_breakpoint"
    STOPPED_AT_EXCEPTION = "stopped_at_exception"
    STOPPED_AFTER_STEP = "stopped_after_step"
    RUNNING_TO_BREAKPOINT = "running_to_breakpoint"
    RUNNING = "running"
    TERMINATED = "terminated"
    PAUSED = "paused"
    INITIALIZED = "initialized"  # Session ready but not started
    UNKNOWN = "unknown"  # Only for error cases


class SessionState(Enum):
    """Session states."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    ERROR = "error"


class ConnectionStatus(Enum):
    """Debug API connection status."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class DetailLevel(Enum):
    """Detail levels for responses."""

    BRIEF = "brief"
    DETAILED = "detailed"
    FULL = "full"


class TestFailureMode(Enum):
    """Test failure modes."""

    ASSERTION = "assertion"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"
    SETUP = "setup"
    TEARDOWN = "teardown"


class SessionAction(Enum):
    """Valid actions for aidb.session tool."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    LIST = "list"
    CLEANUP = "cleanup"
    SWITCH = "switch"
    SUBSCRIBE = "subscribe"


class ConfigAction(Enum):
    """Valid actions for aidb.config tool."""

    GET = "get"
    SET = "set"
    LIST = "list"
    ENV = "env"
    CAPABILITIES = "capabilities"
    LAUNCH = "launch"
    ADAPTERS = "adapters"  # Check adapter installation status
    SHOW = "show"  # Alias for list


class BreakpointAction(Enum):
    """Valid actions for aidb.breakpoint tool."""

    SET = "set"
    REMOVE = "remove"
    LIST = "list"
    CLEAR_ALL = "clear_all"
    WATCH = "watch"
    UNWATCH = "unwatch"


class VariableAction(Enum):
    """Valid actions for aidb.variable tool."""

    GET = "get"
    SET = "set"
    PATCH = "patch"


class InspectTarget(Enum):
    """Valid targets for aidb.inspect tool."""

    LOCALS = "locals"
    GLOBALS = "globals"
    STACK = "stack"
    THREADS = "threads"
    EXPRESSION = "expression"
    ALL = "all"


class ExecutionAction(Enum):
    """Valid actions for aidb.execute tool."""

    RUN = "run"
    CONTINUE = "continue"


class StepAction(Enum):
    """Valid actions for aidb.step tool."""

    INTO = "into"
    OVER = "over"
    OUT = "out"


class AdapterAction(Enum):
    """Valid actions for aidb.adapter tool."""

    DOWNLOAD = "download"
    DOWNLOAD_ALL = "download_all"
    LIST = "list"


class AdapterStatus(Enum):
    """Debug adapter installation status."""

    READY = "ready"
    MISSING = "missing"
    NOT_INSTALLED = "not_installed"


class DefaultValue:
    """Default sentinel values for missing data."""

    UNKNOWN = "unknown"
    VERSION_UNKNOWN = "unknown"
    PATH_UNKNOWN = "unknown"


class BreakpointState(Enum):
    """Breakpoint verification states."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    PENDING = "pending"


class StopReason:
    """MCP-specific stop reasons (not from DAP protocol).

    These are custom stop reasons used by the MCP layer that extend beyond the standard
    DAP protocol stop reasons.
    """

    BREAKPOINT = "breakpoint"
    ENTRY = "entry"
    STEP = "step"
    EXCEPTION = "exception"
    PAUSE = "pause"
    COMPLETED = "completed"


class DebugURI:
    """Constants for debug URI construction."""

    SCHEME = "debug://"
    EVENT_PREFIX = "debug://event/"
    SESSION_PREFIX = "debug://session/"
    BREAKPOINT_PREFIX = "debug://breakpoint/"
    WATCH_PREFIX = "debug://watch/"

    @staticmethod
    def event(event_type: str) -> str:
        """Create an event URI."""
        return f"{DebugURI.EVENT_PREFIX}{event_type}"

    @staticmethod
    def session_event(session_id: str, event_type: str) -> str:
        """Create a session-specific event URI."""
        return f"{DebugURI.SESSION_PREFIX}{session_id}/{event_type}"


class ParamName:
    """Common parameter names."""

    # Core debugging parameters
    SESSION_ID = "session_id"
    TARGET = "target"
    LOCATION = "location"
    EXPRESSION = "expression"
    ACTION = "action"
    FRAME = "frame"
    FRAME_ID = "frame_id"
    BREAKPOINTS = "breakpoints"
    ARGS = "args"
    ENV = "env"
    CONDITION = "condition"
    LOG_MESSAGE = "log_message"
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    PATTERN = "pattern"
    QUERY = "query"
    TIMEOUT = "timeout"
    DETAILED = "detailed"

    # Launch/Debug parameters
    MODE = "mode"
    WORKSPACE_ROOT = "workspace_root"
    WORKSPACE_ROOTS = "workspace_roots"
    LAUNCH_CONFIG_NAME = "launch_config_name"
    CWD = "cwd"
    PID = "pid"
    HOST = "host"
    PORT = "port"
    MODULE = "module"
    SUBSCRIBE_EVENTS = "subscribe_events"
    SOURCE_PATHS = "source_paths"

    # Execution control parameters
    COUNT = "count"
    UNTIL = "until"
    JUMP_TARGET = "jump_target"
    WAIT_FOR_STOP = "wait_for_stop"
    COLLECT_OUTPUT = "collect_output"

    # Breakpoint parameters
    COLUMN = "column"
    HIT_CONDITION = "hit_condition"
    ACCESS_TYPE = "access_type"  # For watchpoints: read, write, readWrite

    # Variable parameters
    NAME = "name"
    VALUE = "value"
    CODE = "code"

    # Tool-specific parameters
    VERSION = "version"
    FORCE = "force"
    KEEP_BREAKPOINTS = "keep_breakpoints"

    # Configuration parameters
    KEY = "key"
    CONFIG_NAME = "config_name"
    DETAIL_LEVEL = "detail_level"
    INCLUDE_SUGGESTIONS = "include_suggestions"
    VERBOSE = "verbose"

    # Advanced parameters
    ALTERNATIVE_LOCATIONS = "alternative_locations"


class FileExtension:
    """Common file extensions."""

    PYTHON = ".py"
    JAVASCRIPT = ".js"
    TYPESCRIPT = ".ts"
    JSX = ".jsx"
    TSX = ".tsx"
    JAVA = ".java"

    PARTIAL = "partial"


class ResponseFieldName:
    """Response field names for MCP responses.

    Centralizes field name constants to avoid magic strings and improve maintainability.
    Used across response classes, builders, and deduplicator.
    """

    # Execution state fields
    EXECUTION_STATE = "execution_state"
    STOP_REASON = "stop_reason"
    BREAKPOINTS_ACTIVE = "breakpoints_active"
    STATUS = "status"
    DETAILED_STATUS = "detailed_status"
    IS_PAUSED = "is_paused"
    STATE = "state"

    # Code context fields
    CODE_CONTEXT = "code_context"
    CODE_SNAPSHOT = "code_snapshot"
    FORMATTED = "formatted"
    LINES = "lines"
    CURRENT_LINE = "current_line"

    # Location fields
    LOCATION = "location"
    CURRENT_LOCATION = "current_location"

    # Inspection fields
    LOCALS = "locals"
    GLOBALS = "globals"
    STACK = "stack"
    THREADS = "threads"
    RESULT = "result"
    EXPRESSION = "expression"

    # Variable fields
    NAME = "name"
    VALUE = "value"
    TYPE_NAME = "type_name"
    VAR_TYPE = "var_type"
    ID = "id"
    HAS_CHILDREN = "has_children"
    CHILDREN = "children"

    # Error fields
    ERROR = "error"
    MODULE = "module"

    # Session fields
    INITIAL_STATE = "initial_state"
    EXECUTION_PAUSED = "execution_paused"

    # Metadata fields (for removal)
    TIMESTAMP = "timestamp"
    CREATED_AT = "created_at"
    CORRELATION_ID = "correlation_id"
    OPERATION_ID = "operation_id"
    OPERATION = "operation"
    VERSION = "version"

    # Additional data fields
    REACHED_TARGET = "reached_target"
    ALL = "all"


class MCPResponseField:
    """MCP Protocol top-level response field names.

    These constants represent the standard top-level fields in MCP responses, used to
    maintain consistency and avoid magic strings throughout the codebase.
    """

    SUCCESS = "success"
    SUMMARY = "summary"
    DATA = "data"
    NEXT_STEPS = "next_steps"
    SESSION_ID = "session_id"
    ERROR_CODE = "error_code"
    ERROR_MESSAGE = "error_message"


class LaunchMode(Enum):
    """Session launch modes."""

    LAUNCH = "launch"
    ATTACH = "attach"
    REMOTE_ATTACH = "remote_attach"


class ResponseDataKey:
    """Keys used in response data dictionaries."""

    ACTION = "action"
    STEP = "step"


class BreakpointStatus:
    """Breakpoint status values."""

    NONE = "none"
    ACTIVE = "active"
    INACTIVE = "inactive"


class ErrorMessage:
    """Error message constants."""

    RESTART_NOT_SUPPORTED = "restart_not_supported"


# Tool sets for categorization
EXECUTION_TOOLS = {
    ToolName.SESSION_START,
    ToolName.EXECUTE,
    ToolName.STEP,
    ToolName.RUN_UNTIL,
}


class ToolAction(Enum):
    """Semantic combinations of tools and their common actions.

    Format: (tool_name, action_enum, description, when_phrase)
    """

    # Session actions
    SESSION_STATUS = (
        ToolName.SESSION,
        SessionAction.STATUS,
        "Check session status",
        "to verify state",
    )
    SESSION_LIST = (
        ToolName.SESSION,
        SessionAction.LIST,
        "List active sessions",
        "to see all sessions",
    )
    SESSION_STOP = (
        ToolName.SESSION,
        SessionAction.STOP,
        "Stop debug session",
        "to free resources",
    )
    SESSION_START = (
        ToolName.SESSION_START,
        None,
        "Start debug session",
        "to begin debugging",
    )
    SESSION_START_WITH_TARGET = (
        ToolName.SESSION_START,
        None,
        "Debug a specific file",
        "with target file",
    )
    SESSION_RESTART = (
        ToolName.SESSION,
        SessionAction.RESTART,
        "Restart debug session",
        "to recover",
    )

    # Breakpoint actions
    BREAKPOINT_SET = (
        ToolName.BREAKPOINT,
        BreakpointAction.SET,
        "Set a breakpoint",
        "to pause execution",
    )
    BREAKPOINT_LIST = (
        ToolName.BREAKPOINT,
        BreakpointAction.LIST,
        "List existing breakpoints",
        "to see active breakpoints",
    )
    BREAKPOINT_REMOVE = (
        ToolName.BREAKPOINT,
        BreakpointAction.REMOVE,
        "Remove breakpoints",
        "to clear stops",
    )

    # Inspection actions
    INSPECT_LOCALS = (
        ToolName.INSPECT,
        InspectTarget.LOCALS,
        "Inspect local variables",
        "to examine state",
    )
    INSPECT_STACK = (
        ToolName.INSPECT,
        InspectTarget.STACK,
        "Check call stack",
        "to see execution path",
    )
    INSPECT_GLOBALS = (
        ToolName.INSPECT,
        InspectTarget.GLOBALS,
        "Inspect global variables",
        "to check globals",
    )
    INSPECT_CURRENT = (
        ToolName.INSPECT,
        None,
        "Check current execution state",
        "to see current values",
    )

    # Execution actions
    EXECUTE_CONTINUE = (
        ToolName.EXECUTE,
        ExecutionAction.CONTINUE,
        "Continue execution",
        "to resume program",
    )
    EXECUTE_RUN = (
        ToolName.EXECUTE,
        ExecutionAction.RUN,
        "Run the program",
        "immediately",
    )

    # Stepping actions
    STEP_OVER = (ToolName.STEP, StepAction.OVER, "Step over line", "to advance")
    STEP_INTO = (
        ToolName.STEP,
        StepAction.INTO,
        "Step into function",
        "for detailed analysis",
    )
    STEP_OUT = (
        ToolName.STEP,
        StepAction.OUT,
        "Step out of function",
        "to return to caller",
    )

    # Variable actions
    VARIABLE_GET = (
        ToolName.VARIABLE,
        VariableAction.GET,
        "Get variable value",
        "to examine",
    )
    VARIABLE_SET = (
        ToolName.VARIABLE,
        VariableAction.SET,
        "Set variable value",
        "to modify",
    )

    # Config actions
    CONFIG_CAPABILITIES = (
        ToolName.CONFIG,
        ConfigAction.CAPABILITIES,
        "Check language capabilities",
        "to verify support",
    )
    CONFIG_ENV = (
        ToolName.CONFIG,
        ConfigAction.ENV,
        "Show environment variables",
        "to check config",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for next_steps."""
        tool, action_enum, description, when = self.value
        result = {"tool": tool, "description": description, "when": when}
        if action_enum:
            result["params_example"] = {"action": action_enum.value}
        return result
