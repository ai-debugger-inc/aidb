"""Context awareness and guidance handlers.

This package provides debugging context analysis:
- Context awareness (state, location, history)
- Pattern analysis (debugging insights)
- Guidance suggestions (next actions)
"""

from __future__ import annotations

from .handler import HANDLERS

__all__ = ["HANDLERS"]
