"""Response models for AIDB operations.

This module contains all response models that are returned from debugging operations.
These models provide AI-friendly responses with additional metadata beyond raw DAP
protocol.
"""

from .breakpoints import (
    AidbBreakpointsResponse,
    AidbDataBreakpointInfoResponse,
    AidbDataBreakpointsResponse,
    AidbExceptionBreakpointsResponse,
    AidbFunctionBreakpointsResponse,
)
from .evaluation import AidbEvaluationResponse
from .exception import AidbExceptionResponse
from .execution import AidbStopResponse, ExecutionStateResponse
from .memory import (
    AidbDisassembleResponse,
    AidbModulesResponse,
    AidbReadMemoryResponse,
    AidbWriteMemoryResponse,
)
from .session import StartResponse, StatusResponse
from .stack import AidbCallStackResponse
from .threads import AidbThreadsResponse
from .variables import AidbVariablesResponse

__all__ = [
    # Breakpoints
    "AidbBreakpointsResponse",
    "AidbDataBreakpointInfoResponse",
    "AidbDataBreakpointsResponse",
    "AidbExceptionBreakpointsResponse",
    "AidbFunctionBreakpointsResponse",
    # Evaluation
    "AidbEvaluationResponse",
    # Exception
    "AidbExceptionResponse",
    # Execution
    "AidbStopResponse",
    "ExecutionStateResponse",
    # Memory
    "AidbDisassembleResponse",
    "AidbModulesResponse",
    "AidbReadMemoryResponse",
    "AidbWriteMemoryResponse",
    # Session
    "StartResponse",
    "StatusResponse",
    # Stack
    "AidbCallStackResponse",
    # Threads
    "AidbThreadsResponse",
    # Variables
    "AidbVariablesResponse",
]
