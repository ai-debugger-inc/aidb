"""Tool registry access via central registry.

Provides a stable surface for callers to access the tool handlers mapping without
importing the handlers registry directly, helping avoid cycles.
"""

from __future__ import annotations

from typing import Any

from ..registry import get_tool_handlers


def _ensure_handlers_loaded() -> None:
    # Lazy-import the handlers registry to populate the central registry if needed
    if not get_tool_handlers():
        # Import triggers population via load_tool_mapping in handlers.registry
        from ..handlers import registry as _  # noqa: F401


# Ensure central registry has been populated
_ensure_handlers_loaded()

# Expose a snapshot view; callers needing live view can call get_tool_handlers()
TOOL_HANDLERS = get_tool_handlers()


async def handle_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Handle a tool invocation by name and arguments.

    Parameters
    ----------
    name : str
        Tool name
    args : dict
        Tool arguments

    Returns
    -------
    dict
        Tool execution result
    """
    # Defer import to avoid import-time cycles
    from ..handlers.registry import handle_tool as _handle

    return await _handle(name, args)


__all__ = ["TOOL_HANDLERS", "handle_tool"]
