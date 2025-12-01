"""Generic response validation assertions.

This module provides assertions for validating response structure, content, and timing.
"""

import json
from typing import Any


class ResponseAssertions:
    """Generic response validation assertions."""

    @staticmethod
    def assert_response_structure(
        response: dict[str, Any],
        expected_fields: list[str],
    ) -> None:
        """Assert that a response has expected structure.

        Parameters
        ----------
        response : Dict[str, Any]
            Response dictionary to verify
        expected_fields : List[str]
            List of required field names

        Raises
        ------
        AssertionError
            If response is missing required fields
        """
        for field in expected_fields:
            assert field in response, f"Response missing required field: {field}"

    @staticmethod
    def assert_json_serializable(data: Any) -> None:
        """Assert that data is JSON serializable.

        Parameters
        ----------
        data : Any
            Data to check for JSON serializability

        Raises
        ------
        AssertionError
            If data cannot be serialized to JSON
        """
        try:
            json.dumps(data)
        except (TypeError, ValueError) as e:
            msg = f"Data is not JSON serializable: {e}"
            raise AssertionError(msg) from e

    @staticmethod
    def assert_response_time(response_time: float, max_time: float) -> None:
        """Assert that response time is within acceptable limits.

        Parameters
        ----------
        response_time : float
            Actual response time in seconds
        max_time : float
            Maximum acceptable response time in seconds

        Raises
        ------
        AssertionError
            If response time exceeds limit
        """
        assert response_time <= max_time, (
            f"Response time {response_time:.3f}s exceeds limit {max_time:.3f}s"
        )

    @staticmethod
    def assert_response_contains(response: dict[str, Any], **expected_values) -> None:
        """Assert that response contains expected key-value pairs.

        Parameters
        ----------
        response : Dict[str, Any]
            Response dictionary to check
        **expected_values
            Expected key-value pairs

        Raises
        ------
        AssertionError
            If response doesn't contain expected values
        """
        for key, expected_value in expected_values.items():
            assert key in response, f"Response missing key: {key}"
            actual_value = response[key]
            assert actual_value == expected_value, (
                f"Expected {key}='{expected_value}', got '{actual_value}'"
            )
