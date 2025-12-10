"""Basic debugging operation tests using DebugInterface abstraction.

These tests demonstrate the zero-duplication pattern by running the same test logic
against both MCP and API entry points via parametrization.

For advanced breakpoint features (conditional, hit conditions, logpoints), see
test_advanced_breakpoints.py.
"""

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
@parametrize_languages()
@pytest.mark.asyncio
async def test_session_lifecycle(debug_interface, language, generated_program_factory):
    """Test basic session lifecycle works for both interfaces and all languages.

    This test demonstrates:
    - Session initialization
    - Session start/stop
    - Cleanup

    The same test runs 6 times: MCP+API × Python+JavaScript+Java.
    """
    # Load generated test program
    program = generated_program_factory("basic_variables", language)
    markers = program["markers"]

    # Start session with initial breakpoint to keep session alive (standard pattern)
    first_marker_line = next(iter(markers.values()))
    session_info = await debug_interface.start_session(
        program=str(program["path"]),
        breakpoints=[{"file": str(program["path"]), "line": first_marker_line}],
    )

    assert session_info["session_id"] is not None
    assert session_info["status"] == "started"
    assert debug_interface.is_session_active

    # Stop session
    await debug_interface.stop_session()

    assert not debug_interface.is_session_active


@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
@parametrize_languages()
@pytest.mark.asyncio
async def test_breakpoint_operations(
    debug_interface,
    language,
    generated_program_factory,
):
    """Test breakpoint set/list/remove operations for both interfaces and all languages.

    This test demonstrates:
    - Setting breakpoints during session creation
    - Listing breakpoints
    - Removing breakpoints

    Uses initial breakpoints to ensure deterministic behavior across all debug adapters.
    The same test runs 6 times: MCP+API × Python+JavaScript+Java.
    """
    # Load generated test program
    program = generated_program_factory("simple_function", language)

    # Get a line with a marker for breakpoint testing
    # Use "var.calc.result" marker which exists in all languages
    breakpoint_line = program["markers"]["var.calc.result"]

    # Start session with initial breakpoint
    # This is the standard pattern for deterministic debugging across all adapters
    breakpoints = [{"file": str(program["path"]), "line": breakpoint_line}]
    await debug_interface.start_session(
        program=str(program["path"]),
        breakpoints=breakpoints,
    )

    # List breakpoints - should see the initial breakpoint
    breakpoints_list = await debug_interface.list_breakpoints()

    assert len(breakpoints_list) >= 1
    assert any(bp["line"] == breakpoint_line for bp in breakpoints_list)

    # Find the breakpoint we set
    bp = next((bp for bp in breakpoints_list if bp["line"] == breakpoint_line), None)
    assert bp is not None, f"No breakpoint found at line {breakpoint_line}"
    assert bp["file"] == str(program["path"])
    assert "id" in bp

    # Remove breakpoint
    bp_id = bp["id"]
    removed = await debug_interface.remove_breakpoint(bp_id)

    assert removed is True

    # Verify removed
    breakpoints_after = await debug_interface.list_breakpoints()
    assert not any(bp.get("id") == bp_id for bp in breakpoints_after)

    # Cleanup
    await debug_interface.stop_session()


class TestBasicDebugging(BaseIntegrationTest):
    """Basic debugging operation tests."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_execution_control(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test execution control (continue, step) for both interfaces and all
        languages.

        This test demonstrates:
        - Setting breakpoints before execution
        - Continue to breakpoint
        - Step operations

        The same test runs 6 times: MCP+API × Python+JavaScript+Java.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        # Start session with two breakpoints so we can test continue
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.x"], markers["var.init.y"]],
        )

        # Session paused at first breakpoint - continue to second breakpoint
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.init.y"],
        )

        # Step over a line
        state = await debug_interface.step_over()
        self.verify_exec.verify_stopped(state)
