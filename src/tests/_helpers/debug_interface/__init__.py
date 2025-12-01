"""Debug interface abstraction for unified MCP and API testing.

This module provides a unified interface for testing both MCP and API entry points with
the same test logic, eliminating duplication.
"""

from tests._helpers.debug_interface.api_interface import APIInterface
from tests._helpers.debug_interface.base import DebugInterface
from tests._helpers.debug_interface.mcp_interface import MCPInterface

__all__ = ["DebugInterface", "APIInterface", "MCPInterface"]
