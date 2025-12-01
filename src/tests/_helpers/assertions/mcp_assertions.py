"""MCP-specific assertion helpers for AIDB test suite.

This module provides specialized assertions for MCP tool responses, validation of
response structure, content accuracy, and efficiency.
"""

from typing import Any


class MCPAssertions:
    """MCP (Model Context Protocol) specific assertions."""

    @staticmethod
    def assert_tool_response_success(
        response: dict[str, Any],
        tool_name: str | None = None,
    ) -> None:
        """Assert that an MCP tool response indicates success.

        Parameters
        ----------
        response : Dict[str, Any]
            Tool response to verify
        tool_name : str, optional
            Expected tool name in response

        Raises
        ------
        AssertionError
            If response indicates failure
        """
        # Handle both old and new response formats
        if "error" in response:
            # Error format
            error_obj = response.get("error", {})
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "Unknown error")
            else:
                error_msg = str(error_obj)
            msg = f"Tool failed with error: {error_msg}"
            raise AssertionError(msg)

        # Check for success field (required for all MCP responses)
        assert "success" in response, (
            "Response missing required 'success' field. "
            f"Got fields: {list(response.keys())}"
        )

        # Validate success is a boolean
        assert isinstance(
            response["success"],
            bool,
        ), (
            f"'success' field must be a boolean, got {type(response['success']).__name__}: {response['success']}"
        )

        # Check if this is actually a success
        assert response["success"], (
            f"Tool failed: "
            f"{response.get('error_message', response.get('error', 'Unknown error'))}"  # noqa: E501
        )

        # Success responses must have data field
        assert "data" in response, "Success response missing data field"

        # Validate data is a dict
        assert isinstance(
            response["data"],
            dict,
        ), (
            f"Success response data must be a dict, got {type(response['data']).__name__}"
        )

        if tool_name and "tool" in response:
            assert response["tool"] == tool_name, (
                f"Tool name mismatch: expected '{tool_name}', got '{response['tool']}'"
            )

    @staticmethod
    def assert_tool_response_error(
        response: dict[str, Any],
        error_code: str | None = None,
        error_message_contains: str | None = None,
    ) -> None:
        """Assert that an MCP tool response indicates an error.

        Parameters
        ----------
        response : Dict[str, Any]
            Tool response to verify
        error_code : str, optional
            Expected error code
        error_message_contains : str, optional
            Expected substring in error message

        Raises
        ------
        AssertionError
            If response doesn't indicate error or doesn't match expectations
        """
        # Check for error indication
        has_error = "error" in response or response.get("success") is False
        assert has_error, f"Expected error response but got: {response}"

        # Check error code if specified
        if error_code:
            actual_code = None
            if isinstance(response.get("error"), dict):
                actual_code = response["error"].get("code")
            if not actual_code:
                actual_code = response.get("error_code")

            assert actual_code == error_code, (
                f"Expected error code '{error_code}' but got '{actual_code}'"
            )

        # Check error message if specified
        if error_message_contains:
            error_msg = None
            if isinstance(response.get("error"), dict):
                error_msg = response["error"].get("message", "")
            if not error_msg:
                error_msg = response.get("error_message", "")

            assert error_message_contains in error_msg, (
                f"Expected error message to contain '{error_message_contains}' "
                f"but got: '{error_msg}'"
            )

    @staticmethod
    def assert_tool_called(
        tool_calls: list[dict[str, Any]],
        tool_name: str,
        **expected_args,
    ) -> None:
        """Assert that a tool was called with expected arguments.

        Parameters
        ----------
        tool_calls : List[Dict[str, Any]]
            List of tool call records
        tool_name : str
            Expected tool name
        **expected_args
            Expected argument values

        Raises
        ------
        AssertionError
            If tool was not called or arguments don't match
        """
        matching_calls = [call for call in tool_calls if call.get("name") == tool_name]

        assert matching_calls, f"Tool '{tool_name}' was not called"

        if expected_args:
            for call in matching_calls:
                args = call.get("arguments", {})
                if all(args.get(k) == v for k, v in expected_args.items()):
                    return  # Found matching call

            msg = (
                f"Tool '{tool_name}' was not called with expected arguments: "
                f"{expected_args}"
            )
            raise AssertionError(
                msg,
            )

    @staticmethod
    def assert_notification_sent(
        notifications: list[dict[str, Any]],
        method: str,
        **expected_params,
    ) -> None:
        """Assert that a notification was sent with expected parameters.

        Parameters
        ----------
        notifications : List[Dict[str, Any]]
            List of notification records
        method : str
            Expected notification method
        **expected_params
            Expected parameter values

        Raises
        ------
        AssertionError
            If notification was not sent or params don't match
        """
        matching_notifications = [n for n in notifications if n.get("method") == method]

        assert matching_notifications, f"Notification '{method}' was not sent"

        if expected_params:
            for notification in matching_notifications:
                params = notification.get("params", {})
                if all(params.get(k) == v for k, v in expected_params.items()):
                    return  # Found matching notification

            msg = (
                f"Notification '{method}' was not sent with expected params: "
                f"{expected_params}"
            )
            raise AssertionError(
                msg,
            )

    @staticmethod
    def assert_resource_valid(
        resource: dict[str, Any],
        expected_uri: str | None = None,
        expected_content_type: str | None = None,
    ) -> None:
        """Assert that a resource is valid.

        Parameters
        ----------
        resource : Dict[str, Any]
            Resource to validate
        expected_uri : str, optional
            Expected resource URI
        expected_content_type : str, optional
            Expected content type

        Raises
        ------
        AssertionError
            If resource is invalid
        """
        required_fields = ["uri", "name", "content"]
        for field in required_fields:
            assert field in resource, f"Resource missing required field: {field}"

        if expected_uri:
            assert resource["uri"] == expected_uri, (
                f"Resource URI mismatch: expected '{expected_uri}', "
                f"got '{resource['uri']}'"
            )

        if expected_content_type:
            content = resource.get("content", {})
            if isinstance(content, dict):
                actual_type = content.get("type", content.get("mimeType"))
                assert actual_type == expected_content_type, (
                    f"Content type mismatch: expected '{expected_content_type}', "
                    f"got '{actual_type}'"
                )

    # NEW METHODS FOR PHASE 1 RESPONSE HEALTH VALIDATION

    @staticmethod
    def assert_response_structure(response: dict[str, Any]) -> None:
        """Validate MCP response has required structure.

        Checks that response contains required fields: success, summary, data.
        Validates field types and basic structure.

        Parameters
        ----------
        response : Dict[str, Any]
            MCP response to validate

        Raises
        ------
        AssertionError
            If response is missing required fields or has invalid structure
        """
        # Required fields
        required_fields = ["success", "summary", "data"]
        for field in required_fields:
            assert field in response, (
                f"Response missing required field '{field}'. "
                f"Got fields: {list(response.keys())}"
            )

        # Field type validation
        assert isinstance(response["success"], bool), (
            f"Field 'success' must be bool, got {type(response['success']).__name__}"
        )
        assert isinstance(response["summary"], str), (
            f"Field 'summary' must be str, got {type(response['summary']).__name__}"
        )
        assert isinstance(response["data"], dict), (
            f"Field 'data' must be dict, got {type(response['data']).__name__}"
        )

    @staticmethod
    def assert_response_content_accuracy(
        response: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        """Validate specific data fields match expected values.

        Checks that response data contains expected fields with correct values.
        Provides detailed error messages for mismatches.

        Parameters
        ----------
        response : Dict[str, Any]
            MCP response to validate
        expected : Dict[str, Any]
            Expected field names and values in response["data"]

        Raises
        ------
        AssertionError
            If any expected field is missing or has wrong value
        """
        data = response.get("data", {})

        for field_name, expected_value in expected.items():
            assert field_name in data, (
                f"Response data missing expected field '{field_name}'. "
                f"Available fields: {list(data.keys())}"
            )

            actual_value = data[field_name]
            assert actual_value == expected_value, (
                f"Field '{field_name}' has incorrect value.\n"
                f"  Expected: {expected_value!r} ({type(expected_value).__name__})\n"
                f"  Got:      {actual_value!r} ({type(actual_value).__name__})"
            )

    @staticmethod
    def assert_response_efficiency(
        response: dict[str, Any],
        max_data_fields: int = 10,
        max_summary_chars: int = 200,
    ) -> None:
        """Validate response has no junk fields and summary is concise.

        Checks for response bloat - too many data fields or verbose summaries.
        This ensures responses are token-efficient for AI consumption.

        Parameters
        ----------
        response : Dict[str, Any]
            MCP response to validate
        max_data_fields : int, optional
            Maximum allowed fields in response data (default: 10)
        max_summary_chars : int, optional
            Maximum allowed characters in summary (default: 200)

        Raises
        ------
        AssertionError
            If response has too many fields or verbose summary
        """
        # Check data field count (no bloat)
        data = response.get("data", {})
        field_count = len(data)
        assert field_count <= max_data_fields, (
            f"Response data has too many fields ({field_count} > {max_data_fields}). "
            f"This indicates bloat. Fields: {list(data.keys())}"
        )

        # Check summary length (concise, not verbose)
        summary = response.get("summary", "")
        summary_length = len(summary)
        assert summary_length <= max_summary_chars, (
            f"Response summary is too long ({summary_length} > {max_summary_chars} chars). "
            f"Summaries should be concise. Got: {summary[:100]}..."
        )

        # Check for common junk fields that shouldn't be in production responses
        junk_fields = ["debug_info", "internal_state", "_metadata", "__debug"]
        for junk_field in junk_fields:
            assert junk_field not in data, (
                f"Response contains unnecessary field '{junk_field}'. "
                "Production responses should not include internal debugging fields."
            )

    @staticmethod
    def assert_next_steps_present(response: dict[str, Any]) -> None:
        """Validate critical tools include next_steps guidance.

        Entry-point tools (init, session_start) should always provide next_steps
        to guide users on what to do next.

        Parameters
        ----------
        response : Dict[str, Any]
            MCP response to validate

        Raises
        ------
        AssertionError
            If next_steps field is missing or invalid
        """
        assert "next_steps" in response, (
            "Critical entry-point tools must include 'next_steps' to guide users. "
            f"Response fields: {list(response.keys())}"
        )

        next_steps = response["next_steps"]
        assert isinstance(next_steps, list), (
            f"Field 'next_steps' must be a list, got {type(next_steps).__name__}"
        )
        assert len(next_steps) > 0, (
            "Field 'next_steps' must not be empty - provide at least one guidance step"
        )

        # Validate each next step has required structure
        for i, step in enumerate(next_steps):
            assert isinstance(step, dict), (
                f"next_steps[{i}] must be a dict, got {type(step).__name__}"
            )
            # Common next_step fields: tool, description, args (structure may vary)
            # Just validate it's a non-empty dict with useful content
            assert len(step) > 0, f"next_steps[{i}] is empty"

    @staticmethod
    def assert_session_id_present(response: dict[str, Any]) -> None:
        """Validate session-specific tools include session_id.

        Session-aware operations should return session_id so users know which
        session the response relates to.

        Parameters
        ----------
        response : Dict[str, Any]
            MCP response to validate

        Raises
        ------
        AssertionError
            If session_id is missing or invalid
        """
        assert "session_id" in response, (
            "Session-aware operations must include 'session_id' in response. "
            f"Response fields: {list(response.keys())}"
        )

        session_id = response["session_id"]
        assert session_id is not None, "Field 'session_id' must not be None"
        assert isinstance(session_id, str), (
            f"Field 'session_id' must be str, got {type(session_id).__name__}"
        )
        assert len(session_id) > 0, "Field 'session_id' must not be empty string"
