"""Result container for adapter download operations."""

from typing import Any


class AdapterDownloaderResult:
    """Result container for adapter download operations."""

    def __init__(
        self,
        success: bool,
        message: str,
        language: str | None = None,
        path: str | None = None,
        status: str | None = None,
        instructions: str | None = None,
        error: str | None = None,
        **kwargs,
    ):
        self.success = success
        self.message = message
        self.language = language
        self.path = path
        self.status = status or ("success" if success else "error")
        self.instructions = instructions
        self.error = error
        self.extra = kwargs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "success": self.success,
            "status": self.status,
            "message": self.message,
        }

        if self.language:
            result["language"] = self.language
        if self.path:
            result["path"] = self.path
        if self.instructions:
            result["instructions"] = self.instructions
        if self.error:
            result["error"] = self.error

        result.update(self.extra)
        return result
