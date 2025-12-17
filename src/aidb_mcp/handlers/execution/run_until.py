"""Run until handlers.

Handles the run_until tool for running to specific locations with temporary breakpoints.
"""

from __future__ import annotations

from typing import Any

from aidb.dap.protocol.bodies import (
    ContinueArguments,
    SetBreakpointsArguments,
)
from aidb.dap.protocol.requests import (
    ContinueRequest,
    SetBreakpointsRequest,
)
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb_logging import get_mcp_logger as get_logger

from ...core import ToolName
from ...core.constants import ParamName, StopReason
from ...core.decorators import mcp_tool
from ...responses import RunUntilResponse
from ...responses.errors import InternalError
from ...responses.helpers import handle_timeout_error, invalid_parameter
from ...session import get_service, get_session

logger = get_logger(__name__)


async def _parse_location_with_file(
    location: str,
) -> tuple[str | None, int | None, dict[str, Any] | None]:
    """Parse location with ``file:line`` format.

    Parameters
    ----------
    location : str
        Location string in ``file:line`` format

    Returns
    -------
    tuple[str | None, int | None, dict[str, Any] | None]
        File path, line number, and error response (if any)

    """
    parts = str(location).rsplit(":", 1)
    file_path = parts[0]
    try:
        line = int(parts[1])
        return file_path, line, None
    except ValueError:
        return (
            None,
            None,
            invalid_parameter(
                param_name=ParamName.LOCATION,
                expected_type="file.py:line format with valid line number",
                received_value=parts[1],
                error_message=(
                    f"Invalid line number: {parts[1]}. Use format 'file.py:42'"
                ),
            ),
        )


async def _parse_location_line_only(
    location: str,
    service: Any,
) -> tuple[str | None, int | None, dict[str, Any] | None]:
    """Parse location with just line number.

    Parameters
    ----------
    location : str
        Location string with just line number
    service : Any
        Debug service instance

    Returns
    -------
    tuple[str | None, int | None, dict[str, Any] | None]
        File path, line number, and error response (if any)
    """
    try:
        line = int(location)
        # Get current file from stack frame
        thread_id = await service.stack.get_current_thread_id()
        stack = await service.stack.callstack(thread_id=thread_id)
        if stack and stack.frames and len(stack.frames) > 0:
            current_frame = stack.frames[0]
            if current_frame.source:
                return current_frame.source.path, line, None

        return (
            None,
            None,
            invalid_parameter(
                param_name=ParamName.LOCATION,
                expected_type="file.py:line or just line number when paused",
                received_value=location,
                error_message=(
                    "Cannot determine current file. Debugger must be "
                    "paused to use line-only format."
                ),
            ),
        )

    except ValueError:
        return (
            None,
            None,
            invalid_parameter(
                param_name=ParamName.LOCATION,
                expected_type="file.py:line or line number",
                received_value=str(location),
                error_message=f"Invalid location format: {location}",
            ),
        )


async def _parse_location(
    location: str,
    service: Any,
) -> tuple[str | None, int | None, dict[str, Any] | None]:
    """Parse location parameter.

    Parameters
    ----------
    location : str
        Location parameter
    service : Any
        Debug service instance

    Returns
    -------
    tuple[str | None, int | None, dict[str, Any] | None]
        File path, line number, and error response (if any)
    """
    if location and ":" in str(location):
        # Format: file.py:line
        return await _parse_location_with_file(location)
    if location:
        # Just a line number - need current file
        return await _parse_location_line_only(location, service)
    return (
        None,
        None,
        invalid_parameter(
            param_name=ParamName.LOCATION,
            expected_type="file.py:line or line number",
            received_value="None",
            error_message="Location is required",
        ),
    )


async def _check_paused_at_target(
    continue_result: Any,
    service: Any,
    file_path: str,
    line: int,
) -> bool:
    """Check if we paused at the target location.

    Parameters
    ----------
    continue_result : Any
        Result from continue operation
    service : Any
        Debug service instance
    file_path : str
        Target file path
    line : int
        Target line number

    Returns
    -------
    bool
        True if paused at target location
    """
    if not hasattr(continue_result, "execution_state"):
        return False

    exec_state = continue_result.execution_state
    if not exec_state.paused:
        return False

    # Check if we're at target location
    try:
        thread_id = await service.stack.get_current_thread_id()
        stack = await service.stack.callstack(thread_id=thread_id)
        if stack and stack.frames and len(stack.frames) > 0:
            current_frame = stack.frames[0]
            if (
                current_frame.source
                and current_frame.source.path == file_path
                and current_frame.line == line
            ):
                return True
    except Exception as e:
        logger.debug("Failed to check if at target location: %s", e)

    return False


