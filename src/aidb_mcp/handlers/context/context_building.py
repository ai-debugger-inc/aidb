"""Context building utilities for debugging state.

This module constructs context dictionaries from session state, including stack frames,
breakpoints, and execution history.
"""

from __future__ import annotations

from typing import Any

from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import BreakpointStatus
from ...core.response_limiter import ResponseLimiter
from .analysis import _analyze_execution_patterns, _calculate_success_rate

logger = get_logger(__name__)


async def _build_frame_data(
    frame: Any,
    index: int,
    service: Any,
    verbose: bool,
) -> dict[str, Any]:
    """Build frame data for a stack frame.

    Parameters
    ----------
    frame : Any
        Stack frame object
    index : int
        Frame index
    service : Any
        Debug service instance
    verbose : bool
        Whether to include verbose details

    Returns
    -------
    dict[str, Any]
        Frame data dictionary
    """
    logger.debug(
        "Building frame data for level %d: %s at %s:%d",
        index,
        frame.name,
        frame.source.path if frame.source else "unknown",
        frame.line,
        extra={
            "frame_level": index,
            "function": frame.name,
            "file": frame.source.path if frame.source else "unknown",
            "line": frame.line,
            "frame_id": frame.id,
        },
    )

    frame_data = {
        "level": index,
        "function": frame.name,
        "file": frame.source.path if frame.source else "unknown",
        "line": frame.line,
        "frame_id": frame.id,
    }

    if verbose and frame.id:
        try:
            logger.debug("Retrieving locals for frame %d", index)
            frame_locals = await service.variables.locals(frame.id) if service else None
            if frame_locals and frame_locals.variables:
                var_count = len(frame_locals.variables)

                # Convert variables to dicts first
                all_vars = [
                    {"name": var.name, "value": var.value}
                    for var in frame_locals.variables
                ]

                # Apply variable limits
                limited_vars, was_truncated = ResponseLimiter.limit_variables(all_vars)

                frame_data["locals"] = {
                    var["name"]: var["value"] for var in limited_vars
                }

                if was_truncated:
                    logger.debug(
                        "Truncated variables for frame %d from %d to %d",
                        index,
                        var_count,
                        len(limited_vars),
                    )

                logger.debug(
                    "Retrieved %d locals for frame %d (showing %d)",
                    var_count,
                    index,
                    len(limited_vars),
                )
            else:
                logger.debug("No locals found for frame %d", index)
        except Exception as e:
            logger.warning(
                "Failed to get locals for frame %s: %s",
                index,
                e,
                extra={
                    "frame_level": index,
                    "frame_id": frame.id,
                    "error": str(e),
                },
            )

    return frame_data


async def _build_paused_context(
    context: dict[str, Any],
    service: Any,
    verbose: bool,
) -> None:
    """Build context when debugger is paused.

    Parameters
    ----------
    context : dict[str, Any]
        Context dictionary to populate
    service : Any
        Debug service instance
    verbose : bool
        Whether to include verbose details
    """
    logger.debug("Building paused context with verbose=%s", verbose)

    try:
        logger.debug("Retrieving call stack")
        thread_id = await service.stack.get_current_thread_id() if service else None
        stack_response = (
            await service.stack.callstack(thread_id=thread_id)
            if service and thread_id is not None
            else None
        )
        if not stack_response or not stack_response.frames:
            logger.warning("No stack frames available in paused state")
            return

        frame_count = len(stack_response.frames)
        logger.info(
            "Retrieved call stack with %d frames",
            frame_count,
            extra={"stack_depth": frame_count, "verbose": verbose},
        )

        current_frame = stack_response.frames[0]
        location = {
            "file": (current_frame.source.path if current_frame.source else "unknown"),
            "line": current_frame.line,
            "function": current_frame.name,
            "frame_id": current_frame.id,
        }
        context["current_location"] = location

        logger.info(
            "Current location: %s() at %s:%d",
            location["function"],
            location["file"],
            location["line"],
            extra={
                "current_function": location["function"],
                "current_file": location["file"],
                "current_line": location["line"],
                "frame_id": location["frame_id"],
            },
        )

        # Apply stack frame limits
        limited_frames, was_truncated = ResponseLimiter.limit_stack_frames(
            stack_response.frames,
        )
        if was_truncated:
            logger.debug(
                "Truncated stack from %d to %d frames",
                frame_count,
                len(limited_frames),
            )

        stack_frames = []
        for i, frame in enumerate(limited_frames):
            frame_data = await _build_frame_data(frame, i, service, verbose)
            stack_frames.append(frame_data)

        context["stack_frames"] = stack_frames
        logger.debug("Built stack trace with %d frames", len(stack_frames))

        if verbose and current_frame.id:
            try:
                logger.debug("Retrieving current frame variables")
                locals_response = (
                    await service.variables.locals(current_frame.id)
                    if service
                    else None
                )
                if locals_response and locals_response.variables:
                    var_count = len(locals_response.variables)

                    # Convert variables to dicts first
                    all_vars = [
                        {"name": var.name, "value": var.value}
                        for var in locals_response.variables
                    ]

                    # Apply variable limits
                    limited_vars, var_truncated = ResponseLimiter.limit_variables(
                        all_vars,
                    )

                    context["variables"] = {
                        "locals": {var["name"]: var["value"] for var in limited_vars},
                        "globals": {},
                    }

                    if var_truncated:
                        logger.info(
                            "Truncated variables from %d to %d",
                            var_count,
                            len(limited_vars),
                        )

                    logger.info(
                        "Retrieved %d local variables (showing %d)",
                        var_count,
                        len(limited_vars),
                        extra={
                            "total_locals": var_count,
                            "displayed_locals": len(limited_vars),
                        },
                    )
                else:
                    logger.debug("No variables found for current frame")
            except Exception as e:
                logger.warning(
                    "Failed to get frame variables: %s",
                    e,
                    extra={"frame_id": current_frame.id, "error": str(e)},
                )

    except Exception as e:
        logger.error(
            "Failed to build paused context: %s",
            e,
            extra={"error": str(e), "verbose": verbose},
        )
        context["location_error"] = str(e)


