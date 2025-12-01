"""Explicit wiring for MCP handlers and registries.

Import order here ensures the central tool registry is populated in a deterministic way,
without relying on lazy side-effects elsewhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aidb_mcp.registry import get_tool_names

if TYPE_CHECKING:
    from collections.abc import Sequence

_wired = False


def wire_handlers() -> Sequence[str]:
    """Import handlers to populate the central registry.

    Returns
    -------
    Sequence[str]
        The list of registered tool names after wiring.
    """
    global _wired
    if not _wired:
        # Importing handlers.registry builds the mapping and loads it into the
        # central registry via load_tool_mapping(). Order here can be extended
        # if we later need to import other groups before tools.
        from aidb_mcp.handlers import registry as _  # noqa: F401

        _wired = True

    return tuple(get_tool_names())
