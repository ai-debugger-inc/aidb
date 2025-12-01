"""Assertions for log output validation.

This module provides assertions for validating log messages, sequences, patterns, and
timing.
"""

import re
from typing import Union

from tests._helpers.logging_capture import LogCapture, LogRecord


class LoggingAssertions:
    """Assertions for log output validation."""

    @staticmethod
    def assert_log_message(
        capture: LogCapture,
        message: str,
        level: int | str | None = None,
        logger: str | None = None,
        partial: bool = True,
    ) -> None:
        """Assert that a specific log message was captured.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        message : str
            Expected message text
        level : Union[int, str], optional
            Expected log level
        logger : str, optional
            Expected logger name
        partial : bool
            Whether to match partial message (substring)

        Raises
        ------
        AssertionError
            If message not found
        """
        records = capture.records

        if logger:
            records = capture.get_logger_records(logger)

        if level:
            if isinstance(level, str):
                import logging

                level = getattr(logging, level.upper())
            records = [r for r in records if r.level >= int(level)]

        found = False
        for record in records:
            if (
                partial
                and message in record.message
                or not partial
                and record.message == message
            ):
                found = True
                break

        if not found:
            messages = [r.message for r in records]
            msg = f"Log message '{message}' not found. Captured messages: {messages}"
            raise AssertionError(
                msg,
            )

    @staticmethod
    def assert_log_sequence(
        capture: LogCapture,
        *expected_messages: str,
        ordered: bool = True,
        logger: str | None = None,
    ) -> None:
        """Assert that messages appear in sequence.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        *expected_messages : str
            Expected messages in order
        ordered : bool
            Whether order matters
        logger : str, optional
            Specific logger to check

        Raises
        ------
        AssertionError
            If sequence not found
        """
        messages = capture.get_messages(logger=logger)

        if not ordered:
            for expected in expected_messages:
                if not any(expected in msg for msg in messages):
                    msg = f"Expected message '{expected}' not found in logs"
                    raise AssertionError(
                        msg,
                    )
        else:
            message_iter = iter(messages)
            for expected in expected_messages:
                found = False
                for actual in message_iter:
                    if expected in actual:
                        found = True
                        break

                if not found:
                    msg = (
                        f"Expected message '{expected}' not found in sequence. "
                        f"Messages: {messages}"
                    )
                    raise AssertionError(
                        msg,
                    )

    @staticmethod
    def assert_no_log_errors(
        capture: LogCapture,
        allowed_errors: list[str] | None = None,
    ) -> None:
        """Assert that no errors were logged (except allowed ones).

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        allowed_errors : List[str], optional
            Error messages that are allowed

        Raises
        ------
        AssertionError
            If unexpected errors found
        """
        import logging

        errors = capture.filter_level(logging.ERROR)

        if allowed_errors:
            errors = [
                e
                for e in errors
                if not any(allowed in e.message for allowed in allowed_errors)
            ]

        if errors:
            error_messages = "\n".join(f"  - {r.message}" for r in errors)
            msg = f"Unexpected errors in logs:\n{error_messages}"
            raise AssertionError(msg)

    @staticmethod
    def assert_log_level_count(
        capture: LogCapture,
        level: int | str,
        expected_count: int,
        operator: str = "==",
    ) -> None:
        """Assert the count of logs at a specific level.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        level : Union[int, str]
            Log level to count
        expected_count : int
            Expected count
        operator : str
            Comparison operator (==, >, <, >=, <=, !=)

        Raises
        ------
        AssertionError
            If count doesn't match expectation
        """
        actual_count = capture.count_level(level)

        operations = {
            "==": actual_count == expected_count,
            ">": actual_count > expected_count,
            "<": actual_count < expected_count,
            ">=": actual_count >= expected_count,
            "<=": actual_count <= expected_count,
            "!=": actual_count != expected_count,
        }

        if operator not in operations:
            msg = f"Invalid operator: {operator}"
            raise ValueError(msg)

        if not operations[operator]:
            msg = (
                f"Log level {level} count {actual_count} not {operator} "
                f"{expected_count}"
            )
            raise AssertionError(
                msg,
            )

    @staticmethod
    def assert_session_logs(
        capture: LogCapture,
        session_id: str,
        min_count: int = 1,
    ) -> list[LogRecord]:
        """Assert that a session has logged messages.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        session_id : str
            Session ID to check
        min_count : int
            Minimum expected log count

        Returns
        -------
        List[LogRecord]
            Session log records

        Raises
        ------
        AssertionError
            If session logs not found or insufficient
        """
        from tests._helpers.logging_capture import get_session_logs

        logs = get_session_logs(capture, session_id)

        if len(logs) < min_count:
            msg = (
                f"Session {session_id} has {len(logs)} logs, expected at least "
                f"{min_count}"
            )
            raise AssertionError(
                msg,
            )

        return logs

    @staticmethod
    def assert_log_pattern(
        capture: LogCapture,
        pattern: str | re.Pattern,
        count: int | None = None,
        logger: str | None = None,
    ) -> None:
        """Assert that logs match a regex pattern.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        pattern : Union[str, re.Pattern]
            Regex pattern to match
        count : int, optional
            Expected number of matches
        logger : str, optional
            Specific logger to check

        Raises
        ------
        AssertionError
            If pattern not matched
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)

        records = capture.get_logger_records(logger) if logger else capture.records

        matches = [r for r in records if r.matches(pattern)]

        if count is not None:
            if len(matches) != count:
                msg = (
                    f"Expected {count} matches for pattern '{pattern.pattern}', "
                    f"found {len(matches)}"
                )
                raise AssertionError(
                    msg,
                )
        elif not matches:
            messages = [r.message for r in records]
            msg = f"No logs match pattern '{pattern.pattern}'. Messages: {messages}"
            raise AssertionError(
                msg,
            )

    @staticmethod
    def assert_log_timing(
        capture: LogCapture,
        start_pattern: str,
        end_pattern: str,
        max_duration: float,
        logger: str | None = None,
    ) -> float:
        """Assert that operations complete within time limits.

        Parameters
        ----------
        capture : LogCapture
            Log capture instance
        start_pattern : str
            Pattern marking operation start
        end_pattern : str
            Pattern marking operation end
        max_duration : float
            Maximum allowed duration in seconds
        logger : str, optional
            Specific logger to check

        Returns
        -------
        float
            Actual duration

        Raises
        ------
        AssertionError
            If timing exceeds limit or patterns not found
        """
        records = capture.get_logger_records(logger) if logger else capture.records

        start_time = None
        end_time = None

        for record in records:
            if start_pattern in record.message and start_time is None:
                start_time = record.timestamp
            elif end_pattern in record.message and start_time is not None:
                end_time = record.timestamp
                break

        if start_time is None:
            msg = f"Start pattern '{start_pattern}' not found in logs"
            raise AssertionError(msg)

        if end_time is None:
            msg = f"End pattern '{end_pattern}' not found in logs"
            raise AssertionError(msg)

        duration = (end_time - start_time).total_seconds()

        if duration > max_duration:
            msg = f"Operation took {duration:.3f}s, expected <= {max_duration:.3f}s"
            raise AssertionError(
                msg,
            )

        return duration
