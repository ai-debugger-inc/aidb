"""Assertions for eventual conditions that may take time.

This module provides assertions for conditions that should eventually become true,
supporting both sync and async conditions.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any


class EventualAssertions:
    """Assertions for eventual conditions that may take time."""

    @staticmethod
    async def assert_eventually(
        condition: Callable[[], bool],
        timeout: float = 5.0,
        interval: float = 0.1,
        message: str = "Condition not met within timeout",
    ) -> None:
        """Assert that a condition eventually becomes true.

        Parameters
        ----------
        condition : callable
            Function that returns True when condition is met
        timeout : float
            Maximum time to wait in seconds
        interval : float
            Check interval in seconds
        message : str
            Custom error message

        Raises
        ------
        AssertionError
            If condition is not met within timeout
        """
        start_time = time.time()
        last_exception = None

        while time.time() - start_time < timeout:
            try:
                if asyncio.iscoroutinefunction(condition):
                    result = await condition()
                else:
                    result = condition()

                if result:
                    return

            except Exception as e:
                last_exception = e

            await asyncio.sleep(interval)

        if last_exception:
            msg = f"{message}. Last exception: {last_exception}"
            raise AssertionError(msg)
        msg = f"{message}"
        raise AssertionError(msg)

    @staticmethod
    async def assert_eventually_equals(
        getter: Callable[[], Any],
        expected_value: Any,
        timeout: float = 5.0,
        interval: float = 0.1,
        message: str | None = None,
    ) -> None:
        """Assert that a getter eventually returns expected value.

        Parameters
        ----------
        getter : callable
            Function that returns the value to check
        expected_value : Any
            Expected value
        timeout : float
            Maximum time to wait in seconds
        interval : float
            Check interval in seconds
        message : str, optional
            Custom error message

        Raises
        ------
        AssertionError
            If value doesn't match within timeout
        """
        if message is None:
            message = f"Value did not become '{expected_value}' within {timeout}s"

        async def condition():
            if asyncio.iscoroutinefunction(getter):
                value = await getter()
            else:
                value = getter()
            return value == expected_value

        await EventualAssertions.assert_eventually(
            condition,
            timeout,
            interval,
            message,
        )
