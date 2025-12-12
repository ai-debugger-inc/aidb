"""Common error response classes for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aidb.common.errors import AidbError
from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from ..core.exceptions import ErrorCode
from .base import ErrorResponse
from .next_steps import (
    ERROR_CONNECTION_LOST_NEXT_STEPS,
    ERROR_INVALID_PARAMETER_NEXT_STEPS,
    ERROR_NO_SESSION_NEXT_STEPS,
    ERROR_NOT_PAUSED_NEXT_STEPS,
)

logger = get_logger(__name__)


def extract_summary_from_exception(e: Exception) -> str | None:
    """Extract user-friendly summary from an exception if available.

    Parameters
    ----------
    e : Exception
        Exception to extract summary from

    Returns
    -------
    str | None
        Summary text if available, None otherwise
    """
    # Check if this is any AidbError subclass with a summary
    if isinstance(e, AidbError) and hasattr(e, "summary") and e.summary:
        return e.summary
    return None


@dataclass
class NoSessionError(ErrorResponse):
    """Error when no active debug session exists."""

    error_code: str = field(default=ErrorCode.AIDB_SESSION_NOT_FOUND.value, init=False)
    requested_operation: str | None = None

    def __post_init__(self):
        """Post-initialization logging for no session error."""
        logger.warning(
            "No session error raised",
            extra={
                "error_code": ErrorCode.AIDB_SESSION_NOT_FOUND.name,
                "requested_operation": self.requested_operation,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.requested_operation:
            return f"No active session for {self.requested_operation}"
        return "No active debug session found"

    def get_next_steps(self):
        """Get next steps when no session exists."""
        return ERROR_NO_SESSION_NEXT_STEPS


@dataclass
class SessionNotStartedError(ErrorResponse):
    """Error when session exists but isn't started."""

    error_code: str = field(
        default=ErrorCode.AIDB_SESSION_NOT_STARTED.value,
        init=False,
    )
    session_id: str | None = None

    def __post_init__(self):
        """Post-initialization logging for session not started error."""
        logger.warning(
            "Session not started error",
            extra={
                "error_code": ErrorCode.AIDB_SESSION_NOT_STARTED.name,
                "session_id": self.session_id,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        return "Debug session not started"

    def get_next_steps(self):
        """Get next steps when session is not started."""
        return ERROR_NO_SESSION_NEXT_STEPS


@dataclass
class SessionTerminatedError(ErrorResponse):
    """Error when session has terminated and cannot execute commands."""

    error_code: str = field(
        default=ErrorCode.AIDB_SESSION_TERMINATED.value,
        init=False,
    )
    session_id: str | None = None

    def __post_init__(self):
        """Post-initialization logging for session terminated error."""
        logger.warning(
            "Session terminated error",
            extra={
                "error_code": ErrorCode.AIDB_SESSION_TERMINATED.name,
                "session_id": self.session_id,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        return "Debug session has terminated"

    def get_next_steps(self):
        """Get next steps when session is terminated."""
        return [
            {
                "tool": "session",
                "description": "Check session status",
                "when": "to verify termination",
                "params_example": {"action": "status"},
            },
            {
                "tool": "session",
                "description": "Restart the terminated session",
                "when": "to restart with same configuration",
                "params_example": {"action": "restart"},
            },
            {
                "tool": "session_start",
                "description": "Start a new debug session",
                "when": "to start fresh debugging session",
                "params_example": {
                    "target": "main.py",
                    "language": Language.PYTHON,
                },
            },
        ]


@dataclass
class NotPausedError(ErrorResponse):
    """Error when operation requires paused state but execution is running."""

    error_code: str = field(default=ErrorCode.AIDB_STATE_NOT_PAUSED.value, init=False)
    requested_operation: str | None = None

    def __post_init__(self):
        logger.debug(
            "Not paused error",
            extra={
                "error_code": ErrorCode.AIDB_STATE_NOT_PAUSED.name,
                "requested_operation": self.requested_operation,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.requested_operation:
            return f"Cannot {self.requested_operation} - execution not paused"
        return "Operation requires paused execution"

    def get_next_steps(self):
        """Get next steps when execution is not paused."""
        return ERROR_NOT_PAUSED_NEXT_STEPS


@dataclass
class ConnectionLostError(ErrorResponse):
    """Error when debug adapter connection is lost."""

    error_code: str = field(default=ErrorCode.AIDB_CONNECTION_LOST.value, init=False)
    session_id: str | None = None
    adapter_type: str | None = None

    def __post_init__(self):
        logger.error(
            "Connection lost to debug adapter",
            extra={
                "error_code": ErrorCode.AIDB_CONNECTION_LOST.name,
                "session_id": self.session_id,
                "adapter_type": self.adapter_type,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.adapter_type:
            return f"Lost connection to {self.adapter_type} adapter"
        return "Debug adapter connection lost"

    def get_next_steps(self):
        """Get next steps when connection is lost."""
        return ERROR_CONNECTION_LOST_NEXT_STEPS


@dataclass
class InvalidParameterError(ErrorResponse):
    """Error for invalid or missing parameters."""

    error_code: str = field(
        default=ErrorCode.AIDB_VALIDATION_INVALID_FORMAT.value,
        init=False,
    )
    parameter_name: str | None = None
    expected_type: str | None = None
    received_value: str | None = None

    def __post_init__(self):
        logger.debug(
            "Invalid parameter error",
            extra={
                "error_code": ErrorCode.AIDB_VALIDATION_INVALID_FORMAT.name,
                "parameter_name": self.parameter_name,
                "expected_type": self.expected_type,
                "received_value": self.received_value,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.parameter_name:
            if self.expected_type:
                return f"Invalid {self.parameter_name}: expected {self.expected_type}"
            return f"Invalid parameter: {self.parameter_name}"
        return "Invalid parameter format"

    def get_next_steps(self):
        """Get next steps for invalid parameter error."""
        return ERROR_INVALID_PARAMETER_NEXT_STEPS


@dataclass
class MissingParameterError(ErrorResponse):
    """Error when required parameter is missing."""

    error_code: str = field(
        default=ErrorCode.AIDB_VALIDATION_MISSING_PARAM.value,
        init=False,
    )
    param_name: str = ""
    param_description: str | None = None
    example_value: str | None = None

    def __post_init__(self):
        logger.debug(
            "Missing parameter error",
            extra={
                "error_code": ErrorCode.AIDB_VALIDATION_MISSING_PARAM.name,
                "param_name": self.param_name,
                "has_description": bool(self.param_description),
                "has_example": bool(self.example_value),
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.param_name:
            return f"Missing required parameter: {self.param_name}"
        return "Missing required parameter"

    def get_next_steps(self):
        """Get next steps for missing parameter error."""
        return ERROR_INVALID_PARAMETER_NEXT_STEPS


@dataclass
class InitRequiredError(ErrorResponse):
    """Error when init hasn't been called before session operations."""

    error_code: str = field(default="INIT_REQUIRED", init=False)
    suggestions: list = field(default_factory=list)

    def _generate_summary(self) -> str:
        return "Init required before session start"


@dataclass
class SessionStartFailedError(ErrorResponse):
    """Error when session start fails."""

    error_code: str = field(
        default=ErrorCode.AIDB_SESSION_START_FAILED.value,
        init=False,
    )
    session_id: str | None = None
    mode: str | None = None
    target: str | None = None
    start_result: str | None = None
    original_exception: Exception | None = None

    def __post_init__(self):
        logger.error(
            "Session start failed",
            extra={
                "error_code": ErrorCode.AIDB_SESSION_START_FAILED.name,
                "session_id": self.session_id,
                "mode": self.mode,
                "target": self.target,
                "start_result": self.start_result,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        # Start with base summary
        base_summary = "Failed to start debug session"

        # Check if this is a VS Code variable error for a more specific base
        if "VS Code variable" in self.error_message or "${" in self.error_message:
            base_summary = "Cannot start session"

        # Try to extract and append summary from original exception
        if self.original_exception:
            exc_summary = extract_summary_from_exception(self.original_exception)
            if exc_summary:
                return f"{base_summary}: {exc_summary}"

        return base_summary


@dataclass
class InvalidActionError(ErrorResponse):
    """Error when action is not valid."""

    error_code: str = field(
        default=ErrorCode.AIDB_VALIDATION_INVALID_ACTION.value,
        init=False,
    )
    action: str = ""
    valid_actions: list = field(default_factory=list)

    def __post_init__(self):
        logger.debug(
            "Invalid action error",
            extra={
                "error_code": ErrorCode.AIDB_VALIDATION_INVALID_ACTION.name,
                "action": self.action,
                "valid_actions": self.valid_actions,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        return f"Invalid action: {self.action}"


@dataclass
class AidbTimeoutError(ErrorResponse):
    """Error when operation times out."""

    error_code: str = field(default=ErrorCode.AIDB_EXECUTION_TIMEOUT.value, init=False)
    operation: str | None = None
    timeout_ms: int | None = None

    def __post_init__(self):
        logger.warning(
            "Operation timeout",
            extra={
                "error_code": ErrorCode.AIDB_EXECUTION_TIMEOUT.name,
                "operation": self.operation,
                "timeout_ms": self.timeout_ms,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.operation and self.timeout_ms:
            return f"{self.operation} timed out after {self.timeout_ms}ms"
        if self.operation:
            return f"{self.operation} timed out"
        return "Operation timed out"


@dataclass
class UnsupportedOperationError(ErrorResponse):
    """Error when operation is not supported by adapter."""

    error_code: str = field(
        default=ErrorCode.AIDB_CAPABILITY_NOT_SUPPORTED.value,
        init=False,
    )
    operation: str = ""
    adapter_type: str | None = None
    language: str | None = None

    def __post_init__(self):
        logger.info(
            "Unsupported operation requested",
            extra={
                "error_code": ErrorCode.AIDB_CAPABILITY_NOT_SUPPORTED.name,
                "operation": self.operation,
                "adapter_type": self.adapter_type,
                "language": self.language,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.adapter_type:
            return f"{self.operation} not supported by {self.adapter_type}"
        if self.language:
            return f"{self.operation} not supported for {self.language}"
        return f"{self.operation} not supported"


@dataclass
class AdapterNotFoundError(ErrorResponse):
    """Error when a debug adapter cannot be found."""

    error_code: str = field(default=ErrorCode.AIDB_ADAPTER_NOT_FOUND.value, init=False)
    language: str | None = None
    searched_locations: list[str] = field(default_factory=list)
    download_instructions: str | None = None

    def __post_init__(self):
        logger.warning(
            "Adapter not found",
            extra={
                "error_code": ErrorCode.AIDB_ADAPTER_NOT_FOUND.name,
                "language": self.language,
                "searched_locations": self.searched_locations,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        if self.language:
            return f"{self.language.capitalize()} debug adapter not found"
        return "Debug adapter not found"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize adapter not found error with enhanced adapter context."""
        # Add adapter-specific context
        if self.language:
            response["language"] = self.language
        if self.searched_locations:
            response["searched_locations"] = self.searched_locations
        if self.download_instructions:
            response["download_instructions"] = self.download_instructions

        # Add immediate action suggestions
        response["immediate_actions"] = [
            f"Use adapter tool with action='download', language='{self.language}'"
            if self.language
            else "Use adapter tool with action='download'",
            "Check adapter installation with adapter tool action='list'",
            "Download all adapters with adapter tool action='download_all'",
        ]

        return response


@dataclass
class InternalError(ErrorResponse):
    """Generic internal error when something unexpected happens."""

    error_code: str = field(default=ErrorCode.AIDB_INTERNAL_ERROR.value, init=False)
    operation: str | None = None
    details: str | None = None
    summary: str = ""
    original_exception: Exception | None = None

    def __post_init__(self):
        # Auto-extract summary from original exception if not provided
        if not self.summary and self.original_exception:
            summary_from_exc = extract_summary_from_exception(self.original_exception)
            if summary_from_exc:
                self.summary = summary_from_exc

        logger.error(
            "Internal error occurred",
            extra={
                "error_code": ErrorCode.AIDB_INTERNAL_ERROR.name,
                "operation": self.operation,
                "details": self.details,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        # Use explicit summary if provided
        if self.summary:
            return self.summary

        # Fallback to generic messages
        if self.operation:
            return f"Internal error during {self.operation}"
        return "Internal error occurred"
