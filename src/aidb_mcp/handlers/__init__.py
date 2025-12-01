"""Consolidated MCP tool handlers organized by domain.

This package contains handlers organized by functional domain:
- session: Session lifecycle and configuration
- execution: Program execution and control flow
- inspection: Variable and state introspection
- workflow: High-level debugging workflows
- context: Context awareness and guidance
"""

from __future__ import annotations

from .registry import TOOL_HANDLERS, handle_tool

__all__ = [
    "TOOL_HANDLERS",
    "handle_tool",
]
