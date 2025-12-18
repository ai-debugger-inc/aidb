"""Session creation, startup, and event infrastructure.

This module handles the actual session creation, event subscription setup, and session
startup verification.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from aidb_common.constants import Language
from aidb_logging import get_mcp_logger as get_logger

from ...core.constants import (
    LaunchMode,
    NotificationEventType,
    ParamName,
    SessionState,
)
from ...integrations.event_bridge import register_event_bridge
from ...integrations.notifications import get_notification_manager
from ...responses.errors import SessionStartFailedError

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core.types import BreakpointSpec

logger = get_logger(__name__)


def create_mcp_child_bridge_callback(
    session_id: str,
    session_context: Any,
) -> Callable[[Any], None]:
    """Create a callback to register MCP event bridge for child sessions.

    This factory creates a callback that will be invoked immediately after a child
    session's DAP initialization completes. The callback registers the MCP event
    bridge with the child's event processor, ensuring events are captured before
    the child hits any breakpoints.

    Parameters
    ----------
    session_id : str
        MCP session identifier (used for bridge registration)
    session_context : Any
        MCP session context to store bridge reference

    Returns
    -------
    Callable[[Any], None]
        Callback function that accepts a child session and registers event bridge
    """

    async def _register_bridge_async(child_session: Any) -> None:
        """Async helper to register event bridge with child session."""
        try:
            if child_session.events:
                bridge, sub_ids = await register_event_bridge(
                    session_id,
                    child_session.events,
                )
                session_context.event_bridge = bridge  # type: ignore[attr-defined]
                session_context.event_subscription_ids = sub_ids  # type: ignore[attr-defined]

                child_id = (
                    child_session.id if hasattr(child_session, "id") else "unknown"
                )
                logger.info(
                    "Registered MCP event bridge with child session via callback",
                    extra={
                        "session_id": session_id,
                        "child_session_id": child_id,
                        "subscription_count": len(sub_ids),
                    },
                )
            else:
                logger.warning(
                    "Child session missing events API for bridge registration",
                    extra={
                        "session_id": session_id,
                        "child_session_id": getattr(
                            child_session,
                            "id",
                            "unknown",
                        ),
                    },
                )
        except Exception as e:
            logger.exception(
                "Failed to register event bridge in child callback",
                extra={
                    "error": str(e),
                    "session_id": session_id,
                },
            )

    def callback(child_session: Any) -> None:
        """Register MCP event bridge with child session's public event API.

        Parameters
        ----------
        child_session : Any
            The child session (from AIDB) that was just created
        """
        # Schedule async registration - the callback is sync but registration is async
        asyncio.create_task(_register_bridge_async(child_session))

    return callback


def _create_session_for_mode(
    session_manager: Any,
    mode: LaunchMode,
    language: str | None,
    breakpoints_parsed: list[BreakpointSpec],
    args: dict[str, Any],
    session_id: str,
    session_context: Any,
    target: str | None = None,
    pid: int | None = None,
    host: str | None = None,
    port: int | None = None,
) -> Any:
    """Create a debug session based on the specified mode.

    Parameters
    ----------
    session_manager : SessionManager
        The session manager instance
    mode : LaunchMode
        Launch mode (LAUNCH, ATTACH, or REMOTE_ATTACH)
    language : str, optional
        Programming language
    breakpoints_parsed : list[BreakpointSpec]
        Parsed breakpoint specifications
    args : dict
        Additional session arguments
    session_id : str
        MCP session identifier
    session_context : Any
        MCP session context
    target : str, optional
        Target file for launch mode
    pid : int, optional
        Process ID for attach mode
    host : str, optional
        Host for remote attach mode
    port : int, optional
        Port for remote attach mode

    Returns
    -------
    Any
        Created debug session
    """
    # Create callback for child session event bridge registration
    # This callback will be invoked immediately after child DAP initialization
    on_child_created_callback = create_mcp_child_bridge_callback(
        session_id=session_id,
        session_context=session_context,
    )

    if mode == LaunchMode.LAUNCH:
        # Extract known MCP parameters
        known_params = {
            ParamName.TARGET,
            ParamName.LANGUAGE,
            ParamName.BREAKPOINTS,
            ParamName.ENV,
            ParamName.ARGS,
            ParamName.CWD,
            ParamName.LAUNCH_CONFIG_NAME,
            ParamName.WORKSPACE_ROOT,
            ParamName.PID,
            ParamName.HOST,
            ParamName.PORT,
            ParamName.MODE,
            ParamName.SESSION_ID,
            ParamName.SUBSCRIBE_EVENTS,
        }

        # Pass through any additional launch args not in known params
        additional_kwargs = {k: v for k, v in args.items() if k not in known_params}

        # Debug logging to trace parameter flow for Java framework tests
        if language == Language.JAVA and additional_kwargs:
            logger.debug(
                "Java session creation - additional_kwargs",
                extra={
                    "target": target,
                    "additional_kwargs": additional_kwargs,
                    "has_main_class": "main_class" in additional_kwargs,
                    "has_project_name": "project_name" in additional_kwargs,
                },
            )

        return session_manager.create_session(
            target=target,
            language=language,
            breakpoints=breakpoints_parsed,
            env=args.get(ParamName.ENV),
            args=args.get(ParamName.ARGS, []),
            cwd=args.get(ParamName.CWD),
            launch_config_name=args.get(ParamName.LAUNCH_CONFIG_NAME),
            workspace_root=args.get(ParamName.WORKSPACE_ROOT),
            on_child_created_callback=on_child_created_callback,
            **additional_kwargs,
        )
    if mode == LaunchMode.ATTACH:
        return session_manager.create_session(
            pid=pid,
            language=language,
            breakpoints=breakpoints_parsed,
            workspace_root=args.get(ParamName.WORKSPACE_ROOT),
            on_child_created_callback=on_child_created_callback,
            **additional_kwargs,
        )
    # REMOTE_ATTACH
    return session_manager.create_session(
        host=host,
        port=port,
        language=language,
        breakpoints=breakpoints_parsed,
        workspace_root=args.get(ParamName.WORKSPACE_ROOT),
        on_child_created_callback=on_child_created_callback,
        **additional_kwargs,
    )


def _setup_event_subscriptions(args: dict[str, Any]) -> list[str]:
    """Set up and validate event subscriptions.

    Parameters
    ----------
    args : dict
        Session arguments containing subscribe_events

    Returns
    -------
    list[str]
        List of subscribed event types
    """
    subscribed_events = [
        NotificationEventType.TERMINATED.value,
        NotificationEventType.BREAKPOINT.value,
    ]

    subscribe_events = args.get(ParamName.SUBSCRIBE_EVENTS, [])
    if subscribe_events:
        # Add user-requested subscriptions
        # Get all valid event types from the enum
        valid_event_values = {e.value for e in NotificationEventType}

        for event in subscribe_events:
            # Validate event is a valid NotificationEventType value
            if event not in valid_event_values:
                logger.warning(
                    "Invalid event type '%s' in subscribe_events. Valid types: %s",
                    event,
                    list(valid_event_values),
                )
                continue

            # Only allow subscription to BREAKPOINT and EXCEPTION
            # (TERMINATED is always auto-subscribed)
            subscribable_events = [
                NotificationEventType.BREAKPOINT.value,
                NotificationEventType.EXCEPTION.value,
            ]
            if event in subscribable_events and event not in subscribed_events:
                subscribed_events.append(event)

    return subscribed_events


async def _setup_event_bridge(
    session: Any,
    session_id: str,
    session_context: Any,
    session_manager: Any,
) -> None:
    """Register MCP event bridge for parent session DAP events.

    Child sessions are handled via on_child_created_callback during child creation.
    This function only handles parent sessions that don't spawn children.

    MUST be called AFTER session.start().

    Parameters
    ----------
    session : Any
        Debug session (parent)
    session_id : str
        Session identifier
    session_context : Any
        Session context for storing bridge reference
    session_manager : SessionManager
        Session manager instance for resolving active session
    """
    try:
        notification_manager = get_notification_manager()
        await notification_manager.start()

        # Only register if this is NOT a parent session with children
        # (JavaScript uses child sessions for debugging)
        active_session = (
            session_manager.get_active_session() if session_manager else session
        )
        if active_session and active_session != session:
            # This is a parent with a child session
            # Child session bridge was already registered via callback
            logger.debug(
                "Skipping parent event bridge registration (child handles events)",
                extra={"session_id": session_id},
            )
            return

        # Register with parent session's public event API
        if session.events:
            bridge, sub_ids = await register_event_bridge(session_id, session.events)
            session_context.event_bridge = bridge  # type: ignore[attr-defined]
            session_context.event_subscription_ids = sub_ids  # type: ignore[attr-defined]

            logger.info(
                "Registered DAP->MCP event bridge with parent session",
                extra={
                    "session_id": session_id,
                    "subscription_count": len(sub_ids),
                },
            )
        else:
            logger.warning(
                "Could not access events API for event bridge registration",
                extra={"session_id": session_id},
            )
    except Exception as e:
        logger.exception(
            "Failed to register event bridge",
            extra={"error": str(e), "session_id": session_id},
        )


def _check_if_paused(
    session_context: Any,
    session: Any,
    session_manager: Any = None,
) -> bool:
    """Check if session is currently paused at a breakpoint.

    Called AFTER session.start() to determine initial state.

    Parameters
    ----------
    session_context : Any
        Session context to update with running state
    session : Any
        Debug session instance
    session_manager : Any, optional
        Session manager for resolving active session

    Returns
    -------
    bool
        True if session is paused at a breakpoint
    """
    # Resolve to active session (handles languages with parent/child patterns)
    active_session = (
        session_manager.get_active_session() if session_manager else session
    )
    check_session = active_session or session

    if check_session and check_session.is_paused():
        logger.debug("Session is paused at breakpoint")
        session_context.is_running = False
        return True

    logger.debug("Session is running")
    session_context.is_running = True
    return False


async def _start_and_verify_session(
    session: Any,
    session_id: str,
    mode: LaunchMode,
    target: str | None,
    pid: int | None,
    host: str | None,
    port: int | None,
) -> dict[str, Any] | None:
    """Start session and verify it started successfully.

    Returns error or None.
    """
    start_result = await session.start()

    if not start_result.success:
        return SessionStartFailedError(
            error_message=f"Debug session failed to start: {start_result.message}",
            session_id=session_id,
            mode=mode.value,
            target=target or f"PID:{pid}" or f"{host}:{port}",
            start_result=str(start_result),
        ).to_mcp_response()

    # Verify the session is actually started
    if not session.started:
        logger.warning(
            "Session start returned success but session.started is False",
            extra={
                "session_id": session_id,
                "has_session": session is not None,
            },
        )
        # Force a check to see if session is there
        if session:
            logger.info(
                "Session exists despite started flag",
                extra={
                    "session_id": session.id,
                    "started": session.started,
                    "state": (
                        SessionState.RUNNING.name
                        if session.started
                        else SessionState.STOPPED.name
                    ),
                },
            )
    return None
