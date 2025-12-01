"""Lightweight performance profiling for MCP operations.

This module provides timing decorators and span-based tracing for MCP operations. Uses
central configuration via aidb_mcp.core.config.
"""

from __future__ import annotations

import csv
import functools
import json
import time
import uuid
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any, TypeVar

import aiofiles

from aidb_logging import get_mcp_logger as get_logger
from aidb_logging import get_request_id, set_request_id

from .config import get_config
from .performance_types import PerformanceSpan, SpanType, TimingFormat

logger = get_logger(__name__)

# In-memory histories (circular buffers)
_timing_history: deque[dict[str, Any]] = deque(maxlen=1000)
_span_history: deque[PerformanceSpan] = deque(maxlen=1000)
_operation_counter = 0


def _get_config():
    """Lazy config access to avoid circular imports.

    Returns
    -------
    PerformanceConfig
        Performance configuration
    """
    return get_config().performance


def _ensure_history_size() -> None:
    """Ensure history buffers match configured size."""
    cfg = _get_config()
    global _timing_history, _span_history

    if _timing_history.maxlen != cfg.history_size:
        _timing_history = deque(_timing_history, maxlen=cfg.history_size)
    if _span_history.maxlen != cfg.span_history_size:
        _span_history = deque(_span_history, maxlen=cfg.span_history_size)


