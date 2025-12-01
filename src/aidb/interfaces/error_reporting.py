"""Error reporting interface definitions.

This module defines Protocol interfaces for error reporting and monitoring within the
AIDB system.
"""

from enum import Enum
from typing import Any, Protocol


class LogLevel(Enum):
    """Log severity levels for error reporting."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IErrorReporter(Protocol):
    """Interface for error reporting and monitoring."""

    def report_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        severity: str = LogLevel.ERROR.value,
    ) -> None:
        """Report an error with context.

        Parameters
        ----------
        error : Exception
            The error to report
        context : dict, optional
            Additional context about the error
        severity : str
            Severity level from LogLevel enum
        """
        ...

    def get_error_statistics(self) -> dict[str, Any]:
        """Get error statistics for monitoring.

        Returns
        -------
        dict
            Error statistics including counts by type, frequency, etc.
        """
        ...

    def get_recent_errors(
        self,
        limit: int = 10,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent errors for debugging.

        Parameters
        ----------
        limit : int
            Maximum number of errors to return
        severity : str, optional
            Filter by severity level from LogLevel enum

        Returns
        -------
        list
            Recent error records
        """
        ...

    def clear_error_history(self) -> None:
        """Clear the error history."""
        ...


class IErrorRecovery(Protocol):
    """Interface for error recovery strategies."""

    def can_recover(self, error: Exception) -> bool:
        """Check if error is recoverable.

        Parameters
        ----------
        error : Exception
            The error to check

        Returns
        -------
        bool
            True if recovery is possible
        """
        ...

    async def attempt_recovery(self, error: Exception, context: dict[str, Any]) -> bool:
        """Attempt to recover from an error.

        Parameters
        ----------
        error : Exception
            The error to recover from
        context : dict
            Error context and recovery parameters

        Returns
        -------
        bool
            True if recovery succeeded
        """
        ...


class IErrorAggregator(Protocol):
    """Interface for aggregating errors from batch operations."""

    def add_error(self, error: Exception, item: Any | None = None) -> None:
        """Add an error to the aggregation.

        Parameters
        ----------
        error : Exception
            The error to add
        item : Any, optional
            The item that caused the error
        """
        ...

    def has_errors(self) -> bool:
        """Check if any errors have been aggregated.

        Returns
        -------
        bool
            True if there are errors
        """
        ...

    def get_summary(self) -> str:
        """Get a summary of aggregated errors.

        Returns
        -------
        str
            Human-readable error summary
        """
        ...

    def to_exception(self) -> Exception:
        """Convert aggregated errors to a single exception.

        Returns
        -------
        Exception
            BatchOperationError or similar containing all errors
        """
        ...
