"""Enum definitions for AIDB test suite."""

from enum import Enum


class DebugInterfaceType(str, Enum):
    """Types of debug interfaces for testing.

    Note: The API interface was removed as part of the service layer refactor.
    All tests now run through MCP, which is the public interface for AI agents.
    """

    MCP = "mcp"


class LogLevel(Enum):
    """Log levels used in tests."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """Get numeric log level."""
        import logging

        return getattr(logging, self.value)


class StopReason(Enum):
    """DAP protocol stop reasons."""

    STEP = "step"
    BREAKPOINT = "breakpoint"
    EXCEPTION = "exception"
    PAUSE = "pause"
    ENTRY = "entry"
    GOTO = "goto"
    FUNCTION_BREAKPOINT = "function breakpoint"
    DATA_BREAKPOINT = "data breakpoint"
    INSTRUCTION_BREAKPOINT = "instruction breakpoint"


class TerminationReason(Enum):
    """Program termination reasons for test verification."""

    END = "end"
    EXIT = "exit"
    TERMINATED = "terminated"
    EXITED = "exited"


class TestMarker(Enum):
    """Pytest markers used in the test suite."""

    SMOKE = "smoke"
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    REQUIRES_DOCKER = "requires_docker"
    SERIAL = "serial"
    SLOW = "slow"
    FLAKY = "flaky"
    PERFORMANCE = "performance"


class AdapterState(Enum):
    """Adapter lifecycle states."""

    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class MCPTool(Enum):
    """MCP tool names used in tests."""

    # Core tools
    INIT = "aidb_init"
    SESSION_START = "aidb_session_start"
    SESSION_STOP = "aidb_session_stop"
    SESSION_STATUS = "aidb_session_status"

    # Breakpoint tools
    BREAKPOINT_SET = "aidb_breakpoint_set"
    BREAKPOINT_REMOVE = "aidb_breakpoint_remove"
    BREAKPOINT_LIST = "aidb_breakpoint_list"

    # Execution tools
    EXECUTION_CONTINUE = "aidb_execution_continue"
    EXECUTION_PAUSE = "aidb_execution_pause"
    EXECUTION_STEP = "aidb_execution_step"
    EXECUTION_RESTART = "aidb_execution_restart"

    # Inspection tools
    INSPECT = "aidb_inspect"
    EVALUATE = "aidb_evaluate"

    # Workflow tools
    WORKFLOW_INVESTIGATE = "aidb_investigate"
    WORKFLOW_TRACE = "aidb_trace"


class MCPResponseCode(Enum):
    """MCP response codes used in tests."""

    OK = "OK"
    ERROR = "ERROR"


__all__ = [
    "AdapterState",
    "DebugInterfaceType",
    "LogLevel",
    "MCPResponseCode",
    "MCPTool",
    "StopReason",
    "TerminationReason",
    "TestMarker",
]
