"""Enhanced error handling for MCP tools optimized for AI consumption.

This module provides structured error responses that help AI systems understand failures
and take corrective actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from aidb.common.errors import (
    AdapterCapabilityNotSupportedError,
    ConfigurationError,
    DebugAdapterError,
    DebugConnectionError,
    DebugSessionLostError,
    DebugTimeoutError,
)


class ErrorCategory(Enum):
    """Categories of errors."""

    VALIDATION = "validation"  # Input validation errors
    SESSION = "session"  # Session-related errors
    CONNECTION = "connection"  # Connection/network errors
    CAPABILITY = "capability"  # Feature not supported
    STATE = "state"  # Invalid state for operation
    TIMEOUT = "timeout"  # Operation timed out
    CONFIGURATION = "configuration"  # Configuration issues
    UNKNOWN = "unknown"  # Unknown/unexpected errors


class ErrorCode(Enum):
    """Standardized error codes for MCP tools.

    Convention: AIDB_<CATEGORY>_<SPECIFIC>
    """

    # Session errors
    AIDB_SESSION_NOT_FOUND = "AIDB_SESSION_NOT_FOUND"
    AIDB_SESSION_NOT_STARTED = "AIDB_SESSION_NOT_STARTED"
    AIDB_SESSION_NOT_ACTIVE = "AIDB_SESSION_NOT_ACTIVE"
    AIDB_SESSION_TERMINATED = "AIDB_SESSION_TERMINATED"
    AIDB_SESSION_LOST = "AIDB_SESSION_LOST"
    AIDB_SESSION_ALREADY_ACTIVE = "AIDB_SESSION_ALREADY_ACTIVE"
    AIDB_SESSION_START_FAILED = "AIDB_SESSION_START_FAILED"

    # State errors
    AIDB_STATE_NOT_PAUSED = "AIDB_STATE_NOT_PAUSED"
    AIDB_STATE_NOT_RUNNING = "AIDB_STATE_NOT_RUNNING"
    AIDB_STATE_INVALID = "AIDB_STATE_INVALID"

    # Validation errors
    AIDB_VALIDATION_MISSING_PARAM = "AIDB_VALIDATION_MISSING_PARAM"
    AIDB_VALIDATION_INVALID_FORMAT = "AIDB_VALIDATION_INVALID_FORMAT"
    AIDB_VALIDATION_INVALID_MODE = "AIDB_VALIDATION_INVALID_MODE"
    AIDB_VALIDATION_INVALID_LOCATION = "AIDB_VALIDATION_INVALID_LOCATION"
    AIDB_VALIDATION_INVALID_PATTERN = "AIDB_VALIDATION_INVALID_PATTERN"
    AIDB_VALIDATION_INVALID_TYPE = "AIDB_VALIDATION_INVALID_TYPE"
    AIDB_VALIDATION_INVALID_ACTION = "AIDB_VALIDATION_INVALID_ACTION"
    AIDB_VALIDATION_INVALID_TARGET = "AIDB_VALIDATION_INVALID_TARGET"

    # Introspection errors
    AIDB_INTROSPECTION_ERROR = "AIDB_INTROSPECTION_ERROR"
    AIDB_INTROSPECTION_LOCALS_ERROR = "AIDB_INTROSPECTION_LOCALS_ERROR"
    AIDB_INTROSPECTION_GLOBALS_ERROR = "AIDB_INTROSPECTION_GLOBALS_ERROR"
    AIDB_INTROSPECTION_EVAL_ERROR = "AIDB_INTROSPECTION_EVAL_ERROR"
    AIDB_INTROSPECTION_INVALID_FRAME = "AIDB_INTROSPECTION_INVALID_FRAME"
    AIDB_INTROSPECTION_INSPECT_FAILED = "AIDB_INTROSPECTION_INSPECT_FAILED"

    # Execution errors
    AIDB_EXECUTION_ERROR = "AIDB_EXECUTION_ERROR"
    AIDB_EXECUTION_TIMEOUT = "AIDB_EXECUTION_TIMEOUT"
    AIDB_EXECUTION_FAILED = "AIDB_EXECUTION_FAILED"
    AIDB_EXECUTION_BREAKPOINT_FAILED = "AIDB_EXECUTION_BREAKPOINT_FAILED"
    AIDB_EXECUTION_VARIABLE_SET_FAILED = "AIDB_EXECUTION_VARIABLE_SET_FAILED"
    AIDB_EXECUTION_PATCH_FAILED = "AIDB_EXECUTION_PATCH_FAILED"

    # Operation control errors
    AIDB_OPERATION_CANCELLED = "AIDB_OPERATION_CANCELLED"

    # Capability errors
    AIDB_CAPABILITY_NOT_SUPPORTED = "AIDB_CAPABILITY_NOT_SUPPORTED"
    AIDB_CAPABILITY_UNAVAILABLE = "AIDB_CAPABILITY_UNAVAILABLE"

    # Connection errors
    AIDB_CONNECTION_ERROR = "AIDB_CONNECTION_ERROR"
    AIDB_CONNECTION_LOST = "AIDB_CONNECTION_LOST"
    AIDB_CONNECTION_TIMEOUT = "AIDB_CONNECTION_TIMEOUT"

    # Configuration errors
    AIDB_CONFIGURATION_ERROR = "AIDB_CONFIGURATION_ERROR"
    AIDB_CONFIGURATION_INVALID = "AIDB_CONFIGURATION_INVALID"
    AIDB_CONFIGURATION_MISSING = "AIDB_CONFIGURATION_MISSING"
    AIDB_CONFIG_NOT_FOUND = "AIDB_CONFIG_NOT_FOUND"

    # Adapter management errors
    AIDB_ADAPTER_DOWNLOAD_FAILED = "AIDB_ADAPTER_DOWNLOAD_FAILED"
    AIDB_ADAPTER_NOT_FOUND = "AIDB_ADAPTER_NOT_FOUND"
    AIDB_ADAPTER_INSTALL_FAILED = "AIDB_ADAPTER_INSTALL_FAILED"

    # Context errors
    AIDB_CONTEXT_ERROR = "AIDB_CONTEXT_ERROR"
    AIDB_CONTEXT_MISSING = "AIDB_CONTEXT_MISSING"
    AIDB_CONTEXT_NO_MATCHES = "AIDB_CONTEXT_NO_MATCHES"

    # Generic errors (use sparingly)
    AIDB_INTERNAL_ERROR = "AIDB_INTERNAL_ERROR"
    AIDB_UNKNOWN_ERROR = "AIDB_UNKNOWN_ERROR"


class ErrorRecovery(Enum):
    """Recovery strategies for errors."""

    RETRY = "retry"  # Can retry the operation
    RESTART_SESSION = "restart_session"  # Need to restart debug session
    CHECK_STATE = "check_state"  # Check session state first
    FIX_INPUT = "fix_input"  # Fix input parameters
    USE_ALTERNATIVE = "use_alternative"  # Use alternative approach
    MANUAL_INTERVENTION = "manual_intervention"  # Requires user intervention
    NOT_RECOVERABLE = "not_recoverable"  # Cannot recover


def _classify_by_type(error: Exception) -> ErrorCategory | None:
    """Classify error by exception type.

    Parameters
    ----------
    error : Exception
        The error to classify

    Returns
    -------
    ErrorCategory | None
        The category if matched, None otherwise
    """
    if isinstance(error, ValueError | TypeError | KeyError):
        return ErrorCategory.VALIDATION
    if isinstance(error, DebugSessionLostError):
        return ErrorCategory.SESSION
    if isinstance(error, DebugConnectionError):
        return ErrorCategory.CONNECTION
    if isinstance(error, DebugTimeoutError):
        return ErrorCategory.TIMEOUT
    if isinstance(error, AdapterCapabilityNotSupportedError):
        return ErrorCategory.CAPABILITY
    if isinstance(error, ConfigurationError | DebugAdapterError):
        return ErrorCategory.CONFIGURATION
    return None


def _classify_by_message(error_msg: str) -> ErrorCategory | None:
    """Classify error by message patterns.

    Parameters
    ----------
    error_msg : str
        The error message (lowercase)

    Returns
    -------
    ErrorCategory | None
        The category if matched, None otherwise
    """
    pattern_map = [
        (["session"], ErrorCategory.SESSION),
        (["connection", "network"], ErrorCategory.CONNECTION),
        (["timeout"], ErrorCategory.TIMEOUT),
        (["not supported", "capability"], ErrorCategory.CAPABILITY),
        (["invalid", "required"], ErrorCategory.VALIDATION),
        (["state", "not paused"], ErrorCategory.STATE),
    ]

    for patterns, category in pattern_map:
        if any(pattern in error_msg for pattern in patterns):
            return category

    return None


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an error into a category for AI understanding.

    Parameters
    ----------
    error : Exception
        The error to classify

    Returns
    -------
    ErrorCategory
        The category of the error
    """
    category = _classify_by_type(error)
    if category:
        return category

    error_msg = str(error).lower()
    category = _classify_by_message(error_msg)
    if category:
        return category

    return ErrorCategory.UNKNOWN


