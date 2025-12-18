"""Breakpoint management handlers.

Handles the breakpoint tool for setting, removing, and listing breakpoints.
"""

from __future__ import annotations

from typing import Any

from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from ...core import BreakpointAction, ToolName
from ...core.constants import BreakpointState, ParamName
from ...core.decorators import mcp_tool
from ...core.serialization import to_jsonable
from ...responses import BreakpointListResponse, BreakpointMutationResponse
from ...responses.errors import InternalError, UnsupportedOperationError
from ...responses.helpers import (
    internal_error,
    invalid_parameter,
    is_session_paused,
    missing_parameter,
)

logger = get_logger(__name__)


async def _handle_set_breakpoint(
    service,
    context,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle SET breakpoint action."""
    from aidb.dap.protocol.bodies import SetBreakpointsArguments
    from aidb.dap.protocol.requests import SetBreakpointsRequest
    from aidb.dap.protocol.types import Source, SourceBreakpoint

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

    # Validate hit condition if provided (Phase 2: using service)
    hit_condition = args.get(ParamName.HIT_CONDITION)
    if hit_condition:
        is_valid, error_msg = service.breakpoints.validate_hit_condition(hit_condition)
        if not is_valid:
            return invalid_parameter(
                param_name="hit_condition",
                expected_type="valid hit condition format",
                received_value=hit_condition,
                error_message=error_msg or "Invalid hit condition",
            )

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

    # Build DAP request (Phase 2: using service with DAP request)
    condition = args.get(ParamName.CONDITION)
    log_message = args.get(ParamName.LOG_MESSAGE)

    source_bp = SourceBreakpoint(line=line)
    if condition:
        source_bp.condition = condition
    if hit_condition:
        source_bp.hitCondition = hit_condition
    if log_message:
        source_bp.logMessage = log_message

    source = Source(path=file_path)
    bp_args = SetBreakpointsArguments(source=source, breakpoints=[source_bp])
    request = SetBreakpointsRequest(seq=0, arguments=bp_args)

    response = await service.breakpoints.set(request)

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
    service,
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

    # Use service to remove breakpoint (Phase 2)
    if file_path and line_to_remove and service:
        try:
            await service.breakpoints.remove(file_path, line_to_remove)
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
    service,
    context,
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Handle LIST breakpoint action.

    Delegates to the service method which handles:
    - Breakpoint state retrieval from session store
    - Proper breakpoint state retrieval

    Note: This handler works on terminated sessions because:
    1. The @mcp_tool decorator allows 'list' action on terminated sessions
    2. The service's list_all() accesses preserved breakpoint state
    """
    breakpoints = []

    # Get breakpoints from service (Phase 2)
    # Works even on terminated sessions since we preserve breakpoint state
    if service:
        response = await service.breakpoints.list_all()

        # Convert AidbBreakpointsResponse to MCP format
        if response.breakpoints:
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

    # Fallback if no service available (shouldn't happen in normal operation)
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
    service,
    context,
    _args: dict[str, Any],
) -> dict[str, Any]:
    """Handle CLEAR_ALL breakpoint action."""
    cleared_count = 0

    # Count breakpoints before clearing (use service.session)
    if service and service.session:
        cleared_count = service.session.breakpoint_count

    # Clear all breakpoints via the service (Phase 2)
    if service:
        try:
            await service.breakpoints.clear(clear_all=True)
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


