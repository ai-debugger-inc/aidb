"""Configuration management for AIDB MCP.

This module centralizes all configuration values that were previously hard-coded
throughout the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass

from aidb_common.config import config
from aidb_logging import get_mcp_logger

logger = get_mcp_logger(__name__)


@dataclass
class SessionConfig:
    """Configuration for session management."""

    # Cleanup configuration
    default_cleanup_timeout: float = 5.0  # seconds
    max_retry_attempts: int = 3
    retry_delay: float = 0.5  # seconds

    # Session limits
    max_concurrent_sessions: int = 10
    session_id_length: int = 8  # For auto-generated IDs

    # Health check configuration
    health_check_interval: float = 30.0  # seconds
    health_check_timeout: float = 2.0  # seconds


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    # Log levels
    default_level: str = "INFO"
    verbose_level: str = "DEBUG"

    # Formatting
    include_session_id: bool = True
    use_color: bool = True  # Auto-detected from terminal

    # Log format strings
    default_format: str = (
        "%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] - %(message)s"
    )
    simple_format: str = "%(levelname)s - %(message)s"

    # Session ID display
    session_id_truncate_length: int = 8


@dataclass
class DebugConfig:
    """Configuration for debugging operations."""

    # Timeouts (milliseconds)
    default_operation_timeout: int = 120000  # 2 minutes
    max_operation_timeout: int = 600000  # 10 minutes
    step_timeout: int = 5000  # 5 seconds

    # Execution limits
    max_step_count: int = 1000
    max_breakpoints: int = 100
    max_watch_expressions: int = 50

    # Buffer sizes
    event_queue_size: int = 100
    output_buffer_size: int = 10000

    # Performance
    variable_inspection_depth: int = 3
    max_array_preview_items: int = 100
    max_string_preview_length: int = 1000


@dataclass
class NotificationConfig:
    """Configuration for event notifications."""

    # Event monitoring
    event_monitoring_enabled: bool = True
    event_batch_size: int = 10
    event_batch_timeout: float = 1.0  # seconds

    # Queue sizes
    notification_queue_size: int = 100

    # Rate limiting
    max_notifications_per_second: int = 100
    notification_cooldown: float = 0.1  # seconds


@dataclass
class ValidationConfig:
    """Configuration for input validation."""

    # Expression validation
    allow_dangerous_expressions: bool = False
    max_expression_length: int = 1000

    # File paths
    require_existing_files: bool = False
    allow_relative_paths: bool = True

    # Limits
    max_session_id_length: int = 64
    max_condition_length: int = 500
    max_log_message_length: int = 1000


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring."""

    # Feature flags
    timing_enabled: bool = False
    detailed_timing: bool = False

    # Output configuration
    timing_format: str = "text"
    timing_file: str = ""  # Set by from_env(), defaults to ~/.aidb/log/mcp-perf.log

    # Thresholds
    slow_threshold_ms: float = 100.0

    # Limits
    history_size: int = 1000
    span_history_size: int = 1000

    # Token tracking
    token_estimation_method: str = "simple"  # noqa: S105


