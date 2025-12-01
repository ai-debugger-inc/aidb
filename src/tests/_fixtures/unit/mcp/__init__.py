"""Centralized MCP fixtures for unit testing.

These fixtures mock the aidb core layer so MCP tests can test MCP logic in isolation.
"""

from tests._fixtures.unit.mcp.config import *  # noqa: F401, F403
from tests._fixtures.unit.mcp.debug_api import *  # noqa: F401, F403
from tests._fixtures.unit.mcp.session_context import *  # noqa: F401, F403
from tests._fixtures.unit.mcp.state import *  # noqa: F401, F403
