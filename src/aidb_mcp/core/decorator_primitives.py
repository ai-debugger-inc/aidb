"""Single-responsibility decorator building blocks.

This module contains focused, single-purpose decorators that provide specific
functionality like thread safety, parameter validation, session initialization checks,
and response standardization. These primitives can be composed together to build more
complex decorator behaviors.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, cast

from aidb_logging import get_mcp_logger as get_logger

from ..responses.errors import (
    InitRequiredError,
    MissingParameterError,
    NoSessionError,
)
from ..session import (
    _state_lock,
    get_or_create_session,
    get_service,
    get_session_id_from_args,
)
from .constants import ParamName
from .decorator_helpers import (
    _add_session_id_to_result,
    _check_connection_health,
    _check_termination_status,
    _get_session_or_error,
    _setup_session_context,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..session.context import MCPSessionContext

logger = get_logger(__name__)


def with_thread_safety(
    require_session: bool = True,
    allow_on_terminated: list[str] | None = None,
) -> Callable:
    """Add thread safety and connection checking to handlers.

    Parameters
    ----------
    require_session : bool
        Whether the handler requires an active session
    allow_on_terminated : list[str], optional
        List of action values that are allowed to proceed even on terminated sessions.
        Useful for read-only operations like 'list' that access preserved state.

    Returns
    -------
    Callable
        Decorated handler function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            args: dict[str, Any],
        ) -> dict[str, Any] | tuple[Any, ...]:
            with _state_lock:
                session_id = args.get(ParamName.SESSION_ID)

                # Check if session is required
                session_id, error = _get_session_or_error(
                    require_session,
                    session_id,
                    func.__name__,
                )
                if error:
                    return error

                # Set up session context
                sid, context = _setup_session_context(require_session, session_id)

                # Log handler invocation
                logger.debug(
                    "Invoking handler %s with args: %s",
                    func.__name__,
                    list(args.keys()),
                )

                # Check session requirement
                if require_session and (not context or not context.session_started):
                    from ..responses.errors import SessionNotStartedError

                    return SessionNotStartedError(
                        session_id=sid,
                        error_message="Session required but not started",
                    ).to_mcp_response()

                # Check connection health
                health_error = await _check_connection_health(require_session, sid)
                if health_error:
                    return health_error

                # Get service for this session (may be None before session_start)
                service = get_service(sid) if sid else None

                # Check if session is terminated (fail fast)
                termination_error = _check_termination_status(
                    require_session,
                    service,
                    sid,
                    args,
                    allow_on_terminated,
                )
                if termination_error:
                    return termination_error

                # Add session info to args for handler
                if sid is not None:
                    args["_session_id"] = sid
                    args["_service"] = service
                    args["_context"] = context

                # Execute the handler
                result = await func(args)

                # Add session_id to result
                return _add_session_id_to_result(result, sid)

        return wrapper

    return decorator


def with_parameter_validation(*required_params: str) -> Callable:
    """Validate required parameters before handler execution.

    Parameters
    ----------
    *required_params : str
        Names of required parameters

    Returns
    -------
    Callable
        Decorated handler function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
            # Check all required parameters
            missing = []
            for param in required_params:
                if param not in args or args[param] is None:
                    missing.append(param)

            if missing:
                _ = args.get("_session_id") or args.get(ParamName.SESSION_ID)

                if len(missing) == 1:
                    error = f"{missing[0]} is required"
                else:
                    error = f"Required parameters missing: {', '.join(missing)}"

                return MissingParameterError(
                    param_name=missing[0] if len(missing) == 1 else ", ".join(missing),
                    param_description=error,
                ).to_mcp_response()

            return await func(args)

        return wrapper

    return decorator


def require_initialized_session(func: Callable) -> Callable:
    """Ensure init was called and session is active before executing handler.

    This decorator validates that:
    1. The init tool was called to set up the debugging context
    2. A debug session is active (started with session_start)

    It should be applied to all handlers except:
    - handle_init (initializes the context)
    - handle_session_start (starts the session)
    - handle_session_management (may check status without active session)
    - handle_config_management (some actions don't need session)

    This decorator should be applied AFTER @with_thread_safety in the decorator
    stack, as it relies on session components being populated in args.

    Parameters
    ----------
    func : Callable
        The handler function to decorate

    Returns
    -------
    Callable
        Decorated handler that validates init and session state
    """

    @functools.wraps(func)
    async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
        # Extract the tool name for better error messages
        tool_name = func.__name__.replace("handle_", "")

        # This decorator is for operations that require both init AND session
        # The init check now happens in session_start, so we just need to ensure
        # there's an active session
        session_id = get_session_id_from_args(args, ParamName.SESSION_ID)

        if not session_id:
            from ..responses.errors import SessionNotStartedError

            logger.warning(
                "Tool '%s' called without session",
                tool_name,
                extra={"tool": tool_name},
            )
            return SessionNotStartedError(
                session_id=None,
                error_message=(
                    f"No active debug session. You must call 'init' and then "
                    f"'session_start' before using '{tool_name}'."
                ),
            ).to_mcp_response()

        _, context = get_or_create_session(session_id)
        if not context.init_completed:
            logger.warning(
                "Tool '%s' called on session without init",
                tool_name,
                extra={"tool": tool_name, "session_id": session_id},
            )
            return InitRequiredError(
                error_message=(
                    f"You must call 'init' first to initialize the debugging "
                    f"context before using '{tool_name}'. "
                    "This sets up the language-specific debugging environment."
                ),
                suggestions=[
                    "Call init with your target language first",
                    "Example: init(language='python')",
                    "Then call session_start to begin debugging",
                    f"After session is started, you can use '{tool_name}'",
                ],
            ).to_mcp_response()

        # Check for session (args should have been populated by @with_thread_safety)
        session_id = args.get("_session_id")
        context = cast("MCPSessionContext", args.get("_context"))

        # No session at all
        if not session_id:
            logger.warning(
                "Tool '%s' called without active session",
                tool_name,
                extra={"tool": tool_name},
            )
            return NoSessionError(
                error_message=(
                    f"No active debug session. You must call 'session_start' "
                    f"to begin debugging before using '{tool_name}'."
                ),
                requested_operation=tool_name,
            ).to_mcp_response()

        # Session exists but not started (shouldn't happen normally)
        if context and not context.session_started:
            from ..responses.errors import SessionNotStartedError

            logger.warning(
                "Tool '%s' called with unstarted session",
                tool_name,
                extra={"tool": tool_name, "session_id": session_id},
            )
            return SessionNotStartedError(
                session_id=session_id,
                error_message=(
                    f"Session '{session_id}' exists but hasn't been started. "
                    f"Cannot use '{tool_name}' yet."
                ),
            ).to_mcp_response()

        # All checks passed, execute the handler
        return await func(args)

    return wrapper


def standardize_response() -> Callable:
    """Ensure response follows standard format with next steps.

    This is a lightweight decorator that just ensures responses have:
    - Proper structure (code, summary, data)
    - Session information
    - Contextual next steps

    Use this for handlers that don't need full execution context tracking.

    Returns
    -------
    Callable
        Decorated handler with standardized responses
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
            # Get session info from args
            _ = args.get("_session_id") or args.get(ParamName.SESSION_ID)
            _ = args.get("_context")
            _ = func.__name__.replace("handle_", "")

            # Execute handler
            return await func(args)

            # Our new response system handles standardization internally,
            # so we don't need to modify responses anymore

        return wrapper

    return decorator
