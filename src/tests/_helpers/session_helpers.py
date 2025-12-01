"""Session management helpers for debug testing.

This module provides utilities for creating, managing, and cleaning up debug sessions in
tests, reducing boilerplate and ensuring consistent session handling.
"""

import contextlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tests._helpers.constants import TestLimits
from tests._helpers.debug_interface import DebugInterface


def get_step_method(
    debug_interface: DebugInterface,
    step_type: str,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Get step method from debug interface by type.

    Parameters
    ----------
    debug_interface : DebugInterface
        Debug interface instance
    step_type : str
        Step type: "over", "into", or "out"

    Returns
    -------
    Callable
        Async step method

    Raises
    ------
    ValueError
        If invalid step_type
    """
    step_methods = {
        "over": debug_interface.step_over,
        "into": debug_interface.step_into,
        "out": debug_interface.step_out,
    }
    if step_type not in step_methods:
        msg = f"Invalid step_type: {step_type}. Use 'over', 'into', or 'out'"
        raise ValueError(msg)
    return step_methods[step_type]


async def create_session_with_program(
    debug_interface: DebugInterface,
    program: str | Path,
    breakpoints: list[dict[str, Any]] | None = None,
    **launch_args,
) -> dict[str, Any]:
    """Create and start a debug session with a program.

    Standardized helper for session creation that handles common setup patterns.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to use (MCP or API)
    program : str | Path
        Path to the program to debug
    breakpoints : list[dict[str, Any]], optional
        Initial breakpoints to set
    **launch_args : dict
        Additional launch arguments (cwd, env, args, etc.)

    Returns
    -------
    dict[str, Any]
        Session information including session_id, status, etc.

    Raises
    ------
    RuntimeError
        If session creation or start fails
    """
    return await debug_interface.start_session(
        program=program,
        breakpoints=breakpoints,
        **launch_args,
    )


async def verify_session_state(
    debug_interface: DebugInterface,
    expected_active: bool = True,
) -> None:
    """Verify debug session state matches expectations.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to verify
    expected_active : bool, optional
        Expected session active state, default True

    Raises
    ------
    AssertionError
        If session state doesn't match expectations
    """
    actual_active = debug_interface.is_session_active

    if expected_active != actual_active:
        state = "active" if expected_active else "stopped"
        actual_state = "active" if actual_active else "stopped"
        msg = f"Expected session to be {state}, but it is {actual_state}"
        raise AssertionError(msg)


async def cleanup_session(
    debug_interface: DebugInterface,
    ignore_errors: bool = True,
) -> None:
    """Clean up debug session with error handling.

    Attempts to stop session and cleanup resources, optionally ignoring errors
    to ensure cleanup completes even if session is in a bad state.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to clean up
    ignore_errors : bool, optional
        Whether to ignore errors during cleanup, default True

    Raises
    ------
    RuntimeError
        If cleanup fails and ignore_errors is False
    """
    try:
        if debug_interface.is_session_active:
            await debug_interface.stop_session()
    except Exception as e:
        if not ignore_errors:
            msg = f"Failed to stop session: {e}"
            raise RuntimeError(msg) from e

    try:
        await debug_interface.cleanup()
    except Exception as e:
        if not ignore_errors:
            msg = f"Failed to cleanup interface: {e}"
            raise RuntimeError(msg) from e


@contextlib.asynccontextmanager
async def debug_session(
    debug_interface: DebugInterface,
    program: str | Path,
    breakpoints: list[dict[str, Any]] | None = None,
    **launch_args,
):
    """Context manager for automatic debug session lifecycle.

    Creates a debug session and ensures cleanup on exit, even if errors occur.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to use
    program : str | Path
        Path to the program to debug
    breakpoints : list[dict[str, Any]], optional
        Initial breakpoints to set
    **launch_args : dict
        Additional launch arguments

    Yields
    ------
    dict[str, Any]
        Session information

    Examples
    --------
    >>> async with debug_session(interface, program, breakpoints=[{"line": 5}]) as session:
    >>>     # Use session
    >>>     result = await interface.continue_execution()
    >>>     # Automatic cleanup on exit
    """
    session_info = None
    try:
        session_info = await create_session_with_program(
            debug_interface,
            program,
            breakpoints,
            **launch_args,
        )
        yield session_info
    finally:
        await cleanup_session(debug_interface, ignore_errors=True)


async def run_to_completion(
    debug_interface: DebugInterface,
    max_steps: int = TestLimits.MAX_STEPS_COMPLETION,
) -> dict[str, Any]:
    """Run program to completion or until max steps reached.

    Continues execution until program ends or max_steps is exceeded.
    Useful for ensuring program completes in tests.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to use
    max_steps : int, optional
        Maximum number of continue operations, default 1000

    Returns
    -------
    dict[str, Any]
        Final execution state

    Raises
    ------
    RuntimeError
        If max_steps exceeded without program completion
    """
    steps = 0
    result: dict[str, Any] = {}

    while steps < max_steps:
        result = await debug_interface.continue_execution()

        if not result.get("stopped", True):
            # Program completed
            break

        if result.get("reason") in ("end", "exit", "terminated"):
            # Program ended
            break

        steps += 1

    if steps >= max_steps:
        msg = f"Program did not complete within {max_steps} steps"
        raise RuntimeError(msg)

    return result


async def step_until_line(
    debug_interface: DebugInterface,
    target_line: int,
    max_steps: int = TestLimits.MAX_STEPS_NAVIGATION,
    step_type: str = "over",
) -> dict[str, Any]:
    """Step execution until reaching target line.

    Parameters
    ----------
    debug_interface : DebugInterface
        The debug interface to use
    target_line : int
        Target line number to reach
    max_steps : int, optional
        Maximum number of steps to take, default 100
    step_type : str, optional
        Type of step ("over", "into", "out"), default "over"

    Returns
    -------
    dict[str, Any]
        Execution state when target line reached

    Raises
    ------
    RuntimeError
        If target line not reached within max_steps
    ValueError
        If invalid step_type provided
    """
    step_method = get_step_method(debug_interface, step_type)
    steps = 0
    result: dict[str, Any] = {}

    while steps < max_steps:
        result = await step_method()

        if result.get("line") == target_line:
            return result

        steps += 1

    msg = f"Did not reach line {target_line} within {max_steps} steps"
    raise RuntimeError(msg)
