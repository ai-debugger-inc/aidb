"""Configuration profiles for aidb_logging package."""

import logging
import sys
from typing import Any, Literal

from aidb_common.env import reader

from .filters import CallerFilter, SessionContextFilter
from .formatters import SafeFormatter, SessionFormatter
from .handlers import HalvingFileHandler
from .utils import (
    get_log_file_path,
    get_log_level,
    should_use_console_logging,
    should_use_file_logging,
)

# TRACE level is custom and not in standard logging module
TRACE = 5
logging.addLevelName(TRACE, "TRACE")

ProfileType = Literal["aidb", "mcp", "cli", "test", "custom"]


def configure_logger(
    name: str = "root",
    profile: ProfileType = "aidb",
    level: str | None = None,
    log_file: str | None = None,
    to_console: bool = False,
    **kwargs: Any,
) -> logging.Logger:
    """Configure a logger with a specific profile.

    Parameters
    ----------
    name : str
        Logger name (default: "root")
    profile : ProfileType
        Configuration profile to use:
        - "aidb": File logging with CallerFilter
        - "mcp": Dual output (stderr + file) with session context
        - "cli": CLI-specific logging to ~/.aidb/log/cli.log
        - "test": Pytest-compatible with optional file output
        - "custom": Custom configuration via kwargs
    level : str, optional
        Log level (overrides profile default and env var)
    log_file : str, optional
        Custom log file path (overrides profile default)
    to_console : bool
        Force console output (default: False, unless profile specifies)
    **kwargs
        Additional configuration for custom profile

    Returns
    -------
    logging.Logger
        Configured logger instance

    Examples
    --------
    >>> # Configure aidb logger
    >>> logger = configure_logger("aidb", profile="aidb")

    >>> # Configure MCP logger with session support
    >>> logger = configure_logger("aidb_mcp", profile="mcp")

    >>> # Configure test logger
    >>> logger = configure_logger("test", profile="test", level="DEBUG")
    """
    logger = logging.getLogger(name)

    # Clear existing handlers (close them first to avoid resource warnings)
    # Preserve handlers marked with _aidb_preserve=True
    for handler in logger.handlers[:]:
        if not getattr(handler, "_aidb_preserve", False):
            handler.close()
            logger.removeHandler(handler)

    logger.filters.clear()

    log_level = level.upper() if level else get_log_level("INFO")

    # Handle custom TRACE level
    if log_level == "TRACE":
        logger.setLevel(TRACE)
    else:
        logger.setLevel(getattr(logging, log_level))

    if profile == "aidb":
        _configure_aidb_profile(logger, log_file, to_console)
    elif profile == "mcp":
        _configure_mcp_profile(logger, log_file)
    elif profile == "cli":
        verbose_debug = kwargs.get("verbose_debug", False)
        _configure_cli_profile(logger, log_file, to_console, verbose_debug)
    elif profile == "test":
        _configure_test_profile(logger, log_file, to_console)
    elif profile == "custom":
        _configure_custom_profile(logger, log_file, to_console, **kwargs)
    else:
        msg = f"Unknown profile: {profile}"
        raise ValueError(msg)

    # Propagation: allow pytest to capture logs in test profile
    if (
        profile == "test"
        and "pytest" in sys.modules
        and not reader.read_bool(
            "AIDB_TEST_LOGGING_DISABLED",
            default=False,
        )
    ):
        logger.propagate = True
    else:
        # Prevent propagation to root logger (avoid duplicates) in other profiles
        logger.propagate = False

    return logger


def _configure_aidb_profile(
    logger: logging.Logger,
    log_file: str | None,
    to_console: bool,
) -> None:
    """Configure logger with aidb profile.

    Features:
    - File logging to ~/.aidb/log/aidb.log
    - CallerFilter for accurate source locations
    - SafeFormatter with real module/function/line info
    """
    logger.addFilter(CallerFilter())

    formatter = SafeFormatter(
        "%(asctime)s %(levelname)-7s "
        "%(real_module)s:%(real_funcName)s:%(real_lineno)d "
        "%(message)s",
    )

    # File handler (default behavior)
    if should_use_file_logging():
        file_path = log_file or get_log_file_path("aidb")
        try:
            file_handler = HalvingFileHandler(file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            # Fall back to console logging if file handler fails
            if not any(
                isinstance(h, logging.StreamHandler)
                and getattr(h, "stream", None) is sys.stdout
                for h in logger.handlers
            ):
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

    # Console handler (if requested)
    if (to_console or should_use_console_logging()) and not any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
        for h in logger.handlers
    ):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)


