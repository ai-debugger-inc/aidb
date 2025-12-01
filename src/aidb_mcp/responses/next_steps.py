"""Centralized next steps definitions for all response types."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.constants import (
    BreakpointAction,
    ExecutionAction,
    InspectTarget,
    ParamName,
    SessionAction,
    StepAction,
    ToolName,
    VariableAction,
)

if TYPE_CHECKING:
    from ..core.types import ToolAction

# ============= COMMON NEXT STEP DEFINITIONS =============

# Session-related next steps
SESSION_START_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.EXECUTE,
        "description": "Run to first breakpoint",
        "when": "immediately",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
        "tip": "Execution will pause at the first breakpoint hit",
    },
    {
        "tool": ToolName.BREAKPOINT,
        "description": "Set a breakpoint",
        "when": "to add breakpoints",
        "params_example": {
            ParamName.ACTION: BreakpointAction.SET.value,
            ParamName.LOCATION: "file.py:42",
        },
        "tip": "Use file:line format for location",
    },
    {
        "tool": ToolName.BREAKPOINT,
        "description": "List active breakpoints",
        "when": "to verify setup",
        "params_example": {ParamName.ACTION: BreakpointAction.LIST.value},
    },
    {
        "tool": ToolName.STEP,
        "description": "Step through code line by line",
        "when": "alternatively",
        "params_example": {ParamName.ACTION: StepAction.OVER.value},
    },
]

# Context-aware session start next steps
SESSION_START_WITH_BREAKPOINTS_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.BREAKPOINT,
        "description": "List current breakpoints",
        "when": "to verify setup",
        "params_example": {ParamName.ACTION: BreakpointAction.LIST.value},
        "tip": (
            "Session started with breakpoints - program already running to "
            "first breakpoint"
        ),
    },
    {
        "tool": ToolName.BREAKPOINT,
        "description": "Set additional breakpoints",
        "when": "to add more stopping points",
        "params_example": {
            ParamName.ACTION: BreakpointAction.SET.value,
            ParamName.LOCATION: "file.py:42",
        },
        "tip": "Use file:line format for location",
    },
    {
        "tool": ToolName.STEP,
        "description": "Step through code line by line",
        "when": "when paused at breakpoint",
        "params_example": {ParamName.ACTION: StepAction.OVER.value},
        "tip": "Use when program pauses at breakpoint",
    },
]

SESSION_START_NO_BREAKPOINTS_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.BREAKPOINT,
        "description": "Set a breakpoint",
        "when": "immediately recommended",
        "params_example": {
            ParamName.ACTION: BreakpointAction.SET.value,
            ParamName.LOCATION: "file.py:42",
        },
        "tip": "Set breakpoints before continuing to control execution",
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Run to next breakpoint",
        "when": "after setting breakpoints",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
        "tip": "Will run to completion if no breakpoints are set",
    },
    {
        "tool": ToolName.STEP,
        "description": "Step through code line by line",
        "when": "if stopped at a breakpoint",
        "params_example": {ParamName.ACTION: StepAction.OVER.value},
        "tip": "Only available if session paused at a breakpoint",
    },
]

SESSION_STOP_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.SESSION_START,
        "description": "Start new debugging session",
        "when": "to debug again",
        "params_example": {
            ParamName.TARGET: "script.py",
            ParamName.BREAKPOINTS: [
                {"file": "script.py", "line": 10},
                {"file": "script.py", "line": 20, "condition": "x > 5"},
            ],
        },
        "tip": "Breakpoints require 'file' and 'line' fields",
    },
]

# Execution-related next steps
PAUSED_AT_BREAKPOINT_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.INSPECT,
        "description": "Inspect local variables",
        "when": "immediately",
        "params_example": {ParamName.TARGET: InspectTarget.LOCALS.value},
    },
    {
        "tool": ToolName.INSPECT,
        "description": "View call stack",
        "when": "to see call chain",
        "params_example": {ParamName.TARGET: InspectTarget.STACK.value},
    },
    {
        "tool": ToolName.VARIABLE,
        "description": "Evaluate expressions in current context",
        "when": "to test expressions",
        "params_example": {
            ParamName.ACTION: VariableAction.GET.value,
            ParamName.EXPRESSION: "len(items)",
        },
    },
    {
        "tool": ToolName.STEP,
        "description": "Step to next line",
        "when": "to continue debugging",
        "params_example": {ParamName.ACTION: StepAction.OVER.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Continue to next breakpoint",
        "when": "to resume",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

PAUSED_AT_EXCEPTION_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.INSPECT,
        "description": "Get exception details",
        "when": "immediately",
        "params_example": {
            ParamName.TARGET: InspectTarget.EXPRESSION.value,
            ParamName.EXPRESSION: "sys.exc_info()",
        },
    },
    {
        "tool": ToolName.INSPECT,
        "description": "View exception stack trace",
        "when": "to trace error",
        "params_example": {ParamName.TARGET: InspectTarget.STACK.value},
    },
    {
        "tool": ToolName.INSPECT,
        "description": "Check variable values at error",
        "when": "to inspect state",
        "params_example": {ParamName.TARGET: InspectTarget.LOCALS.value},
    },
]

PROGRAM_COMPLETED_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.SESSION,
        "description": "Stop the debug session",
        "when": "to clean up",
        "params_example": {ParamName.ACTION: SessionAction.STOP.value},
    },
    {
        "tool": ToolName.SESSION,
        "description": "Restart with same configuration",
        "when": "to run again",
        "params_example": {ParamName.ACTION: SessionAction.RESTART.value},
    },
]

STEP_COMPLETED_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.INSPECT,
        "description": "Check local variables",
        "when": "immediately",
        "params_example": {ParamName.TARGET: InspectTarget.LOCALS.value},
    },
    {
        "tool": ToolName.VARIABLE,
        "description": "Evaluate expressions",
        "when": "to examine values",
        "params_example": {
            ParamName.ACTION: VariableAction.GET.value,
            ParamName.EXPRESSION: "variable_name",
        },
    },
    {
        "tool": ToolName.STEP,
        "description": "Continue stepping",
        "when": "to advance further",
        "params_example": {ParamName.ACTION: StepAction.OVER.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Continue to next breakpoint",
        "when": "to resume execution",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

# Inspection-related next steps
INSPECT_COMPLETED_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.VARIABLE,
        "description": "Modify variable values",
        "when": "to test changes",
        "params_example": {
            ParamName.ACTION: VariableAction.SET.value,
            ParamName.NAME: "variable_name",
            ParamName.VALUE: "new_value",
        },
    },
    {
        "tool": ToolName.INSPECT,
        "description": "Inspect other scopes",
        "when": "for more context",
        "params_example": {ParamName.TARGET: InspectTarget.GLOBALS.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Continue execution",
        "when": "when done inspecting",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

VARIABLE_SET_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.INSPECT,
        "description": "Check updated state",
        "when": "to verify changes",
        "params_example": {ParamName.TARGET: InspectTarget.LOCALS.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Continue with changes",
        "when": "to proceed",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

# Breakpoint-related next steps
BREAKPOINT_SET_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.BREAKPOINT,
        "description": "List all breakpoints",
        "when": "to review",
        "params_example": {ParamName.ACTION: BreakpointAction.LIST.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Run to breakpoint",
        "when": "to test",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

BREAKPOINT_REMOVED_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.BREAKPOINT,
        "description": "List remaining breakpoints",
        "when": "to verify",
        "params_example": {ParamName.ACTION: BreakpointAction.LIST.value},
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Continue execution",
        "when": "to proceed",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

# Error recovery next steps
ERROR_NO_SESSION_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.SESSION_START,
        "description": "Start a debug session",
        "when": "immediately",
        "params_example": {
            ParamName.TARGET: "script.py",
            ParamName.BREAKPOINTS: [{"file": "script.py", "line": 1}],
        },
        "tip": "Each breakpoint must have 'file' and 'line' fields",
    },
    {
        "tool": ToolName.SESSION,
        "description": "List available sessions",
        "when": "to check existing",
        "params_example": {ParamName.ACTION: SessionAction.LIST.value},
    },
]

ERROR_NOT_PAUSED_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.BREAKPOINT,
        "description": "Set a breakpoint",
        "when": "immediately",
        "params_example": {
            ParamName.ACTION: BreakpointAction.SET.value,
            ParamName.LOCATION: "file.py:42",
        },
        "tip": "Use file:line format (e.g., 'main.py:10')",
    },
    {
        "tool": ToolName.EXECUTE,
        "description": "Run to breakpoint",
        "when": "after setting breakpoint",
        "params_example": {ParamName.ACTION: ExecutionAction.CONTINUE.value},
    },
]

ERROR_CONNECTION_LOST_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.SESSION,
        "description": "Restart the session",
        "when": "to recover",
        "params_example": {ParamName.ACTION: SessionAction.RESTART.value},
    },
    {
        "tool": ToolName.SESSION,
        "description": "Check session status",
        "when": "to diagnose",
        "params_example": {ParamName.ACTION: SessionAction.STATUS.value},
    },
]

ERROR_INVALID_PARAMETER_NEXT_STEPS: list[ToolAction] = [
    {
        "tool": ToolName.CONTEXT,
        "description": "Check available options",
        "when": "to see valid parameters",
    },
]

# ============= REGISTRY FOR EASY LOOKUP =============

NEXT_STEPS_REGISTRY: dict[str, list[ToolAction]] = {
    # Session lifecycle
    "session_start": SESSION_START_NEXT_STEPS,
    "session_start_with_breakpoints": SESSION_START_WITH_BREAKPOINTS_NEXT_STEPS,
    "session_start_no_breakpoints": SESSION_START_NO_BREAKPOINTS_NEXT_STEPS,
    "session_stop": SESSION_STOP_NEXT_STEPS,
    # Execution states
    "paused_breakpoint": PAUSED_AT_BREAKPOINT_NEXT_STEPS,
    "paused_exception": PAUSED_AT_EXCEPTION_NEXT_STEPS,
    "program_completed": PROGRAM_COMPLETED_NEXT_STEPS,
    "step_completed": STEP_COMPLETED_NEXT_STEPS,
    # Inspection operations
    "inspect_completed": INSPECT_COMPLETED_NEXT_STEPS,
    "variable_set": VARIABLE_SET_NEXT_STEPS,
    # Breakpoint operations
    "breakpoint_set": BREAKPOINT_SET_NEXT_STEPS,
    "breakpoint_removed": BREAKPOINT_REMOVED_NEXT_STEPS,
    # Error recovery
    "error_no_session": ERROR_NO_SESSION_NEXT_STEPS,
    "error_not_paused": ERROR_NOT_PAUSED_NEXT_STEPS,
    "error_connection_lost": ERROR_CONNECTION_LOST_NEXT_STEPS,
    "error_invalid_parameter": ERROR_INVALID_PARAMETER_NEXT_STEPS,
}


def get_next_steps(key: str) -> list[ToolAction]:
    """Get next steps for a specific scenario.

    Parameters
    ----------
    key : str
        The scenario key to look up

    Returns
    -------
    List[ToolAction]
        List of next step dictionaries, or empty list if key not found
    """
    return NEXT_STEPS_REGISTRY.get(key, [])
