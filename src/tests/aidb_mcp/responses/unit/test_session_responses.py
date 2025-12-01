"""Tests for session response classes."""

import pytest

from aidb_mcp.core.constants import ResponseFieldName
from aidb_mcp.responses.session import SessionStartResponse


class TestSessionStartResponse:
    """Test SessionStartResponse functionality."""

    def test_generates_summary_with_session_id(self):
        """Test summary includes short session ID and mode."""
        response = SessionStartResponse(
            session_id="abc123def456",
            mode="launch",
        )

        assert "abc123de" in response.summary  # First 8 chars
        assert "launch" in response.summary

    def test_generates_summary_with_default_change(self):
        """Test summary includes default session change."""
        response = SessionStartResponse(
            session_id="new12345",
            mode="launch",
            default_changed=True,
            previous_default_session="old12345",
        )

        assert "default" in response.summary
        assert "old12345"[:8] in response.summary

    def test_generates_summary_with_default_set_first_time(self):
        """Test summary when set as default for first time."""
        response = SessionStartResponse(
            session_id="first123",
            mode="attach",
            default_changed=True,
        )

        assert "default" in response.summary
        assert "was:" not in response.summary.lower()

    def test_always_includes_next_steps_property(self):
        """Test always_include_next_steps returns False (uses base class default).

        SessionStartResponse no longer forces next_steps inclusion. Agents learn from
        schema descriptions, not response payloads.
        """
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
        )

        # Base class returns False - next_steps only included in verbose mode
        assert response.always_include_next_steps is False

    def test_provides_next_steps_for_paused_state(self):
        """Test next steps when session starts paused."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            is_paused=True,
        )

        next_steps = response.get_next_steps()

        assert next_steps is not None
        assert len(next_steps) > 0

    def test_provides_next_steps_with_breakpoints(self):
        """Test next steps when breakpoints are set."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            breakpoints_set=3,
        )

        next_steps = response.get_next_steps()

        assert next_steps is not None
        assert len(next_steps) > 0

    def test_provides_next_steps_without_breakpoints(self):
        """Test next steps when no breakpoints set."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            breakpoints_set=0,
        )

        next_steps = response.get_next_steps()

        assert next_steps is not None
        # Should guide user to set breakpoints first
        assert len(next_steps) > 0

    def test_customizes_response_removes_redundant_fields(self):
        """Test redundant state fields are removed."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            is_paused=True,
            detailed_status="paused",
            stop_reason="breakpoint",
        )

        result = response.to_mcp_response()

        # Redundant fields should be removed
        assert ResponseFieldName.IS_PAUSED not in result["data"]
        assert ResponseFieldName.DETAILED_STATUS not in result["data"]
        assert ResponseFieldName.STOP_REASON not in result["data"]

    def test_customizes_response_adds_execution_state(self):
        """Test execution_state is added to response."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            is_paused=True,
            breakpoints_set=2,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.EXECUTION_STATE in result["data"]
        exec_state = result["data"][ResponseFieldName.EXECUTION_STATE]
        assert exec_state[ResponseFieldName.BREAKPOINTS_ACTIVE] is True

    def test_customizes_response_adds_code_snapshot(self):
        """Test code_snapshot is added when context available."""
        code_context = {ResponseFieldName.FORMATTED: "File: main.py\n 1  def main():"}

        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            code_context=code_context,
            location="main.py:1",
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.CODE_SNAPSHOT in result["data"]
        assert (
            "def main():"
            in result["data"][ResponseFieldName.CODE_SNAPSHOT][
                ResponseFieldName.FORMATTED
            ]
        )

    def test_customizes_response_adds_target_display(self):
        """Test target field is added with display value."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            target="main.py",
        )

        result = response.to_mcp_response()

        assert "target" in result["data"]
        assert result["data"]["target"] == "main.py"

    def test_customizes_response_with_pid_target(self):
        """Test target display for attach mode with PID."""
        response = SessionStartResponse(
            session_id="test",
            mode="attach",
            pid=12345,
        )

        result = response.to_mcp_response()

        assert "target" in result["data"]
        assert "12345" in result["data"]["target"]

    def test_customizes_response_with_host_port_target(self):
        """Test target display for remote attach."""
        response = SessionStartResponse(
            session_id="test",
            mode="remote_attach",
            host="localhost",
            port=5678,
        )

        result = response.to_mcp_response()

        assert "target" in result["data"]
        assert "localhost" in result["data"]["target"]
        assert "5678" in result["data"]["target"]

    def test_infers_paused_status(self):
        """Test detailed status inference for paused state."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            is_paused=True,
        )

        status = response._infer_detailed_status()

        from aidb_mcp.core.constants import DetailedExecutionStatus

        assert status == DetailedExecutionStatus.PAUSED

    def test_infers_running_status(self):
        """Test detailed status inference for running state."""
        response = SessionStartResponse(
            session_id="test",
            mode="launch",
            is_paused=False,
        )

        status = response._infer_detailed_status()

        from aidb_mcp.core.constants import DetailedExecutionStatus

        assert status == DetailedExecutionStatus.RUNNING
