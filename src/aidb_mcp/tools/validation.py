"""Validation utilities for MCP tool input parameters.

Provides reusable validation functions and decorators for consistent input validation
across all handlers.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aidb_common.constants import Language
from aidb_common.path import normalize_path
from aidb_logging import get_mcp_logger as get_logger

from ..core.constants import ParamName
from .actions import StepAction

logger = get_logger(__name__)


def validate_required_params(
    args: dict[str, Any],
    required: list[str],
) -> tuple[bool, str | None]:
    """Validate that all required parameters are present.

    Parameters
    ----------
    args : dict
        Arguments to validate
    required : list
        List of required parameter names

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    missing = [param for param in required if not args.get(param)]
    if missing:
        error_msg = f"Missing required parameters: {', '.join(missing)}"
        logger.debug(
            "Validation failed: missing parameters",
            extra={"missing": missing, "provided": list(args.keys())},
        )
        return False, error_msg
    logger.debug(
        "Required parameters validated",
        extra={"required": required, "args_count": len(args)},
    )
    return True, None


def validate_session_id(session_id: str | None) -> tuple[bool, str | None]:
    """Validate session ID format.

    Parameters
    ----------
    session_id : str, optional
        Session ID to validate

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if not session_id:
        return True, None  # Optional parameter

    # Session IDs should be alphanumeric with hyphens/underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
        logger.warning(
            "Invalid session ID format",
            extra={"session_id": session_id, "pattern": "^[a-zA-Z0-9_-]+$"},
        )
        return False, f"Invalid session ID format: {session_id}"

    logger.debug("Session ID validated %s", extra={"session_id": session_id})
    return True, None


def validate_file_path(
    path: str,
    must_exist: bool = False,
) -> tuple[bool, str | None, Path | None]:
    """Validate a file path.

    Parameters
    ----------
    path : str
        File path to validate
    must_exist : bool
        Whether the file must exist

    Returns
    -------
    tuple
        (is_valid, error_message, resolved_path)
    """
    try:
        file_path = Path(path)

        if must_exist and not file_path.exists():
            logger.debug(
                "File validation failed: not found",
                extra={"path": path, "must_exist": must_exist},
            )
            return False, f"File not found: {path}", None

        if must_exist and not file_path.is_file():
            logger.debug(
                "File validation failed: not a file",
                extra={"path": path, "is_dir": file_path.is_dir()},
            )
            return False, f"Not a file: {path}", None

        resolved = normalize_path(file_path, strict=True, return_path=True)
        logger.debug(
            "File path validated",
            extra={
                "original": path,
                "resolved": str(resolved),
                "exists": file_path.exists(),
            },
        )
        return True, None, resolved
    except Exception as e:
        logger.exception(
            "File path validation error",
            extra={"path": path, "error": str(e)},
        )
        return False, f"Invalid file path: {e}", None


def validate_breakpoint_location(
    location: str,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Validate and parse a breakpoint location.

    Parameters
    ----------
    location : str
        Breakpoint location (``file:line``, line, or function)

    Returns
    -------
    tuple
        (is_valid, error_message, parsed_location)
    """
    # Check for file:line format
    if ":" in location:
        parts = location.rsplit(":", 1)
        file_path = parts[0]
        try:
            line = int(parts[1])
            if line < 1:
                logger.debug(
                    "Invalid breakpoint line number",
                    extra={"location": location, "line": line},
                )
                return False, f"Line number must be positive: {line}", None
            parsed = {"file": file_path, "line": line}
            logger.debug(
                "Breakpoint location parsed as file:line",
                extra={"location": location, "parsed": parsed},
            )
            return True, None, parsed
        except ValueError:
            logger.debug(
                "Invalid line number in breakpoint location",
                extra={"location": location, "line_part": parts[1]},
            )
            return False, f"Invalid line number: {parts[1]}", None

    # Check for line number only
    try:
        line = int(location)
        if line < 1:
            logger.debug(
                "Invalid breakpoint line number",
                extra={"location": location, "line": line},
            )
            return False, f"Line number must be positive: {line}", None
        parsed = {"line": line}
        logger.debug(
            "Breakpoint location parsed as line only",
            extra={"location": location, "parsed": parsed},
        )
        return True, None, parsed
    except ValueError:
        pass

    # Assume it's a function name
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", location):
        parsed = {"function": location}
        logger.debug(
            "Breakpoint location parsed as function",
            extra={"location": location, "parsed": parsed},
        )
        return True, None, parsed

    logger.warning(
        "Invalid breakpoint location format %s",
        extra={"location": location},
    )
    return False, f"Invalid breakpoint location format: {location}", None