async def _handle_watch_breakpoint(
    service,
    _context,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle WATCH breakpoint action (data breakpoint / watchpoint).

    Watchpoints break when a variable is read or written. Only supported for Java
    debugging.
    """
    from aidb.dap.protocol.bodies import SetDataBreakpointsArguments
    from aidb.dap.protocol.requests import SetDataBreakpointsRequest
    from aidb.dap.protocol.types import DataBreakpoint

    # Validate language is Java (Phase 2: using service.session)
    language = getattr(service.session, "language", None) if service.session else None
    if language != Language.JAVA.value:
        return UnsupportedOperationError(
            operation="Watchpoints",
            adapter_type=f"{language or 'unknown'} adapter",
            language=language or "unknown",
            error_message=(
                "Watchpoints (data breakpoints) are only supported for Java. "
                "Python and JavaScript runtimes do not support hardware watchpoints."
            ),
        ).to_mcp_response()

    # Validate we're paused - use shared utility for defensive checking
    session = service.session if service else None
    if session and not is_session_paused(session):
        return UnsupportedOperationError(
            operation="Set watchpoint",
            adapter_type="Java adapter",
            language=Language.JAVA.value,
            error_message=(
                "Must be paused at a breakpoint to set a watchpoint. "
                "Set a regular breakpoint first and pause execution."
            ),
        ).to_mcp_response()

    # Get required parameters
    var_name = args.get(ParamName.NAME)
    if not var_name:
        return missing_parameter(
            param_name=ParamName.NAME,
            param_description="Provide 'name' parameter with variable name",
            example_value="user.email",
        )

    access_type = args.get(ParamName.ACCESS_TYPE, "write")
    condition = args.get(ParamName.CONDITION)
    hit_condition = args.get(ParamName.HIT_CONDITION)

    logger.info(
        "Setting watchpoint",
        extra={
            "variable_name": var_name,
            "access_type": access_type,
            "has_condition": bool(condition),
            "has_hit_condition": bool(hit_condition),
        },
    )

    try:
        # Step 1: Resolve variable to get variablesReference (Phase 2)
        var_ref, error_msg = await service.variables.resolve_variable(var_name)
        if error_msg:
            return invalid_parameter(
                param_name=ParamName.NAME,
                expected_type="variable name in current scope",
                received_value=var_name,
                error_message=error_msg,
            )

        # Step 2: Get data breakpoint info (Phase 2)
        var_parts = var_name.split(".")
        data_bp_info = await service.breakpoints.get_data_info(
            variable_reference=var_ref,
            name=var_parts[-1],
        )

        if not data_bp_info.data_id:
            return UnsupportedOperationError(
                operation=f"Watch '{var_name}'",
                adapter_type="Java adapter",
                language=Language.JAVA.value,
                error_message=(
                    f"Cannot set watchpoint on '{var_name}'. "
                    "The variable may not support data breakpoints."
                ),
            ).to_mcp_response()

        # Step 3: Set the data breakpoint using DAP request (Phase 2)
        data_bp = DataBreakpoint(
            dataId=data_bp_info.data_id,
            accessType=access_type,
            condition=condition,
            hitCondition=hit_condition,
        )
        bp_args = SetDataBreakpointsArguments(breakpoints=[data_bp])
        request = SetDataBreakpointsRequest(seq=0, arguments=bp_args)
        response = await service.breakpoints.set_data(request)

        return BreakpointMutationResponse(
            action="watch",
            location=var_name,
            affected_count=1 if response.success else 0,
            condition=condition,
            hit_condition=hit_condition,
            verified=response.success,
        ).to_mcp_response()

    except Exception as e:
        logger.exception("Failed to set watchpoint: %s", e)
        return internal_error(
            operation="watch",
            exception=e,
            summary=f"Failed to set watchpoint on '{var_name}'",
        )


async def _handle_unwatch_breakpoint(
    service,
    _context,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Handle UNWATCH breakpoint action (remove data breakpoint).

    Removes a previously set watchpoint.
    """
    # Validate language is Java (Phase 2: using service.session)
    language = getattr(service.session, "language", None) if service.session else None
    if language != Language.JAVA.value:
        return UnsupportedOperationError(
            operation="Watchpoints",
            adapter_type=f"{language or 'unknown'} adapter",
            language=language or "unknown",
            error_message="Watchpoints are only supported for Java debugging.",
        ).to_mcp_response()

    var_name = args.get(ParamName.NAME)
    if not var_name:
        return missing_parameter(
            param_name=ParamName.NAME,
            param_description="Provide 'name' parameter with watchpoint name to remove",
        )

    logger.info("Removing watchpoint", extra={"variable_name": var_name})

    try:
        # Clear all data breakpoints using the service (Phase 2)
        # DAP's setDataBreakpoints replaces all data breakpoints
        # For per-watchpoint removal, we'd need to track and re-send without this one
        await service.breakpoints.clear_data()

        return BreakpointMutationResponse(
            action="unwatch",
            location=var_name,
            affected_count=1,
        ).to_mcp_response()

    except Exception as e:
        logger.exception("Failed to remove watchpoint: %s", e)
        return internal_error(
            operation="unwatch",
            exception=e,
            summary=f"Failed to remove watchpoint '{var_name}'",
        )


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


@mcp_tool(require_session=True, include_after=True, allow_on_terminated=["list"])
async def handle_breakpoint(args: dict[str, Any]) -> dict[str, Any]:
    """Handle the unified breakpoint tool for managing breakpoints."""
    from ..dispatch import dispatch_action

    raw_action = args.get(ParamName.ACTION, BreakpointAction.SET.value)
    logger.info(
        "Breakpoint handler invoked",
        extra={
            "action": raw_action,
            "tool": ToolName.BREAKPOINT,
        },
    )

    # Get session components from decorator
    service = args.get("_service")
    context = args.get("_context")

    # The decorator guarantees these are present
    if not service:
        return InternalError(
            error_message="DebugService not available",
        ).to_mcp_response()

    action_handlers = {
        BreakpointAction.SET: _handle_set_breakpoint,
        BreakpointAction.REMOVE: _handle_remove_breakpoint,
        BreakpointAction.LIST: _handle_list_breakpoints,
        BreakpointAction.CLEAR_ALL: _handle_clear_all_breakpoints,
        BreakpointAction.WATCH: _handle_watch_breakpoint,
        BreakpointAction.UNWATCH: _handle_unwatch_breakpoint,
    }

    handler, error, handler_args = dispatch_action(
        args,
        BreakpointAction,
        action_handlers,
        default_action=BreakpointAction.SET,
        tool_name=ToolName.BREAKPOINT,
        handler_args=(service, context),
        normalize=True,
    )

    if error or handler is None:
        return error or internal_error(
            operation="breakpoint",
            exception="No handler found",
        )

    try:
        return await handler(*handler_args)
    except Exception as e:
        logger.exception("Breakpoint operation failed: %s", e)
        return internal_error(operation="breakpoint", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.BREAKPOINT: handle_breakpoint,
}
