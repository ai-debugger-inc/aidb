"""Inspection handlers package.

Aggregates inspection-related handlers for state inspection, variables, and breakpoints.
"""

from __future__ import annotations

from .breakpoints import HANDLERS as BREAKPOINT_HANDLERS
from .state_inspection import HANDLERS as INSPECT_HANDLERS
from .variables import HANDLERS as VARIABLE_HANDLERS

# Aggregate all handler dictionaries
HANDLERS = {
    **INSPECT_HANDLERS,
    **VARIABLE_HANDLERS,
    **BREAKPOINT_HANDLERS,
}

__all__ = [
    "HANDLERS",
]