class TraceSpan:
    """Context manager for tracing operation spans.

    Parameters
    ----------
    span_type : SpanType
        Type/category of this span
    operation : str
        Operation name being measured
    **metadata : Any
        Additional metadata to attach to span

    Examples
    --------
    >>> with TraceSpan(SpanType.VALIDATION, "validate_params") as span:
    ...     # do work
    ...     if span:
    ...         span.metadata["param_count"] = 5
    """

    def __init__(
        self,
        span_type: SpanType,
        operation: str,
        **metadata: Any,
    ):
        cfg = _get_config()

        if not cfg.detailed_timing:
            self.enabled = False
            self.span = None
            return

        self.enabled = True

        # Get or create request ID (correlation ID for tracing)
        correlation_id = get_request_id()
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())[:8]
            set_request_id(correlation_id)

        self.span = PerformanceSpan(
            span_id=f"{correlation_id}:{span_type.value}:{operation}",
            span_type=span_type,
            operation=operation,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    def __enter__(self) -> PerformanceSpan | None:
        """Start timing.

        Returns
        -------
        PerformanceSpan | None
            The span if enabled, None otherwise
        """
        if not self.enabled or self.span is None:
            return None

        self.span.start_ns = time.perf_counter_ns()
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record span.

        Parameters
        ----------
        exc_type : type | None
            Exception type if raised
        exc_val : Exception | None
            Exception value if raised
        exc_tb : traceback | None
            Exception traceback if raised

        Returns
        -------
        bool
            False to propagate exceptions
        """
        if not self.enabled or self.span is None:
            return False

        self.span.end_ns = time.perf_counter_ns()
        self.span.duration_ms = (self.span.end_ns - self.span.start_ns) / 1_000_000

        if exc_type is not None:
            self.span.success = False
            self.span.error = str(exc_val)

        _record_span(self.span)
        return False


def _record_span(span: PerformanceSpan) -> None:
    """Record a performance span to history and file.

    Parameters
    ----------
    span : PerformanceSpan
        Span to record
    """
    _ensure_history_size()
    _span_history.append(span)

    cfg = _get_config()

    try:
        log_path = Path(cfg.timing_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        fmt = TimingFormat(cfg.timing_format)

        if fmt == TimingFormat.JSON:
            _write_span_json(log_path, span)
        elif fmt == TimingFormat.CSV:
            _write_span_csv(log_path, span)
        else:
            _write_span_text(log_path, span)

    except Exception as e:
        logger.debug("Failed to write span: %s", e)


def _write_span_json(log_path: Path, span: PerformanceSpan) -> None:
    """Write span as JSON line.

    Parameters
    ----------
    log_path : Path
        Path to log file
    span : PerformanceSpan
        Span to write
    """
    data = {
        "timestamp": time.time(),
        **span.to_dict(),
    }

    with log_path.open("a") as f:
        f.write(json.dumps(data) + "\n")


def _write_span_text(log_path: Path, span: PerformanceSpan) -> None:
    """Write span in human-readable format.

    Parameters
    ----------
    log_path : Path
        Path to log file
    span : PerformanceSpan
        Span to write
    """
    cfg = _get_config()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    slow_marker = " ⚠️" if span.duration_ms > cfg.slow_threshold_ms else ""

    with log_path.open("a") as f:
        f.write(
            f"[{timestamp}] [{span.span_type.value}] {span.operation} - "
            f"{span.duration_ms:.1f}ms{slow_marker}\n",
        )


def _write_span_csv(log_path: Path, span: PerformanceSpan) -> None:
    """Write span as CSV row.

    Parameters
    ----------
    log_path : Path
        Path to log file
    span : PerformanceSpan
        Span to write
    """
    # Write header if file doesn't exist
    write_header = not log_path.exists()

    with log_path.open("a", newline="") as f:
        writer = csv.writer(f)

        if write_header:
            writer.writerow(
                [
                    "timestamp",
                    "span_id",
                    "span_type",
                    "operation",
                    "duration_ms",
                    "success",
                    "error",
                ],
            )

        writer.writerow(
            [
                time.time(),
                span.span_id,
                span.span_type.value,
                span.operation,
                span.duration_ms,
                span.success,
                span.error or "",
            ],
        )


def _write_summary(file_handle: IO[str]) -> None:
    """Write performance summary statistics to file.

    Parameters
    ----------
    file_handle : IO[str]
        Open file handle to write summary to
    """
    if not _timing_history:
        return

    cfg = _get_config()
    ops_stats: dict[str, list[float]] = {}
    for entry in _timing_history:
        op = entry["operation"]
        if op not in ops_stats:
            ops_stats[op] = []
        ops_stats[op].append(entry["duration_ms"])

    file_handle.write("\n--- Summary (last 1000 ops) ---\n")

    for op, timings in sorted(ops_stats.items()):
        if not timings:
            continue

        timings_sorted = sorted(timings)
        avg = sum(timings) / len(timings)

        # Calculate p95 (95th percentile)
        p95_idx = int(len(timings) * 0.95)
        if p95_idx >= len(timings):
            p95_idx = len(timings) - 1
        p95 = timings_sorted[p95_idx] if timings else 0

        slow_marker = " ⚠️" if p95 > cfg.slow_threshold_ms else ""

        file_handle.write(
            f"  {op:20s} avg={avg:7.1f}ms  p95={p95:7.1f}ms  "
            f"count={len(timings):4d}{slow_marker}\n",
        )

    file_handle.write("---\n\n")


async def _write_summary_async(file_handle: Any) -> None:
    """Write performance summary statistics to file (async version).

    Parameters
    ----------
    file_handle : aiofiles file handle
        Open async file handle to write summary to
    """
    if not _timing_history:
        return

    cfg = _get_config()
    ops_stats: dict[str, list[float]] = {}
    for entry in _timing_history:
        op = entry["operation"]
        if op not in ops_stats:
            ops_stats[op] = []
        ops_stats[op].append(entry["duration_ms"])

    await file_handle.write("\n--- Summary (last 1000 ops) ---\n")

    for op, timings in sorted(ops_stats.items()):
        if not timings:
            continue

        timings_sorted = sorted(timings)
        avg = sum(timings) / len(timings)

        # Calculate p95 (95th percentile)
        p95_idx = int(len(timings) * 0.95)
        if p95_idx >= len(timings):
            p95_idx = len(timings) - 1
        p95 = timings_sorted[p95_idx] if timings else 0

        slow_marker = " ⚠️" if p95 > cfg.slow_threshold_ms else ""

        await file_handle.write(
            f"  {op:20s} avg={avg:7.1f}ms  p95={p95:7.1f}ms  "
            f"count={len(timings):4d}{slow_marker}\n",
        )

    await file_handle.write("---\n\n")


F = TypeVar("F", bound=Callable[..., Any])


def timed(func: F) -> F:
    """Lightweight timing decorator for MCP operations.

    Only active when timing is enabled via configuration.

    Parameters
    ----------
    func : Callable
        The async function to time

    Returns
    -------
    Callable
        Wrapped function with timing, or original if timing disabled
    """

    def _is_enabled() -> bool:
        try:
            return _get_config().timing_enabled
        except Exception:
            return False

    if not _is_enabled():
        return func

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        global _operation_counter

        operation = func.__name__.replace("handle_", "")
        start_ns = time.perf_counter_ns()

        try:
            return await func(*args, **kwargs)
        finally:
            cfg = _get_config()
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            is_slow = duration_ms > cfg.slow_threshold_ms

            _ensure_history_size()
            _timing_history.append(
                {
                    "operation": operation,
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                    "slow": is_slow,
                },
            )

            _operation_counter += 1

            # Log to file
            try:
                log_path = Path(cfg.timing_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(log_path, "a") as f:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    slow_marker = " ⚠️" if is_slow else ""
                    await f.write(
                        f"[{timestamp}] {operation} - "
                        f"{duration_ms:.1f}ms{slow_marker}\n",
                    )

                    if _operation_counter % 100 == 0:
                        await _write_summary_async(f)

            except Exception as e:
                logger.debug("Failed to write timing data: %s", e)

    return wrapper  # type: ignore[return-value]


def get_timing_stats() -> dict[str, Any] | None:
    """Get current timing statistics.

    Returns
    -------
    dict[str, Any] | None
        Timing statistics if enabled, None otherwise
    """
    try:
        cfg = _get_config()
        if not cfg.timing_enabled or not _timing_history:
            return None
    except Exception:
        return None

    ops_stats: dict[str, list[float]] = {}
    for entry in _timing_history:
        op = entry["operation"]
        if op not in ops_stats:
            ops_stats[op] = []
        ops_stats[op].append(entry["duration_ms"])

    stats = {}
    for op, timings in ops_stats.items():
        if not timings:
            continue

        timings_sorted = sorted(timings)
        stats[op] = {
            "count": len(timings),
            "avg_ms": sum(timings) / len(timings),
            "min_ms": timings_sorted[0],
            "max_ms": timings_sorted[-1],
            "p95_ms": (
                timings_sorted[int(len(timings) * 0.95)]
                if len(timings) > 1
                else timings[0]
            ),
        }

    return {
        "enabled": cfg.timing_enabled,
        "total_operations": len(_timing_history),
        "operations": stats,
        "slow_threshold_ms": cfg.slow_threshold_ms,
        "log_file": cfg.timing_file,
    }


# Log startup message if enabled
try:
    _cfg = _get_config()
    if _cfg.timing_enabled:
        logger.info(
            "Performance timing ENABLED - logging to %s (slow threshold: %sms)",
            _cfg.timing_file,
            _cfg.slow_threshold_ms,
        )
except Exception as e:
    # Config not available yet (during imports)
    logger.debug("Performance config not available during import: %s", e)
