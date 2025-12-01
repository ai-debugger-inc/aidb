"""Base test class for integration tests.

This module provides the base class for integration tests that span multiple components
and operations.
"""

from pathlib import Path
from typing import Any

from tests._helpers.debug_interface import DebugInterface
from tests._helpers.session_helpers import (
    debug_session,
    get_step_method,
    run_to_completion,
)
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class BaseIntegrationTest(BaseDebugTest):
    """Base class for integration tests spanning multiple components.

    This class extends BaseDebugTest with additional utilities for integration
    testing that involves multiple operations and state transitions.

    Usage
    -----
    Inherit from this class for integration tests:

        class TestComplexWorkflow(BaseIntegrationTest):
            @pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
            @pytest.mark.asyncio
            async def test_workflow(self, debug_interface, temp_workspace):
                # Use helper methods
                session_info = await self.start_session_with_breakpoints(...)
                await self.verify_execution_flow(...)
    """

    async def start_session_with_breakpoints(
        self,
        debug_interface: DebugInterface,
        program: Path,
        breakpoint_lines: list[int] | list[dict[str, Any]],
        **launch_args: Any,
    ) -> dict[str, Any]:
        """Start a debug session with multiple breakpoints.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : Path
            Program file to debug
        breakpoint_lines : list[int] | list[dict[str, Any]]
            Line numbers for initial breakpoints, or breakpoint dicts with conditions
        **launch_args : dict
            Additional launch arguments

        Returns
        -------
        dict[str, Any]
            Session information
        """
        # Handle both simple line numbers and complex breakpoint dicts
        breakpoints = []
        for bp_or_line in breakpoint_lines:
            if isinstance(bp_or_line, dict):
                # Already a breakpoint dict, but ensure file path is a string
                bp_dict = bp_or_line.copy()
                if "file" in bp_dict:
                    bp_dict["file"] = str(bp_dict["file"])
                breakpoints.append(bp_dict)
            else:
                # Simple line number, convert to breakpoint dict
                breakpoints.append({"file": str(program), "line": bp_or_line})

        return await debug_interface.start_session(
            program=program,
            breakpoints=breakpoints,
            **launch_args,
        )

    async def verify_execution_flow(
        self,
        debug_interface: DebugInterface,
        expected_stops: list[int],
    ) -> list[dict[str, Any]]:
        """Verify execution stops at expected lines in sequence.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        expected_stops : list[int]
            Expected line numbers in order

        Returns
        -------
        list[dict[str, Any]]
            List of execution states at each stop

        Raises
        ------
        AssertionError
            If execution doesn't follow expected flow
        """
        states = []

        for expected_line in expected_stops:
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(state, expected_line=expected_line)
            states.append(state)

        return states

    async def collect_variables_at_stops(
        self,
        debug_interface: DebugInterface,
        stop_lines: list[int],
        scope: str = "locals",
    ) -> list[dict[str, Any]]:
        """Collect variables at multiple execution stops.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        stop_lines : list[int]
            Lines where execution should stop
        scope : str, optional
            Variable scope to collect, default "locals"

        Returns
        -------
        list[dict[str, Any]]
            List of variable dictionaries at each stop
        """
        all_variables = []

        for line in stop_lines:
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(state, expected_line=line)

            variables = await debug_interface.get_variables(scope=scope)
            all_variables.append(variables)

        return all_variables

    async def run_complete_workflow(
        self,
        debug_interface: DebugInterface,
        program: Path,
    ) -> dict[str, Any]:
        """Helper method to run a complete test workflow from start to finish.

        This helper starts a session, runs to completion, and returns the
        final execution state.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : Path
            Program file to debug

        Returns
        -------
        dict[str, Any]
            Final execution state
        """
        async with debug_session(debug_interface, program):
            final_state = await run_to_completion(debug_interface)
            self.verify_exec.verify_completion(final_state)
            return final_state

    async def step_and_verify_variables(
        self,
        debug_interface: DebugInterface,
        expected_changes: dict[str, Any],
        step_type: str = "over",
    ) -> dict[str, Any]:
        """Step execution and verify expected variable changes.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        expected_changes : dict[str, Any]
            Expected variable name to value mappings after step
        step_type : str, optional
            Type of step ("over", "into", "out"), default "over"

        Returns
        -------
        dict[str, Any]
            Execution state after step

        Raises
        ------
        ValueError
            If invalid step_type provided
        """
        # Execute step using helper
        step_method = get_step_method(debug_interface, step_type)
        state = await step_method()

        # Verify variables if execution stopped
        if state.get("stopped"):
            variables = await debug_interface.get_variables()
            self.verify_vars.verify_variables_match(variables, expected_changes)

        return state

    async def set_breakpoint(
        self,
        debug_interface: DebugInterface,
        file_path: Path,
        line: int,
    ) -> dict[str, Any]:
        """Set a breakpoint at the specified file and line.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        file_path : Path
            Path to the file where breakpoint should be set
        line : int
            Line number for the breakpoint

        Returns
        -------
        dict[str, Any]
            Breakpoint information
        """
        return await debug_interface.set_breakpoint(
            file=str(file_path),
            line=line,
        )

    async def clear_all_breakpoints(
        self,
        debug_interface: DebugInterface,
    ) -> None:
        """Clear all breakpoints from the current debug session.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        """
        breakpoints = await debug_interface.list_breakpoints()
        for bp in breakpoints:
            bp_id = bp.get("id")
            if bp_id is not None:
                await debug_interface.remove_breakpoint(bp_id)
