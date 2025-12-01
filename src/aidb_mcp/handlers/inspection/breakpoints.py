"""Breakpoint management handlers.

Handles the breakpoint tool for setting, removing, and listing breakpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aidb.models.entities.breakpoint import HitConditionMode
from aidb_logging import get_mcp_logger as get_logger

from ...core import BreakpointAction, ToolName
from ...core.constants import BreakpointState, ParamName
from ...core.decorators import mcp_tool
from ...core.serialization import to_jsonable
from ...responses import BreakpointListResponse, BreakpointMutationResponse
from ...responses.errors import InternalError, UnsupportedOperationError
from ...responses.helpers import (
    internal_error,
    invalid_action,
    invalid_parameter,
    missing_parameter,
)
from ...tools.actions import normalize_action
from ...utils import get_supported_hit_conditions, supports_hit_condition

if TYPE_CHECKING:
    from ...core.types import BreakpointSpec

logger = get_logger(__name__)


async def _handle_set_breakpoint(api, context, args: dict[str, Any]) -> dict[str, Any]:
    """Handle SET breakpoint action."""
    location = args.get(ParamName.LOCATION)
    if not location:
        logger.debug(
            "Missing location for breakpoint set",
            extra={"action": BreakpointAction.SET.name},
        )
        return missing_parameter(
            param_name=ParamName.LOCATION,
            param_description=("Provide 'location' parameter (file:line format)"),
        )

    logger.debug(
        "Setting breakpoint",
        extra={
            "action": BreakpointAction.SET.name,
            "location": location,
            "has_condition": bool(args.get(ParamName.CONDITION)),
            "has_hit_condition": bool(args.get(ParamName.HIT_CONDITION)),
        },
    )

    # Validate hit condition if provided
    hit_condition = args.get(ParamName.HIT_CONDITION)
    if hit_condition:
        validation_result = _validate_hit_condition(api, hit_condition)
        if validation_result:
            return validation_result

    # Parse and validate location
    parsed = _parse_breakpoint_location(location)
    if isinstance(parsed, dict) and parsed.get("error"):
        return parsed

    # At this point, parsed is guaranteed to be tuple[str, int]
    if not isinstance(parsed, tuple):
        return invalid_parameter(
            param_name=ParamName.LOCATION,
            expected_type="tuple[str, int]",
            received_value=str(type(parsed)),
            error_message="Location parsing failed unexpectedly",
        )
    file_path, line = parsed

    # Build BreakpointSpec with all parameters
    bp_spec: BreakpointSpec = {
        "file": file_path,
        "line": line,
    }
    condition = args.get(ParamName.CONDITION)
    if condition:
        bp_spec["condition"] = condition
    if hit_condition:
        bp_spec["hit_condition"] = hit_condition
    log_message = args.get(ParamName.LOG_MESSAGE)
    if log_message:
        bp_spec["log_message"] = log_message

    response = await api.orchestration.breakpoint(bp_spec)

    # Extract verification status from the response
    # Response contains a dict of breakpoints, get the first one
    verified = True  # Default to True if we can't determine
    if response.breakpoints:
        # Get the first breakpoint from the response
        bp = next(iter(response.breakpoints.values()))
        verified = bp.verified if bp.verified is not None else True

    # Update session context for regular breakpoint
    _update_context_breakpoints(context, location, args)

    return BreakpointMutationResponse(
        action="set",
        location=location,
        affected_count=1,
        condition=args.get(ParamName.CONDITION),
        hit_condition=args.get(ParamName.HIT_CONDITION),
        log_message=args.get(ParamName.LOG_MESSAGE),
        verified=verified,
    ).to_mcp_response()


async def _handle_remove_breakpoint(
    api,
    context,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle REMOVE breakpoint action."""
    location = args.get(ParamName.LOCATION)
    if not location:
        return missing_parameter(
            param_name=ParamName.LOCATION,
            param_description=("Provide 'location' parameter (file:line format)"),
        )

    # Parse location to get file and line
    parsed = _parse_breakpoint_location(location)
    if isinstance(parsed, dict) and parsed.get("error"):
        return parsed

    file_path, line_to_remove = parsed

    # Use the new remove_breakpoint method from the session layer
    if file_path and line_to_remove and api:
        try:
            await api.orchestration.remove_breakpoint(file_path, line_to_remove)
            removed_count = 1

            # Update session context if available
            if context and hasattr(context, "breakpoints_set"):
                # Remove from context
                context.breakpoints_set = [
                    bp
                    for bp in context.breakpoints_set
                    if bp.get("location") != location
                ]

            return BreakpointMutationResponse(
                action="remove",
                location=location,
                affected_count=removed_count,
            ).to_mcp_response()

        except Exception as e:
            logger.error("Failed to remove breakpoint: %s", e)
            return internal_error(
                operation="remove_breakpoint",
                exception=e,
                summary="Failed to remove breakpoint",
            )
    else:
        # Could not parse location properly
        return BreakpointMutationResponse(
            action="remove",
            location=location,
            affected_count=0,
        ).to_mcp_response()


