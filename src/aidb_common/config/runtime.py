"""Runtime environment configuration for AIDB (shared).

This module centralizes access to environment-based configuration used across AIDB
components. Uses typed environment variable readers for consistent parsing and
validation.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from aidb_common.constants import SUPPORTED_LANGUAGES
from aidb_common.env.reader import (
    read_bool,
    read_float,
    read_int,
    read_list,
    read_path,
    read_str,
)
from aidb_common.patterns import Singleton
from aidb_logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class ConfigManager(Singleton["ConfigManager"]):
    """Configuration manager for AIDB environment variables.

    Implemented as a thread-safe singleton.
    """

    # ========== Logging & Debugging ==========
    AIDB_LOG_LEVEL = "AIDB_LOG_LEVEL"
    AIDB_ADAPTER_TRACE = "AIDB_ADAPTER_TRACE"
    AIDB_VALIDATE_BREAKPOINTS = "AIDB_VALIDATE_BREAKPOINTS"
    AIDB_CODE_CONTEXT_LINES = "AIDB_CODE_CONTEXT_LINES"
    AIDB_CODE_CONTEXT_MAX_LINE_WIDTH = "AIDB_CODE_CONTEXT_MAX_LINE_WIDTH"
    AIDB_CODE_CONTEXT_MINIFIED_MODE = "AIDB_CODE_CONTEXT_MINIFIED_MODE"

    # ========== Audit Logging ==========
    AIDB_AUDIT_LOG = "AIDB_AUDIT_LOG"
    AIDB_AUDIT_LOG_MB = "AIDB_AUDIT_LOG_MB"
    AIDB_AUDIT_LOG_PATH = "AIDB_AUDIT_LOG_PATH"
    AIDB_AUDIT_LOG_RETENTION_DAYS = "AIDB_AUDIT_LOG_RETENTION_DAYS"
    AIDB_AUDIT_LOG_DAP = "AIDB_AUDIT_LOG_DAP"

    # ========== Audit Masking ==========
    AIDB_AUDIT_ENABLED = "AIDB_AUDIT_ENABLED"
    AIDB_AUDIT_MASK_DEFAULT = "AIDB_AUDIT_MASK_DEFAULT"
    AIDB_AUDIT_CUSTOM_KEYS = "AIDB_AUDIT_CUSTOM_KEYS"
    AIDB_AUDIT_CUSTOM_PATTERNS = "AIDB_AUDIT_CUSTOM_PATTERNS"
    AIDB_AUDIT_STRICT_MODE = "AIDB_AUDIT_STRICT_MODE"
    AIDB_AUDIT_MASK_REPLACEMENT = "AIDB_AUDIT_MASK_REPLACEMENT"
    AIDB_AUDIT_MAX_DEPTH = "AIDB_AUDIT_MAX_DEPTH"
    AIDB_AUDIT_MASK_IN_METADATA = "AIDB_AUDIT_MASK_IN_METADATA"
    AIDB_AUDIT_CASE_SENSITIVE = "AIDB_AUDIT_CASE_SENSITIVE"

    # ========== DAP Protocol ==========
    AIDB_DAP_REQUEST_WAIT_TIMEOUT = "AIDB_DAP_REQUEST_WAIT_TIMEOUT"

    # ========== Language Adapter Paths ==========
    ADAPTER_PATH_TEMPLATE = "AIDB_{}_ADAPTER_PATH"
    AIDB_PYTHON_ADAPTER_PATH = "AIDB_PYTHON_ADAPTER_PATH"
    AIDB_JAVA_ADAPTER_PATH = "AIDB_JAVA_ADAPTER_PATH"
    AIDB_GO_ADAPTER_PATH = "AIDB_GO_ADAPTER_PATH"
    AIDB_CSHARP_ADAPTER_PATH = "AIDB_CSHARP_ADAPTER_PATH"
    AIDB_JAVASCRIPT_ADAPTER_PATH = "AIDB_JAVASCRIPT_ADAPTER_PATH"
    AIDB_CPP_ADAPTER_PATH = "AIDB_CPP_ADAPTER_PATH"

    # ========== Language Adapter Versions ==========
    ADAPTER_VERSION_TEMPLATE = "AIDB_{}_VERSION"

    # ========== Java-specific Configuration ==========
    AIDB_JAVA_AUTO_COMPILE = "AIDB_JAVA_AUTO_COMPILE"
    AIDB_JAVA_LSP_POOL = "AIDB_JAVA_LSP_POOL"
    AIDB_JAVA_LSP_POOL_MAX = "AIDB_JAVA_LSP_POOL_MAX"
    JAVA_HOME = "JAVA_HOME"
    JDT_LS_HOME = "JDT_LS_HOME"
    ECLIPSE_HOME = "ECLIPSE_HOME"

    # ========== Python Environments ==========
    CONDA_PREFIX = "CONDA_PREFIX"
    VIRTUAL_ENV = "VIRTUAL_ENV"

    # ========== MCP Session Configuration ==========
    AIDB_MCP_CLEANUP_TIMEOUT = "AIDB_MCP_CLEANUP_TIMEOUT"
    AIDB_MCP_MAX_RETRIES = "AIDB_MCP_MAX_RETRIES"
    AIDB_MCP_RETRY_DELAY = "AIDB_MCP_RETRY_DELAY"
    AIDB_MCP_MAX_SESSIONS = "AIDB_MCP_MAX_SESSIONS"
    AIDB_MCP_SESSION_ID_LENGTH = "AIDB_MCP_SESSION_ID_LENGTH"
    AIDB_MCP_HEALTH_CHECK_INTERVAL = "AIDB_MCP_HEALTH_CHECK_INTERVAL"
    AIDB_MCP_HEALTH_CHECK_TIMEOUT = "AIDB_MCP_HEALTH_CHECK_TIMEOUT"

    # ========== MCP Debug Configuration ==========
    AIDB_MCP_OPERATION_TIMEOUT = "AIDB_MCP_OPERATION_TIMEOUT"
    AIDB_MCP_MAX_OPERATION_TIMEOUT = "AIDB_MCP_MAX_OPERATION_TIMEOUT"
    AIDB_MCP_STEP_TIMEOUT = "AIDB_MCP_STEP_TIMEOUT"
    AIDB_MCP_MAX_STEPS = "AIDB_MCP_MAX_STEPS"
    AIDB_MCP_MAX_BREAKPOINTS = "AIDB_MCP_MAX_BREAKPOINTS"
    AIDB_MCP_MAX_WATCH_EXPRESSIONS = "AIDB_MCP_MAX_WATCH_EXPRESSIONS"
    AIDB_MCP_EVENT_QUEUE_SIZE = "AIDB_MCP_EVENT_QUEUE_SIZE"
    AIDB_MCP_OUTPUT_BUFFER_SIZE = "AIDB_MCP_OUTPUT_BUFFER_SIZE"
    AIDB_MCP_VARIABLE_INSPECTION_DEPTH = "AIDB_MCP_VARIABLE_INSPECTION_DEPTH"
    AIDB_MCP_MAX_ARRAY_PREVIEW_ITEMS = "AIDB_MCP_MAX_ARRAY_PREVIEW_ITEMS"
    AIDB_MCP_MAX_STRING_PREVIEW_LENGTH = "AIDB_MCP_MAX_STRING_PREVIEW_LENGTH"

    # ========== MCP Logging Configuration ==========
    AIDB_MCP_LOG_LEVEL = "AIDB_MCP_LOG_LEVEL"
    AIDB_MCP_VERBOSE_LEVEL = "AIDB_MCP_VERBOSE_LEVEL"
    AIDB_MCP_LOG_SESSION_ID = "AIDB_MCP_LOG_SESSION_ID"
    AIDB_MCP_LOG_COLOR = "AIDB_MCP_LOG_COLOR"
    AIDB_MCP_LOG_FORMAT = "AIDB_MCP_LOG_FORMAT"
    AIDB_MCP_LOG_FORMAT_SIMPLE = "AIDB_MCP_LOG_FORMAT_SIMPLE"
    AIDB_MCP_SESSION_ID_TRUNCATE_LENGTH = "AIDB_MCP_SESSION_ID_TRUNCATE_LENGTH"

    # ========== MCP Notification Configuration ==========
    AIDB_MCP_EVENT_MONITORING = "AIDB_MCP_EVENT_MONITORING"
    AIDB_MCP_EVENT_BATCH_SIZE = "AIDB_MCP_EVENT_BATCH_SIZE"
    AIDB_MCP_EVENT_BATCH_TIMEOUT = "AIDB_MCP_EVENT_BATCH_TIMEOUT"
    AIDB_MCP_NOTIFICATION_QUEUE_SIZE = "AIDB_MCP_NOTIFICATION_QUEUE_SIZE"
    AIDB_MCP_MAX_NOTIFICATIONS_PER_SEC = "AIDB_MCP_MAX_NOTIFICATIONS_PER_SEC"
    AIDB_MCP_NOTIFICATION_COOLDOWN = "AIDB_MCP_NOTIFICATION_COOLDOWN"
    AIDB_MCP_EVENT_TTL_SECONDS = "AIDB_MCP_EVENT_TTL_SECONDS"
    AIDB_MCP_EVENT_HISTORY_SIZE = "AIDB_MCP_EVENT_HISTORY_SIZE"

    # ========== MCP Validation Configuration ==========
    AIDB_MCP_ALLOW_DANGEROUS_EXPRESSIONS = "AIDB_MCP_ALLOW_DANGEROUS_EXPRESSIONS"
    AIDB_MCP_MAX_EXPRESSION_LENGTH = "AIDB_MCP_MAX_EXPRESSION_LENGTH"
    AIDB_MCP_REQUIRE_EXISTING_FILES = "AIDB_MCP_REQUIRE_EXISTING_FILES"
    AIDB_MCP_ALLOW_RELATIVE_PATHS = "AIDB_MCP_ALLOW_RELATIVE_PATHS"
    AIDB_MCP_MAX_SESSION_ID_LENGTH = "AIDB_MCP_MAX_SESSION_ID_LENGTH"
    AIDB_MCP_MAX_CONDITION_LENGTH = "AIDB_MCP_MAX_CONDITION_LENGTH"
    AIDB_MCP_MAX_LOG_MESSAGE_LENGTH = "AIDB_MCP_MAX_LOG_MESSAGE_LENGTH"

    # ========== MCP Server Configuration ==========
    AIDB_MCP_SERVER_NAME = "AIDB_MCP_SERVER_NAME"
    AIDB_MCP_SERVER_VERSION = "AIDB_MCP_SERVER_VERSION"

    # ========== MCP Response Configuration ==========
    AIDB_MCP_COMPACT = "AIDB_MCP_COMPACT"
    AIDB_MCP_VERBOSE = "AIDB_MCP_VERBOSE"
    AIDB_MCP_MINIMAL_VARIABLES = "AIDB_MCP_MINIMAL_VARIABLES"

    # ========== Logging & Debugging Methods ==========

    def get_log_level(self) -> str:
        """Get configured log level (default: INFO)."""
        return read_str(self.AIDB_LOG_LEVEL, "INFO").strip().upper()

    def is_adapter_trace_enabled(self) -> bool:
        """Check if adapter trace logging is enabled."""
        return read_bool(self.AIDB_ADAPTER_TRACE, False)

    def is_breakpoint_validation_enabled(self) -> bool:
        """Check if breakpoint validation is enabled (default: True)."""
        return read_bool(self.AIDB_VALIDATE_BREAKPOINTS, True)

    def get_code_context_lines(self) -> int:
        """Get number of lines to show around breakpoints (default: 5)."""
        return read_int(self.AIDB_CODE_CONTEXT_LINES, 5)

    def get_code_context_max_width(self) -> int:
        """Maximum width for displayed lines (default: 120)."""
        return read_int(self.AIDB_CODE_CONTEXT_MAX_LINE_WIDTH, 120)

    def get_code_context_minified_mode(self) -> str:
        """How to handle minified files: 'auto'|'force'|'disable' (default: 'auto')."""
        mode = read_str(self.AIDB_CODE_CONTEXT_MINIFIED_MODE, "auto").lower()
        return mode if mode in ("auto", "force", "disable") else "auto"

    # ========== Audit Logging Methods ==========

    def is_audit_enabled(self) -> bool:
        """Check if audit logging is enabled (default: False)."""
        return read_bool(self.AIDB_AUDIT_LOG, False)

    def get_audit_log_size_mb(self) -> int:
        """Get maximum audit log size in megabytes (default: 100)."""
        return read_int(self.AIDB_AUDIT_LOG_MB, 100)

    def get_audit_log_path(self) -> str | None:
        """Get custom audit log file path (default: None)."""
        return read_str(self.AIDB_AUDIT_LOG_PATH)

    def get_audit_retention_days(self) -> int:
        """Get audit log retention period in days (default: 30)."""
        return read_int(self.AIDB_AUDIT_LOG_RETENTION_DAYS, 30)

    def is_dap_audit_enabled(self) -> bool:
        """Check if DAP protocol audit logging is enabled (default: False)."""
        if not self.is_audit_enabled():
            return False
        return read_bool(self.AIDB_AUDIT_LOG_DAP, False)

    # ========== Audit Masking Methods ==========

    def is_audit_masking_enabled(self) -> bool:
        """Check if audit log masking is enabled (default: True)."""
        return read_bool(self.AIDB_AUDIT_ENABLED, True)

    def should_mask_sensitive_by_default(self) -> bool:
        """Check if sensitive data should be masked by default (default: True)."""
        return read_bool(self.AIDB_AUDIT_MASK_DEFAULT, True)

    def get_audit_custom_sensitive_keys(self) -> set[str]:
        """Get custom sensitive keys to mask in audit logs."""
        keys_list = read_list(self.AIDB_AUDIT_CUSTOM_KEYS, default=[])
        return set(keys_list) if keys_list else set()

    def get_audit_custom_patterns(self) -> list[str]:
        """Get custom regex patterns for masking in audit logs."""
        return read_list(self.AIDB_AUDIT_CUSTOM_PATTERNS, default=[])

    def is_audit_strict_mode(self) -> bool:
        """Check if strict mode is enabled for audit masking (default: False)."""
        return read_bool(self.AIDB_AUDIT_STRICT_MODE, False)

    def get_audit_mask_replacement(self) -> str:
        """Get replacement text for masked values (default: '***MASKED***')."""
        return read_str(self.AIDB_AUDIT_MASK_REPLACEMENT, "***MASKED***")

    def get_audit_max_depth(self) -> int:
        """Get maximum depth for nested object masking (default: 10)."""
        return read_int(self.AIDB_AUDIT_MAX_DEPTH, 10)

    def should_mask_metadata(self) -> bool:
        """Check if metadata should be masked in audit logs (default: True)."""
        return read_bool(self.AIDB_AUDIT_MASK_IN_METADATA, True)

    def is_audit_case_sensitive(self) -> bool:
        """Check if audit masking is case-sensitive (default: False)."""
        return read_bool(self.AIDB_AUDIT_CASE_SENSITIVE, False)

    # ========== DAP Protocol Methods ==========

    def get_dap_request_timeout(self) -> float:
        """Get DAP request timeout in seconds (default: 10.0)."""
        return read_float(self.AIDB_DAP_REQUEST_WAIT_TIMEOUT, 10.0)

    # ========== Language Adapter Methods ==========

    def get_binary_override(self, adapter: str) -> Path | None:
        """Get custom binary path for a language adapter."""
        env_var = self.ADAPTER_PATH_TEMPLATE.format(adapter.upper())
        return read_path(env_var)

    def get_adapter_version_override(self, adapter: str) -> str | None:
        """Get version override for a language adapter."""
        env_var = self.ADAPTER_VERSION_TEMPLATE.format(adapter.upper())
        return read_str(env_var)

    # ========== Java-specific Methods ==========

    def is_java_auto_compile_enabled(self) -> bool:
        """Check if Java auto-compilation is enabled (default: False)."""
        return read_bool(self.AIDB_JAVA_AUTO_COMPILE, False)

    def is_java_lsp_pool_enabled(self) -> bool:
        """Check if Java LSP pooling is enabled (default: True).

        When enabled, a single shared JDT LS instance is reused across all Java
        debugging sessions within a process, eliminating 8-9s startup per session.
        """
        return read_bool(self.AIDB_JAVA_LSP_POOL, True)

    def get_java_lsp_pool_max(self) -> int:
        """Get max per-project JDT LS instances (default: 5)."""
        return read_int(self.AIDB_JAVA_LSP_POOL_MAX, 5)

    def get_java_home(self) -> str | None:
        """Get JAVA_HOME environment variable."""
        return read_str(self.JAVA_HOME)

    def get_jdt_ls_home(self) -> str | None:
        """Get JDT Language Server home directory."""
        return read_str(self.JDT_LS_HOME)

    def get_eclipse_home(self) -> str | None:
        """Get Eclipse home directory."""
        return read_str(self.ECLIPSE_HOME)

    # ========== Python Environment Methods ==========

    def get_conda_prefix(self) -> str | None:
        """Get Conda environment prefix."""
        return read_str(self.CONDA_PREFIX)

    def get_virtual_env(self) -> str | None:
        """Get Python virtual environment path."""
        return read_str(self.VIRTUAL_ENV)

    # ========== MCP Session Configuration Methods ==========

    def get_mcp_cleanup_timeout(self) -> float:
        """Get MCP cleanup timeout in seconds (default: 5.0)."""
        return read_float(self.AIDB_MCP_CLEANUP_TIMEOUT, 5.0)

    def get_mcp_max_retries(self) -> int:
        """Get MCP max retry attempts (default: 3)."""
        return read_int(self.AIDB_MCP_MAX_RETRIES, 3)

    def get_mcp_retry_delay(self) -> float:
        """Get MCP retry delay in seconds (default: 0.5)."""
        return read_float(self.AIDB_MCP_RETRY_DELAY, 0.5)

    def get_mcp_max_sessions(self) -> int:
        """Get MCP max concurrent sessions (default: 10)."""
        return read_int(self.AIDB_MCP_MAX_SESSIONS, 10)

    def get_mcp_session_id_length(self) -> int:
        """Get MCP session ID length for auto-generation (default: 8)."""
        return read_int(self.AIDB_MCP_SESSION_ID_LENGTH, 8)

    def get_mcp_health_check_interval(self) -> float:
        """Get MCP health check interval in seconds (default: 30.0)."""
        return read_float(self.AIDB_MCP_HEALTH_CHECK_INTERVAL, 30.0)

    def get_mcp_health_check_timeout(self) -> float:
        """Get MCP health check timeout in seconds (default: 2.0)."""
        return read_float(self.AIDB_MCP_HEALTH_CHECK_TIMEOUT, 2.0)

    # ========== MCP Debug Configuration Methods ==========

    def get_mcp_operation_timeout(self) -> int:
        """Get MCP default operation timeout in milliseconds (default: 120000)."""
        return read_int(self.AIDB_MCP_OPERATION_TIMEOUT, 120000)

    def get_mcp_max_operation_timeout(self) -> int:
        """Get MCP max operation timeout in milliseconds (default: 600000)."""
        return read_int(self.AIDB_MCP_MAX_OPERATION_TIMEOUT, 600000)

    def get_mcp_step_timeout(self) -> int:
        """Get MCP step timeout in milliseconds (default: 5000)."""
        return read_int(self.AIDB_MCP_STEP_TIMEOUT, 5000)

    def get_mcp_max_steps(self) -> int:
        """Get MCP max step count (default: 1000)."""
        return read_int(self.AIDB_MCP_MAX_STEPS, 1000)

    def get_mcp_max_breakpoints(self) -> int:
        """Get MCP max breakpoints (default: 100)."""
        return read_int(self.AIDB_MCP_MAX_BREAKPOINTS, 100)

    def get_mcp_max_watch_expressions(self) -> int:
        """Get MCP max watch expressions (default: 50)."""
        return read_int(self.AIDB_MCP_MAX_WATCH_EXPRESSIONS, 50)

    def get_mcp_event_queue_size(self) -> int:
        """Get MCP event queue size (default: 100)."""
        return read_int(self.AIDB_MCP_EVENT_QUEUE_SIZE, 100)

    def get_mcp_output_buffer_size(self) -> int:
        """Get MCP output buffer size (default: 10000)."""
        return read_int(self.AIDB_MCP_OUTPUT_BUFFER_SIZE, 10000)

    def get_mcp_variable_inspection_depth(self) -> int:
        """Get MCP variable inspection depth (default: 3)."""
        return read_int(self.AIDB_MCP_VARIABLE_INSPECTION_DEPTH, 3)

    def get_mcp_max_array_preview_items(self) -> int:
        """Get MCP max array preview items (default: 100)."""
        return read_int(self.AIDB_MCP_MAX_ARRAY_PREVIEW_ITEMS, 100)

    def get_mcp_max_string_preview_length(self) -> int:
        """Get MCP max string preview length (default: 1000)."""
        return read_int(self.AIDB_MCP_MAX_STRING_PREVIEW_LENGTH, 1000)

    # ========== MCP Logging Configuration Methods ==========

    def get_mcp_log_level(self) -> str:
        """Get MCP log level (default: falls back to global AIDB_LOG_LEVEL or INFO)."""
        # MCP-specific overrides global, but falls back to global if not set
        mcp_level = read_str(self.AIDB_MCP_LOG_LEVEL, "")
        if mcp_level:
            return mcp_level
        # Fall back to global log level
        return self.get_log_level()

    def get_mcp_verbose_level(self) -> str:
        """Get MCP verbose log level (default: DEBUG)."""
        return read_str(self.AIDB_MCP_VERBOSE_LEVEL, "DEBUG")

    def is_mcp_log_session_id_enabled(self) -> bool:
        """Check if MCP should include session ID in logs (default: True)."""
        return read_bool(self.AIDB_MCP_LOG_SESSION_ID, True)

    def is_mcp_log_color_enabled(self) -> bool:
        """Check if MCP should use colored logs (default: True)."""
        return read_bool(self.AIDB_MCP_LOG_COLOR, True)

    def get_mcp_log_format(self) -> str:
        """Get MCP log format string (default format)."""
        return read_str(
            self.AIDB_MCP_LOG_FORMAT,
            "%(asctime)s - %(name)s - %(levelname)s - [%(session_id)s] - %(message)s",
        )

    def get_mcp_log_format_simple(self) -> str:
        """Get MCP simple log format string."""
        return read_str(self.AIDB_MCP_LOG_FORMAT_SIMPLE, "%(levelname)s - %(message)s")

    def get_mcp_session_id_truncate_length(self) -> int:
        """Get MCP session ID truncate length for display (default: 8)."""
        return read_int(self.AIDB_MCP_SESSION_ID_TRUNCATE_LENGTH, 8)

    # ========== MCP Notification Configuration Methods ==========

    def is_mcp_event_monitoring_enabled(self) -> bool:
        """Check if MCP event monitoring is enabled (default: True)."""
        return read_bool(self.AIDB_MCP_EVENT_MONITORING, True)

    def get_mcp_event_batch_size(self) -> int:
        """Get MCP event batch size (default: 10)."""
        return read_int(self.AIDB_MCP_EVENT_BATCH_SIZE, 10)

    def get_mcp_event_batch_timeout(self) -> float:
        """Get MCP event batch timeout in seconds (default: 1.0)."""
        return read_float(self.AIDB_MCP_EVENT_BATCH_TIMEOUT, 1.0)

    def get_mcp_notification_queue_size(self) -> int:
        """Get MCP notification queue size (default: 100)."""
        return read_int(self.AIDB_MCP_NOTIFICATION_QUEUE_SIZE, 100)

    def get_mcp_max_notifications_per_sec(self) -> int:
        """Get MCP max notifications per second (default: 100)."""
        return read_int(self.AIDB_MCP_MAX_NOTIFICATIONS_PER_SEC, 100)

    def get_mcp_notification_cooldown(self) -> float:
        """Get MCP notification cooldown in seconds (default: 0.1)."""
        return read_float(self.AIDB_MCP_NOTIFICATION_COOLDOWN, 0.1)

    def get_mcp_event_ttl_seconds(self) -> int:
        """Get MCP event TTL in seconds (default: 300)."""
        return read_int(self.AIDB_MCP_EVENT_TTL_SECONDS, 300)

    def get_mcp_event_history_size(self) -> int:
        """Get MCP event history buffer size (default: 50)."""
        return read_int(self.AIDB_MCP_EVENT_HISTORY_SIZE, 50)

    # ========== MCP Validation Configuration Methods ==========

    def is_mcp_dangerous_expressions_allowed(self) -> bool:
        """Check if MCP allows dangerous expressions (default: False)."""
        return read_bool(self.AIDB_MCP_ALLOW_DANGEROUS_EXPRESSIONS, False)

    def get_mcp_max_expression_length(self) -> int:
        """Get MCP max expression length (default: 1000)."""
        return read_int(self.AIDB_MCP_MAX_EXPRESSION_LENGTH, 1000)

    def is_mcp_require_existing_files(self) -> bool:
        """Check if MCP requires existing files (default: False)."""
        return read_bool(self.AIDB_MCP_REQUIRE_EXISTING_FILES, False)

    def is_mcp_relative_paths_allowed(self) -> bool:
        """Check if MCP allows relative paths (default: True)."""
        return read_bool(self.AIDB_MCP_ALLOW_RELATIVE_PATHS, True)

    def get_mcp_max_session_id_length(self) -> int:
        """Get MCP max session ID length (default: 64)."""
        return read_int(self.AIDB_MCP_MAX_SESSION_ID_LENGTH, 64)

    def get_mcp_max_condition_length(self) -> int:
        """Get MCP max condition length (default: 500)."""
        return read_int(self.AIDB_MCP_MAX_CONDITION_LENGTH, 500)

    def get_mcp_max_log_message_length(self) -> int:
        """Get MCP max log message length (default: 1000)."""
        return read_int(self.AIDB_MCP_MAX_LOG_MESSAGE_LENGTH, 1000)

    # ========== MCP Server Configuration Methods ==========

    def get_mcp_server_name(self) -> str:
        """Get MCP server name (default: ai-debugger)."""
        return read_str(self.AIDB_MCP_SERVER_NAME, "ai-debugger")

    def get_mcp_server_version(self) -> str:
        """Get MCP server version (default: 0.1.0)."""
        return read_str(self.AIDB_MCP_SERVER_VERSION, "0.1.0")

    # ========== MCP Performance/Tracing Configuration ==========

    def is_mcp_timing_enabled(self) -> bool:
        """Check if MCP timing is enabled.

        Returns
        -------
        bool
            True if AIDB_MCP_TIMING=1
        """
        return read_bool("AIDB_MCP_TIMING", False)

    def is_mcp_timing_detailed(self) -> bool:
        """Check if detailed timing (spans) is enabled.

        Returns
        -------
        bool
            True if AIDB_MCP_TIMING_DETAILED=1
        """
        return read_bool("AIDB_MCP_TIMING_DETAILED", False)

    def get_mcp_timing_format(self) -> str:
        """Get timing output format.

        Returns
        -------
        str
            One of: text, json, csv (default: text)
        """
        valid = ["text", "json", "csv"]
        value = read_str("AIDB_MCP_TIMING_FORMAT", "text").lower()
        return value if value in valid else "text"

    def get_mcp_timing_file(self) -> str:
        """Get timing log file path.

        Returns
        -------
        str
            Path to timing log file (default: ~/.aidb/log/mcp-perf.log)
        """
        from aidb_logging import get_log_file_path

        default = get_log_file_path("mcp", "mcp-perf.log")
        return read_str("AIDB_MCP_TIMING_FILE", default)

    def get_mcp_slow_threshold_ms(self) -> float:
        """Get slow operation threshold in milliseconds.

        Returns
        -------
        float
            Threshold in ms (default: 100.0)
        """
        return read_float("AIDB_MCP_SLOW_THRESHOLD_MS", 100.0)

    def get_mcp_timing_history_size(self) -> int:
        """Get max timing history size.

        Returns
        -------
        int
            Max entries to keep in memory (default: 1000)
        """
        return read_int("AIDB_MCP_TIMING_HISTORY_SIZE", 1000)

    def get_mcp_token_estimation_method(self) -> str:
        """Get token estimation method.

        Returns
        -------
        str
            One of: tiktoken, simple, disabled (default: simple)
        """
        valid = ["tiktoken", "simple", "disabled"]
        value = read_str("AIDB_MCP_TOKEN_ESTIMATION", "simple").lower()
        return value if value in valid else "simple"

    def is_mcp_verbose(self) -> bool:
        """Check if MCP verbose mode is enabled.

        Verbose mode provides human-friendly responses with:
        - Pretty-printed JSON (with indentation)
        - next_steps guidance included in all responses

        By default, MCP uses compact mode optimized for AI agents:
        - Compact JSON (minimal whitespace)
        - No next_steps guidance (saves 100-200 tokens per response)

        Returns
        -------
        bool
            True if AIDB_MCP_VERBOSE=1 (default: False)
        """
        return read_bool("AIDB_MCP_VERBOSE", False)

    def get_mcp_max_stack_frames(self) -> int:
        """Get maximum stack frames to include in responses.

        Returns
        -------
        int
            Maximum frames (default: 10)
        """
        return int(read_str("AIDB_MCP_MAX_STACK_FRAMES", "10"))

    def get_mcp_max_variables(self) -> int:
        """Get maximum variables to include in responses.

        Returns
        -------
        int
            Maximum variables (default: 20)
        """
        return int(read_str("AIDB_MCP_MAX_VARIABLES", "20"))

    def get_mcp_code_context_lines(self) -> int:
        """Get lines of code context before/after current line.

        Returns
        -------
        int
            Context lines (default: 3)
        """
        return int(read_str("AIDB_MCP_CODE_CONTEXT_LINES", "3"))

    def get_mcp_max_threads(self) -> int:
        """Get maximum threads to include in responses.

        Returns
        -------
        int
            Maximum threads (default: 10)
        """
        return int(read_str("AIDB_MCP_MAX_THREADS", "10"))

    def get_mcp_response_token_limit(self) -> int:
        """Get hard token limit for responses.

        Returns
        -------
        int
            Token limit (default: 1000)
        """
        return int(read_str("AIDB_MCP_RESPONSE_TOKEN_LIMIT", "1000"))

    def is_mcp_minimal_variables(self) -> bool:
        """Check if MCP minimal variable format is enabled.

        When enabled, omits redundant fields from variable representations:
        - Removes 'name' field when it duplicates dict key
        - Removes 'id' field when 0 (no children to fetch)

        Reserved for future use - currently deduplication is always enabled
        in compact mode via ResponseDeduplicator.

        Returns
        -------
        bool
            True if AIDB_MCP_MINIMAL_VARIABLES=1 (default: True)
        """
        return read_bool("AIDB_MCP_MINIMAL_VARIABLES", True)

    # ========== System Environment Methods ==========

    def get_user(self) -> str:
        """Get current system user (default: 'unknown')."""
        return read_str("USER", "unknown")

    # ========== Utility Methods ==========

    def get_env_with_prefix(self, prefix: str) -> dict[str, str]:
        """Get all environment variables with a specific prefix.

        Parameters
        ----------
        prefix : str
            Environment variable prefix (e.g., "AIDB_CLI_")

        Returns
        -------
        dict[str, str]
            Dictionary of matching environment variables
        """
        return {k: v for k, v in os.environ.items() if k.startswith(prefix)}

    def get_all_settings(self) -> dict:
        """Get all AIDB configuration settings as a dictionary."""
        settings = {
            "debug_control": {
                self.AIDB_ADAPTER_TRACE: os.environ.get(self.AIDB_ADAPTER_TRACE),
                self.AIDB_LOG_LEVEL: os.environ.get(self.AIDB_LOG_LEVEL),
            },
            "audit_logging": {
                self.AIDB_AUDIT_LOG: os.environ.get(self.AIDB_AUDIT_LOG),
                self.AIDB_AUDIT_LOG_MB: os.environ.get(self.AIDB_AUDIT_LOG_MB),
                self.AIDB_AUDIT_LOG_PATH: os.environ.get(self.AIDB_AUDIT_LOG_PATH),
                self.AIDB_AUDIT_LOG_RETENTION_DAYS: os.environ.get(
                    self.AIDB_AUDIT_LOG_RETENTION_DAYS,
                ),
                self.AIDB_AUDIT_LOG_DAP: os.environ.get(self.AIDB_AUDIT_LOG_DAP),
            },
            "dap": {
                self.AIDB_DAP_REQUEST_WAIT_TIMEOUT: os.environ.get(
                    self.AIDB_DAP_REQUEST_WAIT_TIMEOUT,
                ),
            },
            "java": {
                self.AIDB_JAVA_AUTO_COMPILE: os.environ.get(
                    self.AIDB_JAVA_AUTO_COMPILE,
                ),
                self.JAVA_HOME: os.environ.get(self.JAVA_HOME),
                self.JDT_LS_HOME: os.environ.get(self.JDT_LS_HOME),
                self.ECLIPSE_HOME: os.environ.get(self.ECLIPSE_HOME),
            },
            "system": {
                self.CONDA_PREFIX: os.environ.get(self.CONDA_PREFIX),
                self.VIRTUAL_ENV: os.environ.get(self.VIRTUAL_ENV),
                "USER": os.environ.get("USER"),
            },
            "mcp": {
                self.AIDB_MCP_LOG_LEVEL: os.environ.get(self.AIDB_MCP_LOG_LEVEL),
                self.AIDB_MCP_MAX_SESSIONS: os.environ.get(
                    self.AIDB_MCP_MAX_SESSIONS,
                ),
                self.AIDB_MCP_OPERATION_TIMEOUT: os.environ.get(
                    self.AIDB_MCP_OPERATION_TIMEOUT,
                ),
                self.AIDB_MCP_MAX_BREAKPOINTS: os.environ.get(
                    self.AIDB_MCP_MAX_BREAKPOINTS,
                ),
                self.AIDB_MCP_EVENT_MONITORING: os.environ.get(
                    self.AIDB_MCP_EVENT_MONITORING,
                ),
                self.AIDB_MCP_SERVER_NAME: os.environ.get(self.AIDB_MCP_SERVER_NAME),
                self.AIDB_MCP_SERVER_VERSION: os.environ.get(
                    self.AIDB_MCP_SERVER_VERSION,
                ),
            },
            "adapter_overrides": {},
        }

        for adapter in SUPPORTED_LANGUAGES:
            env_var = self.ADAPTER_PATH_TEMPLATE.format(adapter.upper())
            value = os.environ.get(env_var)
            if value:
                settings["adapter_overrides"][env_var] = value
        return settings

    def get_all_aidb_vars(self) -> dict[str, str]:
        """Get all AIDB_ environment variables.

        Returns
        -------
        dict[str, str]
            Dictionary of all AIDB_ environment variables and their values
        """
        return {k: v for k, v in os.environ.items() if k.startswith("AIDB_")}

    def count_aidb_vars(self) -> int:
        """Count number of AIDB_ environment variables.

        Returns
        -------
        int
            Number of AIDB_ environment variables currently set
        """
        return len(self.get_all_aidb_vars())

    def set_env_var(self, key: str, value: str) -> None:
        """Set an environment variable.

        Parameters
        ----------
        key : str
            Environment variable name
        value : str
            Environment variable value
        """
        os.environ[key] = value

    def validate_settings(self) -> list[str]:
        """Validate configuration settings and return warning messages."""
        warnings: list[str] = []
        for adapter in SUPPORTED_LANGUAGES:
            override = self.get_binary_override(adapter)
            if override and not override.exists():
                warnings.append(
                    f"Warning: {adapter} binary override points to "
                    f"non-existent path: {override}",
                )
        return warnings


# Global instance - singleton via Singleton pattern
config = ConfigManager()