async def _execute_with_temp_breakpoint(
    service: Any,
    file_path: str,
    line: int,
    condition: str | None = None,
) -> tuple[Any, bool]:
    """Execute with temporary breakpoint and check if target was reached.

    Parameters
    ----------
    service : Any
        Debug service instance
    file_path : str
        Target file path
    line : int
        Target line number
    condition : str, optional
        Breakpoint condition

    Returns
    -------
    tuple[Any, bool]
        Continue result and whether target was reached
    """
    # Build DAP breakpoint request
    source_bp = SourceBreakpoint(line=line)
    if condition:
        source_bp.condition = condition

    source = Source(path=file_path)
    bp_args = SetBreakpointsArguments(source=source, breakpoints=[source_bp])
    bp_request = SetBreakpointsRequest(seq=0, arguments=bp_args)

    await service.breakpoints.set(bp_request)

    # Continue execution
    thread_id = await service.execution.get_current_thread_id()
    continue_request = ContinueRequest(
        seq=0,
        arguments=ContinueArguments(threadId=thread_id),
    )
    continue_result = await service.execution.continue_(
        continue_request,
        wait_for_stop=True,
    )

    # Check if we hit the temporary breakpoint
    paused_at_target = await _check_paused_at_target(
        continue_result,
        service,
        file_path,
        line,
    )

    # Remove the temporary breakpoint (best effort - set empty list for file)
    try:
        clear_args = SetBreakpointsArguments(source=source, breakpoints=[])
        clear_request = SetBreakpointsRequest(seq=0, arguments=clear_args)
        await service.breakpoints.set(clear_request)
    except Exception as e:
        logger.debug("Failed to clear temporary breakpoint: %s", e)

    return continue_result, paused_at_target


async def _build_run_until_response(
    session: Any,
    context: Any,
    session_id: str,
    file_path: str,
    line: int,
    paused_at_target: bool,
) -> RunUntilResponse:
    """Build run_until response with status and code context.

    Parameters
    ----------
    session : Any
        Session instance for status/property access
    context : Any
        Session context
    session_id : str
        Session identifier
    file_path : str
        Target file path
    line : int
        Target line number
    paused_at_target : bool
        Whether we reached the target

    Returns
    -------
    RunUntilResponse
        Formatted response
    """
    from ...core.context_utils import build_response_context

    # Determine stop reason for status
    stop_reason = None if paused_at_target else StopReason.COMPLETED
    resp_ctx = await build_response_context(
        session,
        context,
        stop_reason,
        is_paused=paused_at_target,
    )

    return RunUntilResponse(
        target_location=f"{file_path}:{line}",
        reached_target=paused_at_target,
        actual_location=f"{file_path}:{line}" if paused_at_target else None,
        stop_reason=stop_reason,
        session_id=session_id,
        code_context=resp_ctx.code_context,
        has_breakpoints=resp_ctx.has_breakpoints,
        detailed_status=resp_ctx.detailed_status,
    )


@mcp_tool(
    require_session=True,
    include_after=True,
    validate_params=["location"],
)
async def handle_run_until(args: dict[str, Any]) -> dict[str, Any]:
    """Run until a specific location using a temporary breakpoint."""
    try:
        location = args.get(ParamName.LOCATION)

        # Get session components from decorator
        session_id = args.get("_session_id")
        service = args.get("_service")
        context = args.get("_context")

        if location is None:
            return InternalError(
                error_message="Location parameter not available",
            ).to_mcp_response()

        if session_id is None:
            return InternalError(
                error_message="Session ID not available",
            ).to_mcp_response()

        # Get service from decorator or session manager
        if not service:
            service = get_service(session_id)
        if not service:
            return InternalError(
                error_message="Debug service not available",
            ).to_mcp_response()

        # Get session for response building
        session = get_session(session_id)

        # Parse location
        file_path, line, error = await _parse_location(location, service)
        if error:
            return error

        # Ensure parsing was successful
        if file_path is None or line is None:
            return InternalError(
                error_message="Failed to parse location",
            ).to_mcp_response()

        # Execute with temporary breakpoint
        _continue_result, paused_at_target = await _execute_with_temp_breakpoint(
            service,
            file_path,
            line,
            args.get(ParamName.CONDITION),
        )

        # Build and return response
        response = await _build_run_until_response(
            session,
            context,
            session_id,
            file_path,
            line,
            paused_at_target,
        )
        return response.to_mcp_response()

    except Exception as e:
        logger.error("Run until failed: %s", e)

        # Check if this is a timeout error and handle it globally
        timeout_response = handle_timeout_error(e, "run_until")
        if timeout_response:
            return timeout_response
        # Regular error handling
        return InternalError(
            operation="run_until",
            details=str(e),
            error_message=str(e),
            original_exception=e,
        ).to_mcp_response()


# Export handler functions
HANDLERS = {
    ToolName.RUN_UNTIL: handle_run_until,
}