@dataclass
class MCPConfig:
    """Main configuration container for AIDB MCP."""

    session: SessionConfig
    logging: LoggingConfig
    debug: DebugConfig
    notification: NotificationConfig
    validation: ValidationConfig
    performance: PerformanceConfig

    # Server configuration
    server_name: str = "ai-debugger"
    server_version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> MCPConfig:
        """Create configuration from shared ConfigManager.

        Returns
        -------
        MCPConfig
            Configuration with values from environment or defaults
        """
        logger.debug("Loading configuration from shared ConfigManager")

        # Session Configuration
        session = SessionConfig(
            default_cleanup_timeout=config.get_mcp_cleanup_timeout(),
            max_retry_attempts=config.get_mcp_max_retries(),
            retry_delay=config.get_mcp_retry_delay(),
            max_concurrent_sessions=config.get_mcp_max_sessions(),
            session_id_length=config.get_mcp_session_id_length(),
            health_check_interval=config.get_mcp_health_check_interval(),
            health_check_timeout=config.get_mcp_health_check_timeout(),
        )
        logger.debug(
            "Loaded session configuration",
            extra={
                "cleanup_timeout": session.default_cleanup_timeout,
                "max_retries": session.max_retry_attempts,
                "max_sessions": session.max_concurrent_sessions,
            },
        )

        # Logging Configuration
        logging = LoggingConfig(
            default_level=config.get_mcp_log_level(),
            verbose_level=config.get_mcp_verbose_level(),
            include_session_id=config.is_mcp_log_session_id_enabled(),
            use_color=config.is_mcp_log_color_enabled(),
            default_format=config.get_mcp_log_format(),
            simple_format=config.get_mcp_log_format_simple(),
            session_id_truncate_length=config.get_mcp_session_id_truncate_length(),
        )
        logger.debug(
            "Loaded logging configuration",
            extra={
                "log_level": logging.default_level,
                "include_session": logging.include_session_id,
                "use_color": logging.use_color,
            },
        )

        # Debug Configuration
        debug = DebugConfig(
            default_operation_timeout=config.get_mcp_operation_timeout(),
            max_operation_timeout=config.get_mcp_max_operation_timeout(),
            step_timeout=config.get_mcp_step_timeout(),
            max_step_count=config.get_mcp_max_steps(),
            max_breakpoints=config.get_mcp_max_breakpoints(),
            max_watch_expressions=config.get_mcp_max_watch_expressions(),
            event_queue_size=config.get_mcp_event_queue_size(),
            output_buffer_size=config.get_mcp_output_buffer_size(),
            variable_inspection_depth=config.get_mcp_variable_inspection_depth(),
            max_array_preview_items=config.get_mcp_max_array_preview_items(),
            max_string_preview_length=config.get_mcp_max_string_preview_length(),
        )
        logger.debug(
            "Loaded debug configuration",
            extra={
                "operation_timeout_ms": debug.default_operation_timeout,
                "max_steps": debug.max_step_count,
                "max_breakpoints": debug.max_breakpoints,
                "event_queue_size": debug.event_queue_size,
            },
        )

        # Notification Configuration
        notification = NotificationConfig(
            event_monitoring_enabled=config.is_mcp_event_monitoring_enabled(),
            event_batch_size=config.get_mcp_event_batch_size(),
            event_batch_timeout=config.get_mcp_event_batch_timeout(),
            notification_queue_size=config.get_mcp_notification_queue_size(),
            max_notifications_per_second=config.get_mcp_max_notifications_per_sec(),
            notification_cooldown=config.get_mcp_notification_cooldown(),
        )

        # Validation Configuration
        validation = ValidationConfig(
            allow_dangerous_expressions=config.is_mcp_dangerous_expressions_allowed(),
            max_expression_length=config.get_mcp_max_expression_length(),
            require_existing_files=config.is_mcp_require_existing_files(),
            allow_relative_paths=config.is_mcp_relative_paths_allowed(),
            max_session_id_length=config.get_mcp_max_session_id_length(),
            max_condition_length=config.get_mcp_max_condition_length(),
            max_log_message_length=config.get_mcp_max_log_message_length(),
        )

        # Performance Configuration
        performance = PerformanceConfig(
            timing_enabled=config.is_mcp_timing_enabled(),
            detailed_timing=config.is_mcp_timing_detailed(),
            timing_format=config.get_mcp_timing_format(),
            timing_file=config.get_mcp_timing_file(),
            slow_threshold_ms=config.get_mcp_slow_threshold_ms(),
            history_size=config.get_mcp_timing_history_size(),
            span_history_size=config.get_mcp_timing_history_size(),
            token_estimation_method=config.get_mcp_token_estimation_method(),
        )

        mcp_config = cls(
            session=session,
            logging=logging,
            debug=debug,
            notification=notification,
            validation=validation,
            performance=performance,
            server_name=config.get_mcp_server_name(),
            server_version=config.get_mcp_server_version(),
        )

        logger.info(
            "Configuration loaded successfully from ConfigManager",
            extra={
                "server_name": mcp_config.server_name,
                "server_version": mcp_config.server_version,
                "env_vars_used": config.count_aidb_vars(),
            },
        )

        return mcp_config


_config: MCPConfig | None = None


def get_config() -> MCPConfig:
    """Get the global configuration instance.

    Returns
    -------
    MCPConfig
        Global configuration
    """
    global _config
    if _config is None:
        logger.debug("Initializing global configuration")
        _config = MCPConfig.from_env()
    return _config


def set_config(config: MCPConfig) -> None:
    """Set the global configuration instance.

    Parameters
    ----------
    config : MCPConfig
        Configuration to set
    """
    global _config
    _config = config
    logger.info(
        "Global configuration updated",
        extra={
            "server_name": config.server_name,
            "server_version": config.server_version,
        },
    )


def reload_config() -> MCPConfig:
    """Reload configuration from environment.

    Returns
    -------
    MCPConfig
        Reloaded configuration
    """
    global _config
    logger.info("Reloading configuration from environment")
    _config = MCPConfig.from_env()
    logger.info(
        "Configuration reloaded",
        extra={
            "server_name": _config.server_name,
            "server_version": _config.server_version,
        },
    )
    return _config
