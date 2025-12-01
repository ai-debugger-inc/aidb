"""Package entrypoint for AIDB MCP server.

Allows running the server with `python -m aidb_mcp`.
"""

from __future__ import annotations

from aidb_mcp.server.cli import main

if __name__ == "__main__":
    main()
