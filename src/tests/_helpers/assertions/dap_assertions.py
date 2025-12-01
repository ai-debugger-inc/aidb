"""DAP (Debug Adapter Protocol) specific assertion helpers.

This module provides specialized assertions for DAP messages, events, and protocol
interactions.
"""

from aidb.dap.protocol import (
    ContinuedEvent,
    ErrorResponse,
    ExitedEvent,
    InitializeResponse,
    OutputEvent,
    ProcessEvent,
    Response,
    StoppedEvent,
    TerminatedEvent,
    ThreadEvent,
)


class DAPAssertions:
    """Debug Adapter Protocol specific assertions."""

    @staticmethod
    def assert_response_success(response: Response) -> None:
        """Assert that a DAP response indicates success.

        Parameters
        ----------
        response : Response
            DAP response to verify

        Raises
        ------
        AssertionError
            If response indicates failure
        """
        assert response.success, f"DAP response failed: {response.message}"
        assert not isinstance(
            response,
            ErrorResponse,
        ), "Received ErrorResponse instead of success"

    @staticmethod
    def assert_response_error(
        response: Response,
        expected_message: str | None = None,
    ) -> None:
        """Assert that a DAP response indicates an error.

        Parameters
        ----------
        response : Response
            DAP response to verify
        expected_message : str, optional
            Expected error message pattern

        Raises
        ------
        AssertionError
            If response indicates success or wrong error
        """
        assert not response.success, "Expected error response but got success"
        if expected_message:
            assert expected_message in str(response.message), (
                f"Expected error message '{expected_message}' "
                f"not found in '{response.message}'"
            )

    @staticmethod
    def assert_breakpoint_set(response: Response, location: str) -> None:
        """Assert that a breakpoint was successfully set.

        Parameters
        ----------
        response : Response
            Response from setBreakpoints request
        location : str
            Expected breakpoint location (file:line)

        Raises
        ------
        AssertionError
            If breakpoint was not set correctly
        """
        DAPAssertions.assert_response_success(response)

        if (
            hasattr(response, "body")
            and response.body is not None
            and hasattr(response.body, "breakpoints")
        ):
            breakpoints = getattr(response.body, "breakpoints", [])
            assert len(breakpoints) > 0, "No breakpoints returned in response"

            bp = breakpoints[0]
            assert bp.get("verified", False), f"Breakpoint not verified: {bp}"

            if "source" in bp and "line" in bp:
                file_part, line_part = location.split(":")
                assert file_part in bp["source"].get(
                    "path",
                    "",
                ), f"Breakpoint file mismatch: expected {file_part}"
                assert int(line_part) == bp["line"], (
                    f"Breakpoint line mismatch: expected {line_part}, got {bp['line']}"
                )

    @staticmethod
    def assert_stopped_event(
        event: StoppedEvent,
        expected_reason: str | None = None,
        expected_thread: int | None = None,
    ) -> None:
        """Assert properties of a stopped event.

        Parameters
        ----------
        event : StoppedEvent
            Stopped event to verify
        expected_reason : str, optional
            Expected stop reason (breakpoint, step, exception, etc.)
        expected_thread : int, optional
            Expected thread ID

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "stopped", f"Expected stopped event, got {event.event}"

        if expected_reason:
            assert event.body is not None, "Expected event body to be present"
            assert event.body.reason == expected_reason, (
                f"Expected stop reason '{expected_reason}', got '{event.body.reason}'"
            )

        if expected_thread is not None:
            assert event.body is not None, "Expected event body to be present"
            assert event.body.threadId == expected_thread, (
                f"Expected thread {expected_thread}, got {event.body.threadId}"
            )

    @staticmethod
    def assert_continued_event(
        event: ContinuedEvent,
        expected_thread: int | None = None,
    ) -> None:
        """Assert properties of a continued event.

        Parameters
        ----------
        event : ContinuedEvent
            Continued event to verify
        expected_thread : int, optional
            Expected thread ID

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "continued", (
            f"Expected continued event, got {event.event}"
        )

        if expected_thread is not None:
            assert event.body is not None, "Expected event body to be present"
            assert event.body.threadId == expected_thread, (
                f"Expected thread {expected_thread}, got {event.body.threadId}"
            )

    @staticmethod
    def assert_initialize_response(response: InitializeResponse) -> None:
        """Assert that initialize response has expected capabilities.

        Parameters
        ----------
        response : InitializeResponse
            Initialize response to verify

        Raises
        ------
        AssertionError
            If response lacks expected capabilities
        """
        DAPAssertions.assert_response_success(response)

        assert hasattr(response, "body"), "Initialize response missing body"
        capabilities = response.body

        essential_caps = [
            "supportsConfigurationDoneRequest",
            "supportsConditionalBreakpoints",
            "supportsSetVariable",
        ]

        if capabilities is not None and hasattr(capabilities, "__dict__"):
            for cap in essential_caps:
                assert getattr(
                    capabilities,
                    cap,
                    False,
                ), f"Missing essential capability: {cap}"


