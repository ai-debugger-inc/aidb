"""Main context handler and utilities.

This module provides the main context handler that orchestrates context building and
suggestion generation.
"""

from __future__ import annotations

from typing import Any

from aidb.models import SessionStatus
from aidb_logging import get_mcp_logger as get_logger

from ...core import ToolName
from ...core.constants import ConnectionStatus, DetailLevel, ExecutionState, ParamName
from ...core.decorators import mcp_tool
from ...responses import ContextResponse
from ...responses.helpers import no_session, session_not_started
from ...session import get_service, get_session
from .context_building import (
    _build_breakpoints_context,
    _build_execution_history_context,
    _build_paused_context,
)

logger = get_logger(__name__)


def _get_session_execution_state(session: Any) -> tuple[str, bool]:
    """Get the current execution state of the debug session.

    Uses session.status as the authoritative source of truth.
    Resolves to active session (child if exists) for languages like JavaScript
    that use parent-child session patterns.

    Parameters
    ----------
    session : Any
        Session instance

    Returns
    -------
    tuple[str, bool]
        (execution_state, is_paused) where execution_state is one of
        ExecutionState values (TERMINATED, PAUSED, RUNNING) and is_paused
        indicates whether detailed context should be built
    """
    if not session or not session.started:
        return ExecutionState.TERMINATED.value, False

    # Resolve to active session (handles languages with parent/child patterns)
    active_session = session
    if hasattr(session, "registry") and session.registry:
        resolved = session.registry.resolve_active_session(session)
        if resolved:
            active_session = resolved

    # Check session status from core layer (authoritative source)
    if active_session and hasattr(active_session, "status"):
        status = active_session.status
        if status == SessionStatus.TERMINATED or status == SessionStatus.ERROR:
            return ExecutionState.TERMINATED.value, False
        if status == SessionStatus.PAUSED:
            return ExecutionState.PAUSED.value, True
        if status == SessionStatus.RUNNING:
            return ExecutionState.RUNNING.value, False

    # No session available - assume terminated
    return ExecutionState.TERMINATED.value, False


def _generate_suggestions(is_paused: bool) -> list[str]:
    """Generate context-aware suggestions.

    Parameters
    ----------
    is_paused : bool
        Whether the debugger is paused

    Returns
    -------
    list[str]
        List of suggestions
    """
    if not is_paused:
        return [
            "Set a breakpoint to pause execution",
            "Inspect current state when paused",
        ]
    return [
        "Inspect local variables to understand state",
        "Step through code to trace execution",
        "Continue to next breakpoint",
    ]


@mcp_tool(
    require_session=False,
    include_after=True,
    record_history=False,
)
async def handle_context(args: dict[str, Any]) -> dict[str, Any]:
    """Handle rich debugging state awareness with suggestions."""
    logger.info(
        "Context retrieval requested",
        extra={"request_args": list(args.keys())},
    )

    try:
        session_id = args.get("_session_id")
        session_context = args.get("_context")

        # Get session for status/property access
        session = get_session(session_id) if session_id else None

        # Get service from decorator or session manager (for introspection)
        service = args.get("_service") or (
            get_service(session_id) if session_id else None
        )

        include_suggestions = args.get("include_suggestions", True)
        detail_level_str = args.get("detail_level", DetailLevel.DETAILED.value)
        try:
            detail_level = DetailLevel(detail_level_str)
        except ValueError:
            logger.warning(
                "Invalid detail level '%s', using DETAILED",
                detail_level_str,
                extra={"invalid_level": detail_level_str},
            )
            detail_level = DetailLevel.DETAILED
        verbose = detail_level == DetailLevel.FULL

        logger.debug(
            "Context request: session_id=%s, detail_level=%s, suggestions=%s",
            session_id,
            detail_level.value,
            include_suggestions,
            extra={
                "session_id": session_id,
                "detail_level": detail_level.value,
                "include_suggestions": include_suggestions,
                "verbose": verbose,
            },
        )

        if not session_id:
            logger.warning("Context requested without active session")
            return no_session(
                operation="context",
                additional_context="No active debug session to get context from",
            )

        if not session_context or not session_context.session_started:
            logger.warning(
                "Context requested for session that hasn't started",
                extra={"session_id": session_id},
            )
            return session_not_started(
                operation="context",
                session_id=session_id,
            )

        logger.info(
            "Building context for active session %s",
            session_id,
            extra={"session_id": session_id, "session_started": True},
        )

        # Get authoritative execution state from core session layer
        execution_state, is_paused = _get_session_execution_state(session)
        is_terminated = execution_state == ExecutionState.TERMINATED.value

        # Set connection status based on execution state
        connection_status = (
            ConnectionStatus.INACTIVE.value
            if is_terminated
            else (
                ConnectionStatus.ACTIVE.value
                if session_context.session_started
                else ConnectionStatus.INACTIVE.value
            )
        )

        context: dict[str, Any] = {
            "session_id": session_id,
            "status": connection_status,
        }

        if session and session.info:
            session_info = {
                "target": session.info.target,
                "language": session.info.language,
                "pid": getattr(session.info, "pid", None),
                "port": getattr(session.info, "port", None),
            }
            context["session"] = session_info
            logger.debug(
                "Added session info: %s (%s)",
                session_info["target"],
                session_info["language"],
                extra={"session_info": session_info},
            )

        context["execution_state"] = execution_state
        logger.info(
            "Execution state: %s (terminated=%s, paused=%s)",
            execution_state,
            is_terminated,
            is_paused,
            extra={
                "is_paused": is_paused,
                "is_terminated": is_terminated,
                "execution_state": execution_state,
            },
        )

        if is_paused:
            logger.debug("Session is paused, building detailed context")
            await _build_paused_context(context, service, verbose)
        elif is_terminated:
            logger.debug("Session is terminated, skipping detailed context")
        else:
            logger.debug("Session is running, skipping detailed context")

        if session_context:
            logger.debug("Building breakpoints and execution history context")
            _build_breakpoints_context(context, session_context, execution_state)
            _build_execution_history_context(context, session_context)

        suggestions = []
        if include_suggestions:
            suggestions = _generate_suggestions(is_paused)
            logger.debug(
                "Generated %d context suggestions",
                len(suggestions),
                extra={"suggestions": suggestions},
            )
        else:
            logger.debug("Suggestions disabled, skipping generation")

        logger.info(
            "Context retrieval completed successfully",
            extra={
                "session_id": session_id,
                "execution_state": execution_state,
                "suggestions_count": len(suggestions),
                "detail_level": detail_level.value,
            },
        )

        return ContextResponse(
            context_data=context,
            session_active=True,
            session_id=session_id,
            suggestions=suggestions,
            detail_level=detail_level.value,
        ).to_mcp_response()

    except Exception as e:
        logger.exception(
            "Context retrieval failed: %s",
            e,
            extra={
                "error": str(e),
                "session_id": args.get("_session_id") or args.get(ParamName.SESSION_ID),
                "request_args": list(args.keys()),
            },
        )
        from ...responses.errors import InternalError

        return InternalError(
            operation="context",
            details=str(e),
            error_message=str(e),
        ).to_mcp_response()


HANDLERS = {
    ToolName.CONTEXT: handle_context,
}
