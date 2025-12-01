"""Protocol-based response system for MCP tools."""

from __future__ import annotations

from .adapter import (
    AdapterBulkDownloadResponse,
    AdapterDownloadResponse,
    AdapterListResponse,
)
from .base import ErrorResponse, MCPResponseProtocol, Response
from .context import ContextResponse
from .errors import (
    AidbTimeoutError,
    ConnectionLostError,
    InternalError,
    InvalidParameterError,
    MissingParameterError,
    NoSessionError,
    NotPausedError,
    SessionNotStartedError,
    UnsupportedOperationError,
)
from .execution import ExecuteResponse, RunUntilResponse, StepResponse
from .inspection import (
    BreakpointListResponse,
    BreakpointMutationResponse,
    InspectResponse,
    VariableGetResponse,
    VariableSetResponse,
)
from .session import (
    SessionListResponse,
    SessionStartResponse,
    SessionStatusResponse,
    SessionStopResponse,
)

__all__ = [
    # Base classes
    "MCPResponseProtocol",
    "Response",
    "ErrorResponse",
    # Adapter responses
    "AdapterDownloadResponse",
    "AdapterBulkDownloadResponse",
    "AdapterListResponse",
    # Session responses
    "SessionStartResponse",
    "SessionStopResponse",
    "SessionStatusResponse",
    "SessionListResponse",
    # Execution responses
    "ExecuteResponse",
    "StepResponse",
    "RunUntilResponse",
    # Inspection responses
    "InspectResponse",
    "VariableGetResponse",
    "VariableSetResponse",
    "BreakpointMutationResponse",
    "BreakpointListResponse",
    # Context responses
    "ContextResponse",
    # Error responses
    "NoSessionError",
    "SessionNotStartedError",
    "NotPausedError",
    "ConnectionLostError",
    "InvalidParameterError",
    "MissingParameterError",
    "AidbTimeoutError",
    "UnsupportedOperationError",
    "InternalError",
]
