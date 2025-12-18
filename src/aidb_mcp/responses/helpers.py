"""Helper functions for creating common response patterns.

These helpers make it easier to create consistent error and success responses across
handlers without duplicating code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb.common.errors import DebugTimeoutError
from aidb_common.config import config

from ..core.exceptions import ErrorCode
from ..core.types import ErrorContext, MCPResponse, SessionProtocol
from .errors import (
    InternalError,
    InvalidActionError,
    InvalidParameterError,
    MissingParameterError,
    NoSessionError,
    NotPausedError,
    SessionNotStartedError,
)

if TYPE_CHECKING:
    from enum import Enum


def missing_parameter(
    param_name: str,
    param_description: str | None = None,
    example_value: str | None = None,
) -> MCPResponse:
    """Create a missing parameter error response.

    Parameters
    ----------
    param_name : str
        Name of the missing parameter
    param_description : str, optional
        Description of what the parameter should be
    example_value : str, optional
        Example of a valid value

    Returns
    -------
    dict
        MCP response dict with error details
    """
    return MissingParameterError(
        param_name=param_name,
        param_description=param_description or f"'{param_name}' is required",
        example_value=example_value,
    ).to_mcp_response()


def invalid_parameter(
    param_name: str,
    expected_type: str,
    received_value: Any,
    error_message: str | None = None,
) -> MCPResponse:
    """Create an invalid parameter error response.

    Parameters
    ----------
    param_name : str
        Name of the invalid parameter
    expected_type : str
        Description of expected type/format
    received_value : Any
        The invalid value that was provided
    error_message : str, optional
        Custom error message

    Returns
    -------
    dict
        MCP response dict with error details
    """
    return InvalidParameterError(
        parameter_name=param_name,
        expected_type=expected_type,
        received_value=str(received_value) if received_value is not None else None,
        error_message=error_message
        or f"Invalid {param_name}: expected {expected_type}, got {received_value}",
    ).to_mcp_response()


def invalid_action(
    action: str,
    valid_actions: list[str],
    tool_name: str | None = None,
) -> MCPResponse:
    """Create an invalid action error response.

    Parameters
    ----------
    action : str
        The invalid action provided
    valid_actions : list
        List of valid actions for this tool
    tool_name : str, optional
        Name of the tool for context

    Returns
    -------
    dict
        MCP response dict with error details
    """
    error_msg = f"'{action}' is not a valid action"
    if tool_name:
        error_msg += f" for {tool_name}"
    error_msg += f". Valid actions: {', '.join(valid_actions)}"

    return InvalidActionError(
        action=action,
        valid_actions=valid_actions,
        error_message=error_msg,
    ).to_mcp_response()


def no_session(
    operation: str,
    additional_context: str | None = None,
) -> MCPResponse:
    """Create a no session error response.

    Parameters
    ----------
    operation : str
        The operation that requires a session
    additional_context : str, optional
        Additional context about why session is needed

    Returns
    -------
    dict
        MCP response dict with error details
    """
    error_msg = f"No active debug session for {operation}"
    if additional_context:
        error_msg += f". {additional_context}"

    return NoSessionError(
        requested_operation=operation,
        error_message=error_msg,
    ).to_mcp_response()


def session_not_started(
    operation: str,
    session_id: str | None = None,
) -> MCPResponse:
    """Create a session not started error response.

    Parameters
    ----------
    operation : str
        The operation that requires a started session
    session_id : str, optional
        The session ID if known

    Returns
    -------
    dict
        MCP response dict with error details
    """
    return SessionNotStartedError(
        session_id=session_id,
        error_message=f"Session exists but not started for {operation}",
    ).to_mcp_response()


def not_paused(
    operation: str,
    suggestion: str | None = None,
    session: SessionProtocol | None = None,
) -> MCPResponse:
    """Create a not paused error response.

    Parameters
    ----------
    operation : str
        The operation that requires paused execution
    suggestion : str, optional
        Suggestion for how to pause execution
    session : SessionProtocol, optional
        Session object to get current status from

    Returns
    -------
    dict
        MCP response dict with error details
    """
    if session and hasattr(session, "status"):
        current_status = session.status.name
        error_msg = (
            f"Cannot {operation} - execution not paused "
            f"(current status: {current_status})"
        )
    else:
        error_msg = f"Cannot {operation} - execution not paused"

    if suggestion:
        error_msg += f". {suggestion}"

    return NotPausedError(
        requested_operation=operation,
        error_message=error_msg,
    ).to_mcp_response()


def is_session_paused(session: Any) -> bool:
    """Check if session is paused with defensive hasattr checks.

    Safely checks session state with fallbacks for incomplete session objects.
    Consolidates defensive checking pattern used across MCP handlers.

    Parameters
    ----------
    session : Any
        Session object to check (may be incomplete or None)

    Returns
    -------
    bool
        True if session is paused, False otherwise (including if session is None)
    """
    if not session:
        return False

    # Try direct method first (preferred for complete Session objects)
    if hasattr(session, "is_paused") and callable(session.is_paused):
        try:
            return session.is_paused()
        except Exception:  # noqa: S110 - Intentional: fall through to secondary check
            pass

    # Fallback to state.is_paused() for defensive access
    if hasattr(session, "state") and hasattr(session.state, "is_paused"):
        try:
            return session.state.is_paused()
        except Exception:  # noqa: S110 - Intentional: return False on any error
            return False

    return False


def check_paused_or_error(
    session: Any,
    operation: str,
    suggestion: str = "Set a breakpoint or wait for execution to pause",
) -> MCPResponse | None:
    """Check if session is paused and return error response if not.

    Combines defensive session state checking with error response generation.
    Use this in handlers that require the debugger to be paused.

    Parameters
    ----------
    session : Any
        Session object to check (may be incomplete or None)
    operation : str
        The operation that requires paused execution (for error message)
    suggestion : str, optional
        Suggestion for how to pause execution

    Returns
    -------
    MCPResponse | None
        Error response if not paused, None if paused (operation can proceed)

    Examples
    --------
    >>> error = check_paused_or_error(session, "step")
    >>> if error:
    ...     return error
    >>> # Continue with operation...
    """
    if is_session_paused(session):
        return None

    return not_paused(
        operation=operation,
        suggestion=suggestion,
        session=session if session else None,
    )


def validate_action_enum(
    action: str,
    enum_class: type[Enum],
    tool_name: str,
) -> MCPResponse | None:
    """Validate an action against an enum class.

    Parameters
    ----------
    action : str
        The action to validate
    enum_class : type[Enum]
        The enum class with valid actions
    tool_name : str
        Name of the tool for error messages

    Returns
    -------
    MCPResponse or None
        MCP error response dict if invalid, None if valid
    """
    valid_actions = [e.value for e in enum_class]
    if action not in valid_actions:
        return invalid_action(action, valid_actions, tool_name)
    return None


def validate_required_params(
    args: dict[str, Any],
    required: list[str],
) -> MCPResponse | None:
    """Validate that required parameters are present.

    Parameters
    ----------
    args : dict
        Arguments to validate
    required : list
        List of required parameter names

    Returns
    -------
    dict or None
        MCP error response dict if missing params, None if all present
    """
    for param in required:
        if param not in args or args[param] is None:
            return missing_parameter(param)
    return None


def handle_timeout_error(
    exception: Exception,
    operation: str,
    operation_description: str | None = None,
) -> MCPResponse | None:
    """Check if an exception is a timeout error and create appropriate response.

    This is a global handler for timeout errors in execution operations
    (step, execute/continue, run_until). It provides consistent error
    messages and helpful guidance for increasing the timeout.

    Parameters
    ----------
    exception : Exception
        The exception that was caught
    operation : str
        The operation that timed out (e.g., "step", "execute", "run_until")
    operation_description : str, optional
        Human-friendly description of what was happening

    Returns
    -------
    dict or None
        MCP error response dict if this is a timeout error, None otherwise
    """
    # Use proper type checking for timeout detection
    is_timeout = isinstance(exception, DebugTimeoutError)

    # Fallback for wrapped exceptions or edge cases
    if not is_timeout:
        error_msg = str(exception)
        is_timeout = "Timeout waiting for" in error_msg

    if not is_timeout:
        return None

    # Get current timeout value
    current_timeout = config.get_dap_request_timeout()

    # Create operation-specific description
    if not operation_description:
        operation_descriptions = {
            "step": "Step operation",
            "execute": "Execution operation",
            "continue": "Continue operation",
            "run_until": "Run until operation",
        }
        operation_description = operation_descriptions.get(
            operation,
            f"{operation.title()} operation",
        )

    # Create helpful error message
    error_response = InternalError(
        operation=operation,
        details=(
            f"{operation_description} timed out after {current_timeout} seconds. "
            "The debugger may need more time to process the operation."
        ),
        error_message=(
            f"{operation_description} timed out after {current_timeout} seconds"
        ),
    ).to_mcp_response()

    # Add helpful suggestions based on operation type
    timeout_value = int(current_timeout * 2)
    base_suggestions = [
        (
            f"Increase timeout using: config(action='set', "
            f"key='AIDB_DAP_REQUEST_WAIT_TIMEOUT', value='{timeout_value}.0')"
        ),
        f"Then retry the {operation} operation",
        f"Current timeout: {current_timeout} seconds",
    ]

    # Add operation-specific suggestions
    if operation == "step":
        base_suggestions.append(
            "Some debug operations may take longer, especially in loops/complex code",
        )
    elif operation == "run_until":
        base_suggestions.append(
            "Consider if the target location is reachable from current execution point",
        )
    else:
        base_suggestions.append(
            "Complex programs or slow systems may need longer timeouts",
        )

    error_response["suggestions"] = base_suggestions

    return error_response


def internal_error(
    operation: str,
    exception: Exception | str,
    summary: str | None = None,
    error_code: str | None = None,
    context: dict[str, Any] | None = None,
) -> MCPResponse:
    """Create an internal error response from an exception.

    Parameters
    ----------
    operation : str
        The operation that failed
    exception : Exception or str
        The exception or error message
    summary : str, optional
        Brief summary of the error
    error_code : str, optional
        Specific error code (defaults to AIDB_INTERNAL_ERROR)
    context : dict, optional
        Additional context for debugging

    Returns
    -------
    MCPResponse
        Error response with internal error details
    """
    error_msg = str(exception)
    if not summary:
        summary = f"{operation} failed"

    if not error_code:
        error_code = ErrorCode.AIDB_INTERNAL_ERROR.value

    error_context = ErrorContext(operation=operation)
    if context:
        for key, value in context.items():
            setattr(error_context, key, value)

    return InternalError(
        operation=operation,
        details=error_msg,
        error_message=summary,
        context=error_context,
    ).to_mcp_response()
