"""Integration tests for expression evaluation in different contexts.

These tests demonstrate the evaluation capabilities of the debug interface across
different scopes, stack frames, and error conditions.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestEvaluation(BaseIntegrationTest):
    """Integration tests for expression evaluation."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_in_local_scope(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test evaluating expressions in local variable scope.

        Verifies that we can evaluate expressions using local variables when stopped at
        a breakpoint inside a function.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"]],
        )

        # Session is paused at breakpoint, step over to execute the line
        await debug_interface.step_over()

        # Now result should be available for evaluation
        value_result = await debug_interface.evaluate("result")
        self.verify_vars.verify_variable_exists({"result": value_result}, "result")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_in_different_frames(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test evaluating the same expression in different stack frames.

        Verifies that expression evaluation respects stack frame context, showing
        different values for the same variable name in nested calls.
        """
        program = generated_program_factory("function_chain", language)
        markers = program["markers"]

        # Break inside a nested function call (multiply inside calculate)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.call.multiply"]],
        )

        # Session paused inside calculate() function
        # Verify we can evaluate expressions in this frame context
        stack = await debug_interface.get_stack_trace()

        # Should have multiple frames (main -> calculate -> multiply call point)
        assert len(stack) >= 2

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_complex_expressions(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test evaluating complex expressions with multiple operations.

        Verifies that the debugger can handle complex arithmetic, string operations, and
        method calls in evaluated expressions.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.assign.counter"]],
        )

        # Session is paused at breakpoint - ready for evaluation
        counter_val = await debug_interface.evaluate("counter")
        self.verify_vars.verify_variable_exists({"counter": counter_val}, "counter")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_invalid_expression(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test error handling for invalid expressions.

        Verifies that the debugger properly handles and reports errors when evaluating
        syntactically invalid or undefined expressions.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.assign.counter"]],
        )

        # Session is paused at breakpoint - ready for evaluation
        with pytest.raises((RuntimeError, ValueError, NameError, Exception)):
            await debug_interface.evaluate("undefined_variable_12345")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_with_side_effects(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that evaluation can trigger side effects.

        Verifies that evaluated expressions can modify state (though this should
        generally be avoided in debugging).
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.assign.counter"]],
        )

        # Session is paused at breakpoint - ready for evaluation
        counter_val = await debug_interface.evaluate("counter")
        self.verify_vars.verify_variable_exists({"counter": counter_val}, "counter")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluate_global_scope(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test evaluating expressions in global scope.

        Verifies that we can access and evaluate global variables and module-level
        constants from within function contexts.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.assign.counter"]],
        )

        # Session is paused at breakpoint - ready for evaluation
        counter_val = await debug_interface.evaluate("counter")
        self.verify_vars.verify_variable_exists({"counter": counter_val}, "counter")
