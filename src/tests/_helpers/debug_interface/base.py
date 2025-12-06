"""Base debug interface abstraction.

This module defines the abstract base class for debug interfaces, providing a unified
API for testing both MCP and direct API entry points.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from aidb_common.constants import Language


class DebugInterface(ABC):
    """Abstract interface for debug operations.

    This interface provides a unified API for debug operations that can be implemented
    by both MCP and API interfaces, enabling the same test logic to run against both
    entry points.

    Implementations must handle:
    - Session lifecycle (initialize, start, stop, cleanup)
    - Breakpoint management (set, remove, list)
    - Execution control (continue, step over/into/out)
    - State inspection (variables, stack trace, evaluation)
    """

    def __init__(self, language: str | Language | None = None):
        """Initialize the debug interface.

        Parameters
        ----------
        language : str | Language, optional
            Programming language for debugging (python, javascript, java).
            Can be set later via initialize() if not provided.
        """
        # Handle both enum and string
        self.language = language.value if isinstance(language, Language) else language
        self.session_id: str | None = None
        self._initialized = False
        self._session_active = False

    @abstractmethod
    async def initialize(
        self,
        language: str | Language | None = None,
        **config,
    ) -> None:
        """Initialize the debug interface with language and configuration.

        Parameters
        ----------
        language : str | Language, optional
            Programming language (python, javascript, java).
            If not provided, uses language from constructor.
        **config : dict
            Additional configuration parameters specific to the implementation.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If language is not supported or configuration is invalid.
        """

    @abstractmethod
    async def start_session(
        self,
        program: str | Path,
        breakpoints: list[dict[str, Any]] | None = None,
        **launch_args,
    ) -> dict[str, Any]:
        """Start a debug session for the given program.

        Parameters
        ----------
        program : Union[str, Path]
            Path to the program to debug.
        breakpoints : list[dict[str, Any]], optional
            Initial breakpoints to set. Each breakpoint dict should contain:
            - file: str - File path
            - line: int - Line number
            - condition: str, optional - Conditional expression
            - hit_condition: str, optional - Hit count condition
        **launch_args : dict
            Additional launch arguments (cwd, env, args, etc.)

        Returns
        -------
        dict[str, Any]
            Session information including session_id, status, etc.

        Raises
        ------
        RuntimeError
            If session cannot be started or program not found.
        """

    @abstractmethod
    async def stop_session(self) -> None:
        """Stop the current debug session.

        Returns
        -------
        None

        Raises
        ------
        RuntimeError
            If no active session or session cannot be stopped.
        """

    @abstractmethod
    async def set_breakpoint(
        self,
        file: str | Path,
        line: int,
        condition: str | None = None,
        hit_condition: str | None = None,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        """Set a breakpoint at the specified location.

        Parameters
        ----------
        file : Union[str, Path]
            File path for the breakpoint.
        line : int
            Line number for the breakpoint.
        condition : str, optional
            Conditional expression (e.g., 'x > 10').
        hit_condition : str, optional
            Hit count condition (e.g., '>5' to break after 5 hits).
        log_message : str, optional
            Log message instead of breaking (logpoint).

        Returns
        -------
        dict[str, Any]
            Breakpoint information including id, verified status, actual line, etc.

        Raises
        ------
        RuntimeError
            If breakpoint cannot be set or session not active.
        """

    @abstractmethod
    async def remove_breakpoint(self, breakpoint_id: str | int) -> bool:
        """Remove a breakpoint by ID.

        Parameters
        ----------
        breakpoint_id : Union[str, int]
            ID of the breakpoint to remove.

        Returns
        -------
        bool
            True if breakpoint was removed successfully.

        Raises
        ------
        RuntimeError
            If breakpoint cannot be removed or doesn't exist.
        """

    @abstractmethod
    async def list_breakpoints(self) -> list[dict[str, Any]]:
        """List all current breakpoints.

        Returns
        -------
        list[dict[str, Any]]
            List of breakpoint information dictionaries.
        """

    @abstractmethod
    async def step_over(self) -> dict[str, Any]:
        """Step over the current line (execute without entering functions).

        Returns
        -------
        dict[str, Any]
            Execution state after stepping (stopped, reason, location, etc.)

        Raises
        ------
        RuntimeError
            If step operation fails or session not paused.
        """

    @abstractmethod
    async def step_into(self) -> dict[str, Any]:
        """Step into a function call.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping into function.

        Raises
        ------
        RuntimeError
            If step operation fails or session not paused.
        """

    @abstractmethod
    async def step_out(self) -> dict[str, Any]:
        """Step out of the current function.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping out.

        Raises
        ------
        RuntimeError
            If step operation fails or session not paused.
        """

    @abstractmethod
    async def continue_execution(self) -> dict[str, Any]:
        """Continue execution until next breakpoint or program end.

        Returns
        -------
        dict[str, Any]
            Execution state including:
            - stopped: bool - Whether execution stopped
            - reason: str - Reason for stopping (breakpoint, exception, end, etc.)
            - location: dict - Current location if stopped
            - line: int - Current line if stopped
            - file: str - Current file if stopped

        Raises
        ------
        RuntimeError
            If continue operation fails.
        """

    @abstractmethod
    async def get_state(self) -> dict[str, Any]:
        """Get the current execution state.

        Returns
        -------
        dict[str, Any]
            Current execution state including:
            - stopped: bool - Whether execution is stopped
            - running: bool - Whether execution is running
            - terminated: bool - Whether session has terminated
            - reason: str - Stop reason if stopped
            - location: dict - Current location if stopped
            - line: int - Current line if stopped
            - file: str - Current file if stopped

        Raises
        ------
        RuntimeError
            If state retrieval fails or session is not active.
        """

    @abstractmethod
    async def get_variables(
        self,
        scope: str = "locals",
        frame: int = 0,
    ) -> dict[str, Any]:
        """Get variables in the specified scope.

        Parameters
        ----------
        scope : str, optional
            Scope to inspect ('locals', 'globals', 'all'), default 'locals'.
        frame : int, optional
            Stack frame index (0 = current frame), default 0.

        Returns
        -------
        dict[str, Any]
            Dictionary of variable names to values/metadata.

        Raises
        ------
        RuntimeError
            If variables cannot be retrieved or session not paused.
        """

    @abstractmethod
    async def get_stack_trace(self) -> list[dict[str, Any]]:
        """Get the current stack trace.

        Returns
        -------
        list[dict[str, Any]]
            List of stack frames with location, function name, etc.

        Raises
        ------
        RuntimeError
            If stack trace cannot be retrieved or session not paused.
        """

    @abstractmethod
    async def evaluate(
        self,
        expression: str,
        frame: int = 0,
    ) -> Any:
        """Evaluate an expression in the current execution context.

        Parameters
        ----------
        expression : str
            Expression to evaluate.
        frame : int, optional
            Stack frame index for evaluation context, default 0.

        Returns
        -------
        Any
            Evaluation result.

        Raises
        ------
        RuntimeError
            If expression cannot be evaluated or session not paused.
        """

    @abstractmethod
    async def get_output(self, clear: bool = True) -> list[dict[str, Any]]:
        """Get collected program output (logpoints, stdout, stderr).

        Output is collected from DAP output events during program execution.
        Logpoint messages appear with category "console".

        Parameters
        ----------
        clear : bool
            If True (default), clears the buffer after retrieval to avoid
            returning duplicate output on subsequent calls.

        Returns
        -------
        list[dict[str, Any]]
            List of output entries, each with:
            - category: "console" (logpoints), "stdout", "stderr", etc.
            - output: The output text
            - timestamp: Unix timestamp when output was received (API only)
        """

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources and shut down the debug interface.

        This method should:
        - Stop any active sessions
        - Release resources (adapters, connections, etc.)
        - Clean up temporary files

        Should be called in test teardown even if tests fail.

        Returns
        -------
        None
        """

    # Helper properties for state checking

    @property
    def is_initialized(self) -> bool:
        """Check if interface is initialized."""
        return self._initialized

    @property
    def is_session_active(self) -> bool:
        """Check if a session is currently active."""
        return self._session_active

    def _validate_initialized(self) -> None:
        """Validate that interface is initialized.

        Raises
        ------
        RuntimeError
            If interface is not initialized.
        """
        if not self._initialized:
            msg = "Debug interface not initialized. Call initialize() first."
            raise RuntimeError(msg)

    def _validate_session_active(self) -> None:
        """Validate that a session is active.

        Raises
        ------
        RuntimeError
            If no active session.
        """
        if not self._session_active:
            msg = "No active debug session. Call start_session() first."
            raise RuntimeError(msg)

    def _format_execution_state(self, result: Any) -> dict[str, Any]:  # noqa: C901
        """Format execution state from interface result.

        Adapter that unifies MCP string format and API object format into a
        common test interface. Handles:
        - MCP format: location = "file.py:123"
        - DAP format: location.line + location.source.path
        - API format: execution_state.current_file + execution_state.current_line
        - Direct fields: result.line + result.file

        Parameters
        ----------
        result : Any
            Result object (dict or object with attributes)

        Returns
        -------
        dict[str, Any]
            Formatted state with keys: stopped, reason, location, line, file
        """
        import logging

        logger = logging.getLogger(__name__)

        def get_value(obj, key, default=None):
            """Get value from dict or object."""
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        stopped = get_value(result, "stopped", False)
        reason = get_value(result, "reason", "unknown")

        logger.debug(
            f"[_format_execution_state] Initial values: stopped={stopped}, reason={reason}",
        )

        # Check execution_state for both MCP and API formats
        exec_state = get_value(result, "execution_state")
        if exec_state:
            logger.debug(f"[_format_execution_state] Found exec_state: {exec_state}")

            # Both MCP and API responses have stop_reason in execution_state
            stop_reason_value = get_value(exec_state, "stop_reason")
            if stop_reason_value:
                # Handle enum values (API format: StopReason.BREAKPOINT)
                if hasattr(stop_reason_value, "name"):
                    # Get enum name and convert to lowercase for consistency
                    reason = str(stop_reason_value.name).lower()
                # Handle string values (MCP format: "breakpoint")
                elif isinstance(stop_reason_value, str):
                    reason = stop_reason_value
                else:
                    # Fallback: convert to string
                    reason = str(stop_reason_value)
                logger.debug(
                    f"[_format_execution_state] Updated reason from stop_reason: {reason}",
                )

            # Check paused state but don't automatically convert to stopped
            # This prevents masking termination states with stale paused=True values
            paused = get_value(exec_state, "paused", False)
            logger.debug(
                f"[_format_execution_state] paused={paused}, stopped={stopped}, reason={reason}",
            )

            # Only set stopped if we have a valid stop reason
            # This prevents converting stale paused state to stopped after termination
            if paused and not stopped and reason and reason != "unknown":
                logger.debug(
                    "[_format_execution_state] Setting stopped=True based on paused state",
                )
                stopped = True
            else:
                logger.debug(
                    f"[_format_execution_state] NOT setting stopped=True: "
                    f"paused={paused}, stopped={stopped}, reason={reason}",
                )

        # Determine running and terminated states
        running = False
        terminated = False

        if exec_state:
            # Check for status field (SessionStatus enum or string)
            status = get_value(exec_state, "status")
            if status:
                logger.debug(f"[_format_execution_state] Found status: {status}")
                # Handle string values
                if isinstance(status, str):
                    status_upper = status.upper()
                    terminated = status_upper in ("TERMINATED", "ERROR")
                    running = status_upper == "RUNNING"
                # Handle enum values
                elif hasattr(status, "name"):
                    terminated = status.name in ("TERMINATED", "ERROR")
                    running = status.name == "RUNNING"
                logger.debug(
                    f"[_format_execution_state] From status: terminated={terminated}, running={running}",
                )

            # Also check explicit boolean flags
            if not running and not terminated:
                running = get_value(exec_state, "running", False)
                terminated = get_value(exec_state, "terminated", False)
                logger.debug(
                    f"[_format_execution_state] From flags: running={running}, terminated={terminated}",
                )

        state = {
            "stopped": stopped,
            "reason": reason,
            "running": running,
            "terminated": terminated,
        }

        logger.debug(f"[_format_execution_state] Pre-location state: {state}")

        # Handle location info - multiple formats
        location = get_value(result, "location")

        if location:
            # Case 1: String format "file.py:123" (MCP format)
            if isinstance(location, str) and ":" in location:
                parts = location.rsplit(":", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    state["file"] = parts[0]
                    state["line"] = int(parts[1])
                    state["location"] = location
                else:
                    # Keep location but couldn't parse it
                    state["location"] = location
            # Case 2: Dict/object with line/source (DAP format)
            elif isinstance(location, dict) or hasattr(location, "line"):
                state["location"] = location
                state["line"] = get_value(location, "line")
                source = get_value(location, "source")
                if source:
                    state["file"] = get_value(source, "path")

        # Fallback: Try direct fields (legacy format)
        if "line" not in state and (line := get_value(result, "line")) is not None:
            state["line"] = line
        if "file" not in state and (file := get_value(result, "file")) is not None:
            state["file"] = file

        # Check execution_state attribute (API nested format)
        if "line" not in state or "file" not in state:
            exec_state = get_value(result, "execution_state")
            if exec_state:
                if (
                    "line" not in state
                    and (current_line := get_value(exec_state, "current_line"))
                    is not None
                ):
                    state["line"] = current_line
                    logger.debug(
                        f"[_format_execution_state] Set line from exec_state: {current_line}",
                    )
                if (
                    "file" not in state
                    and (current_file := get_value(exec_state, "current_file"))
                    is not None
                ):
                    state["file"] = current_file
                    logger.debug(
                        f"[_format_execution_state] Set file from exec_state: {current_file}",
                    )

        logger.debug(f"[_format_execution_state] Final state: {state}")
        return state
