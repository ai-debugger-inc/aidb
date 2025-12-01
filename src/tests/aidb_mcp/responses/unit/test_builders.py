"""Tests for response builder utilities."""

import pytest

from aidb_mcp.core.constants import DetailedExecutionStatus, ResponseFieldName
from aidb_mcp.responses.builders import CodeSnapshotBuilder, ExecutionStateBuilder


class TestExecutionStateBuilder:
    """Test ExecutionStateBuilder functionality."""

    def test_builds_basic_execution_state(self):
        """Test building basic execution state dict."""
        result = ExecutionStateBuilder.build(
            detailed_status=DetailedExecutionStatus.STOPPED_AT_BREAKPOINT,
            has_breakpoints=True,
            stop_reason="breakpoint",
        )

        assert result[ResponseFieldName.STATUS] == "stopped_at_breakpoint"
        assert result[ResponseFieldName.BREAKPOINTS_ACTIVE] is True
        assert result[ResponseFieldName.STOP_REASON] == "breakpoint"

    def test_builds_state_without_stop_reason(self):
        """Test building state when no stop reason provided."""
        result = ExecutionStateBuilder.build(
            detailed_status=DetailedExecutionStatus.RUNNING,
            has_breakpoints=False,
        )

        assert result[ResponseFieldName.STATUS] == "running"
        assert result[ResponseFieldName.BREAKPOINTS_ACTIVE] is False
        assert result[ResponseFieldName.STOP_REASON] is None

    def test_builds_terminated_state(self):
        """Test building terminated execution state."""
        result = ExecutionStateBuilder.build(
            detailed_status=DetailedExecutionStatus.TERMINATED,
            has_breakpoints=True,
            stop_reason="completed",
        )

        assert result[ResponseFieldName.STATUS] == "terminated"
        assert result[ResponseFieldName.BREAKPOINTS_ACTIVE] is True
        assert result[ResponseFieldName.STOP_REASON] == "completed"

    def test_handles_various_detailed_statuses(self):
        """Test all DetailedExecutionStatus variants."""
        statuses = [
            DetailedExecutionStatus.STOPPED_AT_BREAKPOINT,
            DetailedExecutionStatus.STOPPED_AT_EXCEPTION,
            DetailedExecutionStatus.STOPPED_AFTER_STEP,
            DetailedExecutionStatus.RUNNING_TO_BREAKPOINT,
            DetailedExecutionStatus.RUNNING,
            DetailedExecutionStatus.TERMINATED,
            DetailedExecutionStatus.PAUSED,
        ]

        for status in statuses:
            result = ExecutionStateBuilder.build(
                detailed_status=status,
                has_breakpoints=True,
            )
            assert result[ResponseFieldName.STATUS] == status.value


class TestCodeSnapshotBuilder:
    """Test CodeSnapshotBuilder functionality."""

    def test_builds_code_snapshot_with_formatted(self):
        """Test building code snapshot from code context."""
        code_context = {
            ResponseFieldName.FORMATTED: "File: test.py\n 1  def foo():\n 2→     return 42",
        }

        result = CodeSnapshotBuilder.build(code_context=code_context)

        assert result is not None
        assert ResponseFieldName.FORMATTED in result
        assert "def foo():" in result[ResponseFieldName.FORMATTED]

    def test_returns_none_when_no_code_context(self):
        """Test returns None when code context is missing."""
        result = CodeSnapshotBuilder.build(code_context=None)

        assert result is None

    def test_handles_empty_formatted_string(self):
        """Test handles empty formatted string."""
        code_context = {ResponseFieldName.FORMATTED: ""}

        result = CodeSnapshotBuilder.build(code_context=code_context)

        assert result is not None
        assert result[ResponseFieldName.FORMATTED] == ""

    def test_handles_missing_formatted_key(self):
        """Test handles dict without formatted key."""
        code_context = {"other_field": "value"}

        result = CodeSnapshotBuilder.build(code_context=code_context)

        assert result is not None
        assert result[ResponseFieldName.FORMATTED] == ""

    def test_ignores_location_parameter(self):
        """Test location parameter is kept for API compatibility but unused."""
        code_context = {
            ResponseFieldName.FORMATTED: "File: test.py\n 1  def foo():\n",
        }

        result = CodeSnapshotBuilder.build(
            code_context=code_context,
            location="test.py:1",
        )

        # Location should not appear in result (kept at response level)
        assert result is not None
        assert "location" not in result
        assert ResponseFieldName.FORMATTED in result

    def test_ignores_fallback_target_parameter(self):
        """Test fallback_target parameter is kept for API compatibility."""
        code_context = {ResponseFieldName.FORMATTED: "test"}

        result = CodeSnapshotBuilder.build(
            code_context=code_context,
            fallback_target="test.py",
        )

        # Fallback target should not appear in result
        assert result is not None
        assert "target" not in result
        assert "fallback_target" not in result
