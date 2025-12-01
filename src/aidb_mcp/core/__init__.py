"""Core infrastructure for MCP debugging tools.

This package contains fundamental utilities, constants, and serialization that are used
throughout the MCP system.
"""

from __future__ import annotations

from .constants import (
    BreakpointAction,
    ConfigAction,
    DebugAdapter,
    DetailLevel,
    EventType,
    ExecutionAction,
    FileExtension,
    InspectTarget,
    LaunchMode,
    ParamName,
    ResponseStatus,
    SessionAction,
    SessionState,
    StepAction,
    TestFailureMode,
    ToolAction,
    ToolName,
    VariableAction,
)
from .exceptions import (
    ErrorCategory,
    ErrorCode,
    ErrorRecovery,
    classify_error,
    get_recovery_strategy,
    get_suggested_actions,
)
from .serialization import to_jsonable

__all__ = [
    # Constants (exported from constants module)
    "DebugAdapter",
    "ToolName",
    "ResponseStatus",
    "EventType",
    "SessionState",
    "DetailLevel",
    "TestFailureMode",
    "ParamName",
    "FileExtension",
    "LaunchMode",
    # Action enums
    "SessionAction",
    "ConfigAction",
    "BreakpointAction",
    "VariableAction",
    "InspectTarget",
    "ExecutionAction",
    "StepAction",
    "ToolAction",
    # Error handling utilities
    "ErrorCategory",
    "ErrorCode",
    "ErrorRecovery",
    "classify_error",
    "get_recovery_strategy",
    "get_suggested_actions",
    # Serialization
    "to_jsonable",
]
