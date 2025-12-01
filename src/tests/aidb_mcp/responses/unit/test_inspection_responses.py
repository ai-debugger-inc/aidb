"""Tests for inspection response classes."""

import pytest

from aidb_mcp.core.constants import InspectTarget, ResponseFieldName
from aidb_mcp.responses.inspection import (
    BreakpointListResponse,
    BreakpointMutationResponse,
    InspectResponse,
    VariableGetResponse,
    VariableSetResponse,
)


class TestInspectResponse:
    """Test InspectResponse functionality."""

    def test_generates_summary_for_expression(self):
        """Test summary for expression evaluation."""
        response = InspectResponse(
            target=InspectTarget.EXPRESSION.value,
            expression="x + y",
            result={"value": "10"},
        )

        assert "x + y" in response.summary

    def test_generates_summary_for_other_targets(self):
        """Test summary for non-expression targets."""
        response = InspectResponse(
            target=InspectTarget.LOCALS.value,
            result={"x": {"value": "5"}},
        )

        assert "locals" in response.summary.lower()

    def test_customizes_response_for_locals(self):
        """Test response structure for locals target."""
        result_data = {"x": {"value": "5"}, "y": {"value": "10"}}

        response = InspectResponse(
            target=InspectTarget.LOCALS.value,
            result=result_data,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.LOCALS in result["data"]
        assert result["data"][ResponseFieldName.LOCALS] == result_data

    def test_customizes_response_for_globals(self):
        """Test response structure for globals target."""
        result_data = {"MODULE": {"value": "__main__"}}

        response = InspectResponse(
            target=InspectTarget.GLOBALS.value,
            result=result_data,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.GLOBALS in result["data"]
        assert result["data"][ResponseFieldName.GLOBALS] == result_data

    def test_customizes_response_for_stack(self):
        """Test response structure for stack target."""
        result_data = [{"id": 1, "name": "main"}, {"id": 2, "name": "helper"}]

        response = InspectResponse(
            target=InspectTarget.STACK.value,
            result=result_data,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.STACK in result["data"]
        assert result["data"][ResponseFieldName.STACK] == result_data

    def test_customizes_response_for_threads(self):
        """Test response structure for threads target."""
        result_data = [{"id": 1, "name": "MainThread"}]

        response = InspectResponse(
            target=InspectTarget.THREADS.value,
            result=result_data,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.THREADS in result["data"]
        assert result["data"][ResponseFieldName.THREADS] == result_data

    def test_customizes_response_for_expression(self):
        """Test response structure for expression target."""
        result_data = {"value": "42", "type_name": "int"}

        response = InspectResponse(
            target=InspectTarget.EXPRESSION.value,
            expression="2 * 21",
            result=result_data,
        )

        result = response.to_mcp_response()

        assert ResponseFieldName.RESULT in result["data"]
        # Expression appears in summary instead of data (token optimization)
        assert "2 * 21" in result["summary"]

    def test_customizes_response_for_all_target(self):
        """Test response structure for ALL target with dict result."""
        result_data = {
            "locals": {"x": {"value": "5"}},
            "globals": {"MODULE": {"value": "__main__"}},
        }

        response = InspectResponse(
            target=InspectTarget.ALL.value,
            result=result_data,
        )

        result = response.to_mcp_response()

        # All dict items should be at top level of data
        assert "locals" in result["data"]
        assert "globals" in result["data"]

    def test_customizes_response_removes_generic_result(self):
        """Test generic 'result' field is removed for non-expression targets."""
        response = InspectResponse(
            target=InspectTarget.LOCALS.value,
            result={"x": {"value": "5"}},
        )

        result = response.to_mcp_response()

        # 'result' should not be present (only 'locals')
        # But it gets deduped, so check that LOCALS is there
        assert ResponseFieldName.LOCALS in result["data"]


class TestVariableGetResponse:
    """Test VariableGetResponse functionality."""

    def test_generates_summary_with_expression(self):
        """Test summary includes variable expression."""
        response = VariableGetResponse(
            expression="user.name",
            value={"value": "John", "type_name": "str"},
        )

        assert "user.name" in response.summary

    def test_customizes_response_renames_value_to_result(self):
        """Test value field is renamed to result."""
        response = VariableGetResponse(
            expression="x",
            value={"value": "42", "type_name": "int"},
        )

        result = response.to_mcp_response()

        # Should have 'result' not 'value'
        assert ResponseFieldName.RESULT in result["data"]
        # Original 'value' should be removed
        assert ResponseFieldName.VALUE not in result["data"]


class TestVariableSetResponse:
    """Test VariableSetResponse functionality."""

    def test_generates_summary_with_variable_name(self):
        """Test summary includes variable name."""
        response = VariableSetResponse(
            name="debug_mode",
            new_value=True,
        )

        assert "debug_mode" in response.summary
        assert "updated" in response.summary.lower()


class TestBreakpointMutationResponse:
    """Test BreakpointMutationResponse functionality."""

    def test_generates_summary_for_set_action(self):
        """Test summary for setting breakpoint."""
        response = BreakpointMutationResponse(
            action="set",
            location="test.py:10",
        )

        assert "set" in response.summary.lower()
        assert "test.py:10" in response.summary

    def test_generates_summary_for_conditional_breakpoint(self):
        """Test summary for conditional breakpoint."""
        response = BreakpointMutationResponse(
            action="set",
            location="test.py:10",
            condition="x > 5",
        )

        assert "conditional" in response.summary.lower()

    def test_generates_summary_for_logpoint(self):
        """Test summary for logpoint."""
        response = BreakpointMutationResponse(
            action="set",
            location="test.py:10",
            log_message="Value: {x}",
        )

        assert "logpoint" in response.summary.lower()

    def test_generates_summary_for_remove_action(self):
        """Test summary for removing breakpoint."""
        response = BreakpointMutationResponse(
            action="remove",
            location="test.py:10",
            affected_count=1,
        )

        assert "removed" in response.summary.lower()
        assert "test.py:10" in response.summary

    def test_generates_summary_for_remove_multiple(self):
        """Test summary for removing multiple breakpoints."""
        response = BreakpointMutationResponse(
            action="remove",
            location="test.py",
            affected_count=3,
        )

        assert "removed 3" in response.summary.lower()

    def test_generates_summary_for_clear_all_action(self):
        """Test summary for clearing all breakpoints."""
        response = BreakpointMutationResponse(
            action="clear_all",
            affected_count=5,
        )

        assert "cleared 5" in response.summary.lower()

    def test_generates_summary_for_clear_all_none(self):
        """Test summary when clearing but none exist."""
        response = BreakpointMutationResponse(
            action="clear_all",
            affected_count=0,
        )

        assert "no breakpoints" in response.summary.lower()


class TestBreakpointListResponse:
    """Test BreakpointListResponse functionality."""

    def test_generates_summary_with_count(self):
        """Test summary includes breakpoint count."""
        breakpoints = [
            {"location": "test.py:10"},
            {"location": "test.py:20"},
        ]

        response = BreakpointListResponse(breakpoints=breakpoints)

        assert "2 breakpoint" in response.summary

    def test_generates_summary_for_single_breakpoint(self):
        """Test summary for single breakpoint."""
        breakpoints = [{"location": "test.py:10"}]

        response = BreakpointListResponse(breakpoints=breakpoints)

        assert "1 breakpoint" in response.summary

    def test_generates_summary_for_no_breakpoints(self):
        """Test summary when no breakpoints set."""
        response = BreakpointListResponse(breakpoints=[])

        assert "no breakpoints" in response.summary.lower()

    def test_customizes_response_adds_count(self):
        """Test response includes breakpoint count."""
        breakpoints = [{"location": "test.py:10"}, {"location": "test.py:20"}]

        response = BreakpointListResponse(breakpoints=breakpoints)

        result = response.to_mcp_response()

        assert "count" in result["data"]
        assert result["data"]["count"] == 2