def _build_breakpoints_context(
    context: dict[str, Any],
    session_context: Any,
    execution_state: str,
) -> None:
    """Build breakpoints context with state awareness.

    Parameters
    ----------
    context : dict[str, Any]
        Context dictionary to populate
    session_context : Any
        Session context object
    execution_state : str
        Current execution state (running, paused, terminated)
    """
    from ...core.constants import ExecutionState

    if hasattr(session_context, "breakpoints_set"):
        breakpoints = list(session_context.breakpoints_set)
        count = len(breakpoints)

        # Determine if breakpoints are active based on session state
        is_terminated = execution_state == ExecutionState.TERMINATED.value
        breakpoint_status = (
            BreakpointStatus.INACTIVE if is_terminated else BreakpointStatus.ACTIVE
        )

        logger.debug(
            "Found %d %s breakpoints (session state: %s)",
            count,
            breakpoint_status,
            execution_state,
            extra={
                "breakpoint_count": count,
                "breakpoints": breakpoints,
                "execution_state": execution_state,
                "breakpoint_status": breakpoint_status,
            },
        )
    else:
        logger.debug("No breakpoints_set attribute found on session context")
        breakpoints = []
        count = 0
        breakpoint_status = BreakpointStatus.NONE

    context["breakpoints"] = {
        "active": breakpoints,
        "count": count,
        "status": breakpoint_status,
    }


def _build_execution_history_context(
    context: dict[str, Any],
    session_context: Any,
) -> None:
    """Build execution history context.

    Parameters
    ----------
    context : dict[str, Any]
        Context dictionary to populate
    session_context : Any
        Session context object
    """
    if hasattr(session_context, "execution_history"):
        history = session_context.execution_history
        total_ops = len(history)
        recent_history = history[-10:] if total_ops > 10 else history
        success_rate = _calculate_success_rate(history)

        logger.debug(
            "Building execution history context with %d total operations, %d recent",
            total_ops,
            len(recent_history),
            extra={
                "total_operations": total_ops,
                "recent_operations": len(recent_history),
                "success_rate": success_rate,
            },
        )

        context["execution_history"] = {
            "total_operations": total_ops,
            "recent_operations": [
                {
                    "operation": entry.get("operation", "unknown"),
                    "timestamp": entry.get("timestamp"),
                    "result": entry.get("result", "success"),
                    "details": entry.get("details", {}),
                }
                for entry in recent_history
            ],
            "last_operation": history[-1] if history else None,
            "success_rate": success_rate,
        }
    else:
        logger.debug("Initializing execution history tracking for session")
        session_context.execution_history = []
        context["execution_history"] = {
            "total_operations": 0,
            "recent_operations": [],
            "last_operation": None,
            "success_rate": 100.0,
        }

    if (
        hasattr(session_context, "execution_history")
        and session_context.execution_history
    ):
        logger.debug("Analyzing execution patterns for insights")
        insights = _analyze_execution_patterns(
            session_context.execution_history,
        )
        if insights:
            logger.info(
                "Generated debugging insights: %s",
                list(insights.keys()),
                extra={"insights": insights},
            )
            context["debugging_insights"] = insights
        else:
            logger.debug("No significant patterns found in execution history")
