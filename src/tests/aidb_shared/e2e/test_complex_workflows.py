"""E2E tests for complex debugging workflows.

These tests verify realistic debugging scenarios that combine multiple operations in
sequence, simulating actual debugging workflows that developers perform.
"""

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest


class TestComplexWorkflows(BaseE2ETest):
    """E2E tests for complex multi-step debugging workflows."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_multi_step_debugging_workflow(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test a complete multi-step debugging workflow.

        Simulates a realistic debugging session:
        1. Set breakpoint in function
        2. Continue to breakpoint
        3. Step into function
        4. Inspect variables
        5. Step out of function
        6. Continue execution
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        # Step 1: Set breakpoint at function call
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.call.add"]],
        )

        # Step 2: Session paused at breakpoint
        assert debug_interface.is_session_active
        # Verify we're stopped at the breakpoint by getting variables
        variables = await debug_interface.get_variables()
        # This will implicitly verify we're stopped (get_variables only works when paused)

        # Step 3: Step into the function
        await debug_interface.step_into()
        # Should now be inside add_numbers function

        # Step 4: Inspect variables (should see function parameters)
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "a")
        self.verify_vars.verify_variable_exists(variables, "b")

        # Step 5: Step out of the function
        state = await debug_interface.step_out()
        # Should be back in main function - verify we stopped
        self.verify_exec.verify_stopped(state)

        # Step 6: Continue execution to completion (no more breakpoints)
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_completion(state)

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_conditional_breakpoint_workflow(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test debugging workflow with conditional breakpoints.

        Verifies that conditional breakpoints skip iterations that don't match the
        condition, simulating debugging of loop iterations.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        # Set conditional breakpoint at session start (standard pattern)
        # Only break when i > 2
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                {
                    "file": program["path"],
                    "line": markers["var.add.total"],
                    "condition": "i > 2",
                },
            ],
        )

        # Session paused when condition first met (i=3)
        # Verify we skipped early iterations
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "i")

        # Extract value using helper method to handle both dict and AidbVariable
        i_info = variables["i"]
        i_value = i_info.value if hasattr(i_info, "value") else i_info.get("value")

        # i should be 3 or greater (skipped 0, 1, 2)
        assert int(i_value) > 2, f"Expected i > 2, got i={i_value}"

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_exception_debugging_workflow(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test debugging workflow through exception handling blocks.

        Verifies that the debugger can track execution through try/catch/finally blocks,
        simulating debugging of error handling code.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Set breakpoints throughout exception handling flow
        # Note: Use func.print.attempt instead of flow.try.start because
        # the try statement itself may not be executable in some debuggers
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["func.print.attempt"],
                markers["var.assign.result"],
                markers["func.print.cleanup"],
            ],
        )

        # Session paused at first executable line in try block
        assert debug_interface.is_session_active
        # Verify we're stopped at the breakpoint by getting variables
        variables = await debug_interface.get_variables()
        # This will implicitly verify we're stopped (get_variables only works when paused)

        # Continue to next breakpoint in try block
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.assign.result"],
        )

        # Inspect variable in try block
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "result")

        # Continue to finally block
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.cleanup"],
        )

        # Verify finally block has access to try block variables
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "result")
        self.verify_vars.verify_variable_value(variables, "result", "10")

        # Continue to completion
        await debug_interface.continue_execution()
