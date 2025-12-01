"""Base test class for all debug-related tests.

This module provides the foundational base class with common setup, teardown, and
utility methods for all debug testing.
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.assertions import (
    DebugInterfaceAssertions,
    PerformanceAssertions,
    StateAssertions,
)
from tests._helpers.constants import TestTimeouts
from tests._helpers.debug_interface import DebugInterface
from tests._helpers.session_helpers import cleanup_session
from tests._helpers.state_verification import (
    BreakpointStateVerifier,
    ExecutionStateVerifier,
    VariableStateVerifier,
)


class BaseDebugTest:
    """Base class for all debug-related tests.

    This class provides common functionality for debug testing including:
    - Automatic session cleanup
    - Assertion helper access
    - State verifier access
    - Temp workspace utilities

    Usage
    -----
    Inherit from this class in your test classes:

        class TestMyFeature(BaseDebugTest):
            @pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
            @pytest.mark.asyncio
            async def test_something(self, debug_interface, temp_workspace):
                # Test implementation
                pass

    The class automatically provides:
    - self.assert_interface - DebugInterfaceAssertions instance
    - self.assert_state - StateAssertions instance
    - self.assert_perf - PerformanceAssertions instance
    - self.verify_exec - ExecutionStateVerifier instance
    - self.verify_vars - VariableStateVerifier instance
    - self.verify_bp - BreakpointStateVerifier instance
    """

    # Provide default verifier instances at class level so tests that run in
    # environments where autouse fixtures are bypassed still have access to
    # these helpers. The fixtures below will overwrite them per-test when run.
    verify_exec = ExecutionStateVerifier()
    verify_vars = VariableStateVerifier()
    verify_bp = BreakpointStateVerifier()

    @pytest.fixture(autouse=True)
    def _ensure_verifiers(self):
        """Ensure state verifiers are available for all tests.

        Some parametrization/collection edge cases can bypass the async autouse setup in
        certain environments. This guard ensures verify_* helpers are always present
        before any test runs.
        """
        if not hasattr(self, "verify_exec"):
            self.verify_exec = ExecutionStateVerifier()
        if not hasattr(self, "verify_vars"):
            self.verify_vars = VariableStateVerifier()
        if not hasattr(self, "verify_bp"):
            self.verify_bp = BreakpointStateVerifier()

    @pytest.fixture(autouse=True)
    async def setup_debug_test(
        self,
        debug_interface: DebugInterface | None = None,
    ) -> AsyncGenerator[None, None]:
        """Set up test environment and ensure cleanup.

        This fixture runs automatically for all tests in classes that inherit
        from BaseDebugTest. It provides:
        - Access to assertion helpers
        - Access to state verifiers
        - Automatic session cleanup on teardown

        Parameters
        ----------
        debug_interface : DebugInterface, optional
            Debug interface instance (injected by pytest)

        Yields
        ------
        None
        """
        # Set up assertion helpers
        self.assert_interface = DebugInterfaceAssertions()
        self.assert_state = StateAssertions()
        self.assert_perf = PerformanceAssertions()

        # Set up state verifiers
        self.verify_exec = ExecutionStateVerifier()
        self.verify_vars = VariableStateVerifier()
        self.verify_bp = BreakpointStateVerifier()

        # Store interface for cleanup
        self._debug_interface = debug_interface

        # Run test
        yield

        # Cleanup
        if debug_interface is not None:
            await cleanup_session(debug_interface, ignore_errors=True)

    async def start_session_with_breakpoints(
        self,
        debug_interface: DebugInterface,
        program: Path,
        breakpoint_lines: list[int],
        **launch_args: Any,
    ) -> dict[str, Any]:
        """Start a debug session with multiple breakpoints.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        program : Path
            Program file to debug
        breakpoint_lines : list[int]
            Line numbers for initial breakpoints
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

    def create_test_program(
        self,
        workspace: Path,
        filename: str,
        content: str,
    ) -> Path:
        """Create a test program file in the workspace.

        Parameters
        ----------
        workspace : Path
            Workspace directory
        filename : str
            Program filename
        content : str
            Program source code

        Returns
        -------
        Path
            Path to the created program file
        """
        program_file = workspace / filename
        program_file.write_text(content)
        return program_file

    def extract_line_markers(self, content: str) -> dict[str, int]:
        """Extract line number markers from test program comments.

        Parses comments like "# Line 5" or "// Line 10" to create a mapping
        of marker names to line numbers.

        Parameters
        ----------
        content : str
            Program source code with markers

        Returns
        -------
        dict[str, int]
            Mapping of marker names to line numbers

        Examples
        --------
        >>> content = '''
        ... def main():
        ...     x = 10  # Line 2
        ...     y = 20  # Line 3
        ... '''
        >>> markers = self.extract_line_markers(content)
        >>> markers
        {'2': 2, '3': 3}
        """
        markers: dict[str, int] = {}
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            # Look for markers in comments: # Line X or // Line X
            if "# Line " in line:
                marker = line.split("# Line ")[1].strip()
                markers[marker] = line_num
            elif "// Line " in line:
                marker = line.split("// Line ")[1].strip()
                markers[marker] = line_num

        return markers

    async def wait_for_stop(
        self,
        debug_interface: DebugInterface,
        timeout: float = TestTimeouts.DEFAULT,
    ) -> dict[str, Any]:
        """Wait for debugger to stop (at breakpoint or program end).

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface instance
        timeout : float, optional
            Maximum time to wait in seconds, default 5.0

        Returns
        -------
        dict[str, Any]
            Execution state when stopped

        Raises
        ------
        TimeoutError
            If debugger doesn't stop within timeout
        """
        import asyncio
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Try to get current state
            state = await debug_interface.continue_execution()
            if state.get("stopped"):
                return state

            await asyncio.sleep(0.1)

        msg = f"Debugger did not stop within {timeout} seconds"
        raise TimeoutError(msg)
