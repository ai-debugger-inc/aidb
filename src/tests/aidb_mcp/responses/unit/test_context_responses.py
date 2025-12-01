"""Tests for context response classes."""

import pytest

from aidb_mcp.core.constants import MCPResponseField
from aidb_mcp.responses.context import ContextResponse


class TestContextResponse:
    """Test ContextResponse functionality."""

    def test_generates_summary_with_active_session(self):
        """Test summary indicates active session when session_active=True."""
        response = ContextResponse(
            context_data={"test": "data"},
            session_active=True,
            session_id="test-123",
        )

        assert "active" in response.summary.lower()
        assert "session" in response.summary.lower()

    def test_generates_summary_without_active_session(self):
        """Test summary indicates no active session when session_active=False."""
        response = ContextResponse(context_data={"test": "data"}, session_active=False)

        assert "context retrieved" in response.summary.lower()

    def test_context_data_in_response(self):
        """Test context_data is properly included in response."""
        context_data = {"current_frame": 0, "breakpoints": []}
        response = ContextResponse(context_data=context_data, session_active=True)

        mcp_response = response.to_mcp_response()

        assert MCPResponseField.DATA in mcp_response
        assert "context" in mcp_response[MCPResponseField.DATA]
        assert mcp_response[MCPResponseField.DATA]["context"] == context_data

    def test_suggestions_included_when_provided(self):
        """Test suggestions are included in response when provided."""
        suggestions = ["Try step over", "Check local variables"]
        response = ContextResponse(
            context_data={},
            session_active=True,
            suggestions=suggestions,
        )

        mcp_response = response.to_mcp_response()

        assert "suggestions" in mcp_response[MCPResponseField.DATA]
        assert mcp_response[MCPResponseField.DATA]["suggestions"] == suggestions

    def test_suggestions_not_included_when_none(self):
        """Test suggestions are not included when None."""
        response = ContextResponse(
            context_data={},
            session_active=True,
            suggestions=None,
        )

        mcp_response = response.to_mcp_response()

        assert "suggestions" not in mcp_response[MCPResponseField.DATA]

    def test_session_id_at_top_level(self):
        """Test session_id is included at top level when provided."""
        session_id = "test-session-123"
        response = ContextResponse(
            context_data={},
            session_active=True,
            session_id=session_id,
        )

        mcp_response = response.to_mcp_response()

        assert "session_id" in mcp_response
        assert mcp_response["session_id"] == session_id

    def test_detail_level_in_data(self):
        """Test detail_level is included in response data."""
        response = ContextResponse(
            context_data={},
            session_active=True,
            detail_level="full",
        )

        mcp_response = response.to_mcp_response()

        assert "detail_level" in mcp_response[MCPResponseField.DATA]
        assert mcp_response[MCPResponseField.DATA]["detail_level"] == "full"
