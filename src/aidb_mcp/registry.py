"""Central registry for MCP tool handlers.

Provides a single source of truth for tool handler registration to avoid cross-package
imports between handlers and tools.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class ToolRegistry:
    """Registry for managing MCP tool handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        """Register a tool handler.

        Parameters
        ----------
        name : str
            The tool name.
        handler : Handler
            The handler function.
        """
        self._handlers[name] = handler

    def load_from_dict(self, mapping: dict[str, Handler]) -> None:
        """Load multiple handlers from a dictionary.

        Parameters
        ----------
        mapping : dict[str, Handler]
            Dictionary of tool names to handlers.
        """
        self._handlers.update(mapping)

    def get(self, name: str) -> Handler | None:
        """Get a handler by name.

        Parameters
        ----------
        name : str
            The tool name.

        Returns
        -------
        Handler | None
            The handler if found, None otherwise.
        """
        return self._handlers.get(name)

    def all(self) -> dict[str, Handler]:
        """Get all registered handlers.

        Returns
        -------
        dict[str, Handler]
            Dictionary of all handlers.
        """
        return self._handlers

    def names(self) -> list[str]:
        """Get all registered tool names.

        Returns
        -------
        list[str]
            List of tool names.
        """
        return list(self._handlers.keys())

    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()


# Module-level singleton
_REGISTRY = ToolRegistry()


def register_tool(name: str, handler: Handler) -> None:
    """Register a tool handler in the global registry.

    Parameters
    ----------
    name : str
        The tool name.
    handler : Handler
        The handler function.
    """
    _REGISTRY.register(name, handler)


def load_tool_mapping(mapping: dict[str, Handler]) -> None:
    """Load multiple tool handlers into the global registry.

    Parameters
    ----------
    mapping : dict[str, Handler]
        Dictionary of tool names to handlers.
    """
    _REGISTRY.load_from_dict(mapping)


def get_tool(name: str) -> Handler | None:
    """Get a tool handler from the global registry.

    Parameters
    ----------
    name : str
        The tool name.

    Returns
    -------
    Handler | None
        The handler if found, None otherwise.
    """
    return _REGISTRY.get(name)


def get_tool_handlers() -> dict[str, Handler]:
    """Get all registered tool handlers.

    Returns
    -------
    dict[str, Handler]
        Dictionary of all handlers.
    """
    return _REGISTRY.all()


def get_tool_names() -> list[str]:
    """Get all registered tool names.

    Returns
    -------
    list[str]
        List of tool names.
    """
    return _REGISTRY.names()


def clear_registry() -> None:
    """Clear all registered tool handlers from the global registry."""
    _REGISTRY.clear()