def validate_expression(
    expression: str,
    language: str = "python",
) -> tuple[bool, str | None]:
    """Validate an expression for evaluation.

    Parameters
    ----------
    expression : str
        Expression to validate
    language : str
        Programming language

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if not expression or not expression.strip():
        logger.debug("Expression validation failed: empty expression")
        return False, "Expression cannot be empty"

    # Basic validation - prevent obvious injection attempts
    dangerous_patterns = [
        r"__import__",  # Python import
        r"exec\s*\(",  # Python exec
        r"eval\s*\(",  # Python eval
        r"compile\s*\(",  # Python compile
        r"open\s*\(",  # File operations
        r"subprocess",  # System commands
        r"os\.",  # OS operations
        r"sys\.exit",  # System exit
    ]

    if language == Language.PYTHON:
        for pattern in dangerous_patterns:
            if re.search(pattern, expression, re.IGNORECASE):
                logger.warning(
                    "Dangerous operation detected in expression",
                    extra={
                        "expression": expression[:100],  # Truncate for safety
                        "pattern": pattern,
                        "language": language,
                    },
                )
                return (
                    False,
                    f"Expression contains potentially dangerous operation: {pattern}",
                )

    logger.debug(
        "Expression validated",
        extra={"language": language, "length": len(expression)},
    )
    return True, None


def validate_step_action(action: str) -> tuple[bool, str | None]:
    """Validate step action.

    Parameters
    ----------
    action : str
        Step action to validate

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    valid_actions = [e.value for e in StepAction]
    if action.lower() not in valid_actions:
        logger.debug(
            "Invalid step action",
            extra={"action": action, "valid_actions": valid_actions},
        )
        return (
            False,
            (
                f"Invalid step action '{action}'. "
                f"Valid actions: {', '.join(valid_actions)}"
            ),
        )
    logger.debug("Step action validated %s", extra={"action": action})
    return True, None


def validate_frame_id(frame_id: Any) -> tuple[bool, str | None, int | None]:
    """Validate and parse frame ID.

    Parameters
    ----------
    frame_id : any
        Frame ID to validate

    Returns
    -------
    tuple
        (is_valid, error_message, parsed_frame_id)
    """
    if frame_id is None:
        return True, None, None

    try:
        frame_int = int(frame_id)
        if frame_int < 0:
            logger.debug(
                "Invalid frame ID: negative value",
                extra={"frame_id": frame_id, "parsed": frame_int},
            )
            return False, f"Frame ID must be non-negative: {frame_int}", None
        logger.debug("Frame ID validated %s", extra={"frame_id": frame_int})
        return True, None, frame_int
    except (ValueError, TypeError) as e:
        logger.debug(
            "Invalid frame ID format",
            extra={"frame_id": frame_id, "error": str(e)},
        )
        return False, f"Invalid frame ID: {frame_id}", None


def validate_timeout(timeout: Any) -> tuple[bool, str | None, int | None]:
    """Validate timeout value.

    Parameters
    ----------
    timeout : any
        Timeout value to validate (in milliseconds)

    Returns
    -------
    tuple
        (is_valid, error_message, parsed_timeout)
    """
    if timeout is None:
        return True, None, None

    try:
        timeout_int = int(timeout)
        if timeout_int < 0:
            logger.debug(
                "Invalid timeout: negative value %s",
                extra={"timeout": timeout},
            )
            return False, "Timeout must be non-negative", None
        if timeout_int > 300000:  # 5 minutes max
            logger.debug(
                "Invalid timeout: exceeds maximum",
                extra={"timeout": timeout_int, "max": 300000},
            )
            return False, "Timeout cannot exceed 300000ms (5 minutes)", None
        logger.debug("Timeout validated %s", extra={"timeout": timeout_int})
        return True, None, timeout_int
    except (ValueError, TypeError) as e:
        logger.debug(
            "Invalid timeout format",
            extra={"timeout": timeout, "error": str(e)},
        )
        return False, f"Invalid timeout value: {timeout}", None


def format_validation_error(
    param_name: str,
    expected_format: str,
    provided_value: Any,
    examples: list[str] | None = None,
) -> str:
    """Format a validation error message with examples.

    Parameters
    ----------
    param_name : str
        Name of the parameter
    expected_format : str
        Expected format description
    provided_value : any
        The invalid value provided
    examples : list, optional
        Example valid values

    Returns
    -------
    str
        Formatted error message
    """
    msg = f"Invalid {param_name}: '{provided_value}'. Expected: {expected_format}"

    if examples:
        msg += f". Examples: {', '.join(examples)}"

    return msg


