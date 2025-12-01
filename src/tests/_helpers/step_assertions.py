"""Shared step assertion helpers for multi-language tests.

This module provides common assertion utilities for step-related tests, ensuring
consistent and strict validation of step operations.
"""

from typing import Any, Optional

from aidb_mcp.core.constants import StepAction


def check_execution_stopped_state(
    response_data: dict[str, Any],
) -> tuple[bool, str | None]:
    """Extract stopped state and stop_reason from execution response data.

    Returns
    -------
    tuple[bool, str | None]
        Tuple of (is_stopped, stop_reason)
    """
    # The stopped field should always be a boolean at the top level
    stopped = response_data.get("stopped", False)

    # stop_reason is a separate field (can be None)
    stop_reason = response_data.get("stop_reason")

    # Also check execution_state for consistency
    exec_state = response_data.get("execution_state", {})
    if exec_state:
        # Use execution_state values if top-level ones are missing
        if "stopped" in exec_state and stopped is False:
            stopped = exec_state.get("stopped", False)
        if "stop_reason" in exec_state and stop_reason is None:
            stop_reason = exec_state.get("stop_reason")

    return stopped, stop_reason


class StepAssertions:
    """Common assertions for step functionality."""

    @staticmethod
    def _validate_action(data: dict[str, Any], expected_action: str | None) -> None:
        """Validate the action field in the response.

        Parameters
        ----------
        data : Dict[str, Any]
            Response data
        expected_action : str, optional
            Expected step action
        """
        assert "action" in data, "Response missing action field"
        assert isinstance(data["action"], str), "action must be string"

        if expected_action:
            assert data["action"] == expected_action, (
                f"Action mismatch: expected '{expected_action}', got '{data['action']}'"
            )

        # Validate action is a valid StepAction value
        valid_actions = [e.value for e in StepAction]
        assert data["action"] in valid_actions, (
            f"Invalid action value: '{data['action']}'. Must be one of {valid_actions}"
        )

    @staticmethod
    def _validate_execution_state(
        data: dict[str, Any],
        expected_stopped: bool,
        expected_stop_reason: str,
    ) -> None:
        """Validate the execution_state field if present.

        Parameters
        ----------
        data : Dict[str, Any]
            Response data
        expected_stopped : bool
            Expected stopped state
        expected_stop_reason : str
            Expected stop reason
        """
        if "execution_state" not in data:
            return

        exec_state = data["execution_state"]
        assert isinstance(exec_state, dict), "execution_state must be dict"

        if "stopped" in exec_state:
            assert isinstance(
                exec_state["stopped"],
                bool,
            ), "execution_state.stopped must be boolean"
            assert exec_state["stopped"] == expected_stopped, (
                f"Expected stopped={expected_stopped}, got {exec_state['stopped']}"
            )

        if "stop_reason" in exec_state:
            assert exec_state["stop_reason"] == expected_stop_reason, (
                f"Expected stop_reason='{expected_stop_reason}', "
                f"got '{exec_state['stop_reason']}'"
            )

    @staticmethod
    def _validate_stopped_field(
        data: dict[str, Any],
        expected_stopped: bool,
        expected_stop_reason: str,
    ) -> None:
        """Validate the stopped field (for compatibility).

        Parameters
        ----------
        data : Dict[str, Any]
            Response data
        expected_stopped : bool
            Expected stopped state
        expected_stop_reason : str
            Expected stop reason
        """
        if "stopped" not in data:
            return

        # Should be boolean or dict with reason
        if isinstance(data["stopped"], bool):
            assert data["stopped"] == expected_stopped, (
                f"Expected stopped={expected_stopped}, got {data['stopped']}"
            )
        elif isinstance(data["stopped"], dict):
            # If it's a dict, it should have a reason field
            assert "reason" in data["stopped"], "stopped dict must have 'reason' field"
            assert data["stopped"]["reason"] == expected_stop_reason, (
                f"Expected stop reason '{expected_stop_reason}', "
                f"got '{data['stopped']['reason']}'"
            )
        else:
            msg = f"stopped field must be bool or dict, got {type(data['stopped'])}"
            raise AssertionError(msg)

    @staticmethod
    def _validate_location(data: dict[str, Any]) -> None:
        """Validate the location field if present.

        Parameters
        ----------
        data : Dict[str, Any]
            Response data
        """
        # Check current_location field
        if "current_location" in data:
            assert isinstance(
                data["current_location"],
                str | type(None),
            ), "current_location must be string or None"
            if data["current_location"]:
                # Validate format: file:line
                assert ":" in data["current_location"], (
                    f"Invalid location format: {data['current_location']}"
                )

        # Check location field
        elif "location" in data:
            assert isinstance(
                data["location"],
                str | type(None),
            ), "location must be string or None"
            if data["location"]:
                assert ":" in data["location"], (
                    f"Invalid location format: {data['location']}"
                )

    @staticmethod
    def assert_step_response_structure(
        response: dict[str, Any],
        expected_action: str | None = None,
        expected_stopped: bool = True,
        expected_stop_reason: str = "step",
        check_location: bool = True,
    ) -> None:
        """Assert that a step response has the expected structure.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from step operation
        expected_action : str, optional
            Expected step action ("into", "over", "out")
        expected_stopped : bool
            Whether execution should be stopped (default: True)
        expected_stop_reason : str
            Expected stop reason (default: "step")
        check_location : bool
            Whether to verify location field exists
        """
        assert "success" in response, "Response missing success field"
        assert response["success"] is True, f"Step operation failed: {response}"
        assert "data" in response, "Response missing data field"

        data = response["data"]

        # Validate action
        StepAssertions._validate_action(data, expected_action)

        # Validate execution state
        StepAssertions._validate_execution_state(
            data,
            expected_stopped,
            expected_stop_reason,
        )

        # Validate stopped field
        StepAssertions._validate_stopped_field(
            data,
            expected_stopped,
            expected_stop_reason,
        )

        # Validate location
        if check_location:
            StepAssertions._validate_location(data)

    @staticmethod
    def assert_step_moved_location(
        initial_location: dict[str, Any],
        new_location: dict[str, Any],
        should_change_line: bool = True,
        should_change_depth: bool | None = None,
    ) -> None:
        """Assert that stepping changed the execution location appropriately.

        Parameters
        ----------
        initial_location : Dict[str, Any]
            Initial stack frame or location info
        new_location : Dict[str, Any]
            New stack frame or location info after stepping
        should_change_line : bool
            Whether line number should have changed
        should_change_depth : bool, optional
            Whether stack depth should have changed (None = don't check)
        """
        # Extract line numbers - frames might have various field names
        initial_line = (
            initial_location.get("line")
            or initial_location.get("lineNumber")
            or initial_location.get("lineno")
        )
        new_line = (
            new_location.get("line")
            or new_location.get("lineNumber")
            or new_location.get("lineno")
        )

        assert initial_line is not None, (
            f"Initial location missing line number: {initial_location}"
        )
        assert new_line is not None, f"New location missing line number: {new_location}"

        if should_change_line:
            assert new_line != initial_line, (
                f"Line should have changed after step: {initial_line} -> {new_line}"
            )
        else:
            assert new_line == initial_line, (
                f"Line should not have changed: {initial_line} -> {new_line}"
            )

        # Check stack depth if specified
        if should_change_depth is not None:
            initial_depth = initial_location.get("depth", 0)
            new_depth = new_location.get("depth", 0)

            if should_change_depth:
                assert new_depth != initial_depth, (
                    f"Stack depth should have changed: {initial_depth} -> {new_depth}"
                )
            else:
                assert new_depth == initial_depth, (
                    f"Stack depth should not have changed: {initial_depth} -> {new_depth}"
                )

    @staticmethod
    def assert_step_terminated(response: dict[str, Any]) -> None:
        """Assert that step response indicates program termination.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from step operation
        """
        assert "data" in response, "Response missing data field"
        data = response["data"]

        # Check for terminated flag
        terminated = False

        if "terminated" in data:
            assert isinstance(data["terminated"], bool), "terminated must be boolean"
            terminated = data["terminated"]

        if "execution_state" in data:
            exec_state = data["execution_state"]
            if "terminated" in exec_state:
                assert isinstance(
                    exec_state["terminated"],
                    bool,
                ), "execution_state.terminated must be boolean"
                terminated = terminated or exec_state["terminated"]

        # Check if stopped with terminated reason
        if (
            "stopped" in data
            and isinstance(data["stopped"], dict)
            and data["stopped"].get("reason") == "terminated"
        ):
            terminated = True

        assert terminated, (
            "Step response should indicate program termination but doesn't"
        )

    @staticmethod
    def assert_step_requires_paused_state(response: dict[str, Any]) -> None:
        """Assert that step failed because debugger is not paused.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from failed step operation
        """
        assert "success" in response, "Response missing success field"
        assert response["success"] is False, (
            "Expected step to fail when not paused, but it succeeded"
        )

        # Check for appropriate error message
        if "error" in response:
            error = response["error"]
            error_msg = ""

            if isinstance(error, str):
                error_msg = error.lower()
            elif isinstance(error, dict):
                error_msg = str(error.get("message", "")).lower()

            # Should mention being paused/stopped or running state
            expected_keywords = ["paused", "stopped", "running", "not paused"]
            assert any(keyword in error_msg for keyword in expected_keywords), (
                f"Error message should indicate debugger not paused: {error}"
            )

    @staticmethod
    def assert_invalid_step_action(
        response: dict[str, Any],
        invalid_action: str,
    ) -> None:
        """Assert that step failed due to invalid action.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from failed step operation
        invalid_action : str
            The invalid action that was attempted
        """
        assert "success" in response, "Response missing success field"
        assert response["success"] is False, (
            f"Expected step with invalid action '{invalid_action}' to fail"
        )

        # Check error mentions the invalid action
        if "error" in response:
            error = response["error"]
            error_str = (
                str(error).lower() if not isinstance(error, str) else error.lower()
            )

            # Should mention the invalid action or valid actions
            assert invalid_action.lower() in error_str or "into" in error_str, (
                f"Error should mention invalid action '{invalid_action}': {error}"
            )

    @staticmethod
    def validate_step_count_behavior(
        responses: list[dict[str, Any]],
        expected_count: int,
    ) -> None:
        """Validate behavior when stepping with count parameter.

        Parameters
        ----------
        responses : list[Dict[str, Any]]
            List of responses or steps info
        expected_count : int
            Expected number of steps taken
        """
        assert len(responses) <= expected_count, (
            f"Should not exceed {expected_count} steps, got {len(responses)}"
        )

        # Check if terminated early
        terminated_early = False
        for i, resp in enumerate(responses):
            if isinstance(resp, dict) and (
                resp.get("terminated")
                or (
                    resp.get("stopped")
                    and isinstance(resp["stopped"], dict)
                    and resp["stopped"].get("reason") == "terminated"
                )
            ):
                terminated_early = True
                # Should be the last response
                assert i == len(responses) - 1, (
                    "Terminated response should be the last one"
                )

        if not terminated_early:
            assert len(responses) == expected_count, (
                f"Expected {expected_count} steps, got {len(responses)}"
            )
