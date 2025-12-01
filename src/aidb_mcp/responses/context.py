"""Context-related response classes for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Response


@dataclass
class ContextResponse(Response):
    """Response for context operations."""

    context_data: dict[str, Any] = field(default_factory=dict)
    session_active: bool = False
    session_id: str | None = None
    suggestions: list[str] | None = None
    detail_level: str = "detailed"  # "brief", "detailed", "full"

    def _generate_summary(self) -> str:
        if self.session_active:
            return "Debug context retrieved with active session"
        return "Debug context retrieved"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize context response structure."""
        # Move context_data contents to top level of data
        response["data"]["context"] = self.context_data

        # Remove redundant context_data field
        if "context_data" in response["data"]:
            del response["data"]["context_data"]

        # Add suggestions if present
        if self.suggestions:
            response["data"]["suggestions"] = self.suggestions

        return response
