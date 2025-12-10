"""High-level composite decorators for MCP tool handlers.

This module provides the main decorator APIs used by MCP tool handlers. These composite
decorators combine multiple primitive decorators and helpers to provide comprehensive
functionality like execution context tracking, variable monitoring, and performance
timing.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from aidb_logging import get_mcp_logger as get_logger

from .constants import ResponseStatus
from .decorator_helpers import (
    _add_execution_context_to_result,
    _record_execution_history,
    _standardize_session_response,
    _synchronize_execution_state,
    _track_variable_changes,
)
from .decorator_primitives import (
    require_initialized_session,
    standardize_response,
    with_parameter_validation,
    with_thread_safety,
)
from .performance import timed

if TYPE_CHECKING:
    from collections.abc import Callable

# Re-export for backward compatibility
__all__ = [
    "mcp_tool",
    "with_execution_context",
    "with_thread_safety",
    "with_parameter_validation",
    "require_initialized_session",
    "standardize_response",
]

logger = get_logger(__name__)


def with_execution_context(
    include_before: bool = False,
    include_after: bool = True,
    track_variables: bool = False,
    record_history: bool = True,
    standardize_response: bool = True,
) -> Callable:
    """Add execution context to handler responses.

    Automatically captures and includes debugging context (location, state, etc.)
    in the response. This ensures consistent context across all debugging operations.

    Parameters
    ----------
    include_before : bool
        Capture context before operation (for diff calculation)
    include_after : bool
        Capture context after operation (default True)
    track_variables : bool
        Automatically track variable changes (for inspect operations)
    record_history : bool
        Record operation in execution history (default True)
    standardize_response : bool
        Automatically apply response standardization (default True)

    Returns
    -------
    Callable
        Decorated handler function with context
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(args: dict[str, Any]) -> dict[str, Any]:
            # Get session components from args
            session_id = args.get("_session_id")
            debug_api = args.get("_api")
            session_context = args.get("_context")
            operation_name = func.__name__.replace("handle_", "")

            # Capture before context if requested
            before_context = None
            if include_before and debug_api and session_id:
                from .context_utils import gather_execution_context

                before_context = await gather_execution_context(
                    debug_api,
                    session_id,
                    session_context,
                )
                logger.debug("Captured before context: %s", before_context)

            # Execute the actual handler
            result = await func(args)

            # Record in execution history if enabled
            if record_history:
                _record_execution_history(
                    session_context,
                    operation_name,
                    args,
                    result,
                )

            # Handle both dict and tuple response formats
            if isinstance(result, tuple):
                # Convert tuple response to dict format for consistency
                logger.warning(
                    "Handler returned tuple, converting to dict format: %s",
                    func.__name__,
                )
                if len(result) >= 2:
                    result = (
                        {"code": result[0], "data": result[1]}
                        if result[0]
                        else {
                            "code": ResponseStatus.ERROR,
                            "error": result[1],
                        }
                    )
                else:
                    result = {
                        "code": ResponseStatus.ERROR,
                        "error": "Invalid tuple response format",
                    }

            # Only add context if operation succeeded
            if (
                isinstance(result, dict)
                and result.get("code") == ResponseStatus.OK
                and include_after
                and debug_api
                and session_id
            ):
                # Synchronize session context with actual execution state
                _synchronize_execution_state(
                    session_context,
                    operation_name,
                    result,
                    debug_api,
                )

                # Capture after context
                from .context_utils import gather_execution_context

                after_context = await gather_execution_context(
                    debug_api,
                    session_id,
                    session_context,
                )
                logger.debug("Captured after context: %s", after_context)

                # Track variables if enabled
                if track_variables:
                    _track_variable_changes(
                        session_context,
                        args,
                        result,
                        after_context,
                        operation_name,
                    )

                # Add execution context to result
                _add_execution_context_to_result(result, after_context, before_context)

            # Apply response standardization if enabled
            if standardize_response and isinstance(result, dict):
                _standardize_session_response(
                    result,
                    func,
                    session_id,
                    session_context,
                    args,
                )

            return result

        return wrapper

    return decorator


def mcp_tool(
    require_session: bool = True,
    include_before: bool = False,
    include_after: bool = True,
    track_variables: bool = False,
    record_history: bool = True,
    standardize_response: bool = True,
    validate_params: list[str] | None = None,
    allow_on_terminated: list[str] | None = None,
) -> Callable:
    """Unified decorator for MCP tool handlers.

    Combines @timed, @with_thread_safety, @with_execution_context, and
    optionally @with_parameter_validation into a single decorator for cleaner
    handler signatures and centralized configuration.

    The decorator stack (outermost to innermost):
    1. @timed - Performance tracking (controlled by AIDB_MCP_TIMING env var)
    2. @with_thread_safety - Thread safety and session management
    3. @with_parameter_validation - Parameter validation (if validate_params given)
    4. @with_execution_context - Execution context tracking

    Parameters
    ----------
    require_session : bool, default=True
        Whether handler requires an active debug session
    include_before : bool, default=False
        Capture execution context before operation (for diff calculation)
    include_after : bool, default=True
        Capture execution context after operation
    track_variables : bool, default=False
        Automatically track variable changes (for inspect operations)
    record_history : bool, default=True
        Record operation in execution history
    standardize_response : bool, default=True
        Apply response standardization
    validate_params : list[str], optional
        List of required parameter names to validate before execution
    allow_on_terminated : list[str], optional
        List of action values allowed on terminated sessions (for read-only ops)

    Returns
    -------
    Callable
        Decorated handler with full MCP tool functionality

    Examples
    --------
    Simple handler requiring session:
    >>> @mcp_tool()
    >>> async def handle_something(args: dict[str, Any]) -> dict[str, Any]:
    ...     pass

    Handler with parameter validation:
    >>> @mcp_tool(validate_params=["location", "target"])
    >>> async def handle_something(args: dict[str, Any]) -> dict[str, Any]:
    ...     pass

    Handler tracking variables:
    >>> @mcp_tool(track_variables=True, include_before=True)
    >>> async def handle_inspect(args: dict[str, Any]) -> dict[str, Any]:
    ...     pass
    """

    def decorator(func: Callable) -> Callable:
        # Build decorator stack from inside out
        # 4. Execution context (innermost)
        result = with_execution_context(
            include_before=include_before,
            include_after=include_after,
            track_variables=track_variables,
            record_history=record_history,
            standardize_response=standardize_response,
        )(func)

        # 3. Parameter validation (optional, before execution context)
        if validate_params:
            result = with_parameter_validation(*validate_params)(result)

        # 2. Thread safety and session management
        result = with_thread_safety(
            require_session=require_session,
            allow_on_terminated=allow_on_terminated,
        )(result)

        # 1. Performance timing (outermost)
        return timed(result)

    return decorator
