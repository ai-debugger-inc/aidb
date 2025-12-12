"""Custom logging formatters for aidb_logging package."""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Literal, cast

from .context import get_log_context, get_request_duration, get_session_id

# Standard LogRecord fields to exclude when extracting extras
STANDARD_LOG_RECORD_FIELDS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "real_module",
        "real_funcName",
        "real_lineno",
        "session_id",
        "request_id",
        "getMessage",
    },
)


class SafeFormatter(logging.Formatter):
    """Base formatter that ensures required attributes exist.

    This formatter adds fallback values for any missing attributes to prevent formatting
    errors.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
    ) -> None:
        """Initialize the safe formatter.

        Parameters
        ----------
        fmt : str, optional
            Log message format string
        datefmt : str, optional
            Date format string
        style : str
            Format style (%, {, or $)
        """
        super().__init__(fmt, datefmt, cast("Literal['%', '{', '$']", style or "%"))
        self.converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record safely.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to format

        Returns
        -------
        str
            Formatted log message
        """
        # Ensure real_* attributes exist (from CallerFilter)
        if not hasattr(record, "real_module"):
            record.real_module = getattr(record, "module", "unknown")
        if not hasattr(record, "real_funcName"):
            record.real_funcName = getattr(record, "funcName", "unknown")
        if not hasattr(record, "real_lineno"):
            record.real_lineno = getattr(record, "lineno", 0)

        # Normalize WARNING to WARN for compact display
        if record.levelname == "WARNING":
            record.levelname = "WARN"

        return super().format(record)


class SessionFormatter(SafeFormatter):
    """Formatter that includes session context in log messages.

    Adds session ID and request ID to log messages for better tracing. Optionally adds
    color coding for different log levels.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
        include_session: bool = True,
        include_colors: bool = True,
    ) -> None:
        """Initialize the session formatter.

        Parameters
        ----------
        fmt : str, optional
            Log message format string
        datefmt : str, optional
            Date format string
        style : str
            Format style (%, {, or $)
        include_session : bool
            Whether to include session/request IDs (default: True)
        include_colors : bool
            Whether to add color coding (default: True)
        """
        if fmt is None:
            if include_session:
                # Default format with session/request context
                fmt = (
                    "%(asctime)s %(levelname)-7s "
                    "[%(session_id)s][%(request_id)s] "
                    "%(real_module)s:%(real_funcName)s:%(real_lineno)d "
                    "%(message)s"
                )
            else:
                # Format without session/request context
                fmt = (
                    "%(asctime)s %(levelname)-7s "
                    "%(real_module)s:%(real_funcName)s:%(real_lineno)d "
                    "%(message)s"
                )

        super().__init__(fmt, datefmt, cast("Literal['%', '{', '$']", style or "%"))
        self.include_session = include_session
        self.include_colors = include_colors and self._should_use_colors()

    @staticmethod
    def _should_use_colors() -> bool:
        """Check if colors should be used based on terminal capabilities.

        Returns
        -------
        bool
            True if colors should be used
        """
        # Check if stderr is a TTY
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            return True
        # Check if stdout is a TTY (for some configurations)
        return bool(hasattr(sys.stdout, "isatty") and sys.stdout.isatty())

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with session context and colors.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to format

        Returns
        -------
        str
            Formatted log message
        """
        if self.include_session:
            if not hasattr(record, "session_id"):
                record.session_id = "NO_SESSION"
            if not hasattr(record, "request_id"):
                record.request_id = "NO_REQUEST"

        if self.include_colors:
            original_levelname = record.levelname
            if record.levelno >= logging.ERROR:
                record.levelname = f"\033[91m{record.levelname}\033[0m"  # Red
            elif record.levelno >= logging.WARNING:
                record.levelname = f"\033[93m{record.levelname}\033[0m"  # Yellow
            elif record.levelno >= logging.INFO:
                record.levelname = f"\033[92m{record.levelname}\033[0m"  # Green
            else:  # DEBUG
                record.levelname = f"\033[94m{record.levelname}\033[0m"  # Blue

            result = super().format(record)
            record.levelname = original_levelname  # Restore for other handlers
            return result

        return super().format(record)


class JSONFormatter(SafeFormatter):
    """JSON formatter for structured logging.

    Outputs log records as JSON objects for easy parsing and analysis. Includes all
    context information and extra fields.
    """

    def __init__(
        self,
        include_timestamp: bool = True,
        include_context: bool = True,
        service_name: str | None = None,
        environment: str | None = None,
    ) -> None:
        """Initialize the JSON formatter.

        Parameters
        ----------
        include_timestamp : bool
            Whether to include ISO timestamp (default: True)
        include_context : bool
            Whether to include context variables (default: True)
        service_name : str, optional
            Service name to include in logs
        environment : str, optional
            Environment name to include in logs
        """
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_context = include_context
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to format

        Returns
        -------
        str
            JSON formatted log message
        """
        super().format(record)

        log_data = self._build_base_log_data(record)

        self._add_timestamp(log_data)
        self._add_service_metadata(log_data)
        self._add_context_info(log_data, record)
        self._add_exception_info(log_data, record)
        self._add_extra_fields(log_data, record)

        return json.dumps(log_data, default=str)

    def _build_base_log_data(self, record: logging.LogRecord) -> dict[str, Any]:
        """Build base log data from record."""
        return {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": getattr(record, "real_module", record.module),
            "function": getattr(record, "real_funcName", record.funcName),
            "line": getattr(record, "real_lineno", record.lineno),
        }

    def _add_timestamp(self, log_data: dict[str, Any]) -> None:
        """Add timestamp if enabled."""
        if self.include_timestamp:
            log_data["timestamp"] = datetime.now(timezone.utc).isoformat()

    def _add_service_metadata(self, log_data: dict[str, Any]) -> None:
        """Add service metadata."""
        if self.service_name:
            log_data["service"] = self.service_name
        if self.environment:
            log_data["environment"] = self.environment

    def _add_context_info(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
    ) -> None:
        """Add context information if enabled."""
        if not self.include_context:
            return

        # Session/request IDs
        if hasattr(record, "session_id"):
            log_data["session_id"] = record.session_id
        # Full session id from context (untruncated) for structured logs
        try:
            full_sid = get_session_id()
        except Exception:
            full_sid = None
        if full_sid:
            log_data["session_id_full"] = full_sid
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        # Request duration
        duration_ms = get_request_duration()
        if duration_ms:
            log_data["duration_ms"] = duration_ms

        # Additional context
        context = get_log_context()
        if context:
            log_data["context"] = context

    def _add_exception_info(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
    ) -> None:
        """Add exception info if present."""
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

    def _add_extra_fields(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
    ) -> None:
        """Add extra fields from record."""
        extra_fields = self._extract_extra_fields(record)
        if extra_fields:
            log_data["extra"] = extra_fields

    @staticmethod
    def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
        """Extract extra fields from the log record.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to extract from

        Returns
        -------
        dict
            Extra fields not part of standard logging
        """
        extra = {}
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_FIELDS:
                extra[key] = value

        return extra


class ColoredFormatter(SafeFormatter):
    """Colored formatter for development logging.

    Provides human-readable colored output for console logging.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "WARN": "\033[33m",  # Yellow (normalized)
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
        use_colors: bool = True,
    ) -> None:
        """Initialize the colored formatter.

        Parameters
        ----------
        fmt : str, optional
            Log message format string
        datefmt : str, optional
            Date format string
        style : str
            Format style (%, {, or $)
        use_colors : bool
            Whether to use colors (default: True)
        """
        if fmt is None:
            # Default development format
            fmt = (
                "%(asctime)s %(levelname)-7s "
                "%(real_module)s:%(real_funcName)s:%(real_lineno)d "
                "%(message)s"
            )

        super().__init__(fmt, datefmt, cast("Literal['%', '{', '$']", style or "%"))
        self.use_colors = use_colors and self._should_use_colors()

    @staticmethod
    def _should_use_colors() -> bool:
        """Check if colors should be used based on terminal capabilities.

        Returns
        -------
        bool
            True if colors should be used
        """
        # Check both stdout and stderr
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            return True
        return bool(hasattr(sys.stderr, "isatty") and sys.stderr.isatty())

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to format

        Returns
        -------
        str
            Colored log message
        """
        if self.use_colors:
            levelname_color = self.COLORS.get(record.levelname, self.RESET)
            original_levelname = record.levelname
            record.levelname = f"{levelname_color}{record.levelname}{self.RESET}"

            result = super().format(record)

            # Restore original levelname for other handlers
            record.levelname = original_levelname

            return result

        return super().format(record)
