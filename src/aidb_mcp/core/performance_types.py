"""Performance tracing types and enums.

This module defines the type system for performance monitoring, following the pattern of
core/constants.py and core/types.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "TimingFormat",
    "SpanType",
    "TokenEstimationMethod",
    "PerformanceSpan",
    "PerformanceBreakdown",
    "SessionContextTracking",
]


class TimingFormat(Enum):
    """Performance log output formats."""

    TEXT = "text"
    JSON = "json"
    CSV = "csv"


class SpanType(Enum):
    """Types of performance spans for categorization."""

    MCP_CALL = "mcp_call"
    HANDLER_DISPATCH = "dispatch"
    HANDLER_EXECUTION = "handler"
    VALIDATION = "validation"
    THREAD_SAFETY = "thread_safety"
    CONTEXT_GATHER = "context_gather"
    SERIALIZATION = "serialization"
    DAP_OPERATION = "dap_operation"


class TokenEstimationMethod(Enum):
    """Methods for estimating token count."""

    TIKTOKEN = "tiktoken"
    SIMPLE = "simple"
    DISABLED = "disabled"


@dataclass
class PerformanceSpan:
    """Represents a timed operation span.

    Following the pattern of MCPSessionContext in session/context.py.

    Attributes
    ----------
    span_id : str
        Unique identifier for this span
    span_type : SpanType
        Type/category of this span
    operation : str
        Operation name being measured
    correlation_id : str | None
        ID linking related spans in a request
    parent_span_id : str | None
        ID of parent span if nested
    start_ns : int
        Start time in nanoseconds
    end_ns : int
        End time in nanoseconds
    duration_ms : float
        Duration in milliseconds
    metadata : dict[str, Any]
        Additional span metadata
    success : bool
        Whether operation succeeded
    error : str | None
        Error message if failed
    response_chars : int | None
        Response character count
    response_tokens : int | None
        Estimated response token count
    response_size_bytes : int | None
        Response size in bytes
    """

    span_id: str
    span_type: SpanType
    operation: str
    correlation_id: str | None = None
    parent_span_id: str | None = None
    start_ns: int = 0
    end_ns: int = 0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None

    # Response size tracking
    response_chars: int | None = None
    response_tokens: int | None = None
    response_size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns
        -------
        dict[str, Any]
            Span data as dictionary
        """
        return {
            "span_id": self.span_id,
            "span_type": self.span_type.value,
            "operation": self.operation,
            "correlation_id": self.correlation_id,
            "parent_span_id": self.parent_span_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
            "response_chars": self.response_chars,
            "response_tokens": self.response_tokens,
            "response_size_bytes": self.response_size_bytes,
        }


@dataclass
class PerformanceBreakdown:
    """Performance breakdown for an operation.

    Attributes
    ----------
    operation : str
        Operation name
    total_avg_ms : float
        Average total duration
    breakdown : dict[str, float]
        Breakdown by span type
    percentiles : dict[str, float]
        Percentile statistics (p50, p95, p99)
    count : int
        Number of operations measured
    slow_count : int
        Count of slow operations
    avg_response_tokens : float | None
        Average response size in tokens
    max_response_tokens : int | None
        Maximum response size in tokens
    avg_response_chars : float | None
        Average response size in characters
    p95_response_tokens : float | None
        95th percentile response tokens
    """

    operation: str
    total_avg_ms: float
    breakdown: dict[str, float]
    percentiles: dict[str, float]
    count: int
    slow_count: int

    # Response size stats
    avg_response_tokens: float | None = None
    max_response_tokens: int | None = None
    avg_response_chars: float | None = None
    p95_response_tokens: float | None = None


@dataclass
class SessionContextTracking:
    """Tracks cumulative context consumption for a session.

    Attributes
    ----------
    session_id : str
        Session identifier
    total_request_tokens : int
        Total tokens in requests
    total_response_tokens : int
        Total tokens in responses
    operation_count : int
        Number of operations
    largest_response : int
        Size of largest response in tokens
    largest_operation : str
        Name of operation with largest response
    """

    session_id: str
    total_request_tokens: int = 0
    total_response_tokens: int = 0
    operation_count: int = 0
    largest_response: int = 0
    largest_operation: str = ""

    @property
    def total_tokens(self) -> int:
        """Total context consumed by this session.

        Returns
        -------
        int
            Sum of request and response tokens
        """
        return self.total_request_tokens + self.total_response_tokens
