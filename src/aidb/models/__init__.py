"""Response models for the aidb API.

This subpackage contains dataclasses that represent structured responses returned by
debugger operations.
"""

from .base import OperationResponse, SamplingMixin
from .entities import (
    AidbBreakpoint,
    AidbStackFrame,
    AidbThread,
    AidbVariable,
    BreakpointState,
    DisassembledInstruction,
    EvaluationResult,
    ExceptionInfo,
    ExecutionState,
    Module,
    ScopeVariables,
    SessionInfo,
    SessionStatus,
    SourceLocation,
    StopReason,
    ThreadState,
    VariableType,
)
from .responses import (
    AidbBreakpointsResponse,
    AidbCallStackResponse,
    AidbDataBreakpointInfoResponse,
    AidbDataBreakpointsResponse,
    AidbDisassembleResponse,
    AidbEvaluationResponse,
    AidbExceptionBreakpointsResponse,
    AidbExceptionResponse,
    AidbFunctionBreakpointsResponse,
    AidbModulesResponse,
    AidbReadMemoryResponse,
    AidbStopResponse,
    AidbThreadsResponse,
    AidbVariablesResponse,
    AidbWriteMemoryResponse,
    ExecutionStateResponse,
    StartResponse,
    StatusResponse,
)
from .start_request import StartRequestType

__all__ = [
    # Base models
    "OperationResponse",
    "SamplingMixin",
    # Request type
    "StartRequestType",
    # Entity models with Aidb prefix
    "AidbBreakpoint",
    "AidbStackFrame",
    "AidbThread",
    "AidbVariable",
    # Response models with Aidb prefix
    "AidbBreakpointsResponse",
    "AidbCallStackResponse",
    "AidbDataBreakpointInfoResponse",
    "AidbDataBreakpointsResponse",
    "AidbDisassembleResponse",
    "AidbEvaluationResponse",
    "AidbExceptionBreakpointsResponse",
    "AidbExceptionResponse",
    "AidbFunctionBreakpointsResponse",
    "AidbModulesResponse",
    "AidbReadMemoryResponse",
    "AidbStopResponse",
    "AidbThreadsResponse",
    "AidbVariablesResponse",
    "AidbWriteMemoryResponse",
    # Other entity and response models
    "BreakpointState",
    "DisassembledInstruction",
    "EvaluationResult",
    "ExceptionInfo",
    "ExecutionState",
    "ExecutionStateResponse",
    "Module",
    "ScopeVariables",
    "SessionInfo",
    "SessionStatus",
    "SourceLocation",
    "StartResponse",
    "StatusResponse",
    "StopReason",
    "ThreadState",
    "VariableType",
]
