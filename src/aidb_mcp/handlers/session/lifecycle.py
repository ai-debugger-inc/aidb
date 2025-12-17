"""Session lifecycle handlers.

Handles session creation and startup operations.
"""

from __future__ import annotations

import contextlib
from typing import Any

from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from ...core import (
    ToolName,
)
from ...core.constants import (
    DefaultValue,
    ParamName,
    StopReason,
)
from ...core.exceptions import ErrorCode
from ...core.types import ErrorContext
from ...responses.errors import (
    ErrorResponse,
    SessionStartFailedError,
)
from ...responses.helpers import (
    internal_error,
    missing_parameter,
)
from ...responses.session import (
    SessionStartResponse,
)
from ...session import (
    set_default_session,
)
from .initialization import _validate_initialization
from .session_setup import (
    _check_if_paused,
    _create_session_for_mode,
    _setup_event_bridge,
    _setup_event_subscriptions,
    _start_and_verify_session,
)
from .state_management import (
    _prepare_code_context_and_location,
    _store_breakpoints_in_context,
)
from .validation import _validate_and_prepare_session, _validate_target_syntax

logger = get_logger(__name__)


def _resolve_source_paths(
    args: dict[str, Any],
    language: str,
    session_id: str,
) -> list[str]:
    """Resolve source paths, auto-detecting for Java projects if needed.

    Parameters
    ----------
    args : dict
        Session arguments containing SOURCE_PATHS and WORKSPACE_ROOT
    language : str
        Programming language
    session_id : str
        Session ID for logging

    Returns
    -------
    list[str]
        Resolved source paths (explicit or auto-detected)
    """
    source_paths = args.get(ParamName.SOURCE_PATHS, [])
    workspace_root = args.get(ParamName.WORKSPACE_ROOT)

    # Auto-detect source paths for Java projects if not explicitly provided
    if not source_paths and workspace_root and language == Language.JAVA:
        from aidb.adapters.lang.java.source_detection import (
            detect_java_source_paths,
        )

        auto_detected = detect_java_source_paths(workspace_root)
        if auto_detected:
            source_paths = auto_detected
            logger.info(
                "Auto-detected Java source paths",
                extra={
                    "session_id": session_id,
                    "count": len(auto_detected),
                    "paths_sample": auto_detected[:3],
                },
            )

    if source_paths:
        logger.debug(
            "Stored source paths for code context resolution",
            extra={
                "session_id": session_id,
                "source_paths_count": len(source_paths),
            },
        )

    return source_paths


