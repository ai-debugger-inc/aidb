"""Standalone helper functions and utilities for assertions.

This module provides convenience functions and assertion helper creation utilities.
"""

import time
from collections.abc import Callable
from typing import Any

from aidb.dap.protocol import Response

from .dap_assertions import DAPAssertions
from .mcp_assertions import MCPAssertions


def create_assertion_helper(test_case):
    """Create an assertion helper with access to test case methods.

    Parameters
    ----------
    test_case : TestCase
        Test case instance

    Returns
    -------
    object
        Assertion helper with bound methods
    """
    from .collection_assertions import CollectionAssertions
    from .dap_assertions import ExtendedDAPAssertions
    from .debug_interface_assertions import DebugInterfaceAssertions
    from .eventual_assertions import EventualAssertions
    from .logging_assertions import LoggingAssertions
    from .performance_assertions import PerformanceAssertions
    from .response_assertions import ResponseAssertions
    from .state_assertions import StateAssertions

    class AssertionHelper:
        def __init__(self, tc):
            self.tc = tc
            self.dap = DAPAssertions()
            self.dap_extended = ExtendedDAPAssertions()
            self.mcp = MCPAssertions()
            self.response = ResponseAssertions()
            self.state = StateAssertions()
            self.performance = PerformanceAssertions()
            self.eventual = EventualAssertions()
            self.collection = CollectionAssertions()
            self.logging = LoggingAssertions()
            self.debug_interface = DebugInterfaceAssertions()

        def fail(self, msg):
            """Fail the test with a message."""
            self.tc.fail(msg)

    return AssertionHelper(test_case)


def assert_response_success(response: Response | dict[str, Any]) -> None:
    """Assert that a response indicates success (DAP or MCP).

    Parameters
    ----------
    response : Union[Response, Dict[str, Any]]
        Response to check

    Raises
    ------
    AssertionError
        If response indicates failure
    """
    if isinstance(response, Response):
        DAPAssertions.assert_response_success(response)
    else:
        MCPAssertions.assert_tool_response_success(response)


def assert_within_timeout(
    func: Callable[[], bool],
    timeout: float = 5.0,
    message: str = "Condition not met within timeout",
) -> None:
    """Assert that a condition is met within a timeout (synchronous).

    Parameters
    ----------
    func : Callable[[], bool]
        Function that returns True when condition is met
    timeout : float
        Maximum time to wait in seconds
    message : str
        Error message if timeout

    Raises
    ------
    AssertionError
        If condition not met within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if func():
            return
        time.sleep(0.1)
    raise AssertionError(message)
