"""Utility functions for aidb_logging package."""

import contextlib
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from aidb_common.constants import AIDB_HOME_DIR, LOG_SUBDIR
from aidb_common.env import reader

if TYPE_CHECKING:
    from aidb_logging.context import LoggingContext

# Valid log levels (including custom TRACE)
VALID_LOG_LEVELS = frozenset({"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


def get_log_file_path(
    component: str,
    filename: str | None = None,
    log_dir: str | None = None,
) -> str:
    """Get the path for a log file.

    Uses AidbContext.get_storage_path() for consistent paths,
    with support for environment variable overrides.

    Parameters
    ----------
    component : str
        Component name (e.g., "aidb", "mcp", "cli", "test")
    filename : str, optional
        Custom filename (defaults to {component}.log)
    log_dir : str, optional
        Custom log directory (overrides default ~/.aidb/log/)

    Returns
    -------
    str
        Absolute path to the log file

    Examples
    --------
    >>> get_log_file_path("aidb")
    '/Users/username/.aidb/log/aidb.log'

    >>> get_log_file_path("test", filename="test_run.log")
    '/Users/username/.aidb/log/test_run.log'

    >>> get_log_file_path("cli", log_dir="/var/log/aidb")
    '/var/log/aidb/cli.log'
    """
    # Check for environment variable override
    if log_dir is None:
        log_dir = reader.read_str("AIDB_LOG_DIR", default=None)

    # Use custom directory if provided
    if log_dir:
        log_path = Path(log_dir)
        # Ensure directory exists
        log_path.mkdir(parents=True, exist_ok=True)
    else:
        # Use AidbContext for standard path
        try:
            from aidb.common.context import AidbContext

            log_path = Path(AidbContext.get_storage_path("log"))
        except (ImportError, Exception):
            # Fallback if AidbContext is not available (e.g., in tests)
            log_path = Path.home() / AIDB_HOME_DIR / LOG_SUBDIR
            log_path.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = f"{component}.log"

    return str(log_path / filename)


def get_log_level(default: str = "INFO") -> str:
    """Get the log level from environment or default.

    Parameters
    ----------
    default : str
        Default log level if not specified (default: "INFO")

    Returns
    -------
    str
        Log level name (e.g., "DEBUG", "INFO", "WARNING", "ERROR")

    Examples
    --------
    >>> os.environ["AIDB_LOG_LEVEL"] = "DEBUG"
    >>> get_log_level()
    'DEBUG'

    >>> get_log_level("WARNING")
    'WARNING'
    """
    level = reader.read_str("AIDB_LOG_LEVEL", default=default)
    return level.upper() if level.upper() in VALID_LOG_LEVELS else default.upper()


def should_use_file_logging() -> bool:
    """Check if file logging should be enabled.

    Can be disabled via AIDB_NO_FILE_LOGGING environment variable.

    Returns
    -------
    bool
        True if file logging should be used

    Examples
    --------
    >>> os.environ["AIDB_NO_FILE_LOGGING"] = "1"
    >>> should_use_file_logging()
    False
    """
    return not reader.read_bool("AIDB_NO_FILE_LOGGING", default=False)


def should_use_console_logging() -> bool:
    """Check if console logging should be enabled.

    Can be forced via AIDB_CONSOLE_LOGGING environment variable.

    Returns
    -------
    bool
        True if console logging should be used

    Examples
    --------
    >>> os.environ["AIDB_CONSOLE_LOGGING"] = "1"
    >>> should_use_console_logging()
    True
    """
    return reader.read_bool("AIDB_CONSOLE_LOGGING", default=False)


def is_test_environment() -> bool:
    """Check if running in test environment.

    Checks for common test environment indicators.

    Returns
    -------
    bool
        True if running in test environment
    """
    # Check for pytest
    if "pytest" in reader.read_str("_", default=""):
        return True

    # Check for test mode environment variable
    if reader.read_bool("AIDB_TEST_MODE", default=False):
        return True

    # Pytest sets this env var when running tests
    if reader.read_str("PYTEST_CURRENT_TEST", default=None):
        return True

    # Check if pytest is in sys.modules
    import sys

    return "pytest" in sys.modules


def is_debug_environment() -> bool:
    """Check if running in debug mode.

    Returns
    -------
    bool
        True if debug mode is enabled
    """
    # Check log level
    if get_log_level() == "DEBUG":
        return True

    # Check debug environment variable
    if reader.read_bool("AIDB_DEBUG", default=False):
        return True

    # Check adapter trace mode
    return reader.read_bool("AIDB_ADAPTER_TRACE", default=False)


def clean_old_logs(
    log_dir: str,
    max_files: int = 10,
    pattern: str = "*.log",
) -> None:
    """Clean up old log files.

    Keeps only the most recent N log files based on modification time.

    Parameters
    ----------
    log_dir : str
        Directory containing log files
    max_files : int
        Maximum number of log files to keep (default: 10)
    pattern : str
        Glob pattern for log files (default: "*.log")

    Examples
    --------
    >>> clean_old_logs("/Users/username/.aidb/log", max_files=5)
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return

    log_files = sorted(
        log_path.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Most recent first
    )

    for old_file in log_files[max_files:]:
        with contextlib.suppress(Exception):
            old_file.unlink()


def format_bytes(num_bytes: int) -> str:
    """Format byte count as human-readable string.

    Parameters
    ----------
    num_bytes : int
        Number of bytes

    Returns
    -------
    str
        Formatted string (e.g., "1.5 MB")

    Examples
    --------
    >>> format_bytes(1536)
    '1.5 KB'

    >>> format_bytes(10485760)
    '10.0 MB'
    """
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def get_file_size(file_path: str) -> int:
    """Get size of a file in bytes.

    Parameters
    ----------
    file_path : str
        Path to the file

    Returns
    -------
    int
        File size in bytes, or 0 if file doesn't exist
    """
    try:
        return Path(file_path).stat().st_size
    except OSError:
        return 0


class LogOnce:
    """Throttle log messages to occur only once per key during process lifetime.

    Thread-safe singleton pattern for preventing repetitive initialization
    and status logs that don't provide value on subsequent occurrences.

    Examples
    --------
    >>> from aidb_logging.context import LoggingContext
    >>> ctx = LoggingContext(component="example")
    >>> LogOnce.debug(ctx, "db_init", "Database initialized successfully")
    # First call logs the message
    >>> LogOnce.debug(ctx, "db_init", "Database initialized successfully")
    # Subsequent calls with same key are suppressed
    """

    _logged: set[str] = set()
    _lock = threading.Lock()

    @classmethod
    def debug(cls, ctx: "LoggingContext", key: str, message: str) -> None:
        """Log a DEBUG message only once per key.

        Parameters
        ----------
        ctx : LoggingContext
            Logging context to use for output
        key : str
            Unique key for this log message (e.g., "port_registry_init")
        message : str
            Message to log (only on first call with this key)
        """
        with cls._lock:
            if key not in cls._logged:
                ctx.debug(message)
                cls._logged.add(key)

    @classmethod
    def info(cls, ctx: "LoggingContext", key: str, message: str) -> None:
        """Log an INFO message only once per key.

        Parameters
        ----------
        ctx : LoggingContext
            Logging context to use for output
        key : str
            Unique key for this log message
        message : str
            Message to log (only on first call with this key)
        """
        with cls._lock:
            if key not in cls._logged:
                ctx.info(message)
                cls._logged.add(key)

    @classmethod
    def warning(cls, ctx: "LoggingContext", key: str, message: str) -> None:
        """Log a WARNING message only once per key.

        Parameters
        ----------
        ctx : LoggingContext
            Logging context to use for output
        key : str
            Unique key for this log message
        message : str
            Message to log (only on first call with this key)
        """
        with cls._lock:
            if key not in cls._logged:
                ctx.warning(message)
                cls._logged.add(key)

    @classmethod
    def reset(cls) -> None:
        """Clear all logged keys (primarily for testing)."""
        with cls._lock:
            cls._logged.clear()
