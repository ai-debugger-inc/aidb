"""Retry logic for DAP client operations."""

from enum import Enum
from typing import Any

from aidb.common.errors import (
    DebugConnectionError,
    DebugSessionLostError,
    DebugTimeoutError,
)

from .constants import CommandType


class RetryStrategy(Enum):
    """Retry strategy for DAP operations."""

    NONE = "none"  # No retry
    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        initial_delay: float = 0.1,
        max_delay: float = 2.0,
        backoff_factor: float = 2.0,
    ):
        """Initialize retry configuration.

        Parameters
        ----------
        max_attempts : int
            Maximum number of attempts (including initial)
        strategy : RetryStrategy
            Retry strategy to use
        initial_delay : float
            Initial delay between retries in seconds
        max_delay : float
            Maximum delay between retries in seconds
        backoff_factor : float
            Factor to multiply delay by for exponential backoff
        """
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor


# Transient errors that are worth retrying
TRANSIENT_ERRORS = {
    DebugTimeoutError,
    DebugConnectionError,
}

# Permanent errors that should not be retried
PERMANENT_ERRORS = {
    DebugSessionLostError,
}


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is worth retrying.

    Parameters
    ----------
    error : Exception
        The error to check

    Returns
    -------
    bool
        True if the error is transient and worth retrying
    """
    # Check if it's a known permanent error
    if type(error) in PERMANENT_ERRORS:
        return False

    # Check if it's a known transient error
    if type(error) in TRANSIENT_ERRORS:
        return True

    # Check error messages for patterns
    error_msg = str(error).lower()

    # Connection-related errors are usually transient
    if any(
        pattern in error_msg
        for pattern in ["connection", "timeout", "adapter not ready", "handshake"]
    ):
        return True

    # Session-related errors are usually permanent
    if any(
        pattern in error_msg
        for pattern in ["session lost", "terminated", "invalid session"]
    ):
        return False

    # Default to not retrying unknown errors
    return False


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay before next retry attempt.

    Parameters
    ----------
    attempt : int
        Current attempt number (0-based)
    config : RetryConfig
        Retry configuration

    Returns
    -------
    float
        Delay in seconds before next attempt
    """
    if config.strategy == RetryStrategy.NONE:
        return 0

    if config.strategy == RetryStrategy.LINEAR:
        delay = config.initial_delay * (attempt + 1)
    else:  # EXPONENTIAL
        delay = config.initial_delay * (config.backoff_factor**attempt)

    return min(delay, config.max_delay)


class DAPRetryManager:
    """Manages retry configuration for different DAP operations."""

    # Operations that are safe to retry (idempotent)
    IDEMPOTENT_OPERATIONS: set[str] = {
        # Breakpoint operations
        CommandType.SET_BREAKPOINTS.value,
        CommandType.SET_FUNCTION_BREAKPOINTS.value,
        CommandType.SET_EXCEPTION_BREAKPOINTS.value,
        CommandType.SET_DATA_BREAKPOINTS.value,
        CommandType.SET_INSTRUCTION_BREAKPOINTS.value,
        # Query operations
        CommandType.THREADS.value,
        CommandType.STACK_TRACE.value,
        CommandType.SCOPES.value,
        CommandType.VARIABLES.value,
        CommandType.EVALUATE.value,  # In watch context only
        CommandType.SOURCE.value,
        CommandType.MODULES.value,
        CommandType.LOADED_SOURCES.value,
        CommandType.EXCEPTION_INFO.value,
        CommandType.COMPLETIONS.value,
        # Configuration operations
        CommandType.INITIALIZE.value,
        CommandType.CONFIGURATION_DONE.value,
        "capabilities",  # No CommandType for this yet
    }

    # Operations that should NEVER be retried
    NON_RETRYABLE_OPERATIONS: set[str] = {
        # State-changing operations
        CommandType.CONTINUE.value,
        CommandType.NEXT.value,
        CommandType.STEP_IN.value,
        CommandType.STEP_OUT.value,
        CommandType.STEP_BACK.value,
        CommandType.REVERSE_CONTINUE.value,
        CommandType.GOTO.value,
        CommandType.PAUSE.value,
        # Session lifecycle (can cause issues if retried)
        CommandType.LAUNCH.value,
        CommandType.ATTACH.value,
        "restart",  # No CommandType for this yet
        CommandType.DISCONNECT.value,
        CommandType.TERMINATE.value,
        # Modification operations
        CommandType.SET_VARIABLE.value,
        CommandType.SET_EXPRESSION.value,
        CommandType.RESTART_FRAME.value,
    }

    @classmethod
    def get_retry_config(
        cls,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> RetryConfig | None:
        """Get retry configuration for a specific DAP command.

        Parameters
        ----------
        command : str
            DAP command name
        context : dict, optional
            Additional context (e.g., evaluation context for evaluate command)

        Returns
        -------
        RetryConfig or None
            Retry configuration if operation is retryable, None otherwise
        """
        # Check if explicitly non-retryable
        if command in cls.NON_RETRYABLE_OPERATIONS:
            return None

        # Special handling for evaluate based on context
        if command == CommandType.EVALUATE.value and context:
            eval_context = context.get("context", "watch")
            # Only retry watch evaluations (read-only)
            if eval_context not in ["watch", "hover"]:
                return None

        # Check if idempotent
        if command in cls.IDEMPOTENT_OPERATIONS:
            # More aggressive retry for initialization commands
            init_commands = [
                CommandType.INITIALIZE.value,
                CommandType.CONFIGURATION_DONE.value,
            ]
            if command in init_commands:
                return RetryConfig(
                    max_attempts=5,
                    strategy=RetryStrategy.EXPONENTIAL,
                    initial_delay=0.2,
                    max_delay=3.0,
                )
            # Standard retry for other idempotent operations
            return RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.EXPONENTIAL,
                initial_delay=0.1,
                max_delay=1.0,
            )

        # Default to no retry for unknown operations
        return None
