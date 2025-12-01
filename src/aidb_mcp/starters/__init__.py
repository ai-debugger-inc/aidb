"""MCP Starters - Language-specific debugging guidance generators.

This subpackage provides language and framework-specific debugging examples
and guidance for the MCP start tool, without requiring session initialization.
"""

from __future__ import annotations

from .base import BaseStarter
from .registry import StarterRegistry

__all__ = ["BaseStarter", "StarterRegistry"]
