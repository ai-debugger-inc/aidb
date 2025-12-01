"""Tests for execution response classes."""

import pytest

from aidb_mcp.core.constants import ResponseFieldName
from aidb_mcp.responses.execution import ExecuteResponse, RunUntilResponse, StepResponse


class TestExecuteResponse:
    """Test ExecuteResponse functionality."""

    def test_generates_summary_for_breakpoint(self):
        """Test summary generation when stopped at breakpoint."""
        response = ExecuteResponse(
            action="continue",
            stopped=True,
            stop_reason="breakpoint",
            location="test.py:10",
        )

        assert "breakpoint" in response.summary.lower()
        assert "test.py:10" in response.summary

    def test_generates_summary_for_exception(self):
        """Test summary generation when exception occurs."""
        response = ExecuteResponse(
            action="run",
            stopped=True,
            stop_reason="exception",
            location="test.py:5",
        )

        assert "exception" in response.summary.lower()
        assert "test.py:5" in response.summary

    def test_generates_summary_for_termination(self):
        """Test summary generation when program completes."""
        response = ExecuteResponse(
            action="continue",
            terminated=True,
        )

        assert "completed" in response.summary.lower()

    def test_includes_code_context_in_summary(self):
        """Test code context is included in summary when available."""
        code_context = {
            ResponseFieldName.FORMATTED: "File: test.py\n 10→     x = 5",
        }

        response = ExecuteResponse(
            action="continue",
            stopped=True,
            stop_reason="breakpoint",
            location="test.py:10",
            code_context=code_context,
        )

        assert "x = 5" in response.summary

    def test_customizes_response_with_execution_state(self):
        """Test response includes execution_state dict."""
        response = ExecuteResponse(
            action="continue",
            stopped=True,
            stop_reason="breakpoint",
            has_breakpoints=True,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.EXECUTION_STATE in result["data"]
        exec_state = result["data"][ResponseFieldName.EXECUTION_STATE]
        assert exec_state[ResponseFieldName.STATUS] == "stopped_at_breakpoint"
        assert exec_state[ResponseFieldName.BREAKPOINTS_ACTIVE] is True

    def test_customizes_response_with_code_snapshot(self):
        """Test response includes code_snapshot when context available."""
        code_context = {ResponseFieldName.FORMATTED: "test code"}

        response = ExecuteResponse(
            action="continue",
            stopped=True,
            code_context=code_context,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.CODE_SNAPSHOT in result["data"]
        assert (
            result["data"][ResponseFieldName.CODE_SNAPSHOT][ResponseFieldName.FORMATTED]
            == "test code"
        )


class TestStepResponse:
    """Test StepResponse functionality."""

    def test_generates_summary_with_location(self):
        """Test summary includes step action and location."""
        response = StepResponse(
            action="over",
            location="test.py:15",
        )

        assert "over" in response.summary
        assert "test.py:15" in response.summary

    def test_generates_summary_without_location(self):
        """Test summary when location not available."""
        response = StepResponse(
            action="into",
        )

        assert "into" in response.summary
        assert "completed" in response.summary

    def test_replaces_underscores_in_action(self):
        """Test action with underscores is formatted properly."""
        response = StepResponse(
            action="step_over",
            location="test.py:10",
        )

        assert "step over" in response.summary

    def test_includes_code_context_in_summary(self):
        """Test code context appears in summary."""
        code_context = {ResponseFieldName.FORMATTED: "File: test.py\n 15  return x"}

        response = StepResponse(
            action="over",
            location="test.py:15",
            code_context=code_context,
        )

        assert "return x" in response.summary

    def test_customizes_response_with_frame_info(self):
        """Test frame_info is included when present."""
        frame_info = {"id": 1, "name": "main", "line": 15}

        response = StepResponse(
            action="over",
            location="test.py:15",
            frame_info=frame_info,
        )

        result = response.to_mcp_response()

        assert "frame" in result["data"]
        assert result["data"]["frame"]["name"] == "main"


class TestRunUntilResponse:
    """Test RunUntilResponse functionality."""

    def test_generates_summary_when_target_reached(self):
        """Test summary when target location is reached."""
        response = RunUntilResponse(
            target_location="test.py:20",
            reached_target=True,
            actual_location="test.py:20",
        )

        assert "test.py:20" in response.summary

    def test_generates_summary_when_completed_before_target(self):
        """Test summary when program completes before target."""
        response = RunUntilResponse(
            target_location="test.py:100",
            reached_target=False,
            stop_reason="completed",
        )

        assert "completed" in response.summary.lower()
        assert "target" not in response.summary or "without" in response.summary.lower()

    def test_generates_summary_when_stopped_before_target(self):
        """Test summary when stopped for other reason."""
        response = RunUntilResponse(
            target_location="test.py:50",
            reached_target=False,
            stop_reason="exception",
        )

        assert "stopped" in response.summary.lower()
        assert "exception" in response.summary

    def test_customizes_response_with_reached_target(self):
        """Test response includes reached_target field."""
        response = RunUntilResponse(
            target_location="test.py:20",
            reached_target=True,
            actual_location="test.py:20",
        )

        result = response.to_mcp_response()

        assert "reached_target" in result["data"]
        assert result["data"]["reached_target"] is True

    def test_customizes_response_with_current_location(self):
        """Test response includes current_location when different from target."""
        response = RunUntilResponse(
            target_location="test.py:20",
            reached_target=False,
            actual_location="test.py:18",
            stop_reason="exception",
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.CURRENT_LOCATION in result["data"]
        assert result["data"][ResponseFieldName.CURRENT_LOCATION] == "test.py:18"

    def test_customizes_response_with_stop_reason(self):
        """Test response includes stop_reason in execution_state."""
        response = RunUntilResponse(
            target_location="test.py:20",
            reached_target=False,
            stop_reason="exception",
        )

        result = response.to_mcp_response()

        # stop_reason is moved into execution_state by deduplicator
        assert ResponseFieldName.EXECUTION_STATE in result["data"]
        exec_state = result["data"][ResponseFieldName.EXECUTION_STATE]
        assert exec_state[ResponseFieldName.STOP_REASON] == "exception"