class ExtendedDAPAssertions:
    """Extended DAP assertions for additional event types."""

    @staticmethod
    def assert_output_event(
        event: OutputEvent,
        expected_category: str | None = None,
        expected_output: str | None = None,
        pattern: str | None = None,
    ) -> None:
        """Assert properties of an output event.

        Parameters
        ----------
        event : OutputEvent
            Output event to verify
        expected_category : str, optional
            Expected output category (console, stdout, stderr, etc.)
        expected_output : str, optional
            Expected exact output text
        pattern : str, optional
            Regex pattern to match against output

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        import re

        assert event.event == "output", f"Expected output event, got {event.event}"

        if expected_category and event.body:
            assert event.body.category == expected_category, (
                f"Output category mismatch: expected '{expected_category}', "
                f"got '{event.body.category}'"
            )

        if expected_output and event.body:
            assert event.body.output == expected_output, (
                f"Output mismatch: expected '{expected_output}', "
                f"got '{event.body.output}'"
            )

        if pattern and event.body:
            assert re.search(
                pattern,
                event.body.output,
            ), f"Output doesn't match pattern '{pattern}': {event.body.output}"

    @staticmethod
    def assert_thread_event(
        event: ThreadEvent,
        expected_reason: str | None = None,
        expected_thread_id: int | None = None,
    ) -> None:
        """Assert properties of a thread event.

        Parameters
        ----------
        event : ThreadEvent
            Thread event to verify
        expected_reason : str, optional
            Expected reason (started, exited)
        expected_thread_id : int, optional
            Expected thread ID

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "thread", f"Expected thread event, got {event.event}"

        if expected_reason and event.body:
            assert event.body.reason == expected_reason, (
                f"Thread reason mismatch: expected '{expected_reason}', "
                f"got '{event.body.reason}'"
            )

        if expected_thread_id is not None and event.body:
            assert event.body.threadId == expected_thread_id, (
                f"Thread ID mismatch: expected {expected_thread_id}, "
                f"got {event.body.threadId}"
            )

    @staticmethod
    def assert_process_event(
        event: ProcessEvent,
        expected_name: str | None = None,
        expected_start_method: str | None = None,
    ) -> None:
        """Assert properties of a process event.

        Parameters
        ----------
        event : ProcessEvent
            Process event to verify
        expected_name : str, optional
            Expected process name
        expected_start_method : str, optional
            Expected start method (launch, attach, attachForSuspendedLaunch)

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "process", f"Expected process event, got {event.event}"

        if expected_name and event.body:
            assert event.body.name == expected_name, (
                f"Process name mismatch: expected '{expected_name}', "
                f"got '{event.body.name}'"
            )

        if expected_start_method and event.body:
            assert event.body.startMethod == expected_start_method, (
                f"Start method mismatch: expected '{expected_start_method}', "
                f"got '{event.body.startMethod}'"
            )

    @staticmethod
    def assert_terminated_event(
        event: TerminatedEvent,
        expected_restart: bool | None = None,
    ) -> None:
        """Assert properties of a terminated event.

        Parameters
        ----------
        event : TerminatedEvent
            Terminated event to verify
        expected_restart : bool, optional
            Expected restart flag

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "terminated", (
            f"Expected terminated event, got {event.event}"
        )

        if expected_restart is not None and event.body:
            actual_restart = getattr(event.body, "restart", False)
            assert actual_restart == expected_restart, (
                f"Restart flag mismatch: expected {expected_restart}, "
                f"got {actual_restart}"
            )

    @staticmethod
    def assert_exited_event(
        event: ExitedEvent,
        expected_exit_code: int | None = None,
    ) -> None:
        """Assert properties of an exited event.

        Parameters
        ----------
        event : ExitedEvent
            Exited event to verify
        expected_exit_code : int, optional
            Expected exit code

        Raises
        ------
        AssertionError
            If event properties don't match expectations
        """
        assert event.event == "exited", f"Expected exited event, got {event.event}"

        if expected_exit_code is not None and event.body:
            assert event.body.exitCode == expected_exit_code, (
                f"Exit code mismatch: expected {expected_exit_code}, "
                f"got {event.body.exitCode}"
            )
