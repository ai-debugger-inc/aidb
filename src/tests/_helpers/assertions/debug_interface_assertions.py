"""Interface-agnostic assertions for DebugInterface testing.

This module provides assertions that work with both MCP and API implementations of the
DebugInterface abstraction.
"""

from typing import Any


class DebugInterfaceAssertions:
    """Interface-agnostic assertions for DebugInterface testing.

    Provides assertions that work with both MCP and API implementations of the
    DebugInterface abstraction.
    """

    @staticmethod
    def assert_session_active(debug_interface, should_be_active: bool = True) -> None:
        """Assert debug session is in expected active state.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface to check
        should_be_active : bool, optional
            Expected active state, default True

        Raises
        ------
        AssertionError
            If session state doesn't match expectation
        """
        from tests._helpers.debug_interface import DebugInterface

        if not isinstance(debug_interface, DebugInterface):
            msg = f"Expected DebugInterface, got {type(debug_interface)}"
            raise AssertionError(msg)

        actual = debug_interface.is_session_active
        expected_state = "active" if should_be_active else "stopped"
        actual_state = "active" if actual else "stopped"

        if actual != should_be_active:
            msg = f"Expected session to be {expected_state}, but it is {actual_state}"
            raise AssertionError(msg)

    @staticmethod
    def assert_session_stopped(debug_interface) -> None:
        """Assert debug session is stopped.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface to check

        Raises
        ------
        AssertionError
            If session is still active
        """
        DebugInterfaceAssertions.assert_session_active(
            debug_interface,
            should_be_active=False,
        )

    @staticmethod
    def assert_at_breakpoint(
        execution_state: dict[str, Any],
        expected_line: int | None = None,
    ) -> None:
        """Assert execution stopped at a breakpoint.

        Parameters
        ----------
        execution_state : dict[str, Any]
            Execution state from continue/step operations
        expected_line : int, optional
            Expected line number if known

        Raises
        ------
        AssertionError
            If not stopped at breakpoint or wrong line
        """
        assert execution_state.get("stopped", False), "Expected execution to be stopped"
        assert execution_state.get("reason") == "breakpoint", (
            f"Expected stop reason 'breakpoint', got '{execution_state.get('reason')}'"
        )

        if expected_line is not None:
            actual_line = execution_state.get("line")
            assert actual_line == expected_line, (
                f"Expected to stop at line {expected_line}, but stopped at line {actual_line}"
            )

    @staticmethod
    def assert_execution_completed(execution_state: dict[str, Any]) -> None:
        """Assert execution completed successfully.

        Parameters
        ----------
        execution_state : dict[str, Any]
            Execution state from continue/step operations

        Raises
        ------
        AssertionError
            If execution didn't complete normally
        """
        stopped = execution_state.get("stopped", True)
        reason = execution_state.get("reason", "unknown")

        valid_completion_reasons = ("end", "exit", "terminated")

        if stopped and reason not in valid_completion_reasons:
            msg = f"Execution stopped unexpectedly with reason: {reason}"
            raise AssertionError(msg)

    @staticmethod
    def assert_variable_value(
        variables: dict[str, Any],
        name: str,
        expected_value: Any = None,
        expected_type: type | None = None,
    ) -> None:
        """Assert variable exists with expected value and/or type.

        Parameters
        ----------
        variables : dict[str, Any]
            Variables dictionary from get_variables()
        name : str
            Variable name to check
        expected_value : Any, optional
            Expected value if checking value
        expected_type : type, optional
            Expected type if checking type

        Raises
        ------
        AssertionError
            If variable missing or doesn't match expectations
        """
        assert name in variables, (
            f"Variable '{name}' not found in {list(variables.keys())}"
        )

        actual_value = variables[name]

        if expected_value is not None:
            if isinstance(actual_value, dict) and "value" in actual_value:
                actual_value = actual_value["value"]

            assert actual_value == expected_value, (
                f"Variable '{name}': expected value {expected_value}, got {actual_value}"
            )

        if expected_type is not None:
            check_value = actual_value
            if isinstance(actual_value, dict) and "value" in actual_value:
                check_value = actual_value["value"]

            assert isinstance(check_value, expected_type), (
                f"Variable '{name}': expected type {expected_type.__name__}, "
                f"got {type(check_value).__name__}"
            )

    @staticmethod
    def assert_stack_depth(
        stack_trace: list[dict[str, Any]],
        expected_depth: int,
    ) -> None:
        """Assert stack trace has expected depth.

        Parameters
        ----------
        stack_trace : list[dict[str, Any]]
            Stack trace from get_stack_trace()
        expected_depth : int
            Expected number of frames

        Raises
        ------
        AssertionError
            If stack depth doesn't match
        """
        actual_depth = len(stack_trace)
        assert actual_depth == expected_depth, (
            f"Expected stack depth {expected_depth}, got {actual_depth}"
        )

    @staticmethod
    def assert_breakpoint_verified(breakpoint: dict[str, Any]) -> None:
        """Assert breakpoint was successfully verified.

        Parameters
        ----------
        breakpoint : dict[str, Any]
            Breakpoint info from set_breakpoint()

        Raises
        ------
        AssertionError
            If breakpoint not verified
        """
        assert breakpoint.get("verified", False), (
            f"Breakpoint at line {breakpoint.get('line')} was not verified"
        )

    @staticmethod
    def assert_breakpoint_at_line(breakpoints: list[dict[str, Any]], line: int) -> None:
        """Assert a breakpoint exists at the specified line.

        Parameters
        ----------
        breakpoints : list[dict[str, Any]]
            Breakpoints from list_breakpoints()
        line : int
            Expected line number

        Raises
        ------
        AssertionError
            If no breakpoint at line
        """
        matching_bps = [bp for bp in breakpoints if bp.get("line") == line]
        assert len(matching_bps) > 0, f"No breakpoint found at line {line}"