def validate_language(language: str) -> tuple[bool, str | None]:
    """Validate programming language.

    Parameters
    ----------
    language : str
        Language to validate

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    from ..utils import get_supported_languages

    supported_languages = get_supported_languages()

    if language.lower() not in supported_languages:
        logger.warning(
            "Unsupported language requested",
            extra={"language": language, "supported": supported_languages},
        )
        return False, (
            f"Unsupported language '{language}'. "
            f"Supported: {', '.join(supported_languages)}"
        )

    logger.debug("Language validated %s", extra={"language": language})
    return True, None


def validate_required_param(value: Any, param_name: str) -> tuple[bool, str | None]:
    """Validate that a required parameter is present.

    Parameters
    ----------
    value : any
        Parameter value to check
    param_name : str
        Name of the parameter

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        logger.debug(
            "Required parameter missing or empty",
            extra={"param_name": param_name, "value_type": type(value).__name__},
        )
        return False, f"Required parameter '{param_name}' is missing or empty"
    logger.debug("Required parameter present %s", extra={"param_name": param_name})
    return True, None


def validate_session_active(session: Any) -> tuple[bool, str | None]:
    """Validate that a session is active.

    Parameters
    ----------
    session : any
        Session object to check

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    if not session:
        logger.debug("Session validation failed: no session")
        return False, "No active debug session"

    if hasattr(session, "started") and not session.started:
        logger.debug(
            "Session validation failed: not started",
            extra={"session_id": getattr(session, "session_id", "unknown")},
        )
        return False, "Debug session is not started"

    if hasattr(session, "terminated") and session.terminated:
        logger.debug(
            "Session validation failed: terminated",
            extra={"session_id": getattr(session, "session_id", "unknown")},
        )
        return False, "Debug session has terminated"

    logger.debug(
        "Session validated as active",
        extra={"session_id": getattr(session, "session_id", "unknown")},
    )
    return True, None


def early_validate_handler_args(
    handler_name: str,
    args: dict[str, Any],
) -> dict[str, Any] | None:
    """Perform early validation for handler arguments.

    This function performs validation at the entry point of handlers
    to catch issues early and provide better error messages.

    Parameters
    ----------
    handler_name : str
        Name of the handler (for specific validation rules)
    args : dict
        Arguments to validate

    Returns
    -------
    dict or None
        Error response if validation fails, None if valid
    """
    from ..responses.errors import InvalidParameterError, MissingParameterError

    logger.debug(
        "Early validation starting",
        extra={"handler": handler_name, "args_count": len(args)},
    )

    # Handler-specific validation rules
    validation_rules = {
        "aidb_debug": ["target"],
        "aidb_inspect": [ParamName.EXPRESSION],
        "aidb_breakpoint": ["location"],
        "aidb_step": [],  # Action is optional
        "aidb_variable": [ParamName.ACTION],
        "aidb_run_until": ["location"],
        "aidb_session": [],  # Action is optional
        "aidb_config": [],  # Action is optional
    }

    # Check required parameters
    if handler_name in validation_rules:
        required = validation_rules[handler_name]
        is_valid, error_msg = validate_required_params(args, required)
        if not is_valid:
            logger.info(
                "Early validation failed: missing parameters",
                extra={"handler": handler_name, "error": error_msg},
            )
            return MissingParameterError(
                param_name=", ".join(required),
                param_description=error_msg,
            ).to_mcp_response()

    # Validate specific parameter formats
    if ParamName.SESSION_ID in args:
        is_valid, error_msg = validate_session_id(args[ParamName.SESSION_ID])
        if not is_valid:
            logger.info(
                "Early validation failed: invalid session_id",
                extra={"handler": handler_name, "error": error_msg},
            )
            return InvalidParameterError(
                parameter_name=ParamName.SESSION_ID,
                expected_type="alphanumeric with hyphens/underscores",
                received_value=args[ParamName.SESSION_ID],
                error_message=error_msg or "Invalid session_id format",
            ).to_mcp_response()

    if ParamName.FRAME in args or ParamName.FRAME_ID in args:
        frame_id = args.get(ParamName.FRAME, args.get(ParamName.FRAME_ID))
        is_valid, error_msg, parsed = validate_frame_id(frame_id)
        if not is_valid:
            logger.info(
                "Early validation failed: invalid frame_id",
                extra={"handler": handler_name, "error": error_msg},
            )
            return InvalidParameterError(
                parameter_name="frame_id",
                expected_type="non-negative integer",
                received_value=str(frame_id),
                error_message=error_msg or "Invalid frame_id format",
            ).to_mcp_response()

    logger.debug(
        "Early validation passed",
        extra={"handler": handler_name, "validated_params": list(args.keys())},
    )
    return None  # Validation passed
