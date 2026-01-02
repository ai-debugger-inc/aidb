"""Unified logging infrastructure for AIDB ecosystem.

This package provides consistent logging across aidb, aidb_mcp,
and test environments with profile-based configuration.

Quick Start
-----------
>>> # Get a logger with aidb profile
>>> from aidb_logging import get_logger
>>> logger = get_logger("my_module")

>>> # Use a specific profile
>>> from aidb_logging import get_mcp_logger
>>> logger = get_mcp_logger("aidb_mcp.tools")

>>> # Configure with custom settings
>>> from aidb_logging import configure_logger
>>> logger = configure_logger(
...     "custom",
...     profile="cli",
...     to_console=True
... )

Available Profiles
------------------
- aidb: File logging with CallerFilter for accurate source locations
- mcp: Dual output (stderr + file) with session context and colors
- cli: CLI-specific logging with optional console output
- test: Pytest-compatible with optional file output
- custom: Build your own configuration

Context Management
------------------
>>> from aidb_logging import SessionContext, set_session_id
>>>
>>> # Set session ID globally
>>> set_session_id("abc123")
>>>
>>> # Or use context manager
>>> with SessionContext("xyz789"):
...     logger.info("This log has session context")

Performance Logging
-------------------
>>> from aidb_logging import PerformanceLogger, log_performance
>>>
>>> # Context manager
>>> with PerformanceLogger(logger, "database_query"):
...     # Slow operation
...     pass
>>>
>>> # Decorator
>>> @log_performance(operation="api_call")
... def slow_function():
...     pass
"""

__version__ = "0.1.0"

import logging

# Add TRACE logging level (below DEBUG)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(self, message, *args, **kwargs):
    """Log a message at TRACE level (below DEBUG).

    TRACE level is for ultra-verbose protocol-level logging (DAP messages, LSP messages,
    timing instrumentation) that's rarely needed except when debugging protocol issues.
    """
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


# Add trace() method to Logger class
logging.Logger.trace = _trace  # type: ignore[attr-defined]

# Core configuration
from .config import (  # noqa: E402
    ProfileType,
    configure_logger,
    get_aidb_logger,
    get_cli_logger,
    get_mcp_logger,
    get_test_logger,
    setup_global_debug_logging,
    setup_root_logger,
)

# Context management
from .context import (  # noqa: E402
    ContextManager,
    LogContext,
    RequestContext,
    SessionContext,
    clear_all_context,
    clear_log_context,
    clear_request_id,
    clear_request_timing,
    clear_session_id,
    get_log_context,
    get_request_duration,
    get_request_id,
    get_session_id,
    # General context
    set_log_context,
    # Request context
    set_request_id,
    set_request_id_with_ttl,
    # Session context
    set_session_id,
    set_session_id_with_ttl,
    start_request_timing,
)

# Filters
from .filters import (  # noqa: E402
    CallerFilter,
    LevelFilter,
    ModuleFilter,
    SessionContextFilter,
)

# Formatters
from .formatters import (  # noqa: E402
    ColoredFormatter,
    JSONFormatter,
    SafeFormatter,
    SessionFormatter,
)

# Handlers
from .handlers import (  # noqa: E402
    DualStreamHandler,
    HalvingFileHandler,
)

# Performance utilities
from .performance import (  # noqa: E402
    PerformanceLogger,
    PerformanceTracker,
    TimedOperation,
    log_performance,
)

# Utilities
from .utils import (  # noqa: E402
    LogOnce,
    clean_old_logs,
    format_bytes,
    get_file_size,
    get_log_file_path,
    get_log_level,
    is_debug_environment,
    is_test_environment,
    should_use_console_logging,
    should_use_file_logging,
)


# Convenience function for getting a logger with default profile
def get_logger(name: str, profile: ProfileType = "aidb", **kwargs) -> "logging.Logger":
    """Get a logger with the specified profile.

    This is the primary entry point for most users.

    Parameters
    ----------
    name : str
        Logger name (typically __name__)
    profile : ProfileType
        Configuration profile (default: "aidb")
    **kwargs
        Additional configuration options

    Returns
    -------
    logging.Logger
        Configured logger instance

    Examples
    --------
    >>> logger = get_logger(__name__)
    >>> logger.info("Hello from aidb_logging!")
    """
    return configure_logger(name, profile=profile, **kwargs)


# Export commonly used logging levels for convenience
TRACE = TRACE  # Custom level below DEBUG
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

__all__ = [
    # Version
    "__version__",
    # Main configuration
    "configure_logger",
    "setup_root_logger",
    "setup_global_debug_logging",
    "get_logger",
    # Profile-specific getters
    "get_aidb_logger",
    "get_mcp_logger",
    "get_cli_logger",
    "get_test_logger",
    # Types
    "ProfileType",
    # Handlers
    "HalvingFileHandler",
    "DualStreamHandler",
    # Filters
    "CallerFilter",
    "SessionContextFilter",
    "LevelFilter",
    "ModuleFilter",
    # Formatters
    "SafeFormatter",
    "SessionFormatter",
    "JSONFormatter",
    "ColoredFormatter",
    # Context management
    "set_session_id",
    "set_session_id_with_ttl",
    "get_session_id",
    "clear_session_id",
    "SessionContext",
    "set_request_id",
    "set_request_id_with_ttl",
    "get_request_id",
    "clear_request_id",
    "RequestContext",
    "ContextManager",
    "start_request_timing",
    "get_request_duration",
    "clear_request_timing",
    "set_log_context",
    "get_log_context",
    "clear_log_context",
    "LogContext",
    "clear_all_context",
    # Performance
    "PerformanceLogger",
    "log_performance",
    "TimedOperation",
    "PerformanceTracker",
    # Utilities
    "get_log_file_path",
    "get_log_level",
    "should_use_file_logging",
    "should_use_console_logging",
    "is_test_environment",
    "is_debug_environment",
    "clean_old_logs",
    "format_bytes",
    "get_file_size",
    "LogOnce",
    # Log levels
    "TRACE",
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]
