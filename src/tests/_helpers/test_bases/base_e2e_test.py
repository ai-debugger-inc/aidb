"""Base test class for end-to-end tests.

This module provides the base class for E2E tests using generated test programs.
"""

import asyncio
from pathlib import Path
from typing import Any

from tests._helpers.debug_interface import DebugInterface
from tests._helpers.test_bases.base_debug_test import BaseDebugTest


class BaseE2ETest(BaseDebugTest):
    """Base class for end-to-end tests with generated programs.

    This class extends BaseDebugTest with utilities specifically for E2E tests
    that use generated test programs with markers.

    Usage
    -----
    Inherit from this class for E2E tests:

        class TestCompleteScenario(BaseE2ETest):
            @pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
            @pytest.mark.asyncio
            async def test_scenario(
                self,
                debug_interface,
                generated_program_factory,
                language
            ):
                program = generated_program_factory("basic_variables", language)
                await self.run_generated_program_test(debug_interface, program)
    """

    async def run_generated_program_test(
        self,
        debug_interface: DebugInterface,
        program: dict[str, Any],
        verify_markers: bool = True,
    ) -> dict[str, Any]:
        """Run a complete test on a generated program.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : dict[str, Any]
            Generated program dictionary with path, markers, and metadata
        verify_markers : bool, optional
            Whether to verify all markers are valid, default True

        Returns
        -------
        dict[str, Any]
            Final execution state

        Raises
        ------
        AssertionError
            If markers are invalid or program structure is incorrect
        """
        # Verify program structure
        self._verify_program_structure(program)

        # Verify markers if requested
        if verify_markers:
            self._verify_program_markers(program)

        # Start session
        program_path = program["path"]
        await debug_interface.start_session(program=str(program_path))

        # Continue to completion
        from tests._helpers.session_helpers import run_to_completion

        final_state = await run_to_completion(debug_interface)

        # Verify completion
        self.verify_exec.verify_completion(final_state)

        return final_state

    async def set_breakpoint_at_marker(
        self,
        debug_interface: DebugInterface,
        program: dict[str, Any],
        marker_name: str,
    ) -> dict[str, Any]:
        """Set a breakpoint at a named marker in a generated program.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : dict[str, Any]
            Generated program dictionary
        marker_name : str
            Marker name (e.g., "var.init.counter")

        Returns
        -------
        dict[str, Any]
            Breakpoint information

        Raises
        ------
        KeyError
            If marker doesn't exist in program
        """
        markers = program.get("markers", {})
        if marker_name not in markers:
            available = list(markers.keys())
            msg = f"Marker '{marker_name}' not found. Available: {available}"
            raise KeyError(msg)

        line = markers[marker_name]
        program_path = program["path"]

        return await debug_interface.set_breakpoint(
            file=str(program_path),
            line=line,
        )

    async def run_to_marker(
        self,
        debug_interface: DebugInterface,
        program: dict[str, Any],
        marker_name: str,
    ) -> dict[str, Any]:
        """Continue execution until reaching a specific marker.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : dict[str, Any]
            Generated program dictionary
        marker_name : str
            Target marker name

        Returns
        -------
        dict[str, Any]
            Execution state at marker

        Raises
        ------
        KeyError
            If marker doesn't exist
        AssertionError
            If execution doesn't stop at marker
        """
        # Set temporary breakpoint at marker
        bp_info = await self.set_breakpoint_at_marker(
            debug_interface,
            program,
            marker_name,
        )

        # Continue to breakpoint
        state = await debug_interface.continue_execution()

        # Verify stopped at expected line
        expected_line = program["markers"][marker_name]
        self.verify_exec.verify_stopped(state, expected_line=expected_line)

        # Remove temporary breakpoint
        await debug_interface.remove_breakpoint(bp_info["id"])

        return state

    async def _test_marker_sequence(
        self,
        debug_interface: DebugInterface,
        program: dict[str, Any],
        marker_sequence: list[str],
    ) -> list[dict[str, Any]]:
        """Helper to test execution flow through a sequence of markers.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : dict[str, Any]
            Generated program dictionary
        marker_sequence : list[str]
            List of marker names in expected order

        Returns
        -------
        list[dict[str, Any]]
            Execution states at each marker

        Raises
        ------
        AssertionError
            If execution doesn't follow expected sequence
        """
        states = []

        for marker in marker_sequence:
            state = await self.run_to_marker(debug_interface, program, marker)
            states.append(state)

        return states

    def get_marker_line(
        self,
        program: dict[str, Any],
        marker_name: str,
    ) -> int:
        """Get line number for a marker.

        Parameters
        ----------
        program : dict[str, Any]
            Generated program dictionary
        marker_name : str
            Marker name

        Returns
        -------
        int
            Line number of the marker

        Raises
        ------
        KeyError
            If marker doesn't exist
        """
        markers = program.get("markers", {})
        if marker_name not in markers:
            available = list(markers.keys())
            msg = f"Marker '{marker_name}' not found. Available: {available}"
            raise KeyError(msg)

        return markers[marker_name]

    def get_all_markers(self, program: dict[str, Any]) -> dict[str, int]:
        """Get all markers from a generated program.

        Parameters
        ----------
        program : dict[str, Any]
            Generated program dictionary

        Returns
        -------
        dict[str, int]
            Mapping of marker names to line numbers
        """
        return program.get("markers", {})

    def _verify_program_structure(self, program: dict[str, Any]) -> None:
        """Verify generated program has required structure.

        Parameters
        ----------
        program : dict[str, Any]
            Generated program dictionary

        Raises
        ------
        AssertionError
            If program structure is invalid
        """
        required_fields = ["path", "markers", "scenario", "language"]
        missing = [field for field in required_fields if field not in program]

        if missing:
            msg = f"Generated program missing required fields: {missing}"
            raise AssertionError(msg)

        # Verify path exists
        program_path = Path(program["path"])
        if not program_path.exists():
            msg = f"Generated program file does not exist: {program_path}"
            raise AssertionError(msg)

    def _verify_program_markers(self, program: dict[str, Any]) -> None:
        """Verify program markers are valid.

        Parameters
        ----------
        program : dict[str, Any]
            Generated program dictionary

        Raises
        ------
        AssertionError
            If markers are invalid
        """
        markers = program.get("markers", {})

        if not markers:
            msg = "Generated program has no markers"
            raise AssertionError(msg)

        # Verify all marker lines are positive integers
        for marker_name, line_num in markers.items():
            if not isinstance(line_num, int) or line_num <= 0:
                msg = f"Invalid line number for marker '{marker_name}': {line_num}"
                raise AssertionError(msg)

    async def wait_for_stopped_state(
        self,
        debug_interface: DebugInterface,
        timeout: float = 5.0,
        expected_line: int | None = None,
    ) -> dict[str, Any]:
        """Wait for session to reach stopped state.

        This helper method waits for a debug session to transition to a stopped
        state, which is useful after session start or continue operations where
        the state change may be asynchronous.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        timeout : float, optional
            Maximum time to wait in seconds, default 5.0
        expected_line : int, optional
            If provided, wait for stopped state at this specific line

        Returns
        -------
        dict[str, Any]
            Execution state (stopped or last checked state if timeout)

        Raises
        ------
        TimeoutError
            If session doesn't reach stopped state within timeout
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            state = await debug_interface.get_state()

            # Check if stopped
            if state.get("stopped"):
                # If no specific line expected, return immediately
                if expected_line is None:
                    return state

                # If specific line expected, verify it matches
                if state.get("line") == expected_line:
                    return state

            # Not stopped yet or wrong line, wait a bit
            await asyncio.sleep(0.1)

        # Timeout reached - get final state for diagnostics
        final_state = await debug_interface.get_state()

        # Raise timeout error with diagnostic info
        stopped = final_state.get("stopped", False)
        line = final_state.get("line", "unknown")
        reason = final_state.get("reason", "unknown")

        if expected_line is not None:
            msg = (
                f"Timeout waiting for stopped state at line {expected_line} "
                f"after {timeout}s. Final state: stopped={stopped}, "
                f"line={line}, reason={reason}"
            )
        else:
            msg = (
                f"Timeout waiting for stopped state after {timeout}s. "
                f"Final state: stopped={stopped}, line={line}, reason={reason}"
            )

        raise TimeoutError(msg)
