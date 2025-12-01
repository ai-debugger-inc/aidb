"""Pure pytest MCP test base class."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Optional

import pytest

from aidb.models.entities.breakpoint import BreakpointSpec
from aidb_mcp.core.constants import ParamName
from aidb_mcp.handlers.registry import TOOL_HANDLERS
from aidb_mcp.handlers.session import reset_init_context
from aidb_mcp.session.manager import cleanup_all_sessions
from tests._helpers.assertions import MCPAssertions
from tests._helpers.pytest_base import PytestIntegrationBase


class PytestMCPBase(PytestIntegrationBase):
    """Base class for MCP tests using pure pytest."""

    @pytest.fixture(autouse=True)
    async def mcp_setup(self):
        """Set up MCP test environment."""
        # Clean up any leftover sessions from previous tests
        cleanup_all_sessions()
        # Reset global init state for test isolation
        reset_init_context()

        # Track MCP-specific state
        self._mcp_sessions: dict[str, Any] = {}
        self._tool_history: list[dict[str, Any]] = []

        yield

        # Cleanup sessions after this test
        # Suppress cleanup errors including CancelledError during event loop shutdown
        # Event loop may be closing when this runs in CI
        # Note: In Python 3.8+, CancelledError inherits from BaseException, not Exception
        with suppress(Exception, asyncio.CancelledError):
            await self._cleanup_mcp_sessions()

        if hasattr(self, "_init_session_id"):
            delattr(self, "_init_session_id")

        # Clean up all global sessions to prevent leaking
        cleanup_all_sessions()
        # Reset global init state after test
        reset_init_context()

    async def _cleanup_mcp_sessions(self):
        """Clean up any remaining MCP sessions."""
        for session_id in list(self._mcp_sessions.keys()):
            with suppress(Exception):
                await self.call_tool(
                    "session",
                    {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
                )

    async def call_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        validate_response: bool = True,
    ) -> dict[str, Any]:
        """Call an MCP tool directly.

        Parameters
        ----------
        tool_name : str
            Name of the tool to call
        args : Dict[str, Any]
            Arguments for the tool
        validate_response : bool
            Whether to validate the response structure

        Returns
        -------
        Dict[str, Any]
            Tool response
        """
        # Record the tool call
        call_record = {
            "tool": tool_name,
            "args": args,
            "timestamp": None,  # Would add timestamp if needed
        }
        self._tool_history.append(call_record)

        # Get handler directly to avoid decorator issues
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "success": False,
                "error": True,
                "error_code": "UNKNOWN_TOOL",
                "error_message": f"Unknown tool: {tool_name}",
            }

        # Call the handler
        response = await handler(args)

        # Record the response
        call_record["response"] = response

        # Validate if requested
        if validate_response:
            self._validate_tool_response(tool_name, response)

        return response

    def _validate_tool_response(self, tool_name: str, response: dict[str, Any]) -> None:
        """Validate a tool response has expected structure."""
        if "error" in response:
            # Error responses have error object with code and message
            error_obj = response.get("error", {})
            if isinstance(error_obj, dict):
                assert "code" in error_obj or "error_code" in response, (
                    f"Error response from {tool_name} missing error code"
                )
                assert "message" in error_obj or "error_message" in response, (
                    f"Error response from {tool_name} missing error message"
                )
        else:
            assert "success" in response, (
                f"Response from {tool_name} missing success field"
            )
            if response.get("success"):
                assert "data" in response, (
                    f"Success response from {tool_name} missing data field"
                )

    def assert_response_success(
        self,
        response: dict[str, Any],
        message: str = "",
    ) -> None:
        """Assert a tool response indicates success.

        Delegates to MCPAssertions for consistency.
        """
        try:
            MCPAssertions.assert_tool_response_success(response)
        except AssertionError as e:
            # Add custom message if provided
            if message:
                msg = f"{e}. {message}"
                raise AssertionError(msg) from e
            raise

    def assert_response_error(
        self,
        response: dict[str, Any],
        error_code: str | None = None,
        message: str = "",
    ) -> None:
        """Assert a tool response indicates an error.

        Delegates to MCPAssertions for consistency.
        """
        try:
            MCPAssertions.assert_tool_response_error(response, error_code=error_code)
        except AssertionError as e:
            # Add custom message if provided
            if message:
                msg = f"{e}. {message}"
                raise AssertionError(msg) from e
            raise

    def extract_inspect_value(self, response: dict[str, Any]) -> Any:
        """Extract the actual value from an inspect response.

        Handles various response formats:
        - Expression results with metadata
        - Simple values
        - Nested structures
        """
        data = response.get("data", {})

        # For expression evaluation
        if "result" in data:
            result = data["result"]
            # If result is a dict with metadata, extract the actual value
            if isinstance(result, dict):
                if "result" in result:
                    return result["result"]
                if "value" in result:
                    return result["value"]
            return result

        # For variable get
        if "value" in data:
            return data["value"]

        return data

    def assert_tool_called_with(self, tool_name: str, **expected_args) -> None:
        """Assert a tool was called with expected arguments."""
        for call in self._tool_history:
            if call["tool"] == tool_name:
                args = call["args"]
                if all(args.get(k) == v for k, v in expected_args.items()):
                    return

        # Build helpful error message
        calls_summary = [
            f"{call['tool']}({', '.join(f'{k}={v}' for k, v in call['args'].items())})"
            for call in self._tool_history
        ]

        msg = (
            f"Tool {tool_name} not called with expected args: {expected_args}\n"
            f"Actual calls: {calls_summary}"
        )
        raise AssertionError(
            msg,
        )

    async def init_debugging_context(
        self,
        language: str,
        framework: str | None = None,
        workspace_root: str | None = None,
    ) -> dict[str, Any]:
        """Initialize debugging context with init tool."""
        args = {ParamName.LANGUAGE: language}

        if framework:
            args[ParamName.FRAMEWORK] = framework
        if workspace_root:
            args[ParamName.WORKSPACE_ROOT] = workspace_root

        response = await self.call_tool("init", args)
        self.assert_response_success(response, "Failed to initialize debugging context")

        return response

    async def start_debug_session(
        self,
        target: str | None = None,
        language: str | None = None,
        breakpoints: list[BreakpointSpec] | None = None,
        **kwargs,
    ) -> tuple[str, dict[str, Any]]:
        """Start a debug session and return session ID and response."""
        args: dict[str, Any] = {}

        if target:
            args[ParamName.TARGET] = target
        if language:
            args["language"] = language
        if breakpoints is not None:
            args[ParamName.BREAKPOINTS] = breakpoints

        args.update(kwargs)

        response = await self.call_tool("session_start", args)
        self.assert_response_success(response, "Failed to start debug session")

        session_id = response.get(ParamName.SESSION_ID)
        assert session_id, "No session_id in response"

        # Track session
        self._mcp_sessions[session_id] = response["data"]

        return session_id, response

    @asynccontextmanager
    async def debug_session(
        self,
        target: str | None = None,
        language: str = "python",
        breakpoints: list[BreakpointSpec] | None = None,
        init_first: bool = True,
        **kwargs,
    ):
        """Context manager for debug sessions with automatic cleanup."""
        session_id = None
        try:
            # Initialize if requested
            if init_first:
                await self.init_debugging_context(
                    language,
                    **kwargs.get("init_args", {}),
                )

            # Start session
            session_id, response = await self.start_debug_session(
                target=target,
                language=language,
                breakpoints=breakpoints,
                **kwargs,
            )

            yield session_id, response["data"]

        finally:
            # Always clean up session
            if session_id:
                try:
                    await self.call_tool(
                        "session",
                        {ParamName.ACTION: "stop", ParamName.SESSION_ID: session_id},
                    )
                    if session_id in self._mcp_sessions:
                        del self._mcp_sessions[session_id]
                except Exception as e:
                    # Session cleanup failed, log but don't fail the test
                    logging.debug("Session cleanup failed: %s", e)

    async def setup_python_debug(
        self,
        temp_dir: Path,
        scenario: str = "calculate_function",
        with_breakpoints: bool = True,
    ) -> dict[str, Any]:
        """Set up Python debugging environment with MCP initialization."""
        # Use the mixin's generic method
        setup = await self.setup_debug_environment(
            temp_dir,
            language="python",
            scenario=scenario,
            with_breakpoints=with_breakpoints,
        )

        # Add MCP-specific initialization
        await self.init_debugging_context("python", workspace_root=str(temp_dir))

        return setup

    async def assert_tool_requires_init(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        expected_error_keywords: list[str] | None = None,
    ) -> None:
        """Assert that a tool requires init to be called first.

        This is a common pattern for all MCP tools - they should fail
        with an appropriate error when called without initialization.

        Parameters
        ----------
        tool_name : str
            Name of the tool to test
        tool_args : Dict[str, Any]
            Arguments to pass to the tool
        expected_error_keywords : List[str], optional
            Keywords expected in error message (default: ["session", "init"])

        Raises
        ------
        AssertionError
            If tool doesn't require init or error message is incorrect
        """
        # Ensure we're in a clean state (no init called)
        from aidb_mcp.handlers.session import reset_init_context

        reset_init_context()

        # Try to call the tool without init
        response = await self.call_tool(tool_name, tool_args)

        # Should fail with error
        self.assert_response_error(response)

        # Check error message contains expected keywords
        if expected_error_keywords is None:
            expected_error_keywords = ["session", "init"]

        error_obj = response.get("error", {})
        if isinstance(error_obj, dict):
            error_msg = error_obj.get("message", "").lower()
        else:
            error_msg = str(error_obj).lower()

        found_keyword = False
        for keyword in expected_error_keywords:
            if keyword.lower() in error_msg:
                found_keyword = True
                break

        assert found_keyword, (
            f"Tool '{tool_name}' error should mention one of {expected_error_keywords}, "
            f"got: {error_msg}"
        )

    async def assert_init_enables_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        language: str = "python",
        should_succeed_after_init: bool = False,
    ) -> None:
        """Assert that init properly enables a tool.

        Parameters
        ----------
        tool_name : str
            Name of the tool to test
        tool_args : Dict[str, Any]
            Arguments to pass to the tool
        language : str
            Language to initialize with
        should_succeed_after_init : bool
            If True, expects tool to succeed after init alone.
            If False, expects different error (e.g., needs session_start)

        Raises
        ------
        AssertionError
            If init doesn't properly enable the tool
        """
        # Initialize debugging context
        init_response = await self.init_debugging_context(language)
        self.assert_response_success(init_response)

        # Now try the tool again
        response = await self.call_tool(tool_name, tool_args)

        if should_succeed_after_init:
            # Tool should work after init
            self.assert_response_success(response)
        else:
            # Tool may still fail but with different error (e.g., no active session)
            if "error" in response:
                error_obj = response.get("error", {})
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get("message", "").lower()
                else:
                    error_msg = str(error_obj).lower()

                # Should NOT be about init/not initialized anymore
                assert "initialized" not in error_msg, (
                    f"After init, should not get 'not initialized' error: {error_msg}"
                )
                # Common post-init error is about needing session_start
                if "session_start" in error_msg or "no active" in error_msg:
                    pass  # This is expected
            else:
                # Tool succeeded, which is also fine
                self.assert_response_success(response)
