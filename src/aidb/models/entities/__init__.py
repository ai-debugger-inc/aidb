"""Entity models for AIDB.

This module contains pure data objects representing debugging entities like breakpoints,
threads, variables, and stack frames.
"""

from .breakpoint import AidbBreakpoint, BreakpointState
from .exception import ExceptionInfo
from .memory import DisassembledInstruction, Module
from .session import ExecutionState, SessionInfo, SessionStatus, StopReason
from .stack import AidbStackFrame, SourceLocation
from .thread import AidbThread, ThreadState
from .variable import AidbVariable, EvaluationResult, ScopeVariables, VariableType

__all__ = [
    # Breakpoint
    "AidbBreakpoint",
    "BreakpointState",
    # Exception
    "ExceptionInfo",
    # Memory
    "DisassembledInstruction",
    "Module",
    # Session
    "ExecutionState",
    "SessionInfo",
    "SessionStatus",
    "StopReason",
    # Stack
    "AidbStackFrame",
    "SourceLocation",
    # Thread
    "AidbThread",
    "ThreadState",
    # Variable
    "AidbVariable",
    "EvaluationResult",
    "ScopeVariables",
    "VariableType",
]