async def _handle_list_breakpoints(
    api,
    context,
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Handle LIST breakpoint action.

    Delegates to the public API method which handles:
    - Waiting for breakpoint verification (prevents race conditions)
    - Child session resolution (JavaScript)
    - Proper breakpoint state retrieval
    """
    breakpoints = []

    # Delegate to public API method
    # Breakpoints are automatically synchronized via event handlers
    if api:
        response = await api.orchestration.list_breakpoints()

        # Convert AidbBreakpointsResponse to MCP format
        if response.breakpoints:
            # Iterate over the breakpoint dict
            # Note: current_breakpoints property returns a thread-safe copy
            for bp_id, bp in response.breakpoints.items():
                bp_info = {
                    "id": bp_id,
                    "file": bp.source_path,
                    "line": bp.line,
                    "location": f"{bp.source_path}:{bp.line}",
                    "verified": bp.verified,
                }
                if hasattr(bp, "condition") and bp.condition:
                    bp_info["condition"] = bp.condition
                if hasattr(bp, "hit_condition") and bp.hit_condition:
                    bp_info["hit_condition"] = bp.hit_condition
                if hasattr(bp, "log_message") and bp.log_message:
                    bp_info["log_message"] = bp.log_message
                breakpoints.append(bp_info)

    # Fallback if no API available (shouldn't happen in normal operation)
    elif context and hasattr(context, "breakpoints_set"):
        for bp in context.breakpoints_set:
            if "id" not in bp or bp["id"] in (None, ""):
                loc = bp.get("location") or (f"{bp.get('file')}:{bp.get('line')}")
                bp = {**bp, "id": loc}
            breakpoints.append(bp)

    return BreakpointListResponse(
        breakpoints=to_jsonable(breakpoints),
    ).to_mcp_response()


async def _handle_clear_all_breakpoints(
    api,
    context,
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Handle CLEAR_ALL breakpoint action."""
    cleared_count = 0

    # Count breakpoints before clearing
    if api and hasattr(api.session, "_breakpoint_store"):
        cleared_count = len(api.session._breakpoint_store)

    # Clear all breakpoints via the API
    if api:
        try:
            await api.orchestration.clear_breakpoints(clear_all=True)
        except Exception as e:
            logger.error("Failed to clear all breakpoints: %s", e)
            return internal_error(
                operation="clear_breakpoints",
                exception=e,
                summary="Failed to clear breakpoints",
            )

    # Also clear from context
    if context and hasattr(context, "breakpoints_set"):
        context.breakpoints_set.clear()

    return BreakpointMutationResponse(
        action="clear_all",
        location=None,
        affected_count=cleared_count,
    ).to_mcp_response()


def _validate_hit_condition(api, hit_condition: str) -> dict[str, Any] | None:
    """Validate hit condition for the current language.

    Returns error response or None.
    """
    # Get the language from session
    language = getattr(api.session, "language", "python") if api.session else "python"

    if not supports_hit_condition(language, hit_condition):
        try:
            mode, _ = HitConditionMode.parse(hit_condition)
            supported = get_supported_hit_conditions(language)
            logger.info(
                "Unsupported hit condition",
                extra={
                    "language": language,
                    "hit_condition": hit_condition,
                    "supported": supported,
                },
            )
            return UnsupportedOperationError(
                operation=f"Hit condition '{hit_condition}'",
                adapter_type=f"{language} adapter",
                language=language,
                error_message=(
                    f"The {language} adapter doesn't support "
                    f"{mode.name} hit conditions. "
                    f"Supported: {', '.join(supported)}"
                ),
            ).to_mcp_response()
        except ValueError as e:
            return invalid_parameter(
                param_name="hit_condition",
                expected_type="valid hit condition format",
                received_value=hit_condition,
                error_message=str(e),
            )
    return None


def _parse_breakpoint_location(location: str) -> tuple[str, int] | dict[str, Any]:
    """Parse breakpoint location.

    Returns (file_path, line) or error dict.
    """
    if ":" not in str(location):
        return invalid_parameter(
            param_name=ParamName.LOCATION,
            expected_type="file:line or file:line:column format",
            received_value=location,
            error_message="Breakpoint location must include line number "
            "(e.g., 'file.py:10')",
        )

    file_path, line_str = location.rsplit(":", 1)
    try:
        line = int(line_str)
        return file_path, line
    except ValueError:
        return invalid_parameter(
            param_name=ParamName.LOCATION,
            expected_type="file:line format with valid line number",
            received_value=location,
            error_message=f"Invalid line number in: {location}",
        )


def _update_context_breakpoints(context, location: str, args: dict[str, Any]) -> None:
    """Update context with breakpoint information."""
    if context and hasattr(context, "breakpoints_set"):
        # Parse location for file, line, column
        file_path_parsed = None
        line_parsed = None
        column_parsed = None

        parts = location.split(":")
        file_path_parsed = parts[0]
        if len(parts) >= 2 and parts[1].isdigit():
            line_parsed = int(parts[1])
        if len(parts) >= 3 and parts[2].isdigit():
            column_parsed = int(parts[2])

        bp_info = {
            "location": location,
            "file": file_path_parsed,
            "line": line_parsed,
            "column": column_parsed or args.get(ParamName.COLUMN),
            "condition": args.get(ParamName.CONDITION),
            "hit_condition": args.get(ParamName.HIT_CONDITION),
            "log_message": args.get(ParamName.LOG_MESSAGE),
            "verified": True,  # Assumed verified since API call succeeded
            "state": BreakpointState.VERIFIED.value,
        }
        # Remove None values for cleaner storage
        bp_info = {k: v for k, v in bp_info.items() if v is not None}

        # Check if breakpoint already exists
        if not any(bp.get("location") == location for bp in context.breakpoints_set):
            context.breakpoints_set.append(bp_info)


@mcp_tool(require_session=True, include_after=True)
async def handle_breakpoint(args: dict[str, Any]) -> dict[str, Any]:
    """Handle the unified breakpoint tool for managing breakpoints."""
    try:
        raw_action = args.get(ParamName.ACTION, BreakpointAction.SET.value)
        action = normalize_action(raw_action, "breakpoint")

        # Convert to enum
        try:
            action_enum = BreakpointAction(action)
        except ValueError:
            action_enum = None

        logger.info(
            "Breakpoint handler invoked",
            extra={
                "action": raw_action,
                "normalized_action": action,
                "tool": ToolName.BREAKPOINT,
            },
        )

        # Validate action
        if not action_enum:
            logger.warning(
                "Invalid breakpoint action",
                extra={
                    "action": raw_action,
                    "valid_actions": [a.name for a in BreakpointAction],
                },
            )
            return invalid_action(
                action=raw_action,
                valid_actions=[a.value for a in BreakpointAction],
                tool_name=ToolName.BREAKPOINT,
            )

        # Get session components from decorator
        api = args.get("_api")
        context = args.get("_context")

        # The decorator guarantees these are present
        if not api:
            return InternalError(
                error_message="Debug API not available",
            ).to_mcp_response()

        # Dispatch to action handlers
        action_handlers = {
            BreakpointAction.SET: _handle_set_breakpoint,
            BreakpointAction.REMOVE: _handle_remove_breakpoint,
            BreakpointAction.LIST: _handle_list_breakpoints,
            BreakpointAction.CLEAR_ALL: _handle_clear_all_breakpoints,
        }

        handler = action_handlers.get(action_enum)
        if handler:
            return await handler(api, context, args)
        return invalid_action(
            action=action,
            valid_actions=[a.value for a in BreakpointAction],
            tool_name=ToolName.BREAKPOINT,
        )

    except Exception as e:
        logger.exception("Breakpoint operation failed: %s", e)
        return internal_error(operation="breakpoint", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.BREAKPOINT: handle_breakpoint,
}
