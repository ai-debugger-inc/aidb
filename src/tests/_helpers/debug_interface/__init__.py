"""Debug interface abstraction for MCP testing.

This module provides a unified interface for testing via the MCP entry point.
"""

from tests._helpers.debug_interface.base import DebugInterface
from tests._helpers.debug_interface.mcp_interface import MCPInterface

__all__ = ["DebugInterface", "MCPInterface"]
