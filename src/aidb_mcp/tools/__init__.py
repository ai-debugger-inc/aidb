"""MCP debugging tools registry and definitions.

This package provides the clean interface for tool registration, definitions, and
validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .definitions import get_all_mcp_tools
from .registry import TOOL_HANDLERS, handle_tool

if TYPE_CHECKING:
    from mcp.types import Tool

__all__ = [
    # Tool definitions
    "get_all_mcp_tools",
    # Handler registry
    "TOOL_HANDLERS",
    "handle_tool",
]


def get_all_tools() -> list[Tool]:
    """Get all available MCP tools.

    Returns
    -------
    List[Tool]
        Complete list of tool definitions
    """
    return get_all_mcp_tools()
