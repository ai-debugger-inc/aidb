"""Execution state verification utilities.

This module provides the ExecutionStateVerifier class for validating execution state
during debugging sessions.
"""

from pathlib import Path
from typing import Any

from tests._helpers.constants import StopReason, TerminationReason


class ExecutionStateVerifier:
    """Verify execution state during debugging sessions.

    This verifier provides methods to validate the current execution state, including
    stopped/running status, location, completion, and exceptions.
    """

    @staticmethod
    def verify_stopped(
        state: dict[str, Any],
        expected_line: int | None = None,
        expected_reason: str | None = None,
    ) -> None:
        """Verify execution is stopped at expected location and reason.

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations
        expected_line : int, optional
            Expected line number where execution stopped
        expected_reason : str, optional
            Expected stop reason (breakpoint, step, exception, etc.)

        Raises
        ------
        AssertionError
            If execution is not stopped or doesn't match expectations
        """
        stopped = state.get("stopped", False)
        if not stopped:
            msg = f"Expected execution to be stopped, but it is running. State: {state}"
            raise AssertionError(msg)

        if expected_reason is not None:
            actual_reason = state.get("reason", "unknown")
            if actual_reason != expected_reason:
                msg = (
                    f"Expected stop reason '{expected_reason}', "
                    f"but got '{actual_reason}'"
                )
                raise AssertionError(msg)

        if expected_line is not None:
            actual_line = state.get("line")
            if actual_line != expected_line:
                msg = (
                    f"Expected to stop at line {expected_line}, "
                    f"but stopped at line {actual_line}"
                )
                raise AssertionError(msg)

    @staticmethod
    def verify_running(state: dict[str, Any]) -> None:
        """Verify execution is currently running (not stopped).

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations

        Raises
        ------
        AssertionError
            If execution is stopped
        """
        stopped = state.get("stopped", False)
        if stopped:
            reason = state.get("reason", "unknown")
            msg = f"Expected execution to be running, but it is stopped (reason: {reason})"
            raise AssertionError(msg)

    @staticmethod
    def verify_at_location(
        state: dict[str, Any],
        expected_file: str | Path,
        expected_line: int,
    ) -> None:
        """Verify execution stopped at specific file and line.

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations
        expected_file : str | Path
            Expected file path
        expected_line : int
            Expected line number

        Raises
        ------
        AssertionError
            If execution is not at the expected location
        """
        # First verify it's stopped
        ExecutionStateVerifier.verify_stopped(state)

        # Check line
        actual_line = state.get("line")
        if actual_line != expected_line:
            msg = (
                f"Expected line {expected_line}, but execution is at line {actual_line}"
            )
            raise AssertionError(msg)

        # Check file if present
        actual_file = state.get("file")
        if actual_file is not None:
            expected_file_str = str(expected_file)
            if expected_file_str not in str(actual_file):
                msg = (
                    f"Expected file '{expected_file_str}', "
                    f"but execution is in '{actual_file}'"
                )
                raise AssertionError(msg)

    @staticmethod
    def verify_completion(
        state: dict[str, Any],
        expect_successful: bool = True,
    ) -> None:
        """Verify execution completed (program ended).

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations
        expect_successful : bool, optional
            Whether to expect successful completion (exit code 0), default True

        Raises
        ------
        AssertionError
            If execution didn't complete or completed with wrong status
        """
        stopped = state.get("stopped", True)
        terminated = state.get("terminated", False)
        reason = state.get("reason", "unknown")

        valid_completion_reasons = tuple(r.value for r in TerminationReason)

        # Execution is complete if either:
        # 1. stopped=True with a termination reason, OR
        # 2. terminated=True (explicit termination flag)
        is_complete = (stopped and reason in valid_completion_reasons) or terminated

        if not is_complete:
            msg = (
                f"Expected execution to complete, but it is "
                f"{'running' if not stopped and not terminated else f'stopped with reason: {reason}'}"
            )
            raise AssertionError(msg)

        if expect_successful and "exit_code" in state:
            exit_code = state["exit_code"]
            if exit_code != 0:
                msg = f"Expected successful completion (exit 0), but got exit code {exit_code}"
                raise AssertionError(msg)

    @staticmethod
    def verify_in_function(
        state: dict[str, Any],
        expected_function: str,
    ) -> None:
        """Verify execution is currently inside a specific function.

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations
        expected_function : str
            Expected function name

        Raises
        ------
        AssertionError
            If execution is not in the expected function
        """
        ExecutionStateVerifier.verify_stopped(state)

        # Check function name from location or stack frame info
        function_name = state.get("function")
        if function_name is None:
            location = state.get("location", {})
            if isinstance(location, dict):
                function_name = location.get("function")

        if function_name != expected_function:
            msg = (
                f"Expected execution in function '{expected_function}', "
                f"but found in '{function_name}'"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_exception_stopped(
        state: dict[str, Any],
        expected_exception_type: str | None = None,
    ) -> None:
        """Verify execution stopped due to an exception.

        Parameters
        ----------
        state : dict[str, Any]
            Execution state from continue/step operations
        expected_exception_type : str, optional
            Expected exception type name

        Raises
        ------
        AssertionError
            If execution didn't stop on exception or wrong exception type
        """
        ExecutionStateVerifier.verify_stopped(
            state,
            expected_reason=StopReason.EXCEPTION.value,
        )

        if expected_exception_type is not None:
            exception_info = state.get("exception_info", {})
            if isinstance(exception_info, dict):
                actual_type = exception_info.get("type", exception_info.get("name"))
            else:
                actual_type = str(exception_info)

            if expected_exception_type not in str(actual_type):
                msg = (
                    f"Expected exception type '{expected_exception_type}', "
                    f"but got '{actual_type}'"
                )
                raise AssertionError(msg)
