"""Performance-related assertions.

This module provides assertions for validating operation timing, memory usage, and async
operation completion.

Includes optional pass-side logging of measured timings for perf tests. Enable by
setting environment variable AIDB_PERF_LOG=1. You may also set
  - AIDB_PERF_LOG_FORMAT=text|json (default: text)
  - AIDB_PERF_LOG_FILE=/path/to/file (optional; append one line per metric)
"""

import asyncio
import contextlib
import json
import logging
import os
from typing import Any


class PerformanceAssertions:
    """Performance-related assertions."""

    @staticmethod
    def _emit_perf_result(
        operation_time: float,
        max_time: float,
        operation_name: str,
    ) -> None:
        """Optionally log measured performance for passing assertions.

        Controlled by environment variables:
        - AIDB_PERF_LOG=1 enables emission (default: disabled)
        - AIDB_PERF_LOG_FORMAT=text|json (default: text)
        - AIDB_PERF_LOG_FILE=path to append logs (optional)
        """
        # Enabled by default; allow explicit opt-out via AIDB_PERF_LOG=0/false/no
        flag = os.getenv("AIDB_PERF_LOG", "1").strip().lower()
        if flag in {"0", "false", "no", "off"}:
            return

        ms = int(round(operation_time * 1000))
        budget_ms = int(round(max_time * 1000))
        fmt = os.getenv("AIDB_PERF_LOG_FORMAT", "text").lower().strip()

        if fmt == "json":
            record = {
                "type": "perf",
                "operation": operation_name,
                "duration_ms": ms,
                "budget_ms": budget_ms,
                "passed": operation_time <= max_time,
            }
            line = json.dumps(record, separators=(",", ":"))
        else:
            line = f"[PERF] {operation_name}: {ms} ms (budget {budget_ms} ms)"

        # Emit via logger and stdout to ensure visibility in test logs
        with contextlib.suppress(Exception):
            logging.getLogger("aidb_perf").info(line)
        with contextlib.suppress(Exception):
            print(line)

        # Optionally append to a log file
        log_file = os.getenv("AIDB_PERF_LOG_FILE")
        if log_file:
            with contextlib.suppress(Exception):
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")

    @staticmethod
    def assert_operation_time(
        operation_time: float,
        max_time: float,
        operation_name: str = "Operation",
    ) -> None:
        """Assert that an operation completed within time limit.

        Parameters
        ----------
        operation_time : float
            Actual operation time in seconds
        max_time : float
            Maximum acceptable time in seconds
        operation_name : str
            Name of the operation for error messages

        Raises
        ------
        AssertionError
            If operation took too long
        """
        # Emit pass-side metric before assertion so failures still show last value
        PerformanceAssertions._emit_perf_result(
            operation_time,
            max_time,
            operation_name,
        )

        assert operation_time <= max_time, (
            f"{operation_name} took {operation_time:.3f}s, expected ≤{max_time:.3f}s"
        )

    @staticmethod
    def assert_memory_usage(
        current_mb: float,
        max_mb: float,
        operation_name: str = "Operation",
    ) -> None:
        """Assert that memory usage is within acceptable limits.

        Parameters
        ----------
        current_mb : float
            Current memory usage in MB
        max_mb : float
            Maximum acceptable memory usage in MB
        operation_name : str
            Name of the operation for error messages

        Raises
        ------
        AssertionError
            If memory usage is too high
        """
        assert current_mb <= max_mb, (
            f"{operation_name} used {current_mb:.1f}MB, expected ≤{max_mb:.1f}MB"
        )

    @staticmethod
    async def assert_async_operation_completes(
        operation: Any,
        timeout: float = 5.0,
        operation_name: str = "Async operation",
    ) -> Any:
        """Assert that an async operation completes within timeout.

        Parameters
        ----------
        operation : Any
            Async operation (coroutine or awaitable)
        timeout : float
            Maximum time to wait in seconds
        operation_name : str
            Name of the operation for error messages

        Returns
        -------
        Any
            Result of the operation

        Raises
        ------
        AssertionError
            If operation times out
        """
        try:
            return await asyncio.wait_for(operation, timeout=timeout)
        except asyncio.TimeoutError as e:
            msg = f"{operation_name} timed out after {timeout:.1f}s"
            raise AssertionError(msg) from e