def _configure_mcp_profile(
    logger: logging.Logger,
    log_file: str | None,
) -> None:
    """Configure logger with MCP profile.

    Features:
    - Dual output: stderr for all, file for persistence
    - SessionContextFilter for session/request tracking
    - Color coding in terminal output
    - File logging to ~/.aidb/log/mcp.log (NEW!)
    """
    logger.addFilter(CallerFilter())
    logger.addFilter(SessionContextFilter())

    # Console formatter with colors and session context
    console_formatter = SessionFormatter(
        include_session=True,
        include_colors=True,
    )

    # File formatter without colors
    file_formatter = SessionFormatter(
        include_session=True,
        include_colors=False,
    )

    # Always output to stderr (MCP standard)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(console_formatter)
    logger.addHandler(stderr_handler)

    # File handler
    if should_use_file_logging():
        file_path = log_file or get_log_file_path("mcp")
        try:
            file_handler = HalvingFileHandler(file_path)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            # If file handler fails, we already have stderr handler emitted above
            # Nothing else to do; keep stderr output
            pass


def _configure_cli_profile(
    logger: logging.Logger,
    log_file: str | None,
    to_console: bool,
    verbose_debug: bool = False,
) -> None:
    """Configure logger with CLI profile.

    Features:
    - File logging to ~/.aidb/log/cli.log
    - CallerFilter for accurate source locations
    - SafeFormatter with real module/function/line info
    - Optional console output for debugging
    - Global debug logging for third-party libraries (when verbose_debug=True)
    """
    logger.addFilter(CallerFilter())

    formatter = SafeFormatter(
        "%(asctime)s %(levelname)-7s "
        "%(real_module)s:%(real_funcName)s:%(real_lineno)d "
        "%(message)s",
    )

    # File handler (default behavior)
    if should_use_file_logging():
        file_path = log_file or get_log_file_path("cli")
        try:
            file_handler = HalvingFileHandler(file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            # Fall back to console logging if file handler fails
            if not any(
                isinstance(h, logging.StreamHandler)
                and getattr(getattr(h, "stream", None), "name", None) == "stdout"
                for h in logger.handlers
            ):
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

    # Console handler (if requested)
    if (to_console or should_use_console_logging()) and not any(
        isinstance(h, logging.StreamHandler)
        and getattr(getattr(h, "stream", None), "name", None) == "stdout"
        for h in logger.handlers
    ):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Set up global debug logging for third-party libraries if requested
    if verbose_debug:
        setup_global_debug_logging(log_file or get_log_file_path("cli"))


def _configure_test_profile(
    logger: logging.Logger,
    log_file: str | None,  # noqa: ARG001
    _to_console: bool,
) -> None:
    """Configure logger with test profile.

    Features:
    - Pytest-compatible (works with caplog via propagation)
    - No file handler (relies on pytest's log_file configuration)
    - Console output only when not in pytest
    """
    # Check if pytest logging should be disabled
    if reader.read_bool("AIDB_TEST_LOGGING_DISABLED", default=False):
        logger.disabled = True
        return

    # Add CallerFilter for accurate test locations
    logger.addFilter(CallerFilter())

    # For pytest, ensure proper caplog integration
    if "pytest" in sys.modules:
        # Enable propagation - pytest will capture via root logger
        logger.propagate = True
        # Ensure root logger has appropriate level
        root_logger = logging.getLogger()
        if root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)
    else:
        # Use stderr when not in pytest to avoid interfering with captured output
        formatter = SafeFormatter(
            "%(asctime)s %(levelname)-7s "
            "[%(name)s] %(real_module)s:%(real_funcName)s:%(real_lineno)d "
            "%(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)


def _configure_custom_profile(
    logger: logging.Logger,
    log_file: str | None,
    to_console: bool,
    formatter: logging.Formatter | None = None,
    filters: list[logging.Filter] | None = None,
    handlers: list[logging.Handler] | None = None,
    **_kwargs: Any,
) -> None:
    """Configure logger with custom settings.

    Parameters
    ----------
    logger : logging.Logger
        Logger to configure
    log_file : str, optional
        Log file path
    to_console : bool
        Whether to add console output
    formatter : logging.Formatter, optional
        Custom formatter to use
    filters : list[logging.Filter], optional
        Custom filters to add
    handlers : list[logging.Handler], optional
        Custom handlers to add
    **kwargs
        Additional configuration options
    """
    # Add custom filters
    if filters:
        for filter_obj in filters:
            logger.addFilter(filter_obj)
    else:
        # Default filters
        logger.addFilter(CallerFilter())

    # Use custom formatter or default
    if formatter is None:
        formatter = SafeFormatter()

    # Add custom handlers
    if handlers:
        for handler in handlers:
            if handler.formatter is None:
                handler.setFormatter(formatter)
            logger.addHandler(handler)
    else:
        # Default handlers based on flags
        if log_file or should_use_file_logging():
            file_path = log_file or get_log_file_path("custom")
            file_handler = HalvingFileHandler(file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        if to_console or should_use_console_logging():
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)


def setup_root_logger(profile: ProfileType = "aidb", **kwargs: Any) -> None:
    """Set up the root logger with a profile.

    Parameters
    ----------
    profile : ProfileType
        Profile to use for root logger
    **kwargs
        Additional configuration options

    Examples
    --------
    >>> setup_root_logger("test")  # For pytest
    >>> setup_root_logger("mcp")  # For MCP server
    """
    configure_logger("", profile=profile, **kwargs)


# Convenience functions for each profile
def get_aidb_logger(name: str, **kwargs: Any) -> logging.Logger:
    """Get a logger configured with the default AIDB profile."""
    return configure_logger(name, profile="aidb", **kwargs)


def get_mcp_logger(name: str, **kwargs: Any) -> logging.Logger:
    """Get a logger configured with MCP profile."""
    return configure_logger(name, profile="mcp", **kwargs)


def get_cli_logger(name: str, **kwargs: Any) -> logging.Logger:
    """Get a logger configured with CLI profile."""
    return configure_logger(name, profile="cli", **kwargs)


def get_test_logger(name: str, **kwargs: Any) -> logging.Logger:
    """Get a logger configured with test profile."""
    return configure_logger(name, profile="test", **kwargs)


def setup_global_debug_logging(log_file_path: str | None = None) -> None:
    """Set up global debug logging for all third-party libraries.

    This configures the root logger to capture DEBUG-level logs from all
    third-party libraries and writes them to a log file with a [GLOBAL] prefix.

    Parameters
    ----------
    log_file_path : str, optional
        Path to the log file. If not provided, uses ~/.aidb/log/cli.log

    Examples
    --------
    >>> setup_global_debug_logging()  # Uses default cli.log
    >>> setup_global_debug_logging("/custom/path/debug.log")  # Custom path
    """
    from pathlib import Path

    # Configure root logger to catch all third-party library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Set up log file path
    if log_file_path is None:
        log_file_path = str(get_log_file_path("cli"))

    # Check if we already have a [GLOBAL] handler for this path to avoid duplicates
    resolved_path = str(Path(log_file_path).resolve())
    global_handler_exists = False

    for h in root_logger.handlers:
        if isinstance(h, HalvingFileHandler):
            handler_path = getattr(h, "baseFilename", "")
            # Compare resolved paths to handle symlinks and path differences
            handler_resolved = str(Path(handler_path).resolve()) if handler_path else ""
            if handler_resolved == resolved_path:
                formatter = getattr(h, "formatter", None)
                if (
                    formatter
                    and hasattr(formatter, "_fmt")
                    and "[GLOBAL]" in formatter._fmt
                ):
                    global_handler_exists = True
                    break

    if not global_handler_exists:
        # Create log directory if it doesn't exist
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

        # Add file handler to root logger for third-party logs
        try:
            file_handler = HalvingFileHandler(log_file_path, max_bytes=10 * 1024 * 1024)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                SafeFormatter(
                    "%(asctime)s [GLOBAL] %(name)s %(levelname)-7s %(message)s",
                ),
            )
            root_logger.addHandler(file_handler)

            # Log startup banner to indicate global logging is enabled
            logger = logging.getLogger("aidb_logging.config")
            logger.debug("=" * 43)
            logger.debug("GLOBAL LOGGING ENABLED")
            logger.debug("LOG FILE: %s", log_file_path)
            logger.debug("=" * 43)
        except (OSError, PermissionError):
            # If we can't write to file, silently continue
            # The CLI should still work even if global debug logging fails
            pass

    # Configure common third-party loggers that are used in Docker operations
    third_party_loggers = [
        "docker",  # Docker SDK
        "urllib3",  # HTTP requests from Docker SDK
        "requests",  # HTTP library
        "docker.api",  # Docker API client
        "docker.client",  # Docker client
        "docker.utils",  # Docker utilities
    ]

    for logger_name in third_party_loggers:
        third_party_logger = logging.getLogger(logger_name)
        third_party_logger.setLevel(logging.DEBUG)
        # Ensure propagation so debug info flows to root logger
        third_party_logger.propagate = True
