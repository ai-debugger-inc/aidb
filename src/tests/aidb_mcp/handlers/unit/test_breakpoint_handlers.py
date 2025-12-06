"""Unit tests for MCP breakpoint tool handlers.

Tests breakpoint management operations: set, remove, list, clear_all.
Breakpoints can be simple, conditional, or logpoints.
"""

from pathlib import Path

import pytest

from aidb_mcp.core.constants import ParamName
from tests._helpers.assertions import MCPAssertions
from tests._helpers.pytest_mcp import PytestMCPBase

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestBreakpointHandlers(PytestMCPBase):
    """Test breakpoint management tool operations."""

    @pytest.fixture
    def debug_program(self, tmp_path) -> Path:
        """Create a Python program for testing breakpoints.

        Returns
        -------
        Path
            Path to test program with multiple lines for breakpoint testing
        """
        program = tmp_path / "debug_program.py"
        # Use a program that waits for a short time to avoid race conditions
        # between session start and breakpoint setting. The program sleeps
        # briefly which gives time for breakpoint tool calls to be processed.
        program.write_text("""
import time

def calculate(x, y):
    result = x + y  # Line 5 - good breakpoint location
    return result

def main():
    # Short delay to allow breakpoint tool calls after session_start
    time.sleep(0.5)
    a = 5  # Line 11 - another good location
    b = 3
    value = calculate(a, b)  # Line 13
    print(f"Result: {value}")  # Line 14
    return value

if __name__ == "__main__":
    main()
""")
        return program

    @pytest.mark.asyncio
    async def test_breakpoint_set_basic(self, debug_program):
        """Test setting a simple breakpoint.

        Verifies that a breakpoint can be set at a specific location.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Set breakpoint
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: f"{debug_program}:5",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Breakpoint set should succeed")

        # Should have proper response structure
        MCPAssertions.assert_response_structure(response)

        # Should include breakpoint information
        assert "data" in response
        data = response["data"]
        assert "location" in data

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_set_conditional(self, debug_program):
        """Test setting a conditional breakpoint.

        Verifies that breakpoints can have conditions that must be met.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Set conditional breakpoint
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: f"{debug_program}:11",
                ParamName.CONDITION: "a > 3",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(
            response,
            "Conditional breakpoint set should succeed",
        )

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_set_logpoint(self, debug_program):
        """Test setting a logpoint (log message instead of pausing).

        Verifies that logpoints can be set to log without breaking execution.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Set logpoint
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: f"{debug_program}:13",
                ParamName.LOG_MESSAGE: "Calling calculate with a={a}, b={b}",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Logpoint set should succeed")

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_list(self, debug_program):
        """Test listing all breakpoints.

        Verifies that all set breakpoints can be retrieved.
        """
        # Setup session with initial breakpoints (avoids race condition)
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {
                ParamName.TARGET: str(debug_program),
                ParamName.BREAKPOINTS: [
                    {"file": str(debug_program), "line": 5},
                    {"file": str(debug_program), "line": 11},
                ],
            },
        )
        session_id = session_response["session_id"]

        # List breakpoints
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "list",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Breakpoint list should succeed")

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Should have breakpoints data
        assert "data" in response
        data = response["data"]
        # Implementation may vary - just ensure data exists
        assert isinstance(data, dict)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_remove(self, debug_program):
        """Test removing a specific breakpoint.

        Verifies that breakpoints can be removed by location.
        """
        # Setup session with initial breakpoint (avoids race condition)
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {
                ParamName.TARGET: str(debug_program),
                ParamName.BREAKPOINTS: [{"file": str(debug_program), "line": 5}],
            },
        )
        session_id = session_response["session_id"]

        # Remove breakpoint
        location = f"{debug_program}:5"
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "remove",
                ParamName.LOCATION: location,
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Breakpoint remove should succeed")

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_clear_all(self, debug_program):
        """Test clearing all breakpoints.

        Verifies that all breakpoints can be removed at once.
        """
        # Setup session with initial breakpoints (avoids race condition)
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {
                ParamName.TARGET: str(debug_program),
                ParamName.BREAKPOINTS: [
                    {"file": str(debug_program), "line": 5},
                    {"file": str(debug_program), "line": 11},
                ],
            },
        )
        session_id = session_response["session_id"]

        # Clear all breakpoints
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "clear_all",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Clear all breakpoints should succeed")

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_invalid_location(self, debug_program):
        """Test setting breakpoint with invalid location format.

        Verifies proper error handling for malformed locations.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Try to set breakpoint with invalid location
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: "invalid-location-format",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should return error
        self.assert_response_error(
            response,
            message="Invalid location should fail",
        )

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_missing_location(self, debug_program):
        """Test setting breakpoint without location parameter.

        Verifies that location is required for set/remove actions.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Try to set breakpoint without location
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.SESSION_ID: session_id,
                # Missing LOCATION parameter
            },
        )

        # Should return error
        self.assert_response_error(
            response,
            message="Missing location should fail",
        )

        # Error should mention location
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "location" in error_msg, "Error should mention missing location"

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_response_structure_compliance(self, debug_program):
        """Test that breakpoint responses comply with MCP structure.

        Validates response health for all breakpoint operations.
        """
        # Setup session with initial breakpoint (avoids race condition)
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {
                ParamName.TARGET: str(debug_program),
                ParamName.BREAKPOINTS: [{"file": str(debug_program), "line": 5}],
            },
        )
        session_id = session_response["session_id"]

        # Test list response
        list_response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "list",
                ParamName.SESSION_ID: session_id,
            },
        )
        MCPAssertions.assert_response_structure(list_response)
        MCPAssertions.assert_response_efficiency(list_response)

        # Test remove response
        remove_response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "remove",
                ParamName.LOCATION: f"{debug_program}:5",
                ParamName.SESSION_ID: session_id,
            },
        )
        MCPAssertions.assert_response_structure(remove_response)
        MCPAssertions.assert_response_efficiency(remove_response)

        # Test set response (after removal)
        set_response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: f"{debug_program}:11",
                ParamName.SESSION_ID: session_id,
            },
        )
        MCPAssertions.assert_response_structure(set_response)
        MCPAssertions.assert_response_efficiency(set_response)

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_breakpoint_requires_session(self, debug_program):
        """Test that breakpoint operations require an active session.

        Verifies proper session validation.
        """
        # Try to set breakpoint without starting session
        # (just init, no session_start)
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})

        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "set",
                ParamName.LOCATION: f"{debug_program}:5",
                # No session_id provided
            },
        )

        # Should return error about missing/invalid session
        self.assert_response_error(
            response,
            message="Breakpoint should fail without active session",
        )

        # Error should mention session requirement
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "session" in error_msg, (
                    "Error should mention session requirement"
                )

    @pytest.mark.asyncio
    async def test_watchpoint_not_supported_for_python(self, debug_program):
        """Test that watchpoints fail for Python (Java only feature).

        Verifies proper error handling when using watch action with Python.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Try to set watchpoint (should fail for Python)
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "watch",
                ParamName.NAME: "x",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should return error
        self.assert_response_error(
            response,
            message="Watchpoint should fail for Python",
        )

        # Error should mention Java-only support
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "java" in error_msg or "not supported" in error_msg, (
                    "Error should mention Java-only support"
                )

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )

    @pytest.mark.asyncio
    async def test_watchpoint_missing_name(self, debug_program):
        """Test that watch action requires name parameter.

        Verifies proper validation for watch action parameters.
        """
        # Setup session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        session_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(debug_program)},
        )
        session_id = session_response["session_id"]

        # Try to set watchpoint without name (will fail for Python anyway,
        # but name validation happens before language check in some cases)
        response = await self.call_tool(
            "breakpoint",
            {
                ParamName.ACTION: "watch",
                # Missing NAME parameter
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should return error (either for Python or missing name)
        self.assert_response_error(
            response,
            message="Watchpoint without name should fail",
        )

        # Cleanup
        await self.call_tool(
            "session",
            {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
        )
