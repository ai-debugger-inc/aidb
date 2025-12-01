"""Runtime helpers for MCP server.

Contains lazy configuration access to avoid heavy imports when the CLI is used only for
help or metadata actions.
"""

from __future__ import annotations

_CONFIG = None


def get_runtime_config():
    """Get the global MCP configuration lazily.

    Defers importing the configuration machinery until actually needed to keep "python
    -m aidb_mcp --help" fast and side-effect free.
    """
    global _CONFIG
    if _CONFIG is None:
        from aidb_mcp.core.config import get_config as _gc

        _CONFIG = _gc()
    return _CONFIG
