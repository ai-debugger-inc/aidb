"""Execution handlers package.

Aggregates execution-related handlers for control, stepping, and run-until operations.
"""

from __future__ import annotations

from .control import HANDLERS as CONTROL_HANDLERS
from .run_until import HANDLERS as RUN_UNTIL_HANDLERS
from .stepping import HANDLERS as STEPPING_HANDLERS

# Aggregate all handler dictionaries
HANDLERS = {
    **CONTROL_HANDLERS,
    **STEPPING_HANDLERS,
    **RUN_UNTIL_HANDLERS,
}

__all__ = [
    "HANDLERS",
]