def get_recovery_strategy(
    category: ErrorCategory,
    _error: Exception,
) -> list[ErrorRecovery]:
    """Determine recovery strategies for an error category.

    Parameters
    ----------
    category : ErrorCategory
        The error category
    _error : Exception
        The original error (unused for now)

    Returns
    -------
    List[ErrorRecovery]
        Possible recovery strategies in order of preference
    """
    strategies = []

    if category == ErrorCategory.VALIDATION:
        strategies = [ErrorRecovery.FIX_INPUT]
    elif category == ErrorCategory.SESSION:
        strategies = [ErrorRecovery.RESTART_SESSION]
    elif category == ErrorCategory.CONNECTION:
        strategies = [ErrorRecovery.RETRY, ErrorRecovery.RESTART_SESSION]
    elif category == ErrorCategory.TIMEOUT:
        strategies = [ErrorRecovery.RETRY]
    elif category == ErrorCategory.CAPABILITY:
        strategies = [ErrorRecovery.USE_ALTERNATIVE]
    elif category == ErrorCategory.STATE:
        strategies = [ErrorRecovery.CHECK_STATE]
    elif category == ErrorCategory.CONFIGURATION:
        strategies = [ErrorRecovery.MANUAL_INTERVENTION]
    else:
        strategies = [ErrorRecovery.NOT_RECOVERABLE]

    return strategies


