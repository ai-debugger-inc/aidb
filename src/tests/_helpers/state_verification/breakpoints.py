"""Breakpoint state verification utilities.

This module provides the BreakpointStateVerifier class for validating breakpoint state
during debugging sessions.
"""

from pathlib import Path
from typing import Any


class BreakpointStateVerifier:
    """Verify breakpoint state and hit patterns.

    This verifier provides methods to validate breakpoint setup, verification, and
    behavior during debugging sessions.
    """

    @staticmethod
    def verify_breakpoint_set(bp_info: dict[str, Any]) -> None:
        """Verify a breakpoint was successfully set.

        Parameters
        ----------
        bp_info : dict[str, Any]
            Breakpoint information from set_breakpoint()

        Raises
        ------
        AssertionError
            If breakpoint info is missing required fields
        """
        required_fields = ["id", "line", "file"]

        missing = [field for field in required_fields if field not in bp_info]
        if missing:
            msg = f"Breakpoint info missing required fields: {missing}"
            raise AssertionError(msg)

    @staticmethod
    def verify_breakpoint_verified(bp_info: dict[str, Any]) -> None:
        """Verify a breakpoint was verified by the debug adapter.

        Parameters
        ----------
        bp_info : dict[str, Any]
            Breakpoint information from set_breakpoint()

        Raises
        ------
        AssertionError
            If breakpoint was not verified
        """
        BreakpointStateVerifier.verify_breakpoint_set(bp_info)

        verified = bp_info.get("verified", False)
        if not verified:
            line = bp_info.get("line", "unknown")
            file = bp_info.get("file", "unknown")
            msg = f"Breakpoint at {file}:{line} was not verified by debug adapter"
            raise AssertionError(msg)

    @staticmethod
    def verify_breakpoint_at_line(
        breakpoints: list[dict[str, Any]],
        expected_file: str | Path,
        expected_line: int,
    ) -> None:
        """Verify a breakpoint exists at the specified location.

        Parameters
        ----------
        breakpoints : list[dict[str, Any]]
            List of breakpoints from list_breakpoints()
        expected_file : str | Path
            Expected file path
        expected_line : int
            Expected line number

        Raises
        ------
        AssertionError
            If no breakpoint exists at the location
        """
        expected_file_str = str(expected_file)

        matching = [
            bp
            for bp in breakpoints
            if bp.get("line") == expected_line
            and expected_file_str in str(bp.get("file", ""))
        ]

        if not matching:
            locations = [f"{bp.get('file')}:{bp.get('line')}" for bp in breakpoints]
            msg = (
                f"No breakpoint found at {expected_file_str}:{expected_line}. "
                f"Existing breakpoints: {locations}"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_conditional_breakpoint(
        bp_info: dict[str, Any],
        expected_condition: str,
    ) -> None:
        """Verify a breakpoint has the expected condition.

        Parameters
        ----------
        bp_info : dict[str, Any]
            Breakpoint information from set_breakpoint()
        expected_condition : str
            Expected conditional expression

        Raises
        ------
        AssertionError
            If breakpoint doesn't have the expected condition
        """
        BreakpointStateVerifier.verify_breakpoint_set(bp_info)

        actual_condition = bp_info.get("condition")
        if actual_condition != expected_condition:
            msg = (
                f"Breakpoint condition mismatch: "
                f"expected '{expected_condition}', got '{actual_condition}'"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_hit_condition(
        bp_info: dict[str, Any],
        expected_hit_condition: str,
    ) -> None:
        """Verify a breakpoint has the expected hit condition.

        Parameters
        ----------
        bp_info : dict[str, Any]
            Breakpoint information from set_breakpoint()
        expected_hit_condition : str
            Expected hit condition (e.g., '>5', '==3')

        Raises
        ------
        AssertionError
            If breakpoint doesn't have the expected hit condition
        """
        BreakpointStateVerifier.verify_breakpoint_set(bp_info)

        actual_hit_condition = bp_info.get("hit_condition")
        if actual_hit_condition != expected_hit_condition:
            msg = (
                f"Breakpoint hit condition mismatch: "
                f"expected '{expected_hit_condition}', got '{actual_hit_condition}'"
            )
            raise AssertionError(msg)

    @staticmethod
    def verify_logpoint(
        bp_info: dict[str, Any],
        expected_log_message: str,
    ) -> None:
        """Verify a logpoint has the expected log message.

        Parameters
        ----------
        bp_info : dict[str, Any]
            Breakpoint information from set_breakpoint()
        expected_log_message : str
            Expected log message

        Raises
        ------
        AssertionError
            If logpoint doesn't have the expected log message
        """
        BreakpointStateVerifier.verify_breakpoint_set(bp_info)

        actual_log_message = bp_info.get("log_message")
        if actual_log_message != expected_log_message:
            msg = (
                f"Logpoint message mismatch: "
                f"expected '{expected_log_message}', got '{actual_log_message}'"
            )
            raise AssertionError(msg)