async def handle_session_start(args: dict[str, Any]) -> dict[str, Any]:
    """Handle unified session start - combines create + start operations.

    Supports both launch and attach modes in a single operation.
    """
    try:
        # HARD GATE: Check if init was called first
        init_error = _validate_initialization()
        if init_error:
            return init_error

        # Validate and prepare session
        try:
            (
                session_id,
                session_context,
                mode,
                language,
                breakpoints_parsed,
            ) = await _validate_and_prepare_session(args)

            # Create SessionManager locally for session creation
            # (not stored in registry - only DebugService is stored after start)
            from aidb.session import SessionManager

            session_manager = SessionManager()
        except ValueError as e:
            error_msg = str(e)

            # Check if this is a breakpoint parsing error
            if "breakpoint format error" in error_msg.lower():
                return ErrorResponse(
                    error_message=error_msg,
                    error_code=ErrorCode.AIDB_VALIDATION_INVALID_TYPE.value,
                    context=ErrorContext(
                        operation="session_start",
                        details={
                            "parameter": "breakpoints",
                            "expected_format": (
                                "List of dicts with 'file' and 'line' fields"
                            ),
                            "example": [
                                {"file": "src/main.py", "line": 42},
                                {
                                    "file": "src/utils.py",
                                    "line": 15,
                                    "condition": "x > 5",
                                },
                            ],
                            "required_fields": ["file", "line"],
                            "optional_fields": [
                                "condition",
                                "hit_condition",
                                "log_message",
                                "column",
                            ],
                        },
                    ),
                ).to_mcp_response()

            # Otherwise it's likely a target/mode validation error
            return missing_parameter(
                param_name="target/pid/host+port",
                param_description=error_msg,
                example_value="script.py or pid=1234 or host='localhost', port=5678",
            )

        # Extract target/mode parameters from args for session creation
        target = args.get(ParamName.TARGET)
        pid = args.get(ParamName.PID)
        host = args.get(ParamName.HOST)
        port = args.get(ParamName.PORT)

        # Validate target syntax for launch mode
        syntax_error = await _validate_target_syntax(mode, target, language, args)
        if syntax_error:
            return syntax_error

        # Actually start the debug session
        try:
            # Create the session with appropriate parameters
            # Pass session_id and session_context for child bridge callback
            session = _create_session_for_mode(
                session_manager=session_manager,
                mode=mode,
                language=language,
                breakpoints_parsed=breakpoints_parsed,
                args=args,
                session_id=session_id,
                session_context=session_context,
                target=target,
                pid=pid,
                host=host,
                port=port,
            )

            # Start and verify the session
            # For JavaScript, child session is created during this call
            start_error = await _start_and_verify_session(
                session=session,
                session_id=session_id,
                mode=mode,
                target=target,
                pid=pid,
                host=host,
                port=port,
            )
            if start_error:
                return start_error

            # Mark the session context as started
            session_context.session_started = True

            # Create and store DebugService wrapping the session
            from aidb import DebugService

            from ...session.manager_core import set_service
            from ...session.manager_shared import _DEBUG_SESSIONS

            service = DebugService(session)
            set_service(session_id, service)

            # Store DebugService in _DEBUG_SESSIONS for backward compatibility
            # DebugService now has .started, .session_info, .session properties
            _DEBUG_SESSIONS[session_id] = service

            logger.debug(
                "Created DebugService for session",
                extra={"session_id": session_id},
            )

            # Setup event bridge AFTER starting session
            # This ensures child sessions exist (JavaScript pattern)
            # Registers with active session's event processor (child if exists)
            await _setup_event_bridge(
                session=session,
                session_id=session_id,
                session_context=session_context,
                session_manager=session_manager,
            )

            # Check if paused AFTER starting
            is_paused = _check_if_paused(
                session_context=session_context,
                session=session,
                session_manager=session_manager,
            )

            # Handle event subscriptions
            subscribed_events = _setup_event_subscriptions(args)

            # Store subscriptions in session context
            session_context.subscribed_events = subscribed_events  # type: ignore
            logger.info(
                "Session subscribed to events",
                extra={
                    "session_id": session_id,
                    "events": subscribed_events,
                    "event_count": len(subscribed_events),
                },
            )

            # Store breakpoints in session context for later retrieval
            _store_breakpoints_in_context(session_context, breakpoints_parsed)

            # Store source paths for code context resolution (remote debugging)
            source_paths = _resolve_source_paths(args, language, session_id)
            if source_paths:
                session_context.source_paths = source_paths

            # Store launch params for potential restart
            session_context.launch_params = {
                ParamName.MODE: mode.value,
                ParamName.LANGUAGE: language,
                ParamName.TARGET: target,
                ParamName.PID: pid,
                ParamName.HOST: host,
                ParamName.PORT: port,
                ParamName.ENV: args.get(ParamName.ENV),
                ParamName.ARGS: args.get(ParamName.ARGS, []),
                ParamName.CWD: args.get(ParamName.CWD),
                ParamName.LAUNCH_CONFIG_NAME: args.get(ParamName.LAUNCH_CONFIG_NAME),
                ParamName.WORKSPACE_ROOT: args.get(ParamName.WORKSPACE_ROOT),
                ParamName.SUBSCRIBE_EVENTS: subscribed_events,
                ParamName.SOURCE_PATHS: source_paths,
            }

            # Set as default session and check if it changed
            previous_default = set_default_session(session_id)
            default_changed = previous_default != session_id

            # Always determine detailed status from core session status
            from ...core.context_utils import determine_detailed_status

            # Determine stop reason for context (always breakpoint)
            stop_reason = StopReason.BREAKPOINT
            detailed_status = determine_detailed_status(
                session,
                session_context,
                stop_reason,
            )

            # Get code context and location if paused
            code_context, location = await _prepare_code_context_and_location(
                session,
                service,
                session_context,
                session_id,
                is_paused,
            )

            # Create enhanced response with initial state and next steps
            response = SessionStartResponse(
                session_id=session_id,
                mode=mode.value,
                language=language or DefaultValue.UNKNOWN,
                target=target,
                pid=pid,
                host=host,
                port=port,
                breakpoints_set=len(breakpoints_parsed),
                subscribed_events=subscribed_events,
                workspace_root=args.get(ParamName.WORKSPACE_ROOT),
                is_paused=is_paused,
                default_changed=default_changed,
                previous_default_session=previous_default,
                code_context=code_context,
                location=location,
                detailed_status=detailed_status.value if detailed_status else None,
                stop_reason=stop_reason if is_paused else None,
            )

            # Note: Next steps are handled by the response class's
            # get_next_steps() method
            return response.to_mcp_response()

        except Exception as start_error:
            logger.exception(
                "Failed to start debug session",
                extra={
                    "error": str(start_error),
                    "error_type": type(start_error).__name__,
                    "session_id": session_id,
                    "mode": mode,
                    "language": language,
                    "target": target,
                },
            )
            # Clean up the session on failure
            with contextlib.suppress(Exception):
                await session.stop()
                await session.destroy()
                session_manager.destroy_session()

            # Return a standardized error response
            return SessionStartFailedError(
                error_message=str(start_error),
                original_exception=start_error,
                session_id=session_id,
                mode=mode.value,
                target=target or f"PID:{pid}" or f"{host}:{port}",
            ).to_mcp_response()

    except Exception as e:
        # Handle unexpected errors
        logger.exception(
            "Session start failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": "session_start",
                "error_code": ErrorCode.AIDB_INTERNAL_ERROR.name,
            },
        )
        return internal_error(operation="session_start", exception=e)


# Export handler functions
HANDLERS = {
    ToolName.SESSION_START: handle_session_start,
}
