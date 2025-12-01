"""Helper functions for action validation and normalization.

This module provides utility functions for validating and normalizing tool actions. The
actual enum definitions are in core.constants to maintain a single source of truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.constants import (
    AdapterAction,
    BreakpointAction,
    ConfigAction,
    ExecutionAction,
    InspectTarget,
    SessionAction,
    StepAction,
    ToolName,
    VariableAction,
)

if TYPE_CHECKING:
    from enum import Enum


# Helper functions for validation
def validate_action(action: str, enum_class: type[Enum]) -> tuple[bool, str]:
    """Validate an action string against an enum class.

    Parameters
    ----------
    action : str
        The action string to validate
    enum_class : Type[Enum]
        The enum class to validate against

    Returns
    -------
    tuple[bool, str]
        (is_valid, error_message or empty string)
    """
    valid_actions = [e.value for e in enum_class]

    if action not in valid_actions:
        return False, f"Valid actions: {', '.join(valid_actions)}"

    return True, ""


def get_action_enum(action: str, enum_class: type[Enum]) -> Enum:
    """Get the enum value for an action string.

    Parameters
    ----------
    action : str
        The action string
    enum_class : Type[Enum]
        The enum class

    Returns
    -------
    Enum
        The corresponding enum value

    Raises
    ------
    ValueError
        If the action is not valid
    """
    for e in enum_class:
        if e.value == action:
            return e

    valid_actions = [e.value for e in enum_class]
    msg = f"Invalid action '{action}'. Valid actions: {', '.join(valid_actions)}"
    raise ValueError(
        msg,
    )


# Action aliases for common typos/variations
ACTION_ALIASES: dict[str, dict[str, str]] = {
    ToolName.CONFIG: {
        "show": "list",
        "display": "list",
        "view": "list",
        "capability": "capabilities",
        "cap": "capabilities",
        "environment": "env",
    },
    ToolName.SESSION: {
        "begin": "start",
        "end": "stop",
        "terminate": "stop",
        "kill": "stop",
        "ls": "list",
        "clean": "cleanup",
    },
    ToolName.BREAKPOINT: {
        "add": "set",
        "delete": "remove",
        "rm": "remove",
        "clear": "clear_all",
        "ls": "list",
    },
    ToolName.VARIABLE: {
        "read": "get",
        "write": "set",
        "modify": "patch",
        "update": "patch",
    },
    ToolName.ADAPTER: {
        "install": "download",
        "install_all": "download_all",
        "status": "list",
        "ls": "list",
        "show": "list",
    },
}


def normalize_action(action: str, tool_name: str) -> str:
    """Normalize an action string using aliases.

    Parameters
    ----------
    action : str
        The action string to normalize
    tool_name : str
        The tool name (without 'aidb.' prefix)

    Returns
    -------
    str
        The normalized action string
    """
    action = action.lower()

    # Check for aliases
    if tool_name in ACTION_ALIASES and action in ACTION_ALIASES[tool_name]:
        return ACTION_ALIASES[tool_name][action]

    return action


# Export all action enums and helpers
__all__ = [
    "AdapterAction",
    "SessionAction",
    "ConfigAction",
    "BreakpointAction",
    "VariableAction",
    "InspectTarget",
    "ExecutionAction",
    "StepAction",
    "validate_action",
    "get_action_enum",
    "normalize_action",
    "ACTION_ALIASES",
]
