"""Unit test assertion helpers.

Provides specialized assertions for common unit test patterns, reducing boilerplate and
providing clearer failure messages.
"""

from typing import Any
from unittest.mock import MagicMock


class UnitAssertions:
    """Lightweight assertions for unit tests.

    Provides helper methods for common assertion patterns in AIDB unit tests, with clear
    failure messages.
    """

    @staticmethod
    def assert_called_with_timeout(
        mock: MagicMock,
        timeout: float,
        tolerance: float = 0.1,
    ) -> None:
        """Assert mock was called with approximately the expected timeout.

        Parameters
        ----------
        mock : MagicMock
            Mock to check
        timeout : float
            Expected timeout value
        tolerance : float
            Allowed deviation from expected value

        Raises
        ------
        AssertionError
            If timeout doesn't match within tolerance
        """
        call_args = mock.call_args
        assert call_args is not None, "Mock was not called"

        # Check kwargs first, then positional args
        actual_timeout = call_args.kwargs.get("timeout")
        if actual_timeout is None and call_args.args:
            actual_timeout = call_args.args[-1]

        assert actual_timeout is not None, "No timeout argument found"
        assert abs(actual_timeout - timeout) < tolerance, (
            f"Expected timeout ~{timeout}, got {actual_timeout}"
        )

    @staticmethod
    def assert_request_sent(
        mock_transport: MagicMock,
        command: str,
        **expected_args: Any,
    ) -> None:
        """Assert a DAP request was sent with expected arguments.

        Parameters
        ----------
        mock_transport : MagicMock
            Mock transport to check
        command : str
            Expected command name
        **expected_args
            Expected argument key-value pairs

        Raises
        ------
        AssertionError
            If no matching request was found
        """
        calls = mock_transport.send_message.call_args_list
        matching = []

        for call in calls:
            msg = call.args[0] if call.args else {}
            if isinstance(msg, dict) and msg.get("command") == command:
                matching.append(msg)

        assert matching, f"No {command} request found in {len(calls)} calls"

        if expected_args:
            last_call = matching[-1]
            actual_args = last_call.get("arguments", {})
            for key, value in expected_args.items():
                assert key in actual_args, (
                    f"Expected argument '{key}' not found in {command} request"
                )
                assert actual_args[key] == value, (
                    f"Expected {key}={value}, got {key}={actual_args[key]}"
                )

    @staticmethod
    def assert_error_logged(
        mock_ctx: MagicMock,
        message_contains: str,
    ) -> None:
        """Assert an error was logged containing the message.

        Parameters
        ----------
        mock_ctx : MagicMock
            Mock context to check
        message_contains : str
            Substring that should appear in logged error

        Raises
        ------
        AssertionError
            If no matching error was logged
        """
        calls = mock_ctx.error.call_args_list
        messages = [str(call) for call in calls]

        assert any(message_contains in m for m in messages), (
            f"Expected error containing '{message_contains}' but got: {messages}"
        )

    @staticmethod
    def assert_warning_logged(
        mock_ctx: MagicMock,
        message_contains: str,
    ) -> None:
        """Assert a warning was logged containing the message.

        Parameters
        ----------
        mock_ctx : MagicMock
            Mock context to check
        message_contains : str
            Substring that should appear in logged warning

        Raises
        ------
        AssertionError
            If no matching warning was logged
        """
        calls = mock_ctx.warning.call_args_list
        messages = [str(call) for call in calls]

        assert any(message_contains in m for m in messages), (
            f"Expected warning containing '{message_contains}' but got: {messages}"
        )

    @staticmethod
    def assert_debug_logged(
        mock_ctx: MagicMock,
        message_contains: str,
    ) -> None:
        """Assert a debug message was logged containing the message.

        Parameters
        ----------
        mock_ctx : MagicMock
            Mock context to check
        message_contains : str
            Substring that should appear in logged message

        Raises
        ------
        AssertionError
            If no matching debug message was logged
        """
        calls = mock_ctx.debug.call_args_list
        messages = [str(call) for call in calls]

        assert any(message_contains in m for m in messages), (
            f"Expected debug message containing '{message_contains}' "
            f"but got: {messages}"
        )

    @staticmethod
    def assert_no_errors_logged(mock_ctx: MagicMock) -> None:
        """Assert no errors were logged.

        Parameters
        ----------
        mock_ctx : MagicMock
            Mock context to check

        Raises
        ------
        AssertionError
            If any errors were logged
        """
        calls = mock_ctx.error.call_args_list
        assert not calls, f"Expected no errors but got: {calls}"

    @staticmethod
    def assert_async_mock_awaited(
        mock: MagicMock,
        times: int | None = None,
    ) -> None:
        """Assert an async mock was awaited.

        Parameters
        ----------
        mock : MagicMock
            Async mock to check
        times : int, optional
            Expected number of awaits (None for at least once)

        Raises
        ------
        AssertionError
            If mock was not awaited as expected
        """
        if times is None:
            assert mock.await_count > 0, "Async mock was never awaited"
        else:
            assert mock.await_count == times, (
                f"Expected {times} awaits, got {mock.await_count}"
            )

    @staticmethod
    def assert_dap_response_success(response: Any) -> None:
        """Assert a DAP response indicates success.

        Parameters
        ----------
        response : Any
            DAP response object or dict

        Raises
        ------
        AssertionError
            If response indicates failure
        """
        if hasattr(response, "success"):
            success = response.success
            message = getattr(response, "message", None)
        elif isinstance(response, dict):
            success = response.get("success", False)
            message = response.get("message")
        else:
            msg = f"Unknown response type: {type(response)}"
            raise TypeError(msg)

        assert success, f"Expected success but got failure: {message}"

    @staticmethod
    def assert_dap_response_failure(
        response: Any,
        message_contains: str | None = None,
    ) -> None:
        """Assert a DAP response indicates failure.

        Parameters
        ----------
        response : Any
            DAP response object or dict
        message_contains : str, optional
            Expected substring in error message

        Raises
        ------
        AssertionError
            If response indicates success or wrong message
        """
        if hasattr(response, "success"):
            success = response.success
            message = getattr(response, "message", "")
        elif isinstance(response, dict):
            success = response.get("success", True)
            message = response.get("message", "")
        else:
            msg = f"Unknown response type: {type(response)}"
            raise TypeError(msg)

        assert not success, "Expected failure but got success"

        if message_contains:
            assert message_contains in (message or ""), (
                f"Expected message containing '{message_contains}' but got: {message}"
            )
