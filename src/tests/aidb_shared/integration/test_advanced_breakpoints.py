"""Advanced breakpoint feature tests.

Tests for conditional breakpoints, hit conditions, and logpoints. These features go
beyond basic breakpoint set/list/remove operations.
"""

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestAdvancedBreakpoints(BaseIntegrationTest):
    """Advanced breakpoint feature tests."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_conditional_breakpoint(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test conditional breakpoints for both interfaces and all languages.

        Verifies that conditional breakpoints only pause when condition is true.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        # Set conditional breakpoint that should trigger on 3rd iteration
        # Use var.add.total marker (inside the loop body)
        loop_line = markers.get("var.add.total")
        if not loop_line:
            pytest.skip("No var.add.total marker available for this program")

        # Java conditional breakpoints don't report as verified even when they work
        if language == "java":
            pytest.skip("Java adapter doesn't verify conditional breakpoints")

        # Start session with a conditional breakpoint
        # Condition: i == 2 (third iteration, 0-indexed)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            breakpoint_lines=[
                {
                    "file": str(program["path"]),
                    "line": loop_line,
                    "condition": "i == 2",
                }
            ],
        )

        # Session should now be paused at the breakpoint when condition is met
        # The program pauses when i==2 (third iteration)
        state = await debug_interface.get_state()
        self.verify_exec.verify_stopped(state, expected_line=loop_line)

        # Verify i==2 at this point
        variables = await debug_interface.get_variables()
        assert "i" in variables, "Loop variable 'i' should be in locals"
        # Use verifier helper to extract value (handles AidbVariable, verbose, and compact formats)
        i_value = self.verify_vars._extract_value(variables["i"])
        assert i_value in (2, "2"), f"Expected i=2, got {i_value}"

    @pytest.mark.flaky(reruns=3)
    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_hit_condition_breakpoint(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test hit condition breakpoints for both interfaces and all languages.

        Verifies that hit condition breakpoints skip the specified number of hits.

        Note: This test is flaky on JavaScript due to timing issues with hit condition
        breakpoint stop events. The 3 reruns (vs global 1) help it pass consistently.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        loop_line = markers.get("var.add.total")
        if not loop_line:
            pytest.skip("No var.add.total marker available for this program")

        # Java adapter only supports EXACT hit conditions, not GREATER_THAN
        if language == "java":
            pytest.skip("Java adapter only supports EXACT hit conditions")

        # Start session with hit condition breakpoint at session start
        # (standard pattern - breakpoints must be set before execution starts)
        # Hit condition: >3 means stop when hit count > 3 (4th iteration)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            breakpoint_lines=[
                {
                    "file": str(program["path"]),
                    "line": loop_line,
                    "hit_condition": ">3",
                }
            ],
        )

        # Session should now be paused at the breakpoint after skipping first 3 hits
        state = await debug_interface.get_state()
        self.verify_exec.verify_stopped(state, expected_line=loop_line)

        # Verify we're at iteration 3 (0-indexed) or 4 (1-indexed depending on loop)
        variables = await debug_interface.get_variables()
        assert "i" in variables, "Loop variable 'i' should be in locals"
        # Hit count >3 means we stop on 4th hit, which is i=3 (0-indexed)
        # Use verifier helper to extract value (handles AidbVariable, verbose, and compact formats)
        i_value = self.verify_vars._extract_value(variables["i"])
        assert i_value in (3, "3", 4, "4"), f"Expected i=3 or i=4, got {i_value}"

    @pytest.mark.skip(
        reason="Logpoint output collection broken after service layer refactor - "
        "DAP output events not reaching MCP response. Requires investigation of "
        "async event timing between EventProcessor and ExecuteResponse."
    )
    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_logpoint(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test logpoints for both interfaces and all languages.

        Verifies that:
        1. Logpoints don't pause execution - they only log
        2. Logpoint output is captured and can be retrieved via get_output()
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        # Get line markers for logpoint test
        # We need a logpoint BEFORE a breakpoint in execution order
        # Execution order: var.init.x -> var.init.y -> func.call.add -> func.print.sum
        log_line = markers.get("var.init.y")
        end_line = markers.get("func.print.sum", markers.get("func.call.add"))

        if not log_line:
            pytest.skip("No var.init.y marker available")
        if not end_line:
            pytest.skip("No suitable end marker available")

        # Start session with an early breakpoint so we can set the logpoint
        # BEFORE execution reaches it. Use var.init.x as the initial stop.
        start_line = markers.get("var.init.x")
        if not start_line:
            pytest.skip("No var.init.x marker available")

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [start_line],
        )

        # Now set the logpoint at var.init.y (next line after current stop)
        logpoint_message = "LOGPOINT_TEST_MESSAGE: y initialized"
        bp = await debug_interface.set_breakpoint(
            file=str(program["path"]),
            line=log_line,
            log_message=logpoint_message,
        )
        assert bp["verified"], "Logpoint should be verified"

        # Also set a breakpoint at the end to stop execution
        end_bp = await debug_interface.set_breakpoint(
            file=str(program["path"]),
            line=end_line,
        )
        assert end_bp["verified"], "End breakpoint should be verified"

        # Continue - should pass through logpoint without stopping, then stop at end
        state = await debug_interface.continue_execution()

        # Should stop at end_line, NOT at log_line
        self.verify_exec.verify_stopped(state, expected_line=end_line)

        # Verify logpoint output was captured
        output = await debug_interface.get_output()

        # Find the logpoint message in the output
        logpoint_found = any(
            logpoint_message in entry.get("output", "")
            for entry in output
            if entry.get("category") in ("console", "stdout")
        )
        assert logpoint_found, (
            f"Logpoint message not found in output. "
            f"Expected message containing: {logpoint_message!r}. "
            f"Got output: {output}"
        )
