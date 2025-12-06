"""Base response classes and protocol for MCP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from aidb_logging import get_mcp_logger as get_logger

from ..core.constants import MCPResponseField, ParamName

if TYPE_CHECKING:
    from ..core.types import ErrorContext, ToolAction

logger = get_logger(__name__)


@runtime_checkable
class MCPResponseProtocol(Protocol):
    """Protocol defining what an MCP response must provide."""

    def to_mcp_response(self) -> dict[str, Any]:
        """Convert to MCP wire format.

        Returns
        -------
        Dict[str, Any]
            Response in MCP format with success, summary, data, etc.
        """
        ...


@dataclass
class Response:
    """Base response class with smart defaults and auto-serialization.

    This class automatically:
    - Generates summaries if not provided
    - Extracts dataclass fields into the data dict
    - Adds next_steps if defined
    - Handles session_id at top level
    """

    summary: str = ""
    success: bool = True
    session_id: str | None = None

    @property
    def always_include_next_steps(self) -> bool:
        """Whether to always include next_steps regardless of compact mode.

        Override in subclasses that should always provide guidance (e.g., init,
        session_start) even in compact mode.

        Returns
        -------
        bool
            True to force next_steps inclusion, False to respect compact mode
        """
        return False

    def __post_init__(self):
        """Auto-generate summary if not provided."""
        if not self.summary:
            self.summary = self._generate_summary()

    def _generate_summary(self) -> str:
        """Generate a summary for this response.

        Override in subclasses to provide context-specific summaries.

        Returns
        -------
        str
            Generated summary text
        """
        return (
            "Operation completed successfully" if self.success else "Operation failed"
        )

    def to_mcp_response(self) -> dict[str, Any]:
        """Convert to MCP wire format with automatic field extraction.

        Returns
        -------
        Dict[str, Any]
            Response in MCP format
        """
        response: dict[str, Any] = {
            MCPResponseField.SUCCESS: self.success,
            MCPResponseField.SUMMARY: self.summary,
            MCPResponseField.DATA: {},
        }

        # Auto-extract all dataclass fields into data
        # Skip base fields, session_id (added at top level), and None values
        base_fields = {
            MCPResponseField.SUMMARY,
            MCPResponseField.SUCCESS,
            MCPResponseField.ERROR_CODE,
            MCPResponseField.ERROR_MESSAGE,
            ParamName.SESSION_ID,
        }
        extracted_fields = []
        for key, value in asdict(self).items():
            if key not in base_fields and value is not None:
                response[MCPResponseField.DATA][key] = value
                extracted_fields.append(key)

        # Add session_id at top level if present
        if self.session_id:
            response[ParamName.SESSION_ID] = self.session_id

        # Add next steps based on response type and mode
        # - Always include for init/session_start (entry points need guidance)
        # - Include in verbose mode for other operations (human-friendly)
        # - Skip in compact mode for other operations (save 100-200 tokens)
        from aidb_common.config.runtime import ConfigManager

        config_mgr = ConfigManager()
        next_steps = self.get_next_steps()
        should_include = next_steps and (
            self.always_include_next_steps or config_mgr.is_mcp_verbose()
        )

        if should_include and next_steps:  # Type narrow for mypy
            response[MCPResponseField.NEXT_STEPS] = next_steps

        # Allow subclasses to customize response before deduplication
        response = self._customize_response(response)

        # Apply deduplication ONCE at the end (centralized)
        from .deduplicator import ResponseDeduplicator

        return ResponseDeduplicator.deduplicate(response)

    def _customize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Customize response before deduplication (override in subclasses).

        Override this method instead of to_mcp_response() to avoid
        deduplication issues and ensure proper token optimization.

        Parameters
        ----------
        response : dict
            The base response dict with success, summary, data, etc.

        Returns
        -------
        dict
            The customized response dict

        Notes
        -----
        The deduplicator will run automatically after this method,
        so you don't need to call it manually.
        """
        return response

    def get_next_steps(self) -> list[ToolAction] | None:
        """Get contextual next steps for this response.

        Override in subclasses to provide context-specific next steps.

        Returns
        -------
        Optional[List[ToolAction]]
            List of next step dictionaries or None
        """
        return None


@dataclass
class ErrorResponse(Response):
    """Base class for error responses with automatic success=False."""

    success: bool = field(default=False, init=False)
    error_code: str = ""
    error_message: str = ""
    context: ErrorContext | None = None

    def __post_init__(self):
        """Ensure success is False and generate summary."""
        self.success = False
        logger.debug(
            "Error response initialized",
            extra={
                "error_type": self.__class__.__name__,
                "error_code": self.error_code,
                "has_context": self.context is not None,
            },
        )
        super().__post_init__()

    def _generate_summary(self) -> str:
        """Generate error summary from error message if not provided."""
        if self.error_message:
            # Take first sentence or line of error message
            first_line = self.error_message.split("\n")[0]
            return first_line.split(". ")[0]
        return "Operation failed"

    def to_mcp_response(self) -> dict[str, Any]:
        """Convert to MCP wire format with error information.

        Returns
        -------
        Dict[str, Any]
            Response in MCP format with error field
        """
        response = super().to_mcp_response()

        # Add error information
        if self.error_code or self.error_message:
            response["error"] = {
                "code": self.error_code,
                "message": self.error_message or self.summary,
            }
            logger.debug(
                "Error details added to response",
                extra={
                    "error_type": self.__class__.__name__,
                    "error_code": self.error_code,
                    "has_message": bool(self.error_message),
                    "has_context": self.context is not None,
                },
            )

        # Ensure success is False
        response[MCPResponseField.SUCCESS] = False

        # Apply deduplication in compact mode
        from .deduplicator import ResponseDeduplicator

        return ResponseDeduplicator.deduplicate(response)
