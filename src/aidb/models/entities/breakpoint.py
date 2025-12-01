"""Breakpoint entity models."""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypedDict


class BreakpointSpec(TypedDict, total=False):
    """Unified breakpoint specification schema.

    This TypedDict defines the standard format for all breakpoint specifications
    across the entire AIDB stack. All breakpoint inputs must conform to this schema.

    Attributes
    ----------
    file : str
        Path to the source file (absolute or relative).
        Required field.
    line : int
        Line number for the breakpoint (1-based).
        Required field (unless column is specified for minified files).
    column : int, optional
        Column number for precise placement in minified code (1-based).
    condition : str, optional
        Conditional expression that must evaluate to true to trigger the breakpoint.
        Example: "x > 5 and y < 10"
    hit_condition : str, optional
        Expression controlling how many hits are required to trigger.
        Examples: "5" (exactly 5 hits), ">5" (more than 5), "%5" (every 5th hit)
    log_message : str, optional
        Message to log instead of pausing execution (creates a logpoint).
        Can include expressions in curly braces: "x = {x}, y = {y}"
    """

    file: str
    line: int
    column: int | None
    condition: str | None
    hit_condition: str | None
    log_message: str | None


class BreakpointState(Enum):
    """State of a breakpoint."""

    PENDING = auto()
    VERIFIED = auto()
    UNVERIFIED = auto()
    ERROR = auto()


class HitConditionMode(Enum):
    """Supported hit condition expression modes."""

    EXACT = auto()  # "5" - stops on exactly the 5th hit
    MODULO = auto()  # "%5" - stops on every 5th hit
    GREATER_THAN = auto()  # ">5" - stops after 5 hits
    GREATER_EQUAL = auto()  # ">=5" - stops on 5th hit and after
    LESS_THAN = auto()  # "<5" - stops before 5th hit
    LESS_EQUAL = auto()  # "<=5" - stops on hits 1-5
    EQUALS = auto()  # "==5" or "===5" - same as EXACT

    @classmethod
    def parse(cls, expression: str) -> tuple["HitConditionMode", int]:
        """Parse a hit condition expression to determine its mode and value.

        Parameters
        ----------
        expression : str
            The hit condition expression to parse

        Returns
        -------
        Tuple[HitConditionMode, int]
            The mode and numeric value

        Raises
        ------
        ValueError
            If the expression format is invalid
        """
        expr = expression.strip()
        if not expr:
            msg = "Empty hit condition expression"
            raise ValueError(msg)

        # Match JavaScript adapter's regex pattern
        pattern = r"^(>|>=|={1,3}|<|<=|%)?\s*([0-9]+)$"
        match = re.match(pattern, expr)

        if not match:
            msg = f"Invalid hit condition format: {expression}"
            raise ValueError(msg)

        operator = match.group(1) or ""
        value = int(match.group(2))

        # Map operators to modes
        if operator in ("==", "==="):
            return cls.EQUALS, value
        if operator == "=" or not operator:
            return cls.EXACT, value
        if operator == "%":
            return cls.MODULO, value
        if operator == ">":
            return cls.GREATER_THAN, value
        if operator == ">=":
            return cls.GREATER_EQUAL, value
        if operator == "<":
            return cls.LESS_THAN, value
        if operator == "<=":
            return cls.LESS_EQUAL, value
        msg = f"Unknown hit condition operator: {operator}"
        raise ValueError(msg)


@dataclass(frozen=True)
class AidbBreakpoint:
    """Information about a breakpoint."""

    id: int
    source_path: str
    line: int
    verified: bool
    state: BreakpointState
    message: str = ""
    column: int = 0
    condition: str = ""
    hit_condition: str = ""
    log_message: str = ""
    # Optional fields for specific breakpoint types
    data_id: str = ""  # For data breakpoints
    access_type: str = ""  # For data breakpoints

    @property
    def is_verified(self) -> bool:
        """Check if breakpoint is verified."""
        return self.verified

    @property
    def has_condition(self) -> bool:
        """Check if breakpoint has a condition."""
        return bool(self.condition)

    @property
    def has_hit_condition(self) -> bool:
        """Check if breakpoint has a hit condition."""
        return bool(self.hit_condition)
