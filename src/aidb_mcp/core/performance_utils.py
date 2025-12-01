"""Performance analysis utilities.

Provides functions for analyzing timing data and generating reports. Follows pattern of
core/context_utils.py.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from .config import get_config
from .performance import _span_history, _timing_history
from .performance_types import PerformanceBreakdown

__all__ = [
    "get_operation_breakdown",
    "get_all_operations",
    "get_correlation_trace",
    "get_token_consumption_report",
]

logger = get_logger(__name__)


def _percentile(data: list[float], p: float) -> float:
    """Calculate percentile of data.

    Parameters
    ----------
    data : list[float]
        Sorted data values
    p : float
        Percentile (0.0 to 1.0)

    Returns
    -------
    float
        Percentile value
    """
    if not data:
        return 0.0

    idx = int(len(data) * p)
    return data[min(idx, len(data) - 1)]


def get_operation_breakdown(operation: str) -> PerformanceBreakdown | None:
    """Get detailed performance breakdown for an operation.

    Parameters
    ----------
    operation : str
        Operation name to analyze

    Returns
    -------
    PerformanceBreakdown | None
        Breakdown if data available, None otherwise
    """
    if not _span_history:
        return None

    # Filter spans for this operation
    op_spans = [s for s in _span_history if s.operation == operation]

    if not op_spans:
        return None

    durations = sorted([s.duration_ms for s in op_spans])

    # Aggregate breakdown by span type
    breakdown_by_type: dict[str, list[float]] = {}
    for span in op_spans:
        span_type_name = span.span_type.value
        breakdown_by_type.setdefault(span_type_name, []).append(span.duration_ms)

    breakdown_avg = {
        span_type: sum(durations_list) / len(durations_list)
        for span_type, durations_list in breakdown_by_type.items()
    }

    # Collect token stats
    token_counts: list[int] = []
    for s in op_spans:
        tokens = s.metadata.get("response_tokens") or s.response_tokens
        if tokens is not None:
            token_counts.append(tokens)

    char_counts: list[int] = []
    for s in op_spans:
        chars = s.metadata.get("response_chars") or s.response_chars
        if chars is not None:
            char_counts.append(chars)

    # Calculate token statistics
    avg_tokens = sum(token_counts) / len(token_counts) if token_counts else None
    max_tokens = max(token_counts) if token_counts else None
    p95_tokens = _percentile(sorted(token_counts), 0.95) if token_counts else None

    avg_chars = sum(char_counts) / len(char_counts) if char_counts else None

    # Count slow operations
    cfg = get_config().performance
    slow_count = sum(1 for d in durations if d > cfg.slow_threshold_ms)

    return PerformanceBreakdown(
        operation=operation,
        total_avg_ms=sum(durations) / len(durations),
        breakdown=breakdown_avg,
        percentiles={
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "p99": _percentile(durations, 0.99),
        },
        count=len(durations),
        slow_count=slow_count,
        avg_response_tokens=avg_tokens,
        max_response_tokens=max_tokens,
        avg_response_chars=avg_chars,
        p95_response_tokens=p95_tokens,
    )


def get_all_operations() -> list[str]:
    """Get list of all tracked operations.

    Returns
    -------
    list[str]
        Unique operation names sorted alphabetically
    """
    operations = set()

    for entry in _timing_history:
        operations.add(entry["operation"])

    for span in _span_history:
        operations.add(span.operation)

    return sorted(operations)


def get_correlation_trace(correlation_id: str) -> list[dict[str, Any]]:
    """Get all spans for a specific correlation ID (request trace).

    Parameters
    ----------
    correlation_id : str
        Correlation ID to trace

    Returns
    -------
    list[dict[str, Any]]
        Spans in chronological order
    """
    spans = [s.to_dict() for s in _span_history if s.correlation_id == correlation_id]

    # Sort by start time (using span_id which includes timestamp order)
    spans.sort(key=lambda s: s.get("span_id", ""))

    return spans


def get_token_consumption_report() -> dict[str, Any]:
    """Generate token consumption report across all operations.

    Returns
    -------
    dict[str, Any]
        Report with:
        - total_tokens: sum of all estimated tokens
        - by_operation: breakdown by operation type
        - largest_responses: top 10 largest responses
    """
    if not _span_history:
        return {}

    # Aggregate by operation
    by_operation: dict[str, list[int]] = {}
    all_responses: list[dict[str, Any]] = []

    for span in _span_history:
        # Check both metadata and direct field
        tokens = span.metadata.get("response_tokens") or span.response_tokens
        if tokens:
            by_operation.setdefault(span.operation, []).append(tokens)
            chars = span.metadata.get("response_chars") or span.response_chars or 0
            all_responses.append(
                {
                    "operation": span.operation,
                    "tokens": tokens,
                    "chars": chars,
                    "timestamp": span.metadata.get("timestamp", 0),
                },
            )

    # Calculate totals and averages
    operation_stats = {}
    for op, tokens in by_operation.items():
        operation_stats[op] = {
            "total_tokens": sum(tokens),
            "avg_tokens": sum(tokens) / len(tokens),
            "count": len(tokens),
            "max_tokens": max(tokens),
        }

    # Sort largest responses
    largest = sorted(
        all_responses,
        key=lambda x: x["tokens"],
        reverse=True,
    )[:10]

    total = sum(stats["total_tokens"] for stats in operation_stats.values())
    return {
        "total_tokens": total,
        "by_operation": operation_stats,
        "largest_responses": largest,
    }