def _get_validation_actions(error_msg: str) -> list[str]:
    """Get actions for validation errors."""
    actions = [
        "Check that all required parameters are provided",
        "Verify parameter types and formats",
    ]
    if "expression" in error_msg:
        actions.append("Ensure the expression syntax is valid for the target language")
    return actions


def _get_session_actions(error_msg: str) -> list[str]:
    """Get actions for session errors."""
    if "not started" in error_msg or "no active" in error_msg:
        return ["Start a debug session first using 'debug_start'"]
    if "lost" in error_msg or "terminated" in error_msg:
        return ["The session has ended - restart with 'debug_start'"]
    return [
        "Check session status with 'debug_status'",
        "Restart the session if necessary",
    ]


def _get_connection_actions(_error_msg: str) -> list[str]:
    """Get actions for connection errors."""
    return [
        "Check that the debug adapter is running",
        "Verify network connectivity",
        "Try restarting the debug session",
    ]


def _get_timeout_actions(_error_msg: str) -> list[str]:
    """Get actions for timeout errors."""
    return [
        "The operation is taking longer than expected",
        "Check if the target program is responsive",
        "Consider setting a breakpoint to pause execution first",
    ]


def _get_capability_actions(error_msg: str) -> list[str]:
    """Get actions for capability errors."""
    actions = [
        "This feature is not supported by the current debug adapter",
        "Check adapter capabilities with 'get_capabilities'",
    ]
    if "breakpoint" in error_msg:
        actions.append("Try using a different breakpoint type (line vs function)")
    return actions


def _get_state_actions(error_msg: str) -> list[str]:
    """Get actions for state errors."""
    if "not paused" in error_msg or "running" in error_msg:
        return [
            "The debugger must be paused to perform this operation",
            "Set a breakpoint or use 'debug_pause' first",
        ]
    if "not running" in error_msg:
        return [
            "The program needs to be running for this operation",
            "Use 'debug_continue' to resume execution",
        ]
    return []


def _get_configuration_actions(_error_msg: str) -> list[str]:
    """Get actions for configuration errors."""
    return [
        "Check the debug adapter configuration",
        "Verify the language/runtime is properly installed",
        "Ensure all required paths and settings are correct",
    ]


def get_suggested_actions(
    category: ErrorCategory,
    _error: Exception,
    _context: dict[str, Any] | None = None,
) -> list[str]:
    """Get suggested actions for recovering from an error.

    Parameters
    ----------
    category : ErrorCategory
        The error category
    _error : Exception
        The original error (unused for now)
    _context : dict, optional
        Additional context about the operation (unused for now)

    Returns
    -------
    List[str]
        List of suggested actions in order of preference
    """
    error_msg = str(_error).lower()

    action_handlers = {
        ErrorCategory.VALIDATION: _get_validation_actions,
        ErrorCategory.SESSION: _get_session_actions,
        ErrorCategory.CONNECTION: _get_connection_actions,
        ErrorCategory.TIMEOUT: _get_timeout_actions,
        ErrorCategory.CAPABILITY: _get_capability_actions,
        ErrorCategory.STATE: _get_state_actions,
        ErrorCategory.CONFIGURATION: _get_configuration_actions,
    }

    handler = action_handlers.get(category)
    if handler:
        return handler(error_msg)

    return []
