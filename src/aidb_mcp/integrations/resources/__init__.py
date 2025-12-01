"""MCP Resources for debugging sessions, breakpoints, and watches.

This package provides MCP resource definitions that expose debugging state as queryable
and manageable resources.
"""

from __future__ import annotations

from .deletion import delete_resource
from .listing import (
    get_all_resources,
    get_breakpoint_resources,
    get_session_resources,
    get_watch_resources,
)
from .reading import read_resource


class ResourceType:
    """Constants for resource types."""

    SESSION = "session"
    BREAKPOINT = "breakpoint"
    WATCH = "watch"


__all__ = [
    "ResourceType",
    "get_session_resources",
    "get_breakpoint_resources",
    "get_watch_resources",
    "get_all_resources",
    "read_resource",
    "delete_resource",
]
