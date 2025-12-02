"""MCP-based debug interface implementation.

This module provides a DebugInterface implementation that calls MCP handlers directly,
allowing tests to verify the MCP entry point works correctly.
"""

from pathlib import Path
from typing import Any, Optional

from aidb_mcp.core.constants import ParamName, ToolName
from aidb_mcp.handlers import handle_tool
from tests._helpers.debug_interface.base import DebugInterface


class MCPInterface(DebugInterface):
    """Debug interface implementation using MCP tool handlers.

    This implementation calls MCP tool handlers directly, providing a unified
    interface for testing the MCP entry point.

    Attributes
    ----------
    _initialized_context : bool
        Whether init tool has been called.
    _breakpoints : dict[str, dict[str, Any]]
        Tracking of set breakpoints.
    """

    def __init__(self, language: str | None = None):
        """Initialize the MCP interface.

        Parameters
        ----------
        language : str, optional
            Programming language (python, javascript, java).
        """
        super().__init__(language)
        self._initialized_context = False
        self._breakpoints: dict[str, dict[str, Any]] = {}

    async def _wait_for_breakpoint_verification(
        self,
        breakpoint_count: int,
        timeout: float = 3.0,
        poll_interval: float = 0.1,
    ) -> None:
        """Wait for breakpoints to be verified by the debug adapter.

        JavaScript adapter returns provisional breakpoints initially and sends
        verification events asynchronously via LoadedSource rebinding. This
        polling ensures we wait for verification to complete in CI environments
        where I/O may be slower.

        Parameters
        ----------
        breakpoint_count : int
            Number of breakpoints expected to be verified.
        timeout : float
            Maximum time to wait for verification.
        poll_interval : float
            Time between verification checks.
        """
        import asyncio
        import time

        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            breakpoints_list = await self.list_breakpoints()
            verified_count = sum(
                1 for bp in breakpoints_list if bp.get("verified", False)
            )

            if verified_count == breakpoint_count:
                break

            await asyncio.sleep(poll_interval)

    def _extract_error_message(self, result: dict[str, Any]) -> str:
        """Extract error message from MCP response.

        Parameters
        ----------
        result : dict[str, Any]
            MCP response dictionary.

        Returns
        -------
        str
            Error message string.
        """
        error = result.get("error", {})
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or "Unknown error"
            return str(message)
        return str(error) if error else "Unknown error"

    async def initialize(
        self,
        language: str | None = None,
        **config,
    ) -> None:
        """Initialize the MCP interface by calling the init tool.

        Parameters
        ----------
        language : str, optional
            Programming language (python, javascript, java).
        **config : dict
            Additional configuration (mode, framework, workspace_root, etc.)
        """
        if language:
            self.language = language

        if not self.language:
            msg = "Language must be specified for MCP interface"
            raise ValueError(msg)

        # Call init tool (required first step for MCP)
        init_args = {
            ParamName.LANGUAGE: self.language,
            **config,
        }

        result = await handle_tool(ToolName.INIT, init_args)

        if not result.get("success", False):
            msg = f"MCP init failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        self._initialized_context = True
        self._initialized = True

    async def start_session(
        self,
        program: str | Path,
        breakpoints: list[dict[str, Any]] | None = None,
        **launch_args,
    ) -> dict[str, Any]:
        """Start a debug session via MCP session_start tool.

        Parameters
        ----------
        program : Union[str, Path]
            Path to the program to debug.
        breakpoints : list[dict[str, Any]], optional
            Initial breakpoints to set.
        **launch_args : dict
            Additional launch arguments (cwd, env, args, etc.)

        Returns
        -------
        dict[str, Any]
            Session information.
        """
        self._validate_initialized()

        if not self._initialized_context:
            msg = "MCP context not initialized. Call initialize() first."
            raise RuntimeError(msg)

        # Convert breakpoints to MCP format
        mcp_breakpoints = None
        if breakpoints:
            mcp_breakpoints = [
                {
                    "file": bp.get("file", str(program)),
                    "line": bp["line"],
                    ParamName.CONDITION: bp.get("condition"),
                    "hit_condition": bp.get("hitCondition"),
                    "log_message": bp.get("logMessage"),
                }
                for bp in breakpoints
            ]

        # Build session_start arguments
        session_args = {
            ParamName.LANGUAGE: self.language,
            ParamName.TARGET: str(program),
            **launch_args,
        }

        # Add breakpoints if provided
        if mcp_breakpoints:
            session_args[ParamName.BREAKPOINTS] = mcp_breakpoints

        # Call session_start tool
        result = await handle_tool(ToolName.SESSION_START, session_args)

        if not result.get("success", False):
            msg = f"MCP session_start failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        data = result.get("data", {})

        # Extract and validate session_id from response
        retrieved_session_id = data.get("session_id")
        if not retrieved_session_id:
            msg = (
                f"MCP session_start succeeded but returned no session_id. "
                f"Response data: {data}"
            )
            raise RuntimeError(msg)

        # Store the session ID permanently
        # This is this interface instance's permanent session ID
        # It references an entry in the global _DEBUG_SESSIONS dict in the MCP server
        # Important: This session_id will not change even if new sessions are created,
        # allowing this instance to always reference its original session
        if self.session_id:  # type: ignore[has-type]
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "MCPInterface.start_session called but session_id already set "
                "(current=%s, new=%s)",
                str(self.session_id),  # type: ignore[has-type]
                retrieved_session_id,
            )

        self.session_id = retrieved_session_id
        self._session_active = True

        # Wait for breakpoint verification and populate tracking dict
        # This handles JavaScript's async verification via LoadedSource rebinding
        if breakpoints:
            await self._wait_for_breakpoint_verification(len(breakpoints))

            breakpoints_list = await self.list_breakpoints()
            for bp in breakpoints_list:
                bp_id = str(bp.get("id", ""))
                if bp_id:
                    self._breakpoints[bp_id] = bp

        return {
            "session_id": self.session_id,
            "status": data.get("status", "started"),
            "language": self.language,
            "program": str(program),
        }

    async def stop_session(self) -> None:
        """Stop the current debug session via MCP session tool.

        Raises
        ------
        RuntimeError
            If no active session.
        """
        self._validate_session_active()

        # Call session stop action
        stop_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "stop",
        }

        result = await handle_tool(ToolName.SESSION, stop_args)

        if not result.get("success", False):
            # Check if this is a cancellation error (session already terminated)
            error_msg = self._extract_error_message(result)
            if (
                "cancelled" in error_msg.lower()
                or "already terminated" in error_msg.lower()
            ):
                # Session terminated naturally, just clean up our tracking
                self.session_id = None
                self._session_active = False
                return

            msg = f"MCP session stop failed: {error_msg}"
            raise RuntimeError(msg)

        self.session_id = None
        self._session_active = False

    async def set_breakpoint(  # noqa: C901
        self,
        file: str | Path,
        line: int,
        condition: str | None = None,
        hit_condition: str | None = None,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        """Set a breakpoint via MCP breakpoint tool.

        Parameters
        ----------
        file : Union[str, Path]
            File path for the breakpoint.
        line : int
            Line number.
        condition : str, optional
            Conditional expression.
        hit_condition : str, optional
            Hit count condition.
        log_message : str, optional
            Log message (logpoint).

        Returns
        -------
        dict[str, Any]
            Breakpoint information.
        """
        self._validate_session_active()

        # Call breakpoint set action
        bp_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "set",
            ParamName.LOCATION: f"{file}:{line}",
        }

        if condition:
            bp_args[ParamName.CONDITION] = condition
        if hit_condition:
            bp_args["hit_condition"] = hit_condition
        if log_message:
            bp_args["log_message"] = log_message

        result = await handle_tool(ToolName.BREAKPOINT, bp_args)

        if not result.get("success", False):
            msg = f"MCP breakpoint set failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        data = result.get("data", {})
        bp_id = data.get("id", f"{file}:{line}")

        # Wait for breakpoint verification to avoid race condition in CI
        import asyncio
        import time

        verification_timeout = 3.0
        poll_interval = 0.1
        start_time = time.monotonic()
        verified = data.get("verified", False)

        # Poll for verification if not already verified
        if not verified:
            while time.monotonic() - start_time < verification_timeout:
                breakpoints_list = await self.list_breakpoints()
                # Find our breakpoint in the list
                for bp in breakpoints_list:
                    if (
                        bp.get("file") == str(file)
                        and bp.get("line") == line
                        and bp.get("verified", False)
                    ):
                        verified = True
                        break

                if verified:
                    break

                await asyncio.sleep(poll_interval)

        # Store breakpoint info with final verification status
        self._breakpoints[str(bp_id)] = {
            "id": bp_id,
            "file": str(file),
            "line": line,
            "verified": verified,
            "condition": condition,
            "hit_condition": hit_condition,
            "log_message": log_message,
        }

        return self._breakpoints[str(bp_id)]

    async def remove_breakpoint(self, breakpoint_id: str | int) -> bool:
        """Remove a breakpoint via MCP breakpoint tool.

        Parameters
        ----------
        breakpoint_id : Union[str, int]
            Breakpoint ID.

        Returns
        -------
        bool
            True if removed successfully.
        """
        self._validate_session_active()

        bp_id = str(breakpoint_id)
        if bp_id not in self._breakpoints:
            return False

        bp = self._breakpoints[bp_id]

        # Call breakpoint remove action
        remove_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "remove",
            ParamName.LOCATION: f"{bp['file']}:{bp['line']}",
        }

        result = await handle_tool(ToolName.BREAKPOINT, remove_args)

        if not result.get("success", False):
            return False

        del self._breakpoints[bp_id]
        return True

    async def list_breakpoints(self) -> list[dict[str, Any]]:
        """List all current breakpoints via MCP breakpoint tool.

        Returns
        -------
        list[dict[str, Any]]
            List of breakpoint information.
        """
        self._validate_session_active()

        # Call breakpoint list action
        list_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "list",
        }

        result = await handle_tool(ToolName.BREAKPOINT, list_args)

        def _ensure_ids(bps: list[dict[str, Any]]) -> list[dict[str, Any]]:
            fixed: list[dict[str, Any]] = []
            for bp in bps:
                if "id" not in bp or bp["id"] in (None, ""):
                    loc = bp.get("location") or f"{bp.get('file')}:{bp.get('line')}"
                    fixed.append({**bp, "id": loc})
                else:
                    fixed.append(bp)
            return fixed

        if not result.get("success", False):
            # Fall back to cached breakpoints
            return _ensure_ids(list(self._breakpoints.values()))

        data = result.get("data", {})
        return _ensure_ids(data.get("breakpoints", list(self._breakpoints.values())))

    async def step_over(self) -> dict[str, Any]:
        """Step over the current line via MCP step tool.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        step_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "over",
        }

        result = await handle_tool(ToolName.STEP, step_args)

        if not result.get("success", False):
            msg = f"MCP step_over failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        return self._format_execution_state(result.get("data", {}))

    async def step_into(self) -> dict[str, Any]:
        """Step into a function via MCP step tool.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        step_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "into",
        }

        result = await handle_tool(ToolName.STEP, step_args)

        if not result.get("success", False):
            msg = f"MCP step_into failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        return self._format_execution_state(result.get("data", {}))

    async def step_out(self) -> dict[str, Any]:
        """Step out of the current function via MCP step tool.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        step_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "out",
        }

        result = await handle_tool(ToolName.STEP, step_args)

        if not result.get("success", False):
            msg = f"MCP step_out failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        return self._format_execution_state(result.get("data", {}))

    async def continue_execution(self) -> dict[str, Any]:
        """Continue execution via MCP execute tool.

        Returns
        -------
        dict[str, Any]
            Execution state.
        """
        self._validate_session_active()

        exec_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "continue",
            ParamName.WAIT_FOR_STOP: True,
        }

        result = await handle_tool(ToolName.EXECUTE, exec_args)

        if not result.get("success", False):
            msg = f"MCP continue failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        return self._format_execution_state(result.get("data", {}))

    async def get_state(self) -> dict[str, Any]:
        """Get the current execution state via MCP context tool.

        Returns
        -------
        dict[str, Any]
            Current execution state.

        Raises
        ------
        RuntimeError
            If MCP context call fails or response is invalid
        """
        self._validate_session_active()

        context_args = {
            ParamName.SESSION_ID: self.session_id,
        }

        result = await handle_tool(ToolName.CONTEXT, context_args)

        if not result.get("success", False):
            msg = f"MCP context failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        # Extract state from context response
        data = result.get("data", {})

        # Context response has execution_state nested in context object
        context = data.get("context", {})

        # Validate that execution_state exists in response
        if "execution_state" not in context:
            msg = "MCP context response missing execution_state field in context object"
            raise RuntimeError(msg)

        # Context response has execution_state as a string, but formatter expects
        # an object structure. Convert to expected format:
        # - execution_state is a string ("paused", "running", "terminated")
        # - We need to set stopped=True when paused
        # - location might be present as "file:line" string
        execution_state_str = context.get("execution_state", "unknown")

        # Build a result structure that the formatter can handle
        formatted_result = {
            "stopped": execution_state_str == "paused",
            "running": execution_state_str == "running",
            "terminated": execution_state_str == "terminated",
            "execution_state": {
                "status": execution_state_str,
            },
        }

        # Add location if present
        if "current_location" in context:
            formatted_result["location"] = context["current_location"]

        # Add stop_reason if present
        if "stop_reason" in context:
            formatted_result["reason"] = context["stop_reason"]

        return self._format_execution_state(formatted_result)

    async def get_variables(
        self,
        scope: str = "locals",
        frame: int = 0,
    ) -> dict[str, Any]:
        """Get variables via MCP inspect tool.

        Parameters
        ----------
        scope : str, optional
            Scope ('locals', 'globals', 'all').
        frame : int, optional
            Stack frame index.

        Returns
        -------
        dict[str, Any]
            Dictionary of variables.
        """
        self._validate_session_active()

        inspect_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.TARGET: scope,
            ParamName.FRAME: frame,
        }

        result = await handle_tool(ToolName.INSPECT, inspect_args)

        if not result.get("success", False):
            msg = f"MCP inspect failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        data = result.get("data", {})

        # MCP returns variables under scope-specific fields ("locals", "globals")
        # NOT under a generic "variables" field
        variables = data.get(scope, {})

        # Handle truncation cases where response is a dict with "variables" key
        if isinstance(variables, dict) and "variables" in variables:
            return variables["variables"]

        return variables if isinstance(variables, dict) else {}

    async def get_stack_trace(self) -> list[dict[str, Any]]:
        """Get the current stack trace via MCP inspect tool.

        Returns
        -------
        list[dict[str, Any]]
            List of stack frames.
        """
        self._validate_session_active()

        inspect_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.TARGET: "stack",
        }

        result = await handle_tool(ToolName.INSPECT, inspect_args)

        if not result.get("success", False):
            msg = f"MCP inspect stack failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        # Debug logging to understand response structure
        import json
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(
            "MCP INSPECT RESULT: %s",
            json.dumps(result, indent=2, default=str),
        )

        data = result.get("data", {})
        logger.debug("MCP DATA KEYS: %s", list(data.keys()))

        # Try different extraction paths
        frames = data.get("frames", [])
        if not frames:
            # Try alternative paths
            frames = data.get("call_stack", [])
        if not frames and "stack" in data:
            # Stack is returned as a direct list, not nested under "frames"
            frames = data.get("stack", [])
        if not frames:
            # Try top-level
            frames = result.get("frames", [])

        logger.debug("MCP EXTRACTED FRAMES COUNT: %d", len(frames))
        return frames

    async def evaluate(
        self,
        expression: str,
        frame: int = 0,
    ) -> Any:
        """Evaluate an expression via MCP variable tool.

        Parameters
        ----------
        expression : str
            Expression to evaluate.
        frame : int, optional
            Stack frame index.

        Returns
        -------
        Any
            Evaluation result.
        """
        self._validate_session_active()

        var_args = {
            ParamName.SESSION_ID: self.session_id,
            ParamName.ACTION: "get",
            ParamName.EXPRESSION: expression,
            ParamName.FRAME: frame,
        }

        result = await handle_tool(ToolName.VARIABLE, var_args)

        if not result.get("success", False):
            msg = f"MCP evaluate failed: {self._extract_error_message(result)}"
            raise RuntimeError(msg)

        data = result.get("data", {})
        return data.get("result")

    async def cleanup(self) -> None:
        """Clean up the MCP interface resources.

        Stops any active session and releases resources. Cleanup failures are logged but
        don't fail the test to ensure test teardown completes.
        """
        if self._session_active and self.session_id:
            try:
                await self.stop_session()
            except Exception as e:
                # Log cleanup failure but don't fail test teardown
                # This ensures we see what's failing while allowing tests to complete
                import logging

                logging.getLogger(__name__).warning(
                    "MCP cleanup failed for session %s: %s",
                    self.session_id,
                    e,
                    exc_info=True,
                )

        # Clear state regardless of stop_session() success
        # This prevents retry attempts with stale session IDs
        self.session_id = None
        self._session_active = False
        self._breakpoints.clear()
        self._initialized = False
        self._initialized_context = False
