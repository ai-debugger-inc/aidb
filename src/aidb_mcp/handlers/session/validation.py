"""Session validation and parameter preparation.

This module handles validation of session parameters, mode detection, language
detection, and breakpoint parsing.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from aidb_common.path import normalize_path
from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import LaunchMode, ParamName
from ...core.decorators import with_thread_safety
from ...core.exceptions import ErrorCode
from ...responses.errors import ErrorResponse
from ...session import get_or_create_session
from ...session.manager_state import get_init_language
from ...utils import get_adapter_for_validation, get_language_from_file

if TYPE_CHECKING:
    from ...core.types import BreakpointSpec

logger = get_logger(__name__)


def _validate_and_detect_mode(
    args: dict[str, Any],
) -> tuple[LaunchMode, str | None, int | None, str | None, int | None]:
    """Validate parameters and detect launch mode.

    Returns
    -------
    tuple
        (mode, target, pid, host, port)
    """
    target = args.get(ParamName.TARGET)
    pid = args.get(ParamName.PID)
    host = args.get(ParamName.HOST)
    port = args.get(ParamName.PORT)
    launch_config_name = args.get(ParamName.LAUNCH_CONFIG_NAME)
    module = args.get(ParamName.MODULE)

    if target:
        mode = LaunchMode.LAUNCH
        # Skip path normalization for module mode - target is a module name
        if not module:
            # Use centralized TargetClassifier to detect file vs identifier
            # Identifiers (module names, class names) pass through unchanged
            from aidb.adapters.base.target_classifier import TargetClassifier

            if TargetClassifier.is_file_path(target):
                target = normalize_path(target, strict=True, return_path=False)
            # else: pass target through as-is (module/class identifier)
        return mode, target, None, None, None
    if pid:
        return LaunchMode.ATTACH, None, pid, None, None
    if host and port:
        return LaunchMode.REMOTE_ATTACH, None, None, host, port

    # If launch_config_name is provided, the adapter will handle everything
    # We just need to indicate LAUNCH mode and pass through
    if launch_config_name:
        # The adapter layer will resolve the launch config and determine target
        # We don't need to do anything here except indicate launch mode
        return LaunchMode.LAUNCH, None, None, None, None

    # This will be handled by the caller to return the appropriate error
    msg = (
        "Must provide either 'target' (launch) or 'pid' (attach) or "
        "'host'+'port' (remote) or 'launch_config_name' (VS Code config)"
    )
    raise ValueError(msg)


def _parse_breakpoints(breakpoints: list[Any]) -> list[BreakpointSpec]:
    """Parse and validate breakpoint specifications.

    Parameters
    ----------
    breakpoints : list
        Raw breakpoint data from arguments

    Returns
    -------
    list[BreakpointSpec]
        Validated breakpoint specifications

    Raises
    ------
    ValueError
        If breakpoint format is invalid
    """
    breakpoints_parsed: list[BreakpointSpec] = []

    for bp in breakpoints:
        if isinstance(bp, dict):
            # Validate it has required fields
            if "file" not in bp or "line" not in bp:
                missing_fields = []
                if "file" not in bp:
                    missing_fields.append("file")
                if "line" not in bp:
                    missing_fields.append("line")
                fields_str = ", ".join(missing_fields)
                msg = (
                    f"Breakpoint format error: Missing field(s): {fields_str}. "
                    f"Breakpoint must include 'file' and 'line' fields. Got: {bp}"
                )
                raise ValueError(
                    msg,
                )

            # Build BreakpointSpec
            bp_spec: BreakpointSpec = {
                "file": bp["file"],
                "line": bp["line"],
            }

            # Add optional fields
            if "column" in bp:
                bp_spec["column"] = bp["column"]
            if "condition" in bp:
                bp_spec["condition"] = bp["condition"]
            if "hit_condition" in bp:
                bp_spec["hit_condition"] = bp["hit_condition"]
            if "log_message" in bp:
                bp_spec["log_message"] = bp["log_message"]

            breakpoints_parsed.append(bp_spec)
        else:
            msg = (
                "Breakpoint format error: Breakpoints must be dicts with "
                f"'file' and 'line' fields. Got: {type(bp).__name__} with value: {bp}"
            )
            raise ValueError(
                msg,
            )

    return breakpoints_parsed


def _determine_language(args: dict[str, Any], target: str | None) -> str | None:
    """Determine the programming language for the session.

    Parameters
    ----------
    args : dict
        Session arguments
    target : str, optional
        Target file path

    Returns
    -------
    str, optional
        Detected or specified language
    """
    language = args.get(ParamName.LANGUAGE)

    # Use language from init context if not provided
    init_language = get_init_language()
    if not language and init_language:
        language = init_language

    # Auto-detect language from target if still not provided
    if not language and target:
        detected = get_language_from_file(target)
        if detected:
            language = detected

    return language


@with_thread_safety(require_session=False)
async def _validate_and_prepare_session(
    args: dict[str, Any],
) -> tuple[str, Any, LaunchMode, str | None, list]:
    """Validate parameters and prepare session.

    Returns session components and parsed data.
    """
    # Determine mode and validate parameters
    try:
        mode, target, pid, host, port = _validate_and_detect_mode(args)
    except ValueError as e:
        msg = (
            "Must provide either 'target' (launch) or 'pid' (attach) or "
            "'host'+'port' (remote)"
        )
        raise ValueError(
            msg,
        ) from e

    # Create session
    session_id = args.get(ParamName.SESSION_ID, str(uuid.uuid4()))
    language = _determine_language(args, target)

    # Get or create session context
    session_id, session_context = get_or_create_session(session_id)

    # Parse breakpoints
    breakpoints = args.get(ParamName.BREAKPOINTS, [])
    breakpoints_parsed = _parse_breakpoints(breakpoints)

    return (
        session_id,
        session_context,
        mode,
        language,
        breakpoints_parsed,
    )


async def _validate_target_syntax(
    mode: LaunchMode,
    target: str | None,
    language: str | None,
    args: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate target file syntax for launch mode.

    Skips validation for module mode (e.g., python -m pytest) where target is a module
    name, not a file path.

    Returns error response or None.
    """
    # Skip syntax validation for module mode - target is a module name, not a file
    if args.get(ParamName.MODULE):
        return None

    if mode == LaunchMode.LAUNCH and target and language:
        adapter = get_adapter_for_validation(language)
        if adapter:
            is_valid, error_msg = adapter.validate_syntax(target)
            if not is_valid:
                return ErrorResponse(
                    error_message=(
                        f"{error_msg}. "
                        "Debug session cannot start with syntax errors. "
                        "Please fix the syntax errors and try again."
                    ),
                    error_code=ErrorCode.AIDB_VALIDATION_INVALID_TARGET.value,
                    context=None,
                ).to_mcp_response()
    return None
