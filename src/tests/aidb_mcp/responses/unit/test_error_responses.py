"""Tests for error response classes."""

import pytest

from aidb_mcp.core.constants import MCPResponseField
from aidb_mcp.core.exceptions import ErrorCode
from aidb_mcp.responses.errors import (
    InternalError,
    InvalidParameterError,
    NoSessionError,
)


class TestErrorResponseBase:
    """Test ErrorResponse base class functionality."""

    def test_error_response_sets_success_false(self):
        """Test that error responses always have success=False."""
        error = NoSessionError(requested_operation="inspect")

        response = error.to_mcp_response()

        assert response[MCPResponseField.SUCCESS] is False

    def test_error_response_includes_error_code(self):
        """Test that error responses include error_code field."""
        error = NoSessionError(requested_operation="inspect")

        response = error.to_mcp_response()

        assert "error" in response
        assert "code" in response["error"]
        assert response["error"]["code"] == ErrorCode.AIDB_SESSION_NOT_FOUND.value


class TestNoSessionError:
    """Test NoSessionError functionality."""

    def test_generates_summary_with_operation(self):
        """Test summary includes requested operation when provided."""
        error = NoSessionError(requested_operation="inspect")

        assert "inspect" in error.summary.lower()

    def test_generates_summary_without_operation(self):
        """Test summary has default message when operation not provided."""
        error = NoSessionError()

        assert "no active" in error.summary.lower()
        assert "session" in error.summary.lower()

    def test_includes_next_steps(self):
        """Test that NoSessionError includes next steps."""
        error = NoSessionError()

        next_steps = error.get_next_steps()

        assert next_steps is not None
        assert len(next_steps) > 0


class TestInvalidParameterError:
    """Test InvalidParameterError functionality."""

    def test_generates_summary_with_parameter_name(self):
        """Test summary includes parameter name when provided."""
        error = InvalidParameterError(
            parameter_name="target",
            expected_type="string",
        )

        assert "target" in error.summary.lower()
        assert "string" in error.summary.lower()

    def test_generates_summary_with_parameter_name_only(self):
        """Test summary with parameter name but no expected type."""
        error = InvalidParameterError(parameter_name="target")

        assert "target" in error.summary.lower()

    def test_generates_default_summary(self):
        """Test summary has default message when nothing provided."""
        error = InvalidParameterError()

        assert "invalid parameter" in error.summary.lower()

    def test_includes_error_code(self):
        """Test that InvalidParameterError has correct error code."""
        error = InvalidParameterError(parameter_name="target")

        response = error.to_mcp_response()

        assert (
            response["error"]["code"] == ErrorCode.AIDB_VALIDATION_INVALID_FORMAT.value
        )


class TestInternalError:
    """Test InternalError functionality."""

    def test_generates_summary_with_operation(self):
        """Test summary includes operation when provided."""
        error = InternalError(operation="step", details="Unexpected state")

        assert "step" in error.summary.lower()

    def test_generates_summary_with_explicit_summary(self):
        """Test explicit summary is used when provided."""
        explicit_summary = "Custom error message"
        error = InternalError(summary=explicit_summary)

        assert error.summary == explicit_summary

    def test_generates_default_summary(self):
        """Test summary has default message when nothing provided."""
        error = InternalError()

        assert "internal error" in error.summary.lower()

    def test_includes_error_code(self):
        """Test that InternalError has correct error code."""
        error = InternalError()

        response = error.to_mcp_response()

        assert response["error"]["code"] == ErrorCode.AIDB_INTERNAL_ERROR.value

    def test_error_message_in_response(self):
        """Test error message is included in response."""
        error = InternalError(
            error_message="Something went wrong",
            operation="execute",
        )

        response = error.to_mcp_response()

        assert "error" in response
        assert response["error"]["message"] == "Something went wrong"
