"""State validation assertions for debugging sessions.

This module provides assertions for verifying session state, variables, stack frames,
and execution state.
"""

from typing import Any


class StateAssertions:
    """State validation assertions for debugging sessions."""

    @staticmethod
    def assert_session_state(session_info: dict[str, Any], expected_state: str) -> None:
        """Assert that session is in expected state.

        Parameters
        ----------
        session_info : Dict[str, Any]
            Session information dictionary
        expected_state : str
            Expected session state

        Raises
        ------
        AssertionError
            If session is not in expected state
        """
        actual_state = session_info.get("status", session_info.get("state", "unknown"))
        assert actual_state == expected_state, (
            f"Expected session state '{expected_state}', got '{actual_state}'"
        )

    @staticmethod
    def assert_variable_value(
        variables: dict[str, Any],
        var_name: str,
        expected_value: Any,
        expected_type: str | None = None,
    ) -> None:
        """Assert that a variable has expected value and type.

        Parameters
        ----------
        variables : Dict[str, Any]
            Variables dictionary from debug session
        var_name : str
            Variable name to check
        expected_value : Any
            Expected variable value
        expected_type : str, optional
            Expected variable type

        Raises
        ------
        AssertionError
            If variable doesn't match expectations
        """
        assert var_name in variables, f"Variable '{var_name}' not found in variables"

        var_info = variables[var_name]

        if isinstance(var_info, dict):
            actual_value = var_info.get("value", var_info)
            actual_type = var_info.get("type")
        else:
            actual_value = var_info
            actual_type = None

        assert str(actual_value) == str(expected_value), (
            f"Variable '{var_name}' value mismatch: expected '{expected_value}', "
            f"got '{actual_value}'"
        )

        if expected_type and actual_type:
            assert actual_type == expected_type, (
                f"Variable '{var_name}' type mismatch: expected '{expected_type}', "
                f"got '{actual_type}'"
            )

    @staticmethod
    def assert_stack_frame(
        frame: dict[str, Any],
        expected_name: str | None = None,
        expected_line: int | None = None,
        expected_source: str | None = None,
    ) -> None:
        """Assert properties of a stack frame.

        Parameters
        ----------
        frame : Dict[str, Any]
            Stack frame dictionary
        expected_name : str, optional
            Expected function/method name
        expected_line : int, optional
            Expected line number
        expected_source : str, optional
            Expected source file name

        Raises
        ------
        AssertionError
            If frame properties don't match expectations
        """
        if expected_name:
            actual_name = frame.get("name", frame.get("function"))
            assert actual_name == expected_name, (
                f"Frame name mismatch: expected '{expected_name}', got '{actual_name}'"
            )

        if expected_line is not None:
            actual_line = frame.get("line")
            assert actual_line == expected_line, (
                f"Frame line mismatch: expected {expected_line}, got {actual_line}"
            )

        if expected_source:
            source_info = frame.get("source", {})
            if isinstance(source_info, dict) and source_info is not None:
                actual_source = source_info.get("path", source_info.get("name", ""))
            elif source_info is not None:
                actual_source = str(source_info)
            else:
                actual_source = ""

            if actual_source:
                assert expected_source in actual_source, (
                    f"Frame source mismatch: expected '{expected_source}' in "
                    f"'{actual_source}'"
                )

    @staticmethod
    def assert_has_frames(
        stack_trace: list[dict[str, Any]],
        min_frames: int | None = None,
        max_frames: int | None = None,
    ) -> None:
        """Assert stack trace has expected number of frames.

        Parameters
        ----------
        stack_trace : list[dict[str, Any]]
            Stack trace from get_stack_trace()
        min_frames : int, optional
            Minimum expected number of frames
        max_frames : int, optional
            Maximum expected number of frames

        Raises
        ------
        AssertionError
            If frame count doesn't meet expectations
        """
        actual_count = len(stack_trace)

        if min_frames is not None and actual_count < min_frames:
            msg = f"Expected at least {min_frames} stack frames, got {actual_count}"
            raise AssertionError(msg)

        if max_frames is not None and actual_count > max_frames:
            msg = f"Expected at most {max_frames} stack frames, got {actual_count}"
            raise AssertionError(msg)
