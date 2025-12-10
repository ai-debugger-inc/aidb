"""Action dispatch utilities for MCP handlers.

Provides common patterns for action-based handler dispatch without requiring inheritance
hierarchies.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from aidb_logging import get_mcp_logger as get_logger

from ..responses.helpers import invalid_action
from ..tools.actions import normalize_action

logger = get_logger(__name__)

ActionT = TypeVar("ActionT", bound=Enum)


def dispatch_action(
    args: dict[str, Any],
    action_enum_class: type[ActionT],
    action_handlers: dict[ActionT, Callable[..., Any]],
    default_action: ActionT,
    tool_name: str,
    *,
    handler_args: tuple[Any, ...] = (),
    normalize: bool = False,
    param_name: str = "action",
) -> tuple[Callable[..., Any] | None, dict[str, Any] | None, tuple[Any, ...]]:
    """Dispatch to the appropriate action handler.

    Validates and resolves the action from args, returning the handler function
    to call or an error response.

    Parameters
    ----------
    args : dict[str, Any]
        Handler arguments containing the action parameter
    action_enum_class : type[ActionT]
        The enum class defining valid actions
    action_handlers : dict[ActionT, Callable]
        Mapping of action enum values to handler functions
    default_action : ActionT
        Default action if none specified
    tool_name : str
        Tool name for error messages
    handler_args : tuple[Any, ...]
        Additional positional args to pass to handler (e.g., (api, context))
    normalize : bool
        Whether to normalize the action string before enum conversion
    param_name : str
        Name of the action parameter in args

    Returns
    -------
    tuple[Callable | None, dict | None, tuple]
        (handler_func, error_response, full_handler_args)
        - If handler_func is not None, call it with full_handler_args
        - If error_response is not None, return it directly
        - full_handler_args includes handler_args + (args,)
    """
    raw_action = args.get(param_name, default_action.value)

    # Optionally normalize (handles aliases like "over" -> "step_over")
    action_str = normalize_action(raw_action, tool_name) if normalize else raw_action

    # Convert to enum
    try:
        action = action_enum_class(action_str)
    except ValueError:
        valid_actions = [a.value for a in action_enum_class]
        error = invalid_action(
            action=raw_action,
            valid_actions=valid_actions,
            tool_name=tool_name,
        )
        return None, error, ()

    # Find handler
    handler = action_handlers.get(action)
    if not handler:
        valid_actions = [a.value for a in action_enum_class]
        error = invalid_action(
            action=action.value,
            valid_actions=valid_actions,
            tool_name=tool_name,
        )
        return None, error, ()

    # Build full handler args
    full_args = (*handler_args, args)

    return handler, None, full_args
