"""Performance logging utilities for aidb_logging package."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any


class PerformanceLogger:
    """Context manager for performance logging.

    Tracks execution time and logs performance metrics with automatic level selection
    based on duration.
    """

    def __init__(
        self,
        logger: logging.Logger,
        operation: str,
        slow_threshold_ms: int = 1000,
        very_slow_threshold_ms: int = 5000,
        **context: Any,
    ) -> None:
        """Initialize performance logger.

        Parameters
        ----------
        logger : logging.Logger
            Logger to use for output
        operation : str
            Name/description of the operation being timed
        slow_threshold_ms : int
            Milliseconds before operation is considered slow (default: 1000)
        very_slow_threshold_ms : int
            Milliseconds before operation is considered very slow (default: 5000)
        **context
            Additional context to include in log messages
        """
        self.logger = logger
        self.operation = operation
        self.slow_threshold = slow_threshold_ms
        self.very_slow_threshold = very_slow_threshold_ms
        self.context = context
        self.start_time: float | None = None

    def __enter__(self) -> "PerformanceLogger":
        """Start timing the operation."""
        self.start_time = time.time()
        self.logger.debug(
            "Starting %s",
            self.operation,
            extra={"operation": self.operation, **self.context},
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End timing and log results."""
        if self.start_time is None:
            duration_ms = 0
        else:
            duration_ms = int((time.time() - self.start_time) * 1000)

        log_data = {
            "operation": self.operation,
            "duration_ms": duration_ms,
            **self.context,
        }

        if exc_type:
            # Operation failed
            self.logger.error(
                "%s failed after %dms: %s",
                self.operation,
                duration_ms,
                exc_val,
                extra=log_data,
                exc_info=True,
            )
        else:
            # Operation succeeded - choose log level based on duration
            if duration_ms > self.very_slow_threshold:
                level = logging.WARNING
                msg = f"{self.operation} completed slowly in {duration_ms}ms"
            elif duration_ms > self.slow_threshold:
                level = logging.INFO
                msg = f"{self.operation} completed in {duration_ms}ms"
            else:
                level = logging.DEBUG
                msg = f"{self.operation} completed in {duration_ms}ms"

            self.logger.log(level, msg, extra=log_data)


def log_performance(
    operation: str | None = None,
    logger: logging.Logger | None = None,
    slow_threshold_ms: int = 1000,
    very_slow_threshold_ms: int = 5000,
) -> Callable:
    """Add performance logging to functions.

    Parameters
    ----------
    operation : str, optional
        Operation name (defaults to function name)
    logger : logging.Logger, optional
        Logger to use (defaults to module logger)
    slow_threshold_ms : int
        Milliseconds before operation is considered slow
    very_slow_threshold_ms : int
        Milliseconds before operation is considered very slow

    Returns
    -------
    callable
        Decorated function

    Examples
    --------
    >>> @log_performance()
    ... def slow_function():
    ...     time.sleep(2)
    ...
    >>> @log_performance(operation="database_query", slow_threshold_ms=500)
    ... def query_db():
    ...     # Query implementation
    ...     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation or f"{func.__module__}.{func.__name__}"

            target_logger = logger or logging.getLogger(func.__module__)

            with PerformanceLogger(
                target_logger,
                op_name,
                slow_threshold_ms=slow_threshold_ms,
                very_slow_threshold_ms=very_slow_threshold_ms,
            ):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class TimedOperation:
    """Utility class for manually timing operations.

    Useful when you need more control over timing than the context manager provides.
    """

    def __init__(self, name: str) -> None:
        """Initialize timed operation.

        Parameters
        ----------
        name : str
            Name of the operation
        """
        self.name = name
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.duration_ms: int | None = None

    def start(self) -> None:
        """Start timing."""
        self.start_time = time.time()
        self.end_time = None
        self.duration_ms = None

    def stop(self) -> int:
        """Stop timing and return duration.

        Returns
        -------
        int
            Duration in milliseconds

        Raises
        ------
        RuntimeError
            If timing was not started
        """
        if self.start_time is None:
            msg = f"Timer for {self.name} was not started"
            raise RuntimeError(msg)

        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        return self.duration_ms

    def reset(self) -> None:
        """Reset the timer."""
        self.start_time = None
        self.end_time = None
        self.duration_ms = None

    def __str__(self) -> str:
        """Return string representation of the timed operation."""
        if self.duration_ms is not None:
            return f"{self.name}: {self.duration_ms}ms"
        if self.start_time is not None:
            current_duration = int((time.time() - self.start_time) * 1000)
            return f"{self.name}: {current_duration}ms (running)"
        return f"{self.name}: not started"


class PerformanceTracker:
    """Track multiple timed operations.

    Useful for tracking performance of different parts of a larger operation.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize performance tracker.

        Parameters
        ----------
        logger : logging.Logger, optional
            Logger for output
        """
        self.logger = logger or logging.getLogger(__name__)
        self.operations: dict[str, TimedOperation] = {}
        self.total_timer = TimedOperation("total")

    def start(self, operation: str) -> None:
        """Start timing an operation.

        Parameters
        ----------
        operation : str
            Name of the operation
        """
        if operation not in self.operations:
            self.operations[operation] = TimedOperation(operation)
        self.operations[operation].start()

        # Start total timer if not started
        if self.total_timer.start_time is None:
            self.total_timer.start()

    def stop(self, operation: str) -> int:
        """Stop timing an operation.

        Parameters
        ----------
        operation : str
            Name of the operation

        Returns
        -------
        int
            Duration in milliseconds

        Raises
        ------
        KeyError
            If operation was not started
        """
        if operation not in self.operations:
            msg = f"Operation {operation} was not started"
            raise KeyError(msg)

        return self.operations[operation].stop()

    def get_duration(self, operation: str) -> int | None:
        """Get duration of a completed operation.

        Parameters
        ----------
        operation : str
            Name of the operation

        Returns
        -------
        int or None
            Duration in milliseconds, or None if not completed
        """
        if operation in self.operations:
            return self.operations[operation].duration_ms
        return None

    def log_summary(self, level: int = logging.INFO) -> None:
        """Log a summary of all timed operations.

        Parameters
        ----------
        level : int
            Log level to use (default: INFO)
        """
        # Stop total timer if running
        if self.total_timer.start_time and not self.total_timer.end_time:
            self.total_timer.stop()

        summary_parts = []
        for name, timer in self.operations.items():
            if timer.duration_ms is not None:
                summary_parts.append(f"{name}={timer.duration_ms}ms")

        if self.total_timer.duration_ms is not None:
            summary_parts.append(f"total={self.total_timer.duration_ms}ms")

        if summary_parts:
            summary = ", ".join(summary_parts)
            self.logger.log(level, "Performance summary: %s", summary)

    def reset(self) -> None:
        """Reset all timers."""
        self.operations.clear()
        self.total_timer.reset()
