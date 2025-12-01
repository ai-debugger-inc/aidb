"""Inspection-related response classes for MCP tools.

This module provides response classes for runtime inspection operations:
- InspectResponse: For inspecting locals, globals, stack, threads, or expressions
- VariableGetResponse: For retrieving variable values
- VariableSetResponse: For modifying variable values
- BreakpointMutationResponse: For setting/removing breakpoints
- BreakpointListResponse: For listing active breakpoints

All responses structure data appropriately based on the operation type and
provide context-aware next steps to guide the debugging workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aidb_mcp.core.constants import InspectTarget, ResponseFieldName

from .base import Response
from .next_steps import (
    BREAKPOINT_REMOVED_NEXT_STEPS,
    BREAKPOINT_SET_NEXT_STEPS,
    INSPECT_COMPLETED_NEXT_STEPS,
    VARIABLE_SET_NEXT_STEPS,
)

if TYPE_CHECKING:
    from aidb_mcp.core.types import BreakpointSpec, InspectionResult, VariableValue


@dataclass
class InspectResponse(Response):
    """Response for inspection operations.

    Handles multiple inspection targets (locals, globals, stack, threads, expressions)
    and structures the response data appropriately based on the target type.
    Automatically provides next steps after inspection to guide the debugging workflow.
    """

    target: str = ""  # InspectTarget enum values
    result: InspectionResult = None
    frame: int = 0
    expression: str | None = None

    def _generate_summary(self) -> str:
        if self.target == InspectTarget.EXPRESSION.value and self.expression:
            return f"Evaluated: {self.expression}"
        return f"Inspected: {self.target}"

    def get_next_steps(self):
        """Get next steps after inspection."""
        return INSPECT_COMPLETED_NEXT_STEPS

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize inspection response structure."""
        # Structure the result based on target type
        if self.target == InspectTarget.LOCALS.value:
            response["data"][ResponseFieldName.LOCALS] = self.result
        elif self.target == InspectTarget.GLOBALS.value:
            response["data"][ResponseFieldName.GLOBALS] = self.result
        elif self.target == InspectTarget.STACK.value:
            response["data"][ResponseFieldName.STACK] = self.result
        elif self.target == InspectTarget.THREADS.value:
            response["data"][ResponseFieldName.THREADS] = self.result
        elif self.target == InspectTarget.EXPRESSION.value:
            response["data"][ResponseFieldName.RESULT] = self.result
            if self.expression:
                response["data"][ResponseFieldName.EXPRESSION] = self.expression
        elif self.target == InspectTarget.ALL.value:
            # For ALL, the result is already a dict with all categories
            if isinstance(self.result, dict):
                response["data"].update(self.result)
            else:
                response["data"][ResponseFieldName.ALL] = self.result
        else:
            response["data"][self.target] = self.result

        # Remove the generic 'result' field
        if (
            ResponseFieldName.RESULT in response["data"]
            and self.target != InspectTarget.EXPRESSION.value
        ):
            del response["data"][ResponseFieldName.RESULT]

        return response


@dataclass
class VariableGetResponse(Response):
    """Response for variable get operation."""

    expression: str = ""
    value: str | int | float | bool | list[VariableValue] | dict[str, Any] | None = None
    type_name: str | None = None
    frame: int = 0

    def _generate_summary(self) -> str:
        return f"Variable '{self.expression}' retrieved"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize variable response structure."""
        # The value is already in data.value from base class auto-extraction
        # Rename it to 'result' for clarity and remove 'value'
        if ResponseFieldName.VALUE in response["data"]:
            response["data"][ResponseFieldName.RESULT] = response["data"][
                ResponseFieldName.VALUE
            ]
            del response["data"][ResponseFieldName.VALUE]
        return response


@dataclass
class VariableSetResponse(Response):
    """Response for variable set operation."""

    name: str = ""
    new_value: str | int | float | bool | None = None
    old_value: str | int | float | bool | None = None
    frame: int = 0

    def _generate_summary(self) -> str:
        return f"Variable '{self.name}' updated"

    def get_next_steps(self):
        """Get next steps after setting variable."""
        return VARIABLE_SET_NEXT_STEPS


@dataclass
class BreakpointMutationResponse(Response):
    """Response for breakpoint mutations (set/remove/clear_all).

    This consolidated response handles all breakpoint mutation operations. Use the
    action field to distinguish between operations.
    """

    action: str = "set"  # "set", "remove", "clear_all"
    location: str | None = None
    affected_count: int = 1
    # Fields specific to "set" action
    breakpoint_id: str | None = None
    condition: str | None = None
    hit_condition: str | None = None
    log_message: str | None = None
    verified: bool = True
    line: int | None = None
    column: int | None = None

    def _generate_summary(self) -> str:
        if self.action == "set":
            if self.condition:
                return f"Conditional breakpoint set at {self.location}"
            if self.log_message:
                return f"Logpoint set at {self.location}"
            return f"Breakpoint set at {self.location}"
        if self.action == "remove":
            if self.affected_count > 1:
                return f"Removed {self.affected_count} breakpoints from {self.location}"
            return f"Breakpoint removed from {self.location}"
        if self.action == "clear_all":
            if self.affected_count == 0:
                return "No breakpoints to clear"
            if self.affected_count == 1:
                return "Cleared 1 breakpoint"
            return f"Cleared {self.affected_count} breakpoints"
        return "Breakpoint mutation completed"

    def get_next_steps(self):
        """Get next steps after breakpoint mutation."""
        if self.action == "set":
            return BREAKPOINT_SET_NEXT_STEPS
        return BREAKPOINT_REMOVED_NEXT_STEPS


@dataclass
class BreakpointListResponse(Response):
    """Response for listing breakpoints."""

    breakpoints: list[BreakpointSpec] = field(default_factory=list)

    def _generate_summary(self) -> str:
        count = len(self.breakpoints)
        if count == 0:
            return "No breakpoints set"
        if count == 1:
            return "1 breakpoint set"
        return f"{count} breakpoints set"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize breakpoint list response structure."""
        response["data"]["breakpoints"] = self.breakpoints
        response["data"]["count"] = len(self.breakpoints)
        return response
