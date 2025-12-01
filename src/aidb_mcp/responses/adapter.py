"""Response classes for adapter-related operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import Response


@dataclass
class AdapterDownloadResponse(Response):
    """Response for successful adapter download operation."""

    language: str = ""
    path: str = ""
    status: str = ""
    message: str = ""
    version: str | None = None

    def _generate_summary(self) -> str:
        """Generate summary for adapter download."""
        if self.status == "already_installed":
            return f"{self.language} adapter verified"
        return f"{self.language} adapter {self.status}"


@dataclass
class AdapterBulkDownloadResponse(Response):
    """Response for bulk adapter download operations."""

    adapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    successful: int = 0
    failed: int = 0
    total: int = 0

    def _generate_summary(self) -> str:
        """Generate summary for bulk download."""
        summary = f"Downloaded {self.successful}/{self.total} adapters"
        if self.failed > 0:
            summary += f" ({self.failed} failed)"
        return summary

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize adapter download response with nested summary."""
        # Add nested summary in data
        response["data"]["summary"] = {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
        }
        return response


@dataclass
class AdapterListResponse(Response):
    """Response for listing installed adapters."""

    adapters: dict[str, dict[str, Any]] = field(default_factory=dict)
    total_installed: int = 0
    install_directory: str = ""
    suggestions: list[str] | None = None

    def _generate_summary(self) -> str:
        """Generate summary for adapter list."""
        if self.total_installed > 0:
            plural = "s" if self.total_installed != 1 else ""
            return f"Found {self.total_installed} installed adapter{plural}"
        return "No adapters currently installed"

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize adapter list response with nested summary."""
        # Add nested summary in data
        response["data"]["summary"] = {
            "total_installed": self.total_installed,
            "install_directory": self.install_directory,
        }
        if self.suggestions:
            response["data"]["suggestions"] = self.suggestions
        return response
