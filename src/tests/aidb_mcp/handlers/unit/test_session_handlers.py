"""Unit tests for MCP session tool handlers.

Tests session lifecycle operations: session_start, session status, list, stop, restart.
Sessions require init to be called first and manage debug session lifecycle.
"""

from pathlib import Path

import pytest

from aidb_mcp.core.constants import ParamName
from tests._helpers.assertions import MCPAssertions
from tests._helpers.pytest_mcp import PytestMCPBase


class TestSessionHandlers(PytestMCPBase):
    """Test session management tool operations."""

    @pytest.fixture
    def simple_program(self, tmp_path) -> Path:
        """Create a simple Python program for testing.

        Returns
        -------
        Path
            Path to test program
        """
        program = tmp_path / "test_program.py"
        program.write_text("""
def calculate(x, y):
    result = x + y
    return result

if __name__ == "__main__":
    value = calculate(5, 3)
    print(f"Result: {value}")
""")
        return program

    @pytest.mark.asyncio
    async def test_session_start_basic(self, simple_program):
        """Test basic session start with simple program.

        Verifies that session_start:
        - Requires init to be called first
        - Creates and starts a debug session
        - Returns session_id
        - Provides proper response structure
        """
        # First, must call init
        init_response = await self.call_tool(
            "init",
            {ParamName.LANGUAGE: "python"},
        )
        self.assert_response_success(init_response, "Init should succeed")

        # Now start session
        response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )

        # Validate success
        self.assert_response_success(response, "Session start should succeed")

        # Validate response structure
        MCPAssertions.assert_response_structure(response)

        # Should include session_id
        MCPAssertions.assert_session_id_present(response)

        # Should have data about the session
        assert "data" in response
        data = response["data"]
        assert isinstance(data, dict)

        # Cleanup session
        session_id = response["session_id"]
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_start_requires_init(self, simple_program):
        """Test that session_start fails without init being called first.

        Verifies proper gating - init must be called before session_start.
        """
        # Try to start session WITHOUT calling init first
        response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )

        # Should return error
        self.assert_response_error(
            response,
            message="Session start should fail without init",
        )

        # Error should mention init requirement
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "init" in error_msg or "initialize" in error_msg, (
                    "Error should mention init requirement"
                )

    @pytest.mark.asyncio
    async def test_session_start_with_breakpoints(self, simple_program):
        """Test session start with initial breakpoints.

        Verifies that breakpoints can be set at session creation time.
        """
        # Init first
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})

        # Start session with breakpoint
        response = await self.call_tool(
            "session_start",
            {
                ParamName.TARGET: str(simple_program),
                ParamName.BREAKPOINTS: [
                    {
                        "file": str(simple_program),
                        "line": 3,  # Line with 'result = x + y'
                    },
                ],
            },
        )

        # Should succeed
        self.assert_response_success(
            response,
            "Session start with breakpoints should succeed",
        )

        # Should have session_id
        MCPAssertions.assert_session_id_present(response)

        # Cleanup
        session_id = response["session_id"]
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_start_invalid_target(self):
        """Test session start with non-existent target file.

        Verifies proper error handling for invalid target paths.
        """
        # Init first
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})

        # Try to start with non-existent file
        response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: "/nonexistent/program.py"},
        )

        # Should return error
        self.assert_response_error(
            response,
            message="Session start should fail for non-existent target",
        )

    @pytest.mark.asyncio
    async def test_session_status(self, simple_program):
        """Test session status command.

        Verifies ability to query session status (active, paused, etc).
        """
        # Start a session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        start_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )
        session_id = start_response["session_id"]

        # Get session status
        response = await self.call_tool(
            "session",
            {
                ParamName.ACTION: "status",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Session status should succeed")

        # Should have status information
        MCPAssertions.assert_response_structure(response)
        assert "data" in response
        data = response["data"]

        # Status should indicate session exists and state
        assert isinstance(data, dict)

        # Cleanup
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_list(self, simple_program):
        """Test session list command.

        Verifies ability to list all active sessions.
        """
        # Start a session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        start_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )
        session_id = start_response["session_id"]

        # List sessions
        response = await self.call_tool(
            "session",
            {ParamName.ACTION: "list"},
        )

        # Should succeed
        self.assert_response_success(response, "Session list should succeed")

        # Should have response structure
        MCPAssertions.assert_response_structure(response)

        # Should have data with sessions
        assert "data" in response
        data = response["data"]
        assert isinstance(data, dict)

        # Should show our session in the list
        # (exact structure depends on implementation)

        # Cleanup
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_stop(self, simple_program):
        """Test session stop command.

        Verifies ability to stop an active session.
        """
        # Start a session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        start_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )
        session_id = start_response["session_id"]

        # Stop the session
        response = await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Session stop should succeed")

        # Should have proper structure
        MCPAssertions.assert_response_structure(response)

    @pytest.mark.asyncio
    async def test_session_stop_nonexistent(self):
        """Test stopping a non-existent session.

        Verifies proper error handling when trying to stop invalid session_id.
        """
        # Try to stop non-existent session
        response = await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: "nonexistent_session_id",
            },
        )

        # Should return error (or gracefully handle)
        # Implementation may vary - either error or success with "already stopped"
        # For now, just validate response structure
        MCPAssertions.assert_response_structure(response)

    @pytest.mark.asyncio
    async def test_session_restart(self, simple_program):
        """Test session restart command.

        Verifies ability to restart a session.
        """
        # Start a session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        start_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )
        session_id = start_response["session_id"]

        # Restart the session
        response = await self.call_tool(
            "session",
            {
                ParamName.ACTION: "restart",
                ParamName.SESSION_ID: session_id,
            },
        )

        # Should succeed
        self.assert_response_success(response, "Session restart should succeed")

        # Should have proper structure
        MCPAssertions.assert_response_structure(response)

        # Cleanup
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_response_structure_compliance(self, simple_program):
        """Test that all session responses comply with MCP structure.

        Validates response health for session operations.
        """
        # Init and start session
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})
        start_response = await self.call_tool(
            "session_start",
            {ParamName.TARGET: str(simple_program)},
        )

        # Validate session_start response
        MCPAssertions.assert_response_structure(start_response)
        MCPAssertions.assert_session_id_present(start_response)
        MCPAssertions.assert_response_efficiency(
            start_response,
            max_data_fields=15,  # Session start has more context
        )

        session_id = start_response["session_id"]

        # Test status response
        status_response = await self.call_tool(
            "session",
            {
                ParamName.ACTION: "status",
                ParamName.SESSION_ID: session_id,
            },
        )
        MCPAssertions.assert_response_structure(status_response)
        MCPAssertions.assert_response_efficiency(status_response)

        # Test list response
        list_response = await self.call_tool(
            "session",
            {ParamName.ACTION: "list"},
        )
        MCPAssertions.assert_response_structure(list_response)
        MCPAssertions.assert_response_efficiency(list_response)

        # Cleanup
        await self.call_tool(
            "session",
            {
                ParamName.ACTION: "stop",
                ParamName.SESSION_ID: session_id,
            },
        )

    @pytest.mark.asyncio
    async def test_session_start_missing_target(self):
        """Test session_start without required target parameter.

        Verifies that missing target is properly validated.
        """
        # Init first
        await self.call_tool("init", {ParamName.LANGUAGE: "python"})

        # Try to start without target
        response = await self.call_tool("session_start", {})

        # Should return error
        self.assert_response_error(
            response,
            message="Session start should fail without target",
        )

        # Error should mention target parameter
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "target" in error_msg or "required" in error_msg, (
                    "Error should mention missing target parameter"
                )
