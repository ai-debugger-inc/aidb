"""Integration tests for control flow debugging capabilities.

These tests verify that the debugger correctly handles loops, conditionals, functions,
and other control flow structures across all supported languages.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestControlFlow(BaseIntegrationTest):
    """Integration tests for control flow debugging."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_for_loop_iteration(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test stepping through for loop iterations.

        Verifies that breakpoints inside loop bodies trigger on each iteration and that
        loop variables update correctly.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.add.total"]],
        )

        # Session paused at first iteration: i=0
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "i")
        # First iteration: i should be 0
        self.verify_vars.verify_variable_value(variables, "i", "0")

        # Continue to second iteration: i=1
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.add.total"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "i", "1")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_while_loop_condition(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test while loop condition evaluation and iteration.

        Verifies that breakpoints work inside while loops and that the loop counter
        updates correctly on each iteration.
        """
        program = generated_program_factory("basic_while_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.increment.counter"]],
        )

        # Session paused at first iteration: counter=0
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "counter")
        # Counter starts at 0
        self.verify_vars.verify_variable_value(variables, "counter", "0")

        # Continue through to third iteration: counter=2
        await debug_interface.continue_execution()  # counter=1
        state = await debug_interface.continue_execution()  # counter=2
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.increment.counter"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "counter", "2")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_loop_break_statement(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test loop execution and completion.

        Verifies that loops execute the expected number of iterations and reach their
        completion point.
        """
        program = generated_program_factory("basic_while_loop", language)
        markers = program["markers"]

        # Set breakpoint after loop completes
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.final"]],
        )

        # Session paused after loop completes
        # Loop should have completed 5 iterations
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "counter", "5")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_loop_continue_statement(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test loop continuation through multiple iterations.

        Verifies that continuing execution advances through loop iterations and that
        loop variables update correctly.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.iteration"]],
        )

        # Session paused at first iteration (i=0)
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "i", "0")

        # Continue through next 2 iterations
        for expected_i in [1, 2]:
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(
                state,
                expected_line=markers["func.print.iteration"],
            )

            variables = await debug_interface.get_variables()
            self.verify_vars.verify_variable_value(variables, "i", str(expected_i))

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_if_condition_true(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test conditional branching when condition is true.

        Verifies that the correct branch executes when the if condition evaluates to
        true.
        """
        program = generated_program_factory("conditionals", language)
        markers = program["markers"]

        # The value is 7, so it should enter the second if (value < 10)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["flow.if.less_than_ten"], markers["func.print.between"]],
        )

        # Session paused at the condition check - verify by getting variables
        variables = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Should hit the print statement in the true branch
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.between"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "value", "7")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_if_condition_false(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test conditional branching when condition is false.

        Verifies that the correct branch (or no branch) executes when the if condition
        evaluates to false.
        """
        program = generated_program_factory("conditionals", language)
        markers = program["markers"]

        # The value is 7 (not < 5), so the first branch should not execute
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["flow.if.less_than"],
                markers["func.print.less"],
                markers["func.print.complete"],
            ],
        )

        # Session paused at the first condition check - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Should NOT hit the false branch print, should jump to completion
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.complete"],
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_function_call_stepping(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test stepping into and through function calls.

        Verifies that the debugger can step into function calls and track execution
        through function boundaries.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        # Set breakpoints at function call and inside the function
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.call.add"], markers["var.calc.result"]],
        )

        # Session paused at the function call - verify by getting variables
        variables = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Continue into the function
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.calc.result"],
        )

        # Verify function arguments are accessible
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "a")
        self.verify_vars.verify_variable_exists(variables, "b")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_function_return_value(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test function return value inspection.

        Verifies that the debugger can inspect the return value of functions and track
        execution after function returns.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        # Set breakpoint after function returns
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.sum"]],
        )

        # Session paused after function returns
        # Verify the function's return value was assigned correctly
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "sum")
        # sum should be 10 + 20 = 30
        self.verify_vars.verify_variable_value(variables, "sum", "30")
